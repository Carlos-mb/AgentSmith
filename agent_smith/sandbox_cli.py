"""Interactive command-line interface required by ``uv run sandbox``."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from agent_smith.mcp_client import MCPClient
from agent_smith.models import SandboxConfig
from agent_smith.sandbox import SandboxSession


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the subject's sandbox CLI shape.

    Required interface::

        uv run sandbox [--mcp-stdio COMMAND | --mcp-server URL] [CONFIG_JSON]

    Pseudocode:
        - Add one optional positional ``Path`` for the sandbox JSON file.
        - Add mutually exclusive ``--mcp-stdio`` and ``--mcp-server`` options.
        - Keep every option optional so plain ``uv run sandbox`` opens a REPL.
        - Let argparse produce English usage and validation errors.
    """
    raise NotImplementedError("Sandbox argument parsing is not implemented yet.")


def _build_mcp_client(args: argparse.Namespace) -> MCPClient | None:
    """Create the optional MCP client selected on the command line.

    Pseudocode:
        - Return ``None`` when neither transport was requested.
        - Parse a stdio command with ``shlex`` instead of a shell.
        - Pass the HTTP URL unchanged to ``MCPClient`` for later validation.
        - Do not connect until the surrounding cleanup structure is ready.
    """
    raise NotImplementedError("Sandbox MCP client creation is not implemented yet.")


def run_repl(session: SandboxSession) -> int:
    """Read and execute entries repeatedly in one persistent namespace.

    Pseudocode:
        1. Show a short prompt without mixing it with MCP stdio output.
        2. Read one complete entry; support multi-line input in a simple way.
        3. Exit cleanly on the exact ``exit`` command or EOF.
        4. Execute through ``session`` and print output or the raised error.
        5. Stop when ``final_answer`` is captured.
        6. Convert an interactive keyboard interrupt to a clean next prompt or exit.
    """
    raise NotImplementedError("The interactive sandbox REPL is not implemented yet.")


def main(argv: Sequence[str] | None = None) -> int:
    """Load configuration, connect MCP, and run the interactive sandbox.

    Pseudocode:
        1. Parse arguments and load ``SandboxConfig`` or safe defaults.
        2. Build the optional MCP client.
        3. Enter MCP and sandbox context managers with ``ExitStack``.
        4. Print the dynamically generated manual when an MCP server is present.
        5. Delegate to ``run_repl``.
        6. Report expected configuration/startup errors in English and return 1.
        7. Always close the worker and MCP transport.
    """
    raise NotImplementedError("The sandbox CLI is not implemented yet.")
