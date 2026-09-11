"""Tests for MCP client configuration."""

import pytest

from agent_smith.mcp_client import MCPClient


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
