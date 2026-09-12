"""Helpers used by the MBPP MCP server."""

from agent_smith.logging_config import get_logger

logger = get_logger('agent_smith.mbpp_tools')

import os
import time
import uuid
from typing import Any

import docker
from docker.errors import DockerException, ImageNotFound, NotFound


DEFAULT_DOCKER_IMAGE = "python:3.10.12-slim"
DEFAULT_TIMEOUT_SECONDS = 10
MAX_OUTPUT_CHARACTERS = 12_000


def build_test_program(
    code: str,
    test_imports: list[str],
    test_list: list[str],
) -> str:
    """Combine a candidate solution with the public MBPP tests."""
    logger.debug("Entrando en build_test_program")
    logger.debug("Preparando programa de tests: imports=%s, aserciones=%s, código=%s caracteres", len(test_imports), len(test_list), len(code))

    sections = []
    sections.extend(item.strip() for item in test_imports if item.strip())
    sections.append(code.strip())
    sections.extend(item.strip() for item in test_list if item.strip())
    return "\n\n".join(section for section in sections if section) + "\n"


def truncate_output(output: str) -> str:
    """Limit tool output so one failed test does
    not consume the whole prompt."""
    logger.debug("Entrando en truncate_output")
    if len(output) <= MAX_OUTPUT_CHARACTERS:
        return output

    removed = len(output) - MAX_OUTPUT_CHARACTERS
    logger.warning("Salida Docker truncada: se omiten %s caracteres", removed)
    return (
        output[:MAX_OUTPUT_CHARACTERS]
        + f"\n\n[Output truncated: {removed} characters were removed.]"
    )


def run_mbpp_tests(
    code: str,
    test_imports: list[str],
    test_list: list[str],
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Run tests in an owned container, with a task deadline and bounded cleanup."""
    logger.debug("Entrando en run_mbpp_tests")
    logger.info("Tests MBPP solicitados: %s aserciones, timeout=%ss", len(test_list), timeout_seconds)
    if not code.strip():
        logger.warning("No se ejecutarán tests: candidato vacío")
        return {
            "success": False,
            "message": "Public tests were not executed.",
            "output": "The candidate solution is empty.",
            "exit_code": None,
        }

    if timeout_seconds <= 0:
        logger.warning("No se ejecutarán tests: timeout no positivo")
        return {
            "success": False,
            "message": "Public tests were not executed.",
            "output": "timeout_seconds must be greater than zero.",
            "exit_code": None,
        }

    program = build_test_program(code, test_imports, test_list)
    client = None
    container = None
    started = False
    result = None

    deadline = None
    container_name = "agent-smith-mbpp-" + uuid.uuid4().hex

    def set_timeout(*, cleanup=False):
        logger.debug("Entrando en run_mbpp_tests.set_timeout")
        remaining = 2.0 if cleanup else (
            60.0 if deadline is None else deadline - time.monotonic() - 2
        )
        if remaining <= 0:
            raise TimeoutError("Task deadline reached before Docker operation.")
        if client is not None:
            client.api.timeout = min(remaining, 5.0)
        logger.debug("Plazo Docker: %.3fs restantes; operación de limpieza=%s", remaining, cleanup)
        return remaining

    try:
        if os.environ.get("AGENT_SMITH_DEADLINE"):
            deadline = float(os.environ["AGENT_SMITH_DEADLINE"])
        remaining = set_timeout()
        logger.debug("Conectando al daemon Docker")
        client = docker.from_env(timeout=min(remaining, 5.0))
        set_timeout()
        logger.info("Creando contenedor %s con imagen %s", container_name, DEFAULT_DOCKER_IMAGE)
        logger.debug("DOCKER ENTRADA [%s]: python -u -c; programa completo:\n%s", container_name, program)
        container = client.containers.create(
            DEFAULT_DOCKER_IMAGE,
            command=["python", "-u", "-c", program],
            name=container_name,
            labels={"agent-smith.mbpp.session": os.environ.get("AGENT_SMITH_MBPP_SESSION", "standalone")},
            network_disabled=True,
            mem_limit="128m",
            cpu_period=100_000,
            cpu_quota=50_000,
        )
        set_timeout()
        logger.debug("Contenedor creado; solicitando arranque")
        container.start()
        started = True
        logger.info("Contenedor en ejecución; esperando resultado de tests")

        remaining = set_timeout()
        wait_result = container.wait(timeout=min(timeout_seconds, remaining))
        exit_code = int(wait_result.get("StatusCode", 1))
        logger.debug("Proceso de tests terminado: exit_code=%s; leyendo logs Docker", exit_code)

        set_timeout()
        output = container.logs(stdout=True, stderr=True).decode(
            "utf-8", errors="replace"
        )
        logger.debug(
            "DOCKER SALIDA [%s, exit_code=%s, stdout/stderr combinados]:\n%s",
            container_name, exit_code, output or "[sin salida]",
        )
        output = truncate_output(output.strip())

        if exit_code == 0:
            logger.info("Tests públicos correctos")
            result = {
                "success": True,
                "message": "All public tests passed.",
                "output": output,
                "exit_code": exit_code,
            }

        else:
            logger.warning("Tests públicos fallidos: exit_code=%s", exit_code)
            result = {
                "success": False,
                "message": "Public tests failed.",
                "output": output or "The test process failed without output.",
                "exit_code": exit_code,
            }

    except ImageNotFound:
        logger.error("No está disponible la imagen Docker %s", DEFAULT_DOCKER_IMAGE)
        result = {
            "success": False,
            "message": "Public tests could not start.",
            "output": (
                f"Docker image '{DEFAULT_DOCKER_IMAGE}' was not found. "
                f"Run: docker pull {DEFAULT_DOCKER_IMAGE}"
            ),
            "exit_code": None,
        }
    except Exception as exc:
        logger.error("Los tests Docker no pudieron completarse: %s", type(exc).__name__)
        logger.debug("DOCKER ERROR [%s]: %s: %s", container_name, type(exc).__name__, exc)
        text = str(exc)
        if started and (
            isinstance(exc, TimeoutError)
            or "timeout" in text.lower() or "timed out" in text.lower()
        ):
            output = f"Execution timed out after {timeout_seconds} seconds."
        else:
            kind = "Docker" if isinstance(exc, DockerException) else "Execution"
            output = f"{kind} error: {text}"

        if started:
            try:
                logger.debug("Intentando recuperar salida parcial del contenedor")
                set_timeout(cleanup=True)
                partial = container.logs(stdout=True, stderr=True).decode(
                    "utf-8", errors="replace"
                )
                logger.debug(
                    "DOCKER SALIDA PARCIAL [%s, stdout/stderr combinados]:\n%s",
                    container_name, partial or "[sin salida]",
                )
                output += "\nOutput is partial:\n" + truncate_output(partial.strip())
            except Exception as log_error:
                logger.warning("No se pudo recuperar la salida parcial: %s", type(log_error).__name__)
                output += f"\nCould not read partial output: {log_error}"

        result = {
            "success": False,
            "message": (
                "Public tests could not complete."
                if started else "Public tests could not start."
            ),
            "output": output,
            "exit_code": None,
        }
    finally:
        logger.debug("Iniciando limpieza del contenedor de tests")
        cleanup_errors = []
        if container is None and client is not None:
            # Creation can reach Docker even if its HTTP response is lost.
            try:
                logger.debug("Comprobando si Docker llegó a crear el contenedor pese al fallo")
                set_timeout(cleanup=True)
                container = client.containers.get(container_name)
            except NotFound:
                pass
            except Exception as exc:
                cleanup_errors.append(f"Could not check container creation: {exc}")
        if container is not None:
            try:
                logger.debug("Parando contenedor %s", container_name)
                set_timeout(cleanup=True)
                container.stop(timeout=1)
            except Exception as exc:
                cleanup_errors.append(f"Could not stop the test container: {exc}")
            try:
                logger.debug("Eliminando contenedor %s", container_name)
                set_timeout(cleanup=True)
                container.remove(force=True)
                logger.info("Contenedor de tests eliminado")
            except Exception as exc:
                cleanup_errors.append(f"Could not remove the test container: {exc}")

        if client is not None:
            try:
                client.close()
                logger.debug("Cliente Docker cerrado")
            except Exception as exc:
                cleanup_errors.append(f"Could not close the Docker client: {exc}")

        if cleanup_errors:
            cleanup_message = "Cleanup failed:\n" + "\n".join(cleanup_errors)
            logger.error("Limpieza Docker incompleta: %s", cleanup_message)
            if result is None:
                # Keep KeyboardInterrupt/SystemExit propagating after cleanup.
                logger.error("Se propaga la interrupción después de intentar limpiar")
            else:
                result["success"] = False
                result["message"] += " Cleanup failed."
                result["output"] += "\n" + cleanup_message

    logger.debug("Resultado de run_mbpp_tests: success=%s, exit_code=%s", result["success"], result["exit_code"])
    return result


def cleanup_mbpp_containers(session_id: str) -> None:
    """Remove this task's containers after MCP closes, including cancellation."""
    logger.debug("Entrando en cleanup_mbpp_containers")
    logger.debug("Comprobando contenedores restantes con la etiqueta de esta tarea")
    client = docker.from_env(timeout=2)
    errors = []
    try:
        for container in client.containers.list(
            all=True, filters={"label": f"agent-smith.mbpp.session={session_id}"},
        ):
            try:
                container.remove(force=True)
                logger.info("Contenedor restante de la tarea eliminado")
            except NotFound:
                pass
            except Exception as exc:
                logger.error("No se pudo eliminar un contenedor restante: %s", type(exc).__name__)
                errors.append(str(exc))
    finally:
        client.close()
    if errors:
        raise RuntimeError("MBPP cleanup failed: " + "; ".join(errors))
    logger.debug("Comprobación de limpieza Docker completada")
