"""Interactive command-line interface required by ``uv run sandbox``."""

from __future__ import annotations

from agent_smith.logging_config import LoggingArgumentParser, configure_logging, get_logger

logger = get_logger('agent_smith.sandbox_cli')

import argparse
import shlex
from pathlib import Path
from typing import Sequence

from agent_smith.mcp_client import MCPClient
from agent_smith.sandbox import SandboxSession


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse sandbox command-line arguments."""
    logger.debug("Entrando en parse_arguments")

    parser = LoggingArgumentParser(
        description="Run the interactive sandbox."
    )

    parser.add_argument(
        "config",
        nargs="?",
        type=Path,
        help="Path to the sandbox configuration JSON file.",
    )

    mcp_group = parser.add_mutually_exclusive_group()

    mcp_group.add_argument(
        "--mcp-stdio",
        help="Command used to start an MCP server with stdio.",
    )

    mcp_group.add_argument(
        "--mcp-server",
        help="URL of an MCP server.",
    )

    return parser.parse_args(argv)


def _build_mcp_client(args: argparse.Namespace) -> MCPClient | None:
    """Build an MCP client from CLI arguments without connecting."""
    logger.debug("Entrando en _build_mcp_client")

    if args.mcp_stdio is not None:
        command = shlex.split(args.mcp_stdio)
        return MCPClient(stdio_command=command)

    if args.mcp_server is not None:
        return MCPClient(server_url=args.mcp_server)

    return None

async def run_repl(session: SandboxSession) -> int:
    """Read and execute persistent Python entries until exit or EOF."""
    logger.debug("Entrando en run_repl")
    # 1. Leer input con prompt corto. Acumular líneas hasta que
    #    codeop.compile_command indique bloque completo; no ejecutarlo aquí.
    #    Ante SyntaxError, mostrar error, vaciar entrada y pedir otro bloque.
    # 2. 'exit' exacto en el prompt principal o EOF devuelven 0. No añadir
    #    comandos reset/quit ni confundir texto dentro de un bloque con comandos.
    # 3. Hacer await session.execute(code). Mostrar output y error reales, además
    #    de final_answer si existe (comprobar is not None, no su valor booleano).
    #    No duplicar el aviso de truncamiento ya incluido en output.
    # 4. final_answer sólo acaba la tarea del agente; aquí vuelve al prompt y
    #    conserva variables del trabajador. Un error Python normal también.
    # 5. Si worker_failed=True, avisar que se perdieron las variables, await close
    #    y await start antes de otra entrada. No reejecutar entradas anteriores.
    #    Si el reinicio falla, propagar para que el propietario cierre los recursos.
    # 6. KeyboardInterrupt/SystemExit se propagan; el finally del propietario
    #    cierra trabajador y MCP. No convertirlas en errores corrientes del REPL.
    # 7. El input síncrono es inicialmente aceptable con una operación activa;
    #    no crear un hilo de MCP para esperar al usuario ni nuevas tareas del agente.
    logger.warning("Funcionalidad pendiente; se mantiene NotImplementedError")
    raise NotImplementedError("The interactive sandbox REPL is not implemented yet.")


async def _run_sandbox(args: argparse.Namespace) -> int:
    """Own MCP and worker lifetimes in the same asynchronous task as the REPL."""
    logger.debug("Entrando en _run_sandbox")
    # 1. Cargar config con load_sandbox_config(args.config) y construir el cliente
    #    opcional con _build_mcp_client. Preparar session=None para el finally.
    # 2. Dentro de try, si hay cliente, await client.start() devuelve sdk_session
    #    y manual. Sin cliente, ambos son None. No abrir en otra tarea/hilo.
    # 3. Crear SandboxSession(config, mcp_session=sdk_session, manual=manual)
    #    y hacer await session.start(). Si hay manual, mostrar manual.as_text().
    # 4. Devolver await run_repl(session). Los errores ordinarios se propagan
    #    a main; KeyboardInterrupt y SystemExit también, después de la limpieza.
    # 5. En finally, intentar await session.close() si llegó a existir; después,
    #    incluso si falla, intentar await client.close() si había cliente.
    #    Todo este recorrido permanece en la misma tarea, incluidos contextos SDK.
    # 6. Mantener el error original y añadir diagnóstico de limpieza si lo hay.
    #    No usar context managers de SandboxSession ni inventar su método reset.
    logger.warning("Funcionalidad pendiente; se mantiene NotImplementedError")
    raise NotImplementedError("The asynchronous sandbox owner is not implemented yet.")


def main(argv: Sequence[str] | None = None) -> int:
    """Parse CLI arguments and drive the asynchronous sandbox with graceful errors."""
    configure_logging()
    logger.debug("Entrando en main")
    # 1. Usar parse_arguments(argv), que ya está implementado.
    # 2. Ejecutar asyncio.run(_run_sandbox(args)) una sola vez y devolver su código.
    #    La apertura, uso y cierre de MCP ocurren dentro de esa misma coroutine.
    # 3. Errores ordinarios de config/arranque/REPL: diagnóstico en stderr y 1.
    #    No ocultar que una pieza sigue pendiente por NotImplementedError.
    # 4. KeyboardInterrupt y SystemExit se propagan después del cierre ya realizado
    #    por _run_sandbox. No dejar el trabajador vivo al abandonar el CLI.
    logger.warning("Funcionalidad pendiente; se mantiene NotImplementedError")
    raise NotImplementedError("The sandbox CLI is not implemented yet.")
