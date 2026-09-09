"""Tests for sandbox CLI argument parsing."""

from pathlib import Path

import pytest

from agent_smith.sandbox_cli import _build_mcp_client, parse_arguments

def test_parse_arguments_with_no_options():
    args = parse_arguments([])

    assert args.config is None
    assert args.mcp_stdio is None
    assert args.mcp_server is None


def test_parse_arguments_with_config_file():
    args = parse_arguments(["configs/sandbox_template.json"])

    assert args.config == Path("configs/sandbox_template.json")
    assert isinstance(args.config, Path)


def test_parse_arguments_with_mcp_stdio():
    args = parse_arguments(
        ["--mcp-stdio", "python mcp_tools_mbpp.py"]
    )

    assert args.mcp_stdio == "python mcp_tools_mbpp.py"
    assert args.mcp_server is None


def test_parse_arguments_with_mcp_server():
    args = parse_arguments(
        ["--mcp-server", "http://127.0.0.1:8000/mcp"]
    )

    assert args.mcp_server == "http://127.0.0.1:8000/mcp"
    assert args.mcp_stdio is None


def test_parse_arguments_rejects_both_mcp_transports():
    with pytest.raises(SystemExit) as error:
        parse_arguments(
            [
                "--mcp-stdio",
                "python mcp_tools_mbpp.py",
                "--mcp-server",
                "http://127.0.0.1:8000/mcp",
            ]
        )

    assert error.value.code == 2

def test_build_mcp_client_returns_none_without_transport():
    args = parse_arguments([])

    client = _build_mcp_client(args)

    assert client is None


def test_build_mcp_client_with_stdio():
    args = parse_arguments(
        ["--mcp-stdio", "python mcp_tools_mbpp.py"]
    )

    client = _build_mcp_client(args)

    assert client is not None
    assert client.stdio_command == [
        "python",
        "mcp_tools_mbpp.py",
    ]
    assert client.server_url is None


def test_build_mcp_client_with_http():
    args = parse_arguments(
        ["--mcp-server", "http://127.0.0.1:8000/mcp"]
    )

    client = _build_mcp_client(args)

    assert client is not None
    assert client.server_url == "http://127.0.0.1:8000/mcp"
    assert client.stdio_command is None


def test_build_mcp_client_uses_shlex_for_stdio_command():
    args = parse_arguments(
        [
            "--mcp-stdio",
            'python server.py --message "hello world"',
        ]
    )

    client = _build_mcp_client(args)

    assert client is not None
    assert client.stdio_command == [
        "python",
        "server.py",
        "--message",
        "hello world",
    ]
