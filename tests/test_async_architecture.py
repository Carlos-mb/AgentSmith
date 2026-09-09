"""R3/R4 integration probe, plus one controlled worker-failure scenario.

Linux, Python 3.10, MCP SDK 1.26.0. No agent, sandbox or LLM is used.
Only the two fixed candidates in _architecture_worker.py reach Docker.
"""

import asyncio
import json
import os
import sys
from contextlib import suppress
from datetime import timedelta
from pathlib import Path

import anyio
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


ROOT = Path(__file__).resolve().parents[1]
WORKER = Path(__file__).with_name("_architecture_worker.py")
IO_TIMEOUT = 10
CLOSE_TIMEOUT = 5
MCP_TIMEOUT = timedelta(seconds=30)


@pytest.fixture
def mcp_processes(monkeypatch: pytest.MonkeyPatch) -> list:
    """Observe the real MCP process; do not replace its execution."""
    processes = []
    original = anyio.open_process

    async def record_process(*args, **kwargs):
        process = await original(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(anyio, "open_process", record_process)
    return processes


def server_parameters() -> StdioServerParameters:
    names = ("DOCKER_HOST", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH")
    return StdioServerParameters(
        command=sys.executable,
        args=[str(ROOT / "mcp_tools_mbpp.py")],
        cwd=str(ROOT),
        env={name: os.environ[name] for name in names if name in os.environ},
    )


async def start_worker() -> asyncio.subprocess.Process:
    return await asyncio.create_subprocess_exec(
        sys.executable, "-I", "-u", str(WORKER),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={},  # Do not copy the supervisor's environment or API keys.
        cwd=str(ROOT),
    )


async def send_message(worker: asyncio.subprocess.Process, message: dict) -> None:
    worker.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
    await asyncio.wait_for(worker.stdin.drain(), IO_TIMEOUT)


async def receive_message(worker: asyncio.subprocess.Process) -> dict:
    line = await asyncio.wait_for(worker.stdout.readline(), IO_TIMEOUT)
    if not line:
        raise EOFError("Worker closed stdout before replying.")
    message = json.loads(line.decode("utf-8"))
    assert isinstance(message, dict), message
    assert message.get("pid") == worker.pid, message
    return message


async def close_worker(worker: asyncio.subprocess.Process) -> tuple[bytes, str]:
    """EOF must stop the worker; forced cleanup is a test failure, not success."""
    worker.stdin.close()
    try:
        remaining, errors = await asyncio.wait_for(
            worker.communicate(), CLOSE_TIMEOUT,
        )
    except asyncio.TimeoutError as exc:
        with suppress(ProcessLookupError):
            worker.kill()
        await asyncio.wait_for(worker.communicate(), CLOSE_TIMEOUT)
        raise AssertionError("Worker needed forced shutdown after EOF.") from exc
    return remaining, errors.decode("utf-8", errors="replace")


async def check_worker_messages() -> None:
    worker = await start_worker()
    try:
        for value in ("primero", "segundo"):
            await send_message(worker, {"type": "ping", "value": value})
            reply = await receive_message(worker)
            assert reply == {"type": "pong", "value": value, "pid": worker.pid}
            assert worker.returncode is None
    finally:
        remaining, errors = await close_worker(worker)

    assert worker.returncode == 0, errors
    assert remaining == b"", remaining
    assert errors == "", errors


async def check_event_loop(
    worker: asyncio.subprocess.Process,
    session: ClientSession,
) -> None:
    """MCP must progress while another coroutine waits for worker output."""
    await send_message(worker, {"type": "wait"})
    assert (await receive_message(worker))["type"] == "waiting"

    pending_read = asyncio.create_task(receive_message(worker))
    try:
        await asyncio.sleep(0)  # Let the pending read start, without a thread.
        tools = await session.list_tools()
        assert any(tool.name == "run_tests" for tool in tools.tools)
        assert not pending_read.done(), "Worker should still await release."
        await send_message(worker, {"type": "release"})
        assert (await pending_read)["type"] == "released"
    finally:
        pending_read.cancel()
        with suppress(asyncio.CancelledError):
            await pending_read


async def check_tool_calls(
    worker: asyncio.subprocess.Process,
    session: ClientSession,
) -> None:
    for candidate in ("bad", "good"):
        await send_message(worker, {
            "type": "test_candidate", "candidate": candidate,
        })
        request = await receive_message(worker)
        assert request["type"] == "tool_call", request
        assert request["name"] == "run_tests", request

        response = await session.call_tool(
            request["name"], arguments=request["arguments"],
        )
        assert response.isError is False, response
        result = response.structuredContent
        assert isinstance(result, dict), response

        await send_message(worker, {"type": "tool_result", "result": result})
        reply = await receive_message(worker)
        assert reply["type"] == "done", reply
        assert reply["result"] == result, reply
        assert worker.returncode is None

        if candidate == "bad":
            assert result["success"] is False, result
            assert result["message"] == "Public tests failed.", result
            assert isinstance(result["exit_code"], int), result
            assert result["exit_code"] != 0, result
            assert "AssertionError" in result["output"], result
        else:
            assert result["success"] is True, result
            assert result["message"] == "All public tests passed.", result
            assert result["exit_code"] == 0, result


async def check_architecture(processes: list, fail_worker: bool) -> None:
    worker = await start_worker()
    try:
        # All MCP operations and both context exits stay in this same task.
        async with stdio_client(server_parameters()) as (read, write):
            async with ClientSession(
                read, write, read_timeout_seconds=MCP_TIMEOUT,
            ) as session:
                await session.initialize()
                await check_event_loop(worker, session)
                await check_tool_calls(worker, session)

                if fail_worker:
                    # No tool call is in flight when this failure is requested.
                    await send_message(worker, {"type": "fail"})
                    with pytest.raises(EOFError, match="Worker closed stdout"):
                        await receive_message(worker)
                    await asyncio.wait_for(worker.wait(), CLOSE_TIMEOUT)
                    assert worker.returncode == 1

                    # The worker's failure must not destroy the MCP session.
                    tools = await session.list_tools()
                    assert any(tool.name == "run_tests" for tool in tools.tools)
    finally:
        remaining, errors = await close_worker(worker)

    # Check termination before asyncio.run performs its own final cleanup.
    assert len(processes) == 1, "Expected exactly one MCP server process."
    assert processes[0].returncode is not None, "MCP server is still running."
    assert remaining == b"", remaining
    if fail_worker:
        assert worker.returncode == 1, errors
        assert errors.strip() == "ValueError: Controlled worker failure.", errors
    else:
        assert worker.returncode == 0, errors
        assert errors == "", errors


def test_r3_two_messages_and_normal_close() -> None:
    asyncio.run(check_worker_messages())


def test_r4_worker_mcp_and_normal_close(mcp_processes: list) -> None:
    asyncio.run(check_architecture(mcp_processes, fail_worker=False))


def test_worker_failure_with_mcp_connected(mcp_processes: list) -> None:
    asyncio.run(check_architecture(mcp_processes, fail_worker=True))
