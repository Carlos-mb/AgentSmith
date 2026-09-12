"""Small Python controls and supervision of a persistent worker.

These controls do not resist hostile Python introspection. Project tests use
the execution environment authorized in AGENTS.md.
"""

from __future__ import annotations

from agent_smith.logging_config import LOG_LEVEL_ENV, get_logger

logger = get_logger('agent_smith.sandbox')

import asyncio
import builtins
import json
import logging
import os
import sys
import tempfile
import time

import anyio
import importlib
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any, Callable
from agent_smith.io import load_model

from agent_smith.models import SandboxConfig

if TYPE_CHECKING:
    from mcp import ClientSession

    from agent_smith.mcp_client import MCPManual


@dataclass
class SandboxExecution:
    """Carry one block's output, final answer, and execution status.

    Output may be partial or truncated. A final answer is kept in full.
    worker_failed distinguishes a lost process from an ordinary Python error.
    """

    output: str = ""
    final_answer: str | None = None
    error: str | None = None
    timed_out: bool = False
    truncated: bool = False
    worker_failed: bool = False


class FinalAnswerSignal(BaseException):
    """Stop the current block and carry the answer in the exception argument."""


def final_answer(answer: str) -> None:
    """Stop execution and carry the complete final answer."""
    logger.debug("Entrando en final_answer")
    if not isinstance(answer, str):
        logger.warning("final_answer rechazado: la respuesta debe ser texto")
        raise TypeError("Final answer must be a string.")

    logger.info("Solicitud local de finalización: %s caracteres", len(answer))
    raise FinalAnswerSignal(answer)


def load_sandbox_config(path: str | Path | None) -> SandboxConfig:
    """Load sandbox settings and require positive resource limits."""
    logger.debug("Entrando en load_sandbox_config")
    if path is None:
        config = SandboxConfig()
    else:
        config = load_model(path, SandboxConfig)

    if config.max_execution_time_seconds <= 0:
        raise RuntimeError("max_execution_time_seconds must be positive.")

    if config.max_memory_mb <= 0:
        raise RuntimeError("max_memory_mb must be positive.")

    logger.debug("Configuración sandbox válida: memoria=%s MiB, timeout de bloque=%ss", config.max_memory_mb, config.max_execution_time_seconds)
    return config

def _is_import_allowed(module_name, patterns):
    """Check exact module names and patterns ending in .*."""
    logger.debug("Entrando en _is_import_allowed")
    if module_name.startswith("."):
        return False

    for pattern in patterns:
        if module_name == pattern:
            logger.debug("Import permitido por coincidencia exacta: %s", module_name)
            return True

        if pattern.endswith(".*"):
            prefix = pattern[:-1]
            if module_name.startswith(prefix):
                logger.debug("Import permitido por patrón: %s", module_name)
                return True

    logger.debug("Import no autorizado: %s", module_name)
    return False


def _make_safe_import(authorized_imports):
    """Create an importer that checks the configured allowlist."""
    logger.debug("Entrando en _make_safe_import")
    allowed_imports = tuple(authorized_imports)

    def restricted_import(
        name, globals=None, locals=None, fromlist=(), level=0
    ):
        """Reject disallowed modules before delegating to Python's importer."""
        logger.debug("Entrando en _make_safe_import.restricted_import")
        logger.debug("Solicitado import %s; nivel relativo=%s; fromlist=%s", name, level, fromlist)
        if level != 0:
            raise ImportError("Relative imports are not allowed.")

        if not _is_import_allowed(name, allowed_imports):
            raise ImportError(f"Import not allowed: {name}")

        if fromlist:
            if "*" in fromlist:
                raise ImportError("Use explicit names instead of import *.")

            # Load the allowed module without processing fromlist yet.
            module = importlib.import_module(name)
            attributes = vars(module)

            for item in fromlist:
                value = attributes.get(item)

                if isinstance(value, ModuleType):
                    module_name = value.__name__
                elif item not in attributes:
                    module_name = f"{name}.{item}"
                else:
                    continue

                if not _is_import_allowed(module_name, allowed_imports):
                    raise ImportError(f"Import not allowed: {module_name}")

        return builtins.__import__(name, globals, locals, fromlist, level)

    return restricted_import


def _resolve_allowed_path(
        path: str | Path,
        allowed_directories: list[Path],
        ) -> Path:
    """Resolve a path and require membership in an allowed directory."""
    logger.debug("Entrando en _resolve_allowed_path")
    candidate = Path(path).resolve(strict=False)
    logger.debug("Comprobando pertenencia de la ruta resuelta: %s", candidate)

    for directory in allowed_directories:
        root = directory.resolve(strict=False)
        if candidate.is_relative_to(root):
            logger.debug("Ruta autorizada dentro de %s", root)
            return candidate

    logger.warning("Acceso a archivo rechazado: ruta fuera de los directorios permitidos")
    raise PermissionError(f"Filesystem access denied by sandbox: {candidate}")


def _make_safe_open(allowed_directories: list[str]) -> Callable[..., Any]:
    """Create a file opener restricted to allowed directories."""
    logger.debug("Entrando en _make_safe_open")
    allowed_paths = [
        Path(directory).resolve(strict=False)
        for directory in allowed_directories
    ]

    def restricted_open(
        file, mode="r", buffering=-1, encoding=None, errors=None,
        newline=None, closefd=True, opener=None,
    ):
        """Check access before opening the resolved path."""
        logger.debug("Entrando en _make_safe_open.restricted_open")
        if opener is not None:
            raise ValueError("Custom openers are not allowed.")

        if closefd is not True:
            raise ValueError("closefd must be True.")

        path = _resolve_allowed_path(file, allowed_paths)
        logger.debug("Abriendo archivo autorizado %s con modo %s", path, mode)

        return builtins.open(
            path,
            mode=mode,
            buffering=buffering,
            encoding=encoding,
            errors=errors,
            newline=newline,
        )

    return restricted_open


def _make_safe_builtins(config: SandboxConfig) -> dict[str, Any]:
    """Build the allowed builtins and attach restricted import and open."""
    logger.debug("Entrando en _make_safe_builtins")
    names = [
        "print", "len", "range", "enumerate", "zip",
        "iter", "next", "map", "filter",
        "sum", "min", "max", "sorted", "reversed",
        "abs", "round", "pow", "divmod", "all", "any",
        "int", "float", "bool", "str", "bytes",
        "list", "tuple", "dict", "set", "frozenset",
        "chr", "ord", "repr",
        "object", "isinstance", "issubclass", "type",
        "super", "property", "staticmethod", "classmethod",
        "__build_class__",
        "Exception", "AssertionError", "ValueError", "TypeError",
        "KeyError", "IndexError", "AttributeError", "NameError",
        "RuntimeError", "NotImplementedError", "StopIteration",
        "ZeroDivisionError", "ImportError", "OSError",
        "FileNotFoundError", "PermissionError",
        "MemoryError", "TimeoutError", "KeyboardInterrupt", "SystemExit",
    ]

    safe = {name: getattr(builtins, name) for name in names}
    safe["__import__"] = _make_safe_import(config.authorized_imports)
    safe["open"] = _make_safe_open(config.allowed_directories)

    logger.debug("Builtins preparados: %s nombres; import y open controlados", len(safe))
    return safe


def _apply_worker_limits(config: SandboxConfig) -> None:
    """Set memory limits and disable exposed socket entry points in the worker."""
    logger.debug("Entrando en _apply_worker_limits")
    import resource
    import socket

    if config.max_memory_mb <= 0 or config.max_execution_time_seconds <= 0:
        raise ValueError("Sandbox resource limits must be positive.")
    memory = config.max_memory_mb * 1024 * 1024
    _, hard = resource.getrlimit(resource.RLIMIT_AS)
    if hard != resource.RLIM_INFINITY:
        memory = min(memory, hard)
    resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    logger.info("Límite de memoria del trabajador aplicado: %s bytes de espacio virtual", memory)

    def reject_network(*args, **kwargs):
        logger.debug("Entrando en _apply_worker_limits.reject_network")
        logger.warning("Acceso de red del trabajador rechazado")
        raise PermissionError("Network access is disabled in the sandbox.")

    for name in (
        "socket", "create_connection", "create_server", "socketpair", "fromfd",
        "getaddrinfo", "gethostbyname", "gethostbyname_ex", "gethostbyaddr",
        "getnameinfo",
    ):
        if hasattr(socket, name):
            setattr(socket, name, reject_network)
    logger.debug("Vías de red expuestas deshabilitadas en el trabajador")


async def _send_worker_message(worker, message: dict) -> None:
    logger.debug("Entrando en _send_worker_message")
    logger.debug("Enviando JSON al trabajador: tipo=%s", message.get("type"))
    worker.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
    await worker.stdin.drain()


async def _read_worker_message(worker, buffer: bytearray) -> dict:
    # Read chunks so an intact final answer can exceed StreamReader's line limit.
    logger.debug("Entrando en _read_worker_message")
    while b"\n" not in buffer:
        chunk = await worker.stdout.read(16_384)
        if not chunk:
            logger.warning("EOF del trabajador al esperar un mensaje JSON")
            raise EOFError("Worker closed its output channel.")
        buffer.extend(chunk)
    end = buffer.index(b"\n")
    line = bytes(buffer[:end])
    del buffer[:end + 1]
    message = json.loads(line)
    if not isinstance(message, dict) or not isinstance(message.get("type"), str):
        raise ValueError("Invalid worker message.")
    logger.debug("JSON recibido del trabajador: tipo=%s, bytes=%s", message["type"], len(line))
    return message


async def _dispatch_mcp(session, message: dict) -> dict:
    """Call the SDK directly; tool errors are observations, disconnects are fatal."""
    logger.debug("Entrando en _dispatch_mcp")
    from mcp.shared.exceptions import McpError

    if session is None:
        logger.warning("El trabajador pidió MCP sin una sesión conectada")
        return {"type": "mcp_result", "error": "No MCP server is connected."}
    operation, arguments = message["operation"], message["arguments"]
    logger.info("Ejecutando MCP %s; herramienta/prompt=%s", operation, arguments.get("name", "—"))
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("MCP ENVIADO [%s]:\n%s", operation, json.dumps(arguments, ensure_ascii=False, indent=2))
    try:
        if operation == "call_tool":
            response = await session.call_tool(**arguments)
        elif operation == "read_resource":
            response = await session.read_resource(**arguments)
        elif operation == "get_prompt":
            response = await session.get_prompt(**arguments)
        else:
            raise ValueError(f"Unknown MCP operation: {operation}")
    except McpError as exc:
        logger.warning("El SDK MCP devolvió un error: código=%s", exc.error.code)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("MCP RECIBIDO [%s, error SDK]:\n%s", operation, exc.error.model_dump_json(indent=2, by_alias=True))
        if exc.error.code not in (-32601, -32602):
            raise
        return {"type": "mcp_result", "error": str(exc)}
    data = response.model_dump(mode="json", by_alias=True)
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("MCP RECIBIDO [%s]:\n%s", operation, json.dumps(data, ensure_ascii=False, indent=2))
    if data.get("isError"):
        logger.warning("La herramienta MCP informó un error; se devolverá como observación")
        return {"type": "mcp_result", "error": json.dumps(data, ensure_ascii=False)}
    result = data.get("structuredContent")
    if result is None:
        content = data.get("content", data.get("contents"))
        if content is not None and len(content) == 1 and "text" in content[0]:
            result = content[0]["text"]
        else:
            result = data
    logger.debug("Operación MCP completada; devolviendo resultado al trabajador")
    return {"type": "mcp_result", "result": result}


class SandboxSession:
    """Own one worker; borrow MCP from the task that opens and closes it."""

    def __init__(
        self,
        config: SandboxConfig,
        mcp_session: ClientSession | None = None,
        manual: MCPManual | None = None,
    ) -> None:
        logger.debug("Entrando en SandboxSession.__init__")
        if (mcp_session is None) != (manual is None):
            raise ValueError("MCP session and manual must be supplied together.")
        self.config = config.model_copy(deep=True)
        self.mcp_session = mcp_session
        self.manual = manual
        self.worker = None
        self.work_directory = None
        self._temporary = None
        self._buffer = bytearray()
        self._active = False

    async def start(self) -> None:
        """Start Python with a temporary cwd and no inherited credentials."""
        logger.debug("Entrando en SandboxSession.start")
        logger.info("Arrancando trabajador Python persistente")
        if self.worker is not None:
            raise RuntimeError("Sandbox is already started.")
        try:
            self._temporary = tempfile.TemporaryDirectory(prefix="agent-smith-")
            self.work_directory = Path(self._temporary.name)
            logger.debug("Directorio temporal del trabajador creado: %s", self.work_directory)
            script = Path(__file__).resolve().parents[1] / "json_worker.py"
            self.worker = await asyncio.create_subprocess_exec(
                sys.executable, "-u", str(script),
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=None, cwd=self.work_directory,
                env={"PYTHONIOENCODING": "utf-8", "PYTHONNOUSERSITE": "1",
                     LOG_LEVEL_ENV: os.environ.get(LOG_LEVEL_ENV, "")},
            )
            with anyio.fail_after(10):
                await _send_worker_message(self.worker, {
                    "type": "init", "config": self.config.model_dump(),
                    "tools": self.manual.tools if self.manual else [],
                })
                reply = await _read_worker_message(self.worker, self._buffer)
                if reply["type"] == "worker_error":
                    raise RuntimeError(reply["error"])
                if reply["type"] != "ready":
                    raise RuntimeError("Worker did not become ready.")
            logger.info("Trabajador listo; pid=%s", self.worker.pid)
        except BaseException as exc:
            logger.error("Fallo al iniciar el trabajador: %s", exc)
            await self.close()
            if isinstance(exc, Exception):
                raise RuntimeError(f"Sandbox startup failed: {exc}") from exc
            raise

    async def execute(
        self, code: str, *, deadline: float | None = None,
    ) -> SandboxExecution:
        """Execute once, retaining output and serving sequential MCP requests."""
        logger.debug("Entrando en SandboxSession.execute")
        logger.debug("Enviando bloque al trabajador: %s caracteres", len(code))
        if self.worker is None or self._active:
            raise RuntimeError("Sandbox must be started and idle.")
        self._active = True
        result = SandboxExecution()
        output = []
        omitted = None
        started = time.monotonic()
        mcp_wait = 0.0

        def remaining():
            logger.debug("Entrando en SandboxSession.execute.remaining")
            now = time.monotonic()
            block = self.config.max_execution_time_seconds - (now - started - mcp_wait)
            return min(block, deadline - now) if deadline is not None else block

        try:
            with anyio.fail_after(max(0, remaining())):
                await _send_worker_message(self.worker, {"type": "execute", "code": code})
            while True:
                with anyio.fail_after(max(0, remaining())):
                    message = await _read_worker_message(self.worker, self._buffer)
                kind = message["type"]
                if kind == "output":
                    output.append(message["text"])
                elif kind == "truncated":
                    result.truncated = True
                elif kind == "mcp_request":
                    logger.debug("Pausando el reloj del bloque durante la espera MCP; el plazo de tarea continúa")
                    mcp_started = time.monotonic()
                    timeout = None if deadline is None else max(0, deadline - mcp_started)
                    with anyio.fail_after(timeout):
                        reply = await _dispatch_mcp(self.mcp_session, message)
                        await _send_worker_message(self.worker, reply)
                    mcp_wait += time.monotonic() - mcp_started
                    logger.debug("MCP terminó; espera MCP acumulada=%.3fs; reanudando reloj del bloque", mcp_wait)
                elif kind == "done":
                    result.final_answer = message["final_answer"]
                    result.error = message["error"]
                    result.truncated = message["truncated"]
                    omitted = message["omitted"]
                    if remaining() < 0:
                        raise TimeoutError("Execution deadline exceeded.")
                    break
                elif kind == "control_exit":
                    logger.warning("Interrupción del trabajador: %s", message["exception"])
                    if message["exception"] == "KeyboardInterrupt":
                        raise KeyboardInterrupt()
                    if message["exception"] == "SystemExit":
                        raise SystemExit(message.get("code"))
                    raise ValueError("Unknown control exception.")
                elif kind == "worker_error":
                    raise RuntimeError(message["error"])
                else:
                    raise ValueError(f"Unexpected worker message: {kind}")
        except Exception as exc:
            logger.error("Fallo fatal de ejecución; se conservará la salida parcial: %s", exc)
            result.timed_out = isinstance(exc, TimeoutError)
            result.worker_failed = True
            result.error = f"{type(exc).__name__}: {exc}"
            if result.timed_out:
                result.error = "Execution timed out; worker state was lost."
            try:
                await self.close()
            except Exception as cleanup:
                result.error += f" Cleanup failed: {cleanup}"
        except BaseException:
            logger.warning("Ejecución interrumpida; cerrando el trabajador")
            await self.close()
            raise
        finally:
            self._active = False
        result.output = "".join(output)
        if result.truncated:
            count = str(omitted) if omitted is not None else "an unknown number of"
            result.output += f"\n[Output truncated: {count} characters omitted.]"
        logger.info(
            "Bloque recibido: error=%s, timeout=%s, trabajador perdido=%s, final=%s, salida=%s caracteres",
            result.error is not None, result.timed_out, result.worker_failed,
            result.final_answer is not None, len(result.output),
        )
        return result

    async def close(self) -> None:
        """Reap only our process, then release only our temporary files."""
        logger.debug("Entrando en SandboxSession.close")
        logger.info("Cerrando trabajador y directorio temporal")
        errors = []
        with anyio.CancelScope(shield=True):
            try:
                if self.worker is not None:
                    if self.worker.stdin is not None:
                        logger.debug("Cerrando stdin para enviar EOF al trabajador")
                        self.worker.stdin.close()
                    # communicate also drains pipes; wait alone can block on full output.
                    for action, timeout in ((None, 0.3), ("terminate", 0.5), ("kill", 1.0)):
                        if action and self.worker.returncode is None:
                            logger.warning("El trabajador sigue activo; enviando %s", action)
                            try:
                                getattr(self.worker, action)()
                            except ProcessLookupError:
                                pass
                        try:
                            await asyncio.wait_for(self.worker.communicate(), timeout)
                            logger.debug("Trabajador recogido; código de salida=%s", self.worker.returncode)
                            break
                        except asyncio.TimeoutError:
                            if action == "kill":
                                raise RuntimeError("Worker did not exit after kill.")
            except Exception as exc:
                logger.error("Fallo al cerrar el trabajador: %s", exc)
                errors.append(str(exc))
            finally:
                self.worker = None
                if self._temporary is not None:
                    try:
                        self._temporary.cleanup()
                        logger.debug("Directorio temporal del trabajador eliminado")
                    except Exception as exc:
                        logger.error("No se pudo eliminar el directorio temporal: %s", exc)
                        errors.append(str(exc))
                self._temporary = self.work_directory = None
                self._buffer.clear()
                self._active = False
        if errors:
            raise RuntimeError("Sandbox cleanup failed: " + "; ".join(errors))
        logger.debug("Sandbox cerrado correctamente")
