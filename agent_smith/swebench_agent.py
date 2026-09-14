"""SWE-bench prompts and resource ownership around the shared agent loop."""

from __future__ import annotations

from agent_smith.logging_config import get_logger

logger = get_logger('agent_smith.swebench_agent')

import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

import anyio

from agent_smith.agent_loop import run_agent_loop
from agent_smith.mcp_client import MCPClient
from agent_smith.models import AgentLimits, SolutionOutput, SWEBenchTaskInput
from agent_smith.providers import ProviderClient
from agent_smith.sandbox import SandboxSession, load_sandbox_config


MAX_TASK_SECONDS = 900
CLEANUP_RESERVE_SECONDS = 20
REQUIRED_TOOLS = (
    "read_file", "edit_file", "list_files", "search_code",
    "search_function_or_class_definition_in_code", "find_references",
    "run_tests", "get_patch", "run_command",
)


class SWEEnvironment:
    """Own exactly one Docker container for one SWE-bench task.

    The container holds the repository checkout, never the generated Python:
    that keeps running in the restricted worker. Explicit start/close, because
    the adapter must be able to close a container whose start failed halfway.
    """

    def __init__(self, task: SWEBenchTaskInput, *, deadline: float) -> None:
        """Store the task and its deadline without contacting Docker yet."""
        logger.debug("Entrando en SWEEnvironment.__init__")
        self.task = task
        self.deadline = deadline
        self.container_id = f"agent-smith-{uuid.uuid4().hex[:12]}"
        self.holder = None
        self.started = False

    def _docker(self, *arguments: str, timeout_seconds: float | None = None) -> str:
        """Run one docker command, bounded by whatever is left of the deadline."""
        logger.debug("Entrando en SWEEnvironment._docker")
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("No time left for Docker operations.")
        completed = subprocess.run(
            ["docker", *arguments], text=True, capture_output=True, check=False,
            timeout=min(remaining, timeout_seconds) if timeout_seconds else remaining,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"docker {arguments[0]} failed: {completed.stderr.strip() or completed.stdout.strip()}"
            )
        return completed.stdout.strip()

    def start(self) -> None:
        """Make the task image available and run one container holding /testbed."""
        logger.debug("Entrando en SWEEnvironment.start")
        image = self.task.docker_image
        if not image:
            raise RuntimeError("The task does not name a Docker image.")
        try:
            self._docker("image", "inspect", image)
            logger.info("La imagen de la tarea ya esta disponible")
        except RuntimeError:
            logger.info("Descargando la imagen de la tarea; puede tardar")
            self._docker("pull", image)
        # El contenedor se queda vivo leyendo NUESTRA entrada estándar, no con un
        # `tail -f` suelto. Si el agente muere de cualquier forma, incluido un
        # kill -9 que ningún finally puede interceptar, el kernel cierra esta
        # tubería, `cat` ve el fin de entrada, el contenedor para y --rm lo
        # borra. Sin red y sin privilegios: dentro sólo corren los tests del repo.
        self.holder = subprocess.Popen(
            ["docker", "run", "-i", "--rm", "--name", self.container_id,
             "--network", "none", image, "cat"],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
        self.started = True
        self._wait_until_running()
        logger.info("Contenedor de la tarea arrancado: %s", self.container_id)
        listing = self._docker("exec", self.container_id, "ls", "/testbed", timeout_seconds=30)
        if not listing:
            raise RuntimeError("The container has no /testbed checkout.")

    def _wait_until_running(self) -> None:
        """Wait for the container to report itself running, or explain why not."""
        logger.debug("Entrando en SWEEnvironment._wait_until_running")
        while time.monotonic() < self.deadline:
            running = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Running}}", self.container_id],
                text=True, capture_output=True, check=False, timeout=30,
            )
            if running.stdout.strip() == "true":
                return
            if self.holder.poll() is not None:
                _, errors = self.holder.communicate(timeout=10)
                raise RuntimeError(f"docker run failed: {(errors or '').strip()}")
            time.sleep(0.5)
        raise TimeoutError("The task container did not start in time.")

    def mcp_environment(self) -> dict[str, str]:
        """Return what the MCP server needs to reach this task's own container."""
        logger.debug("Entrando en SWEEnvironment.mcp_environment")
        if not self.started:
            raise RuntimeError("The task container is not running.")
        return {
            "AGENT_SMITH_CONTAINER_ID": self.container_id,
            "AGENT_SMITH_EVAL_SCRIPT": self.task.eval_script,
            "AGENT_SMITH_DEADLINE": str(self.deadline),
        }

    def close(self) -> None:
        """Remove only the container this instance created."""
        logger.debug("Entrando en SWEEnvironment.close")
        if not self.started:
            return
        self.started = False
        logger.info("Eliminando el contenedor de la tarea")
        # Cerrar la tubería basta para que el contenedor pare y se borre solo;
        # el rm es el cinturón por si el demonio no llegó a recogerlo.
        if self.holder is not None:
            if self.holder.stdin is not None:
                self.holder.stdin.close()
            try:
                self.holder.wait(timeout=CLEANUP_RESERVE_SECONDS // 2)
            except subprocess.TimeoutExpired:
                logger.warning("El proceso que sostenía el contenedor sigue vivo; se termina")
                self.holder.kill()
                self.holder.wait(timeout=5)
            self.holder = None
        completed = subprocess.run(
            ["docker", "rm", "-f", self.container_id],
            text=True, capture_output=True, check=False, timeout=CLEANUP_RESERVE_SECONDS,
        )
        errors = completed.stderr.strip()
        if completed.returncode != 0 and "No such container" not in errors:
            raise RuntimeError(f"Could not remove the task container: {errors}")


def build_swebench_system_prompt(mcp_manual: str) -> str:
    """Build the English SWE-bench instructions around the discovered manual."""
    logger.debug("Entrando en build_swebench_system_prompt")
    return '''Fix the reported issue in the repository at /testbed, using
Thought -> Code -> Observation.
Write a Thought of at most 40 words and one closed ```python block, then <end_code>.
Only Python in that block is executed. Variables persist between blocks.
Use print to see results: you receive an Observation only for what you print.
Your Python runs in a restricted sandbox that cannot import the project: an
`import` of anything under /testbed will fail. To run the project's own code use
run_command, for example run_command(command='python -c "..."', workdir="/testbed").
Never invent an Observation and never guess a file's contents.
Work in small steps and let each step depend on what you actually observed:
1. Locate the code. Use search_function_or_class_definition_in_code to find a
   definition, search_code to find a pattern and find_references to see callers.
2. Read it with read_file before changing anything.
3. Change the smallest thing that fixes the issue, with edit_file. Its old_str
   must appear exactly once, so include enough surrounding lines.
4. Run run_tests and read its output. A failure tells you what to correct.
Example methodology for a separate task:
Thought: I will find where the reported function is defined before reading it.
```python
print(search_function_or_class_definition_in_code(name="parse_header"))
```
<end_code>
Never call final_answer until get_patch shows your change: if it reports that
there are no changes yet, you have not edited anything and must keep working.
When the tests pass, submit in a NEW response:
```python
final_answer(get_patch())
```
<end_code>
final_answer is a local sandbox function, never an MCP tool. Submit the diff
exactly as get_patch returns it, with no Markdown and no explanation.
Do not look for the official fix, a pull request or a remembered patch: solve
the issue from what you read in this checkout. Passing the tests you can run
does not guarantee the hidden tests pass.
Available MCP manual:
''' + mcp_manual


def build_swebench_task_prompt(task: SWEBenchTaskInput) -> str:
    """Format the supplied issue without adding external solution material."""
    logger.debug("Entrando en build_swebench_task_prompt")
    parts = [f"Task {task.instance_id}"]
    if task.repo:
        parts.append(f"Repository: {task.repo}")
    parts.append("Issue:\n" + task.problem_statement)
    if task.hints_text:
        parts.append("Hints from the discussion:\n" + task.hints_text)
    parts.append("The checkout is at /testbed. Inspect it before editing.")
    return "\n\n".join(parts)


def _build_swebench_limits(max_iterations: int) -> AgentLimits:
    """Return the SWE-bench limits with the requested iteration ceiling."""
    logger.debug("Entrando en _build_swebench_limits")
    if max_iterations <= 0:
        raise ValueError("max_iterations must be positive.")
    return AgentLimits(
        max_iterations=min(max_iterations, 30), max_input_tokens=300_000,
        max_output_tokens=10_000, max_time_seconds=MAX_TASK_SECONDS,
    )


async def run_swebench_agent(
    task: SWEBenchTaskInput, args: argparse.Namespace, *, started_at: float,
) -> SolutionOutput:
    """Prepare one testbed, await the shared loop, and preserve the whole patch."""
    logger.debug("Entrando en run_swebench_agent")
    logger.info("Preparando recursos de SWE-bench %s", task.instance_id)
    result = SolutionOutput(
        task_id=task.instance_id, benchmark="swebench", success=False, solution="",
        iterations=0, total_requests=0, total_input_tokens=0, total_output_tokens=0,
        total_time_seconds=0,
    )
    environment = client = sandbox = None
    try:
        limits = _build_swebench_limits(args.max_iterations)
        deadline = started_at + limits.max_time_seconds - CLEANUP_RESERVE_SECONDS
        if time.monotonic() >= deadline:
            raise TimeoutError("Task expired before setup.")

        provider = ProviderClient.from_environment(
            args.provider_url, args.model_name, os.environ.get("AGENT_SMITH_MODELS_CONFIG"),
        )
        config = load_sandbox_config(os.environ.get("AGENT_SMITH_SANDBOX_CONFIG"))

        environment = SWEEnvironment(task, deadline=deadline)
        await anyio.to_thread.run_sync(environment.start)

        server_environment = {name: os.environ[name] for name in (
            "PATH", "HOME", "DOCKER_HOST", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH",
        ) if name in os.environ}
        server_environment.update(environment.mcp_environment())
        root = Path(__file__).resolve().parents[1]
        client = MCPClient(
            stdio_command=[sys.executable, str(root / "mcp_tools_swebench.py")],
            environment=server_environment,
        )

        session, manual = await client.start(deadline=deadline)
        logger.info("MCP listo: %s herramientas descubiertas", len(manual.tools))
        advertised = {tool["name"] for tool in manual.tools}
        missing = [name for name in REQUIRED_TOOLS if name not in advertised]
        if missing:
            raise RuntimeError("The MCP server did not advertise: " + ", ".join(missing))

        result.system_prompt = build_swebench_system_prompt(manual.as_text())
        sandbox = SandboxSession(config, session, manual)
        with anyio.fail_after(max(0, deadline - time.monotonic())):
            await sandbox.start()
        logger.info("Trabajador preparado; comenzando Thought -> Code -> Observation")
        result = await run_agent_loop(
            task_id=task.instance_id, benchmark="swebench",
            system_prompt=result.system_prompt, task_prompt=build_swebench_task_prompt(task),
            provider=provider, sandbox=sandbox, limits=limits, started_at=started_at,
            deadline=deadline,
        )
        # Un parche real siempre empieza por "diff --git". Comprobar sólo que no
        # esté vacío no basta: un modelo entregó el aviso "No changes yet." de
        # get_patch como si fuera su solución y la tarea se daba por buena.
        if result.success and "diff --git" not in result.solution:
            result.success = False
            result.error = (
                "The final answer is not a diff; the agent submitted without "
                f"changing any file: {result.solution.strip()[:200]!r}"
            )
    except Exception as exc:
        logger.exception("Fallo del adaptador SWE-bench; iniciando cierre de recursos")
        result.success = False
        result.error = f"{type(exc).__name__}: {exc}"
    finally:
        logger.info("Limpieza SWE-bench: cerrando trabajador, MCP y contenedor")
        cleanup_errors = []
        for resource in (sandbox, client):
            if resource is not None:
                try:
                    await resource.close()
                except Exception as exc:
                    logger.error("No se pudo cerrar %s: %s", type(resource).__name__, exc)
                    cleanup_errors.append(f"{type(resource).__name__}: {exc}")
        if environment is not None:
            try:
                # El contenedor debe morir aunque se haya agotado el tiempo o
                # nos esten cancelando: por eso el shield.
                with anyio.CancelScope(shield=True):
                    await anyio.to_thread.run_sync(environment.close)
            except Exception as exc:
                logger.error("No se pudo eliminar el contenedor: %s", exc)
                cleanup_errors.append(f"Docker cleanup: {exc}")
        result.total_time_seconds = time.monotonic() - started_at
        if result.total_time_seconds > MAX_TASK_SECONDS:
            cleanup_errors.append(f"Total task time exceeded {MAX_TASK_SECONDS} seconds.")
        if cleanup_errors:
            result.success = False
            result.error = "\n".join(filter(None, [result.error, *cleanup_errors]))
        logger.info("Fin SWE-bench: success=%s, tiempo total=%.3fs", result.success, result.total_time_seconds)
        if result.error:
            logger.error("Motivo del fallo SWE-bench: %s", result.error)
    return result
