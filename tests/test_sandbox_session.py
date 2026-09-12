"""Known code only: persistent subprocesses, controls, and JSON transport."""

import asyncio
import json
import time
from io import StringIO
from types import SimpleNamespace

import pytest

from agent_smith.models import SandboxConfig
from agent_smith.sandbox import SandboxSession, FinalAnswerSignal
from agent_smith.mcp_client import MCPManual
from json_worker import _build_namespace, WorkerProtocolError


def test_persistent_worker_and_complete_answer():
    async def scenario():
        sandbox = SandboxSession(SandboxConfig(allowed_directories=[]))
        try:
            await sandbox.start()
            process, directory = sandbox.worker, sandbox.work_directory
            first = await sandbox.execute("x = 6\ndef value():\n    return x\nprint('first')")
            assert first.output == "first\n"
            failed = await sandbox.execute("x += 1\nprint('before')\nraise ValueError('bad')")
            assert failed.error == "ValueError: bad"
            assert failed.output == "before\n"
            assert not failed.worker_failed
            answer = await sandbox.execute("final_answer(str(value()) * 130000)")
            assert answer.final_answer == "7" * 130000
            assert sandbox.worker is process
        finally:
            await sandbox.close()
        assert process.returncode is not None
        assert not directory.exists()
        await sandbox.close()
    asyncio.run(scenario())


def test_timeout_preserves_output_and_closes_worker():
    async def scenario():
        sandbox = SandboxSession(SandboxConfig(max_execution_time_seconds=1))
        try:
            await sandbox.start()
            process = sandbox.worker
            result = await sandbox.execute("print('before', end='')\nwhile True: pass")
            assert result.timed_out and result.worker_failed
            assert result.output == "before"
            assert process.returncode is not None
            assert sandbox.worker is None
        finally:
            await sandbox.close()
    asyncio.run(scenario())


@pytest.mark.parametrize("statement, expected", [
    ("import os", "ImportError"),
    ("open('/etc/passwd')", "PermissionError"),
    ("import socket\nsocket.socket()", "PermissionError"),
    ("huge = 'x' * (1024 * 1024 * 1024)", "MemoryError"),
])
def test_worker_controls(statement, expected):
    async def scenario():
        sandbox = SandboxSession(SandboxConfig(
            authorized_imports=["socket"], allowed_directories=[], max_memory_mb=128,
        ))
        try:
            await sandbox.start()
            result = await sandbox.execute(statement)
            assert expected in result.error
        finally:
            await sandbox.close()
    asyncio.run(scenario())


def test_truncation_does_not_truncate_final_answer():
    async def scenario():
        sandbox = SandboxSession(SandboxConfig())
        try:
            await sandbox.start()
            result = await sandbox.execute("print('x' * 12010, end='')\nfinal_answer('z' * 130000)")
            assert result.truncated
            assert result.output.count("[Output truncated:") == 1
            assert "10 characters omitted" in result.output
            assert result.final_answer == "z" * 130000
        finally:
            await sandbox.close()
    asyncio.run(scenario())


@pytest.mark.parametrize("statement, exception", [
    ("raise KeyboardInterrupt()", KeyboardInterrupt),
    ("raise SystemExit(7)", SystemExit),
])
def test_control_exceptions_close_worker(statement, exception):
    async def scenario():
        sandbox = SandboxSession(SandboxConfig())
        try:
            await sandbox.start()
            process = sandbox.worker
            with pytest.raises(exception):
                await sandbox.execute(statement)
            assert process.returncode is not None
        finally:
            await sandbox.close()
    asyncio.run(scenario())


def test_mcp_wait_excluded_from_block_timeout():
    class Session:
        async def call_tool(self, **kwargs):
            await asyncio.sleep(1.1)
            return SimpleNamespace(model_dump=lambda **kw: {"structuredContent": {"answer": 42}})

    async def scenario():
        tool = {"name": "slow", "inputSchema": {"properties": {}}}
        sandbox = SandboxSession(
            SandboxConfig(max_execution_time_seconds=1), Session(),
            MCPManual("", [tool], [], [], []),
        )
        try:
            await sandbox.start()
            result = await sandbox.execute("print(slow())", deadline=time.monotonic() + 5)
            assert result.error is None
            assert "42" in result.output
            result = await sandbox.execute("slow()", deadline=time.monotonic() + 0.05)
            assert result.timed_out and result.worker_failed
        finally:
            await sandbox.close()
    asyncio.run(scenario())


def test_namespace_collision_and_positional_arguments():
    tools = [
        {"name": name, "inputSchema": {"properties": {"code": {}, "tests": {}}}}
        for name in ("run_tests", "final_answer", "print", "class", "has-dash")
    ]
    output = StringIO()
    namespace = _build_namespace(SandboxConfig(), tools, StringIO(
        '{"type":"mcp_result","result":{"success":true}}\n'
    ), output)
    assert "class" not in namespace and "has-dash" not in namespace
    assert "print" not in namespace
    with pytest.raises(FinalAnswerSignal):
        namespace["final_answer"]("local")
    assert namespace["run_tests"]("candidate", tests=[]) == {"success": True}
    request = json.loads(output.getvalue())
    assert request["arguments"] == {"name": "run_tests", "arguments": {"code": "candidate", "tests": []}}
    with pytest.raises(TypeError):
        namespace["run_tests"]("one", code="two")
    with pytest.raises(WorkerProtocolError):
        namespace["run_tests"]("no reply")


def test_missing_mcp_is_an_ordinary_error():
    async def scenario():
        sandbox = SandboxSession(SandboxConfig())
        try:
            await sandbox.start()
            result = await sandbox.execute("mcp_call_tool('absent')")
            assert "No MCP server" in result.error
            assert not result.worker_failed
        finally:
            await sandbox.close()
    asyncio.run(scenario())
