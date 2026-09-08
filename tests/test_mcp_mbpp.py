"""Protocol test for the MBPP MCP server."""

import asyncio
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def docker_environment() -> dict[str, str]:
    """Return only the environment variables Docker may need."""
    names = (
        "DOCKER_HOST",
        "DOCKER_TLS_VERIFY",
        "DOCKER_CERT_PATH",
    )

    return {
        name: os.environ[name]
        for name in names
        if name in os.environ
    }


async def list_mbpp_tools() -> list[object]:
    """Start the stdio server and return its advertised tools."""
    project_root = Path(__file__).resolve().parents[1]
    server_path = project_root / "mcp_tools_mbpp.py"

    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(server_path)],
        env=docker_environment(),
    )

    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            response = await session.list_tools()
            return list(response.tools)


async def call_run_tests(code: str) -> dict:
    """Call the MCP run_tests tool with some Python code."""
    project_root = Path(__file__).resolve().parents[1]
    server_path = project_root / "mcp_tools_mbpp.py"

    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(server_path)],
        env=docker_environment(),
    )

    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            result = await asyncio.wait_for(
                session.call_tool(
                    "run_tests",
                    arguments={
                        "code": code,
                        "test_imports": [],
                        "test_list": [
                            "assert add(2, 3) == 5",
                        ],
                        "timeout_seconds": 10,
                    },
                ),
                timeout=30,
            )

            assert result.isError is False
            assert result.content
            assert result.structuredContent is not None

            data = result.structuredContent

            if "result" in data:
                data = data["result"]

            assert isinstance(data, dict)

            return data


def test_mcp_server_exposes_run_tests() -> None:
    """The stdio MCP server must advertise a run_tests tool."""
    tools = asyncio.run(list_mbpp_tools())

    run_tests_tool = next(
        tool for tool in tools
        if tool.name == "run_tests"
    )

    schema = run_tests_tool.inputSchema

    assert "code" in schema["properties"]
    assert "test_imports" in schema["properties"]
    assert "test_list" in schema["properties"]


def test_mcp_run_tests_correct_code() -> None:
    """Correct Python code should pass the public test."""
    code = """
def add(a, b):
    return a + b
"""

    result = asyncio.run(call_run_tests(code))

    assert result["success"] is True
    assert result["exit_code"] == 0


def test_mcp_run_tests_incorrect_code() -> None:
    """Incorrect Python code should fail the public test."""
    code = """
def add(a, b):
    return 0
"""

    result = asyncio.run(call_run_tests(code))

    assert result["success"] is False
    assert result["exit_code"] != 0
    assert "AssertionError" in result["output"]