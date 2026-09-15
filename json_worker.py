"""Persistent Python worker. stdout carries only newline-delimited JSON."""

from __future__ import annotations

import ast
import json
import keyword
import sys
from contextlib import redirect_stderr, redirect_stdout
from typing import Any, Callable, TextIO

from agent_smith.logging_config import configure_logging, get_logger
from agent_smith.models import SandboxConfig
from agent_smith.sandbox import (
    FinalAnswerSignal, _apply_worker_limits, _make_safe_builtins, final_answer,
)

logger = get_logger('json_worker')


class WorkerProtocolError(BaseException):
    """Abort the worker when its JSON channel can no longer be trusted."""


def _send_message(stream: TextIO, message: dict[str, Any]) -> None:
    """Write and flush one JSON message."""
    logger.debug("Entrando en _send_message")
    logger.debug("Enviando mensaje JSON tipo=%s", message.get("type"))
    try:
        stream.write(json.dumps(message) + "\n")
        stream.flush()
    except Exception as exc:
        raise WorkerProtocolError(f"Could not send message: {exc}") from exc


def _receive_message(stream: TextIO) -> dict[str, Any] | None:
    """Read one JSON message, returning None at end of input."""
    logger.debug("Entrando en _receive_message")
    try:
        line = stream.readline()
        if line == "":
            logger.info("EOF del supervisor recibido")
            return None

        message = json.loads(line)
    except Exception as exc:
        raise WorkerProtocolError(f"Could not read message: {exc}") from exc

    if not isinstance(message, dict):
        raise WorkerProtocolError("Expected a JSON object.")

    if not isinstance(message.get("type"), str):
        raise WorkerProtocolError("Message type must be a string.")

    logger.debug("Mensaje JSON recibido: tipo=%s", message["type"])
    return message


class WorkerOutput:
    """Send limited output and count omitted characters."""

    def __init__(self, stream: TextIO, max_characters: int = 12_000) -> None:
        logger.debug("Entrando en WorkerOutput.__init__")
        if max_characters <= 0:
            raise ValueError("max_characters must be positive.")

        self.stream = stream
        self.max_characters = max_characters
        self.sent = 0
        self.omitted = 0

    def write(self, text: str) -> int:
        """Send the allowed text and report truncation once."""
        logger.debug("Entrando en WorkerOutput.write")
        logger.debug("Salida del código: %s caracteres recibidos; "
                     "%s enviados previamente", len(text), self.sent)
        remaining = self.max_characters - self.sent
        chunk = text[:remaining]

        if chunk:
            _send_message(self.stream, {"type": "output", "text": chunk})
            self.sent += len(chunk)

        omitted = len(text) - len(chunk)
        if omitted > 0:
            if self.omitted == 0:
                logger.warning("Salida del bloque truncada al alcanzar "
                               "%s caracteres", self.max_characters)
                _send_message(self.stream, {"type": "truncated"})
            self.omitted += omitted

        return len(text)

    def flush(self) -> None:
        """Flush the stream used for JSON messages."""
        logger.debug("Entrando en WorkerOutput.flush")
        try:
            self.stream.flush()
        except Exception as exc:
            raise WorkerProtocolError(
                f"Could not flush output: {exc}"
            ) from exc


def _request_mcp(
    input_stream: TextIO,
    output_stream: TextIO,
    operation: str,
    arguments: dict[str, Any],
) -> Any:
    """Request one MCP operation from the supervisor and wait for its reply."""
    logger.debug("Entrando en _request_mcp")
    logger.info("Solicitando operación MCP %s al supervisor", operation)
    _send_message(output_stream, {
        "type": "mcp_request", "operation": operation, "arguments": arguments,
    })
    reply = _receive_message(input_stream)
    if reply is None or reply["type"] != "mcp_result":
        raise WorkerProtocolError("Expected mcp_result.")
    if reply.get("error") is not None:
        logger.warning("La operación MCP devolvió un error; "
                       "se entregará al código")
        raise RuntimeError(reply["error"])
    if "result" not in reply:
        raise WorkerProtocolError("MCP reply is missing result.")
    logger.debug("Resultado MCP recibido; reanudando el bloque Python")
    return reply["result"]


def _make_tool_wrapper(
    tool: dict[str, Any],
    input_stream: TextIO,
    output_stream: TextIO,
) -> Callable[..., Any]:
    """Describe a local Python wrapper for one discovered MCP tool."""
    logger.debug("Entrando en _make_tool_wrapper")
    name = tool["name"]
    parameters = list(tool.get("inputSchema", {}).get("properties", {}))

    def tool_wrapper(*args, **kwargs):
        logger.debug("Entrando en _make_tool_wrapper.tool_wrapper")
        logger.debug("Llamada a herramienta descubierta: %s", name)
        if len(args) > len(parameters):
            raise TypeError(f"Too many positional arguments for {name}.")
        arguments = dict(zip(parameters, args))
        if arguments.keys() & kwargs.keys():
            raise TypeError(f"Duplicate arguments for {name}.")
        arguments.update(kwargs)
        return _request_mcp(input_stream, output_stream, "call_tool", {
            "name": name, "arguments": arguments,
        })

    return tool_wrapper


def _build_namespace(
    config: SandboxConfig,
    tools: list[dict[str, Any]],
    input_stream: TextIO,
    output_stream: TextIO,
) -> dict[str, Any]:
    """Prepare persistent user globals with safe builtins and MCP wrappers."""
    logger.debug("Entrando en _build_namespace")
    safe = _make_safe_builtins(config)

    def mcp_call_tool(name, arguments=None):
        logger.debug("Entrando en _build_namespace.mcp_call_tool")
        return _request_mcp(input_stream, output_stream, "call_tool", {
            "name": name,
            "arguments": arguments if arguments is not None else {},
        })

    def read_resource(uri):
        logger.debug("Entrando en _build_namespace.read_resource")
        return _request_mcp(input_stream, output_stream, "read_resource",
                            {"uri": uri})

    def get_prompt(name, arguments=None):
        logger.debug("Entrando en _build_namespace.get_prompt")
        return _request_mcp(input_stream, output_stream, "get_prompt", {
            "name": name,
            "arguments": arguments if arguments is not None else {},
        })

    namespace = {
        "__builtins__": safe, "__name__": "__sandbox__",
        "final_answer": final_answer, "mcp_call_tool": mcp_call_tool,
        "read_resource": read_resource, "get_prompt": get_prompt,
    }
    for tool in tools:
        name = tool["name"]
        if (name.isidentifier() and not keyword.iskeyword(name)
                and name not in safe and name not in namespace):
            namespace[name] = _make_tool_wrapper(tool, input_stream,
                                                 output_stream)
            logger.debug("Función local MCP registrada: %s", name)
        else:
            logger.debug("Herramienta %s disponible mediante mcp_call_tool; "
                         "nombre reservado o no válido", name)
    logger.debug("Namespace persistente preparado; entradas=%s",
                 len(namespace))
    return namespace


def execute_block(
    code: str,
    namespace: dict[str, Any],
    output_stream: TextIO,
) -> None:
    """Execute code in the shared namespace and send its result."""
    logger.debug("Entrando en execute_block")
    logger.info("Ejecutando bloque Python en el namespace persistente: "
                "%s caracteres", len(code))
    output = WorkerOutput(output_stream)
    answer = None
    error = None

    try:
        with redirect_stdout(output), redirect_stderr(output):
            parsed = ast.parse(code)
            # Como en el REPL de Python: si el bloque termina en una
            # expresión, mostrar su valor. Los modelos llaman a las
            # herramientas sin print, y sin esto la observación llegaba
            # vacía y se quedaban en bucle.
            trailing = None
            if parsed.body and isinstance(parsed.body[-1], ast.Expr):
                trailing = parsed.body.pop().value
            exec(compile(parsed, "<sandbox>", "exec"), namespace, namespace)
            if trailing is not None:
                value = eval(
                    compile(ast.Expression(trailing), "<sandbox>", "eval"),
                    namespace, namespace,
                )
                if value is not None:
                    print(value)

    except FinalAnswerSignal as exc:
        answer = exc.args[0]
        logger.info("final_answer capturado: %s caracteres", len(answer))

    except (KeyboardInterrupt, SystemExit) as exc:
        logger.warning("El bloque pidió terminar el trabajador: %s",
                       type(exc).__name__)
        _send_message(output_stream, {
            "type": "control_exit",
            "exception": type(exc).__name__,
            "code": getattr(exc, "code", None),
        })
        raise

    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        logger.warning("Bloque Python fallido: %s; se enviará una "
                       "observación", type(exc).__name__)

    _send_message(output_stream, {
        "type": "done",
        "final_answer": answer,
        "error": error,
        "truncated": output.omitted > 0,
        "omitted": output.omitted,
    })
    logger.info("Bloque terminado: error=%s, respuesta final=%s, "
                "caracteres omitidos=%s",
                error is not None, answer is not None, output.omitted)


def main() -> int:
    """Initialize once and run sequential code blocks until shutdown or EOF."""
    configure_logging()
    logger.debug("Entrando en main")
    logger.info("Trabajador iniciado; esperando configuración JSON "
                "del supervisor")
    input_stream, output_stream = sys.stdin, sys.stdout
    try:
        message = _receive_message(input_stream)
        if message is None or message["type"] != "init":
            raise WorkerProtocolError("Expected init as the first message.")
        config = SandboxConfig.model_validate(message["config"])
        _apply_worker_limits(config)
        namespace = _build_namespace(
            config, message["tools"], input_stream, output_stream,
        )
        _send_message(output_stream, {"type": "ready"})
        logger.info("Trabajador listo para recibir bloques consecutivos")
        while True:
            message = _receive_message(input_stream)
            if message is None:
                return 0
            if (message["type"] != "execute"
                    or not isinstance(message.get("code"), str)):
                raise WorkerProtocolError(
                    "Expected execute with a code string."
                )
            execute_block(message["code"], namespace, output_stream)
    except (Exception, WorkerProtocolError) as exc:
        logger.error("Fallo fatal del trabajador: %s", type(exc).__name__)
        # Fatal errors are data too, so silence never hides the startup
        # diagnosis.
        try:
            _send_message(output_stream, {
                "type": "worker_error",
                "error": f"{type(exc).__name__}: {exc}",
            })
        except WorkerProtocolError:
            logger.error("No se pudo comunicar el fallo: canal JSON cerrado")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
