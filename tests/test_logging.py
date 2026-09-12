"""Logging is opt-in, readable across processes, and separate from JSON data."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


def environment(level):
    result = dict(os.environ)
    result.pop("AGENT_SMITH_LOG_LEVEL", None)
    if level is not None:
        result["AGENT_SMITH_LOG_LEVEL"] = level
    return result


@pytest.mark.parametrize("level, expected", [
    (None, []), ("", []), ("DEBUG", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    ("info", ["INFO", "WARNING", "ERROR", "CRITICAL"]),
    ("WARNING", ["WARNING", "ERROR", "CRITICAL"]),
    ("ERROR", ["ERROR", "CRITICAL"]), ("CRITICAL", ["CRITICAL"]),
])
def test_levels_stderr_only_and_no_duplicate_or_sdk_logs(level, expected):
    code = '''
import logging
from agent_smith.logging_config import configure_logging, get_logger
configure_logging()
configure_logging()
logger = get_logger("logging_test")
for name in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
    logger.log(getattr(logging, name), "event_" + name)
logging.getLogger("httpcore").critical("SDK Authorization header should stay private")
'''
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=environment(level),
                            text=True, capture_output=True, timeout=10)
    assert result.returncode == 0 and result.stdout == ""
    for name in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        assert result.stderr.count("event_" + name) == (1 if name in expected else 0)
    assert "SDK Authorization" not in result.stderr
    if not expected:
        assert result.stderr == ""


def test_invalid_level_reports_error_without_echoing_its_value():
    result = subprocess.run([sys.executable, "-c", "import agent_smith.providers"],
                            cwd=ROOT, env=environment("mistyped-private-value"),
                            text=True, capture_output=True, timeout=10)
    assert result.returncode == 0 and result.stdout == ""
    assert "no válido; usando ERROR" in result.stderr
    assert "mistyped-private-value" not in result.stderr


def test_custom_provider_keys_are_redacted_in_messages_and_tracebacks():
    code = '''
from agent_smith.providers import ProviderClient, ProviderConfig
from agent_smith.logging_config import get_logger
ProviderClient(ProviderConfig(api_url="https://example.invalid", model_name="fixture",
    api_key_environment_variables=["CUSTOM_KEY"]), {"CUSTOM_KEY": "private-test-credential"})
logger = get_logger("test")
logger.info("Echo: %s", "private-test-credential")
try:
    raise RuntimeError("server echoed private-test-credential")
except RuntimeError:
    logger.exception("Operation failed")
'''
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=environment("DEBUG"),
                            text=True, capture_output=True, timeout=10)
    assert result.returncode == 0 and result.stdout == ""
    assert "private-test-credential" not in result.stderr
    assert "[REDACTED]" in result.stderr and "RuntimeError" in result.stderr


@pytest.mark.parametrize("level", [None, "INFO", "DEBUG"])
@pytest.mark.parametrize("reply_kind", ["json", "non_json_error"])
def test_ai_exchange_logs_full_history_and_body_only_in_debug(level, reply_kind):
    code = '''
import asyncio
import json
import sys
import time
import httpx
from agent_smith.providers import ProviderClient, ProviderConfig

messages = [
    {"role": "system", "content": "SYSTEM_MARKER\\nComplete instructions."},
    {"role": "user", "content": "TASK_MARKER"},
    {"role": "assistant", "content": "PREVIOUS_REPLY_MARKER"},
    {"role": "user", "content": "OBSERVATION_MARKER\\nCorrect the previous failure."},
]
def handler(request):
    assert json.loads(request.content)["messages"] == messages
    assert request.headers["Authorization"] == "Bearer private-test-credential"
    if sys.argv[1] == "json":
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "REPLY_MARKER private-test-credential"}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20},
        })
    return httpx.Response(503, text="ERROR_BODY_MARKER private-test-credential")

original = httpx.AsyncClient
httpx.AsyncClient = lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs)
client = ProviderClient(ProviderConfig(api_url="https://example.invalid/v1", model_name="fixture",
    api_key_environment_variables=["CUSTOM_KEY"]), {"CUSTOM_KEY": "private-test-credential"})
result = asyncio.run(client.complete(messages, max_input_tokens=6000, max_output_tokens=500,
                                    deadline=time.monotonic() + 5))
assert result.request_count == 1
assert (result.error is None) == (sys.argv[1] == "json")
'''
    result = subprocess.run([sys.executable, "-c", code, reply_kind], cwd=ROOT,
                            env=environment(level), text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert "private-test-credential" not in result.stderr
    assert "Bearer" not in result.stderr
    for marker in ("SYSTEM_MARKER", "TASK_MARKER", "PREVIOUS_REPLY_MARKER", "OBSERVATION_MARKER",
                   "REPLY_MARKER" if reply_kind == "json" else "ERROR_BODY_MARKER"):
        assert (marker in result.stderr) == (level == "DEBUG")
    if level == "DEBUG":
        assert result.stderr.count("IA ENVIADO [mensaje") == 4
        assert "IA RECIBIDO [HTTP" in result.stderr and "[REDACTED]" in result.stderr
    elif level is None:
        assert result.stderr == ""


@pytest.mark.parametrize("level", [None, "DEBUG"])
def test_worker_logs_arrive_live_without_polluting_json_or_output(level):
    process = subprocess.Popen([sys.executable, "-u", "json_worker.py"], cwd=ROOT,
                               env=environment(level), stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        process.stdin.write(json.dumps({"type": "init", "config": {}, "tools": []}) + "\n")
        process.stdin.flush()
        assert json.loads(process.stdout.readline()) == {"type": "ready"}
        if level:
            # A log is visible while the worker is still waiting for its first block.
            assert "json_worker.main" in process.stderr.readline()
            assert process.poll() is None
        output, logs = process.communicate(json.dumps({
            "type": "execute", "code": "print('hello'); final_answer('done')",
        }) + "\n", timeout=10)
        assert process.returncode == 0
        messages = [json.loads(line) for line in output.splitlines()]
        assert "".join(m["text"] for m in messages if m["type"] == "output") == "hello\n"
        assert messages[-1]["type"] == "done" and messages[-1]["final_answer"] == "done"
        if level:
            assert "execute_block" in logs and "final_answer capturado" in logs
        else:
            assert logs == ""
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate()


def test_startup_failure_is_json_data_even_when_logging_is_disabled():
    result = subprocess.run([sys.executable, "json_worker.py"], cwd=ROOT,
                            env=environment(None), text=True, capture_output=True,
                            input=json.dumps({"type": "init", "config": {"max_memory_mb": 0}, "tools": []}) + "\n",
                            timeout=10)
    assert result.returncode == 1 and result.stderr == ""
    message = json.loads(result.stdout)
    assert message["type"] == "worker_error" and "must be positive" in message["error"]


@pytest.mark.parametrize("level", [None, "ERROR"])
def test_argument_errors_follow_log_level_and_keep_exit_code(level):
    result = subprocess.run([sys.executable, "-m", "agent_mbpp"], cwd=ROOT,
                            env=environment(level), text=True, capture_output=True, timeout=10)
    assert result.returncode == 2 and result.stdout == ""
    if level:
        assert "Argumentos CLI inválidos" in result.stderr
    else:
        assert result.stderr == ""
