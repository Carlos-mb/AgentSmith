"""Interactive command-line interface required by ``uv run sandbox``."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from agent_smith.mcp_client import MCPClient
from agent_smith.models import SandboxConfig
from agent_smith.sandbox import SandboxSession


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Recibir argv opcional; devolver argparse.Namespace.

    1. Aceptar uv run sandbox [--mcp-stdio COMMAND | --mcp-server URL] [CONFIG_JSON].
    2. Path posicional opcional y transportes mutuamente excluyentes; sin argumentos
       abrir REPL con defaults. No añadir comandos opcionales.
    3. argparse da uso/errores en inglés; no crea recursos.
    """
    raise NotImplementedError("Sandbox argument parsing is not implemented yet.")


def _build_mcp_client(args: argparse.Namespace) -> MCPClient | None:
    """Recibir argumentos; devolver MCPClient sin abrir o None si no se pidió MCP.

    1. stdio: separar con shlex.split, nunca ejecutar mediante shell.
    2. HTTP: pasar server_url al validador del cliente, sin cambiar el transporte.
    3. No conectar aquí; el llamante prepara primero la limpieza.
    """
    raise NotImplementedError("Sandbox MCP client creation is not implemented yet.")


def run_repl(session: SandboxSession) -> int:
    """Recibir sesión iniciada; ejecutar entradas persistentes y devolver código de salida.

    1. Leer con input un prompt corto. codeop.compile_command distingue entrada
       incompleta y pide continuación; sólo comprueba completitud, no ejecuta código.
       Si detecta SyntaxError, mostrarlo, vaciar la entrada y volver al prompt;
       no propagarlo como fallo de arranque a main ni enviarlo a ejecutar.
    2. exit exacto en prompt principal o EOF terminan normalmente (devolver 0).
       No añadir reset/quit ni otros comandos.
    3. Cada entrada completa pasa por session.execute y las mismas restricciones
       que en agente. Imprimir salida, truncamiento y errores; volver al prompt.
    4. final_answer imprime su string y vuelve al prompt conservando variables;
       sólo termina el bucle en modo agente, no este REPL.
    5. KeyboardInterrupt/SystemExit salen hacia main para limpieza y propagación;
       no convertirlos silenciosamente en un error corriente o nuevo prompt.
    6. Tras timeout/muerte del trabajador, explicar que se perdieron las variables;
       session reinicia internamente en la siguiente entrada si es posible.
       La sesión la cierra main; no cerrar MCP ni worker prestados aquí.
    """
    raise NotImplementedError("The interactive sandbox REPL is not implemented yet.")


def main(argv: Sequence[str] | None = None) -> int:
    """Recibir argv opcional; preparar y cerrar REPL, devolviendo su código.

    1. Parsear, cargar config JSON o defaults y construir cliente MCP opcional.
    2. Usar ExitStack para MCP y SandboxSession en ese orden; si una entrada falla,
       start limpia sus recursos parciales y ExitStack cierra las anteriores.
    3. Mostrar manual dinámico si hay MCP, sin contaminar stdout del servidor stdio.
    4. Ejecutar run_repl. Errores ordinarios de configuración/arranque: stderr y 1.
    5. finally cierra sandbox y MCP también al salir por exit, EOF, interrupción o
       SystemExit. Propagar estas dos excepciones después del cierre.
    """
    raise NotImplementedError("The sandbox CLI is not implemented yet.")
