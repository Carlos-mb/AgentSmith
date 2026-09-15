"""Interactive command-line interface required by ``uv run sandbox``."""

from __future__ import annotations

from agent_smith.logging_config import (
    LoggingArgumentParser, configure_logging, get_logger,
)

import argparse
import ast
import asyncio
import codeop
import os
import shlex
import sys
from pathlib import Path
from typing import Sequence

from agent_smith.mcp_client import MCPClient
from agent_smith.sandbox import SandboxSession, load_sandbox_config

logger = get_logger('agent_smith.sandbox_cli')


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


# The MCP server starts with a minimal environment, so it must be given
# explicitly what it needs to find the testbed and talk to Docker.
SERVER_ENVIRONMENT_NAMES = (
    "PATH", "HOME", "TESTBED_PATH", "AGENT_SMITH_CONTAINER_ID",
    "AGENT_SMITH_EVAL_SCRIPT", "AGENT_SMITH_DEADLINE",
    "AGENT_SMITH_MBPP_SESSION",
    "DOCKER_HOST", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH",
)


def _build_mcp_client(args: argparse.Namespace) -> MCPClient | None:
    """Build an MCP client from CLI arguments without connecting."""
    logger.debug("Entrando en _build_mcp_client")

    if args.mcp_stdio is not None:
        command = shlex.split(args.mcp_stdio)
        environment = {
            name: os.environ[name]
            for name in SERVER_ENVIRONMENT_NAMES if name in os.environ
        }
        return MCPClient(stdio_command=command, environment=environment)

    if args.mcp_server is not None:
        return MCPClient(server_url=args.mcp_server)

    return None


async def _run_entry(session: SandboxSession, code: str) -> None:
    """Execute one complete entry and print what the sandbox reports."""
    logger.debug("Entrando en _run_entry")
    execution = await session.execute(code)
    if execution.output:
        print(execution.output, end="")
    if execution.error:
        print("Error: " + execution.error)
    if execution.final_answer is not None:
        print("Final answer: " + execution.final_answer)
    if execution.worker_failed:
        print("Worker restarted; variables were lost.")
        await session.close()
        await session.start()


async def run_script(session: SandboxSession, text: str | None = None) -> int:
    """Execute a piped script one top-level statement at a time.

    Line-by-line reading cannot handle a pasted file: a blank line inside a
    block would close it early, and a final_answer would abort everything that
    follows it. Splitting on top-level statements keeps both working.
    """
    logger.debug("Entrando en run_script")
    if text is None:
        text = sys.stdin.read()
    try:
        parsed = ast.parse(text)
    except SyntaxError as exc:
        print(f"SyntaxError: {exc}")
        return 1
    lines = text.splitlines()
    for node in parsed.body:
        first = min([node.lineno]
                    + [d.lineno for d in getattr(node, "decorator_list", [])])
        statement = "\n".join(lines[first - 1:node.end_lineno])
        if statement.strip() == "exit":
            return 0
        await _run_entry(session, statement)
    return 0


async def run_repl(session: SandboxSession) -> int:
    """Read and execute persistent Python entries until exit or EOF."""
    logger.debug("Entrando en run_repl")
    lines: list[str] = []
    while True:
        try:
            line = input("... " if lines else ">>> ")
        except EOFError:
            print()
            # With redirected input the last block arrives without a blank
            # line.
            if lines:
                await _run_entry(session, "\n".join(lines))
            return 0

        if not lines and line == "exit":
            return 0
        if not lines and not line:
            continue

        lines.append(line)
        code = "\n".join(lines)
        try:
            # "single" waits for a blank line to close a block, like the
            # Python REPL. With "exec" the block closed before else/except.
            compiled = codeop.compile_command(code, symbol="single")
        except (OverflowError, SyntaxError, ValueError) as exc:
            print(f"{type(exc).__name__}: {exc}")
            lines.clear()
            continue
        if compiled is None:
            continue

        lines.clear()
        await _run_entry(session, code)


async def _run_sandbox(args: argparse.Namespace) -> int:
    """Own MCP and worker lifetimes in the same async task as the REPL."""
    logger.debug("Entrando en _run_sandbox")
    config = load_sandbox_config(args.config)
    client = _build_mcp_client(args)
    session = None
    manual = None
    try:
        mcp_session = None
        if client is not None:
            mcp_session, manual = await client.start()
        session = SandboxSession(config, mcp_session=mcp_session,
                                 manual=manual)
        await session.start()
        if manual is not None:
            print(manual.as_text())
        if sys.stdin.isatty():
            return await run_repl(session)
        return await run_script(session)
    finally:
        cleanup_errors = []
        if session is not None:
            try:
                await session.close()
            except Exception as exc:
                cleanup_errors.append(f"sandbox: {exc}")
        if client is not None:
            try:
                await client.close()
            except Exception as exc:
                cleanup_errors.append(f"MCP: {exc}")
        if cleanup_errors:
            logger.error("Cleanup failed: %s", "; ".join(cleanup_errors))
            if sys.exc_info()[0] is None:
                raise RuntimeError("Sandbox cleanup failed: "
                                   + "; ".join(cleanup_errors))


def main(argv: Sequence[str] | None = None) -> int:
    """Parse CLI arguments and run the async sandbox with graceful errors."""
    configure_logging()
    logger.debug("Entrando en main")
    args = parse_arguments(argv)
    try:
        return asyncio.run(_run_sandbox(args))
    except Exception as exc:
        logger.error("Error: %s", exc)
        return 1
