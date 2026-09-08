"""Protocol test for the MBPP MCP server."""

import asyncio
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def list_mbpp_tools() -> list[object]:
    """Start the stdio server and return its advertised tools."""
    project_root = Path(__file__).resolve().parents[1]
    server_path = project_root / "mcp_tools_mbpp.py"

    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(server_path)],
        env=os.environ.copy(),
    )

    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            response = await session.list_tools()
            return list(response.tools)


def test_mcp_server_exposes_run_tests() -> None:
    """The stdio MCP server must advertise a run_tests tool."""
    tools = asyncio.run(list_mbpp_tools())

    # Returns the first item from an iterator that matches the condition
    run_tests_tool = next(tool for tool in tools if tool.name == "run_tests")

    schema = run_tests_tool.inputSchema
    assert "code" in schema["properties"]
    assert "test_imports" in schema["properties"]
    assert "test_list" in schema["properties"]


async def call_run_tests() -> object:
    """Call run_tests with a simple correct solution."""

    project_root = Path(__file__).resolve().parents[1]
    server_path = project_root / "mcp_tools_mbpp.py"

    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(server_path)],
        env=os.environ.copy(),
    )

    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            result = await session.call_tool(
                "run_tests",
                arguments={
                    "code": "def add(a, b):\n    return a + b\n",
                    "test_imports": [],
                    "test_list": ["assert add(2, 3) == 5"],
                    "timeout_seconds": 10,
                },
            )

            return result


def test_mcp_run_tests_correct_solution() -> None:
    """Call run_tests with code that should pass."""

    result = asyncio.run(call_run_tests())

    print("\nisError:")
    print(result.isError)

    print("\nstructuredContent:")
    print(result.structuredContent)

    print("\ncontent:")
    print(result.content)

    assert result is not None