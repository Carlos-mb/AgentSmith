"""Tests for MCP client configuration and streamable HTTP discovery."""

import asyncio
from contextlib import suppress
from pathlib import Path
import socket
import subprocess
import sys
import time

import pytest

from agent_smith.mcp_client import MCPClient
from agent_smith.models import SandboxConfig
from agent_smith.sandbox import SandboxSession


def test_mcp_client_accepts_stdio_command() -> None:
    command = ["python", "mcp_tools_mbpp.py"]

    client = MCPClient(stdio_command=command)

    assert client.stdio_command == command
    assert client.server_url is None

    assert client.environment == {}


def test_mcp_client_accepts_http_url() -> None:
    url = "http://127.0.0.1:8000/mcp"

    client = MCPClient(server_url=url)

    assert client.server_url == url
    assert client.stdio_command is None

    assert client.environment == {}


def test_mcp_client_rejects_both_transports() -> None:
    with pytest.raises(ValueError):
        MCPClient(
            stdio_command=["python", "mcp_tools_mbpp.py"],
            server_url="http://127.0.0.1:8000/mcp",
        )


def test_mcp_client_rejects_no_transport() -> None:
    with pytest.raises(ValueError):
        MCPClient()


def test_mcp_client_rejects_invalid_transport_values() -> None:
    with pytest.raises(ValueError):
        MCPClient(stdio_command=[])

    with pytest.raises(ValueError):
        MCPClient(server_url="not-a-valid-url")


def test_mcp_client_copies_configuration() -> None:
    command = ["python", "mcp_tools_mbpp.py"]
    environment = {"EXAMPLE": "original"}

    client = MCPClient(
        stdio_command=command,
        environment=environment,
    )

    command.append("--changed")
    environment["EXAMPLE"] = "changed"

    assert client.stdio_command == [
        "python",
        "mcp_tools_mbpp.py",
    ]
    assert client.environment == {
        "EXAMPLE": "original",
    }

def test_mcp_client_rejects_blank_executable() -> None:
    with pytest.raises(ValueError):
        MCPClient(stdio_command=[""])

    with pytest.raises(ValueError):
        MCPClient(stdio_command=["   "])


def test_mcp_client_accepts_empty_argument() -> None:
    command = ["python", "server.py", "--message", ""]

    client = MCPClient(stdio_command=command)

    assert client.stdio_command == command


def test_mcp_client_discovers_and_uses_streamable_http_server() -> None:
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]

    root = Path(__file__).resolve().parents[1]
    server = subprocess.Popen(
        [sys.executable, "tests/_http_mcp_server.py", str(port)],
        cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    url = f"http://127.0.0.1:{port}/mcp"

    async def scenario():
        deadline = time.monotonic() + 10
        client = None
        while client is None:
            candidate = MCPClient(server_url=url)
            try:
                session, manual = await candidate.start(deadline=deadline)
            except Exception:
                if time.monotonic() >= deadline:
                    raise
                await asyncio.sleep(0.05)
            else:
                client = candidate
        try:
            assert [tool["name"] for tool in manual.tools] == ["identify"]
            assert [resource["uri"] for resource in manual.resources] == ["test://status"]
            assert [template["uriTemplate"] for template in manual.resource_templates] == [
                "test://items/{name}",
            ]
            assert [prompt["name"] for prompt in manual.prompts] == ["discuss"]
            assert "HTTP integration instructions." in manual.as_text()

            tool = await session.call_tool("identify", arguments={"value": "MCP"})
            assert tool.content[0].text == "identified: MCP"
            resource = await session.read_resource("test://status")
            assert resource.contents[0].text == "ready"
            item = await session.read_resource("test://items/example")
            assert item.contents[0].text == "item: example"
            prompt = await session.get_prompt("discuss", arguments={"topic": "HTTP"})
            assert prompt.messages[0].content.text == "Discuss HTTP"

            sandbox = SandboxSession(
                SandboxConfig(allowed_directories=[]), session, manual,
            )
            try:
                await sandbox.start()
                execution = await sandbox.execute(
                    "print(identify('worker'))\n"
                    "print(read_resource('test://status'))\n"
                    "print(get_prompt('discuss', {'topic': 'worker'}))"
                )
                assert execution.error is None
                assert "identified: worker" in execution.output
                assert "ready" in execution.output
                assert "Discuss worker" in execution.output
            finally:
                await sandbox.close()
        finally:
            await client.close()

    try:
        asyncio.run(scenario())
    finally:
        with suppress(ProcessLookupError):
            server.terminate()
        try:
            stdout, stderr = server.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            stdout, stderr = server.communicate(timeout=5)
        assert server.returncode is not None, stderr
        assert stdout == ""
