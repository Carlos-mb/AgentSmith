"""Tests for the MBPP test execution helper."""

import docker
import logging
import pytest
from docker.errors import DockerException, ImageNotFound
from unittest.mock import Mock

from agent_smith.mbpp_tools import (
    DEFAULT_DOCKER_IMAGE,
    MAX_OUTPUT_CHARACTERS,
    build_test_program,
    run_mbpp_tests,
)


def docker_image_is_ready() -> bool:
    """Return True when Docker and the required Python image are available."""
    try:
        client = docker.from_env()
        client.ping()
        client.images.get(DEFAULT_DOCKER_IMAGE)
        client.close()
        return True
    except (DockerException, ImageNotFound):
        return False


DOCKER_READY = docker_image_is_ready()


def test_build_test_program() -> None:
    """The helper must place imports before the solution and assertions."""
    program = build_test_program(
        code="def add(a, b):\n    return a + b",
        test_imports=["import math"],
        test_list=["assert add(2, 3) == 5"],
    )

    assert program.index("def add") > program.index("import math")
    assert program.index("import math") < program.index("assert add")


@pytest.mark.skipif(not DOCKER_READY, reason="Docker image is not available")
def test_run_mbpp_tests_success() -> None:
    """A correct solution must pass its public tests."""
    result = run_mbpp_tests(
        code="def add(a, b):\n    return a + b",
        test_imports=[],
        test_list=["assert add(2, 3) == 5"],
    )

    assert result["success"] is True
    assert result["exit_code"] == 0


@pytest.mark.skipif(not DOCKER_READY, reason="Docker image is not available")
def test_run_mbpp_tests_failure() -> None:
    """A wrong solution must return the assertion failure."""
    result = run_mbpp_tests(
        code="def add(a, b):\n    return 0",
        test_imports=[],
        test_list=["assert add(2, 3) == 5"],
    )

    assert result["success"] is False
    assert "AssertionError" in result["output"]


@pytest.mark.skipif(not DOCKER_READY, reason="Docker image is not available")
def test_run_mbpp_tests_syntax_error() -> None:
    """Invalid Python must return the syntax error without crashing the server."""
    result = run_mbpp_tests(
        code="def add(a, b)\n    return a + b",
        test_imports=[],
        test_list=["assert add(2, 3) == 5"],
    )

    assert result["success"] is False
    assert "SyntaxError" in result["output"]


@pytest.fixture
def docker_client(monkeypatch: pytest.MonkeyPatch) -> Mock:
    """Replace Docker only for the focused error-path regression tests."""
    client = Mock()
    container = client.containers.create.return_value
    container.wait.return_value = {"StatusCode": 0}
    container.logs.return_value = b""
    monkeypatch.setattr("agent_smith.mbpp_tools.docker.from_env", lambda **kwargs: client)
    return client


def test_failure_keeps_stdout_and_reports_truncation(docker_client: Mock) -> None:
    container = docker_client.containers.create.return_value
    container.wait.return_value = {"StatusCode": 1}
    container.logs.return_value = b"progress\n" + b"x" * MAX_OUTPUT_CHARACTERS

    result = run_mbpp_tests("print('progress')", [], [])

    assert result["message"] == "Public tests failed."
    assert result["output"].startswith("progress\n")
    assert "Output truncated: 9 characters were removed" in result["output"]
    container.logs.assert_called_once_with(stdout=True, stderr=True)


@pytest.mark.parametrize("timed_out", [False, True])
def test_debug_keeps_full_docker_output_before_observation_truncation(docker_client, caplog, timed_out):
    container = docker_client.containers.create.return_value
    raw_output = "DOCKER_BEGIN\n" + "x" * MAX_OUTPUT_CHARACTERS + "\nDOCKER_END\n"
    container.logs.return_value = raw_output.encode()
    if timed_out:
        container.wait.side_effect = TimeoutError("known timeout")
    with caplog.at_level(logging.DEBUG, logger="agent_smith.mbpp_tools"):
        result = run_mbpp_tests("print('known output')", [], [])
    assert raw_output in caplog.text
    assert "DOCKER_END" not in result["output"]
    assert "Output truncated" in result["output"]
    assert ("DOCKER SALIDA PARCIAL" in caplog.text) == timed_out
    container.logs.assert_called_once_with(stdout=True, stderr=True)
    container.remove.assert_called_once_with(force=True)


@pytest.mark.parametrize("error_type", [TimeoutError, DockerException])
def test_timeout_keeps_partial_output_and_cleans_up(
    docker_client: Mock, error_type: type[Exception],
) -> None:
    container = docker_client.containers.create.return_value
    container.wait.side_effect = error_type("read timed out")
    container.logs.return_value = b"before timeout\n"

    result = run_mbpp_tests("print('before timeout')", [], [], timeout_seconds=1)

    assert result["success"] is False
    assert result["exit_code"] is None
    assert result["message"] == "Public tests could not complete."
    assert "timed out after 1 seconds" in result["output"]
    assert "Output is partial:\nbefore timeout" in result["output"]
    assert docker_client.containers.create.call_args.kwargs["command"][1] == "-u"
    container.stop.assert_called_once_with(timeout=1)
    container.remove.assert_called_once_with(force=True)
    docker_client.close.assert_called_once_with()
    docker_client.containers.list.assert_not_called()


def test_start_failure_is_not_a_test_failure(docker_client: Mock) -> None:
    container = docker_client.containers.create.return_value
    container.start.side_effect = RuntimeError("cannot start")

    result = run_mbpp_tests("pass", [], [])

    assert result["success"] is False
    assert result["message"] == "Public tests could not start."
    assert result["exit_code"] is None
    container.logs.assert_not_called()
    container.remove.assert_called_once_with(force=True)


def test_timeout_without_message_is_reported(docker_client: Mock) -> None:
    container = docker_client.containers.create.return_value
    container.wait.side_effect = TimeoutError()
    container.logs.return_value = b"before timeout\n"

    result = run_mbpp_tests("print('before timeout')", [], [], timeout_seconds=1)

    assert result["success"] is False
    assert result["exit_code"] is None
    assert "Execution timed out after 1 seconds." in result["output"]
    assert "Output is partial:\nbefore timeout" in result["output"]
    container.remove.assert_called_once_with(force=True)
    docker_client.close.assert_called_once_with()


def test_docker_failure_after_start_is_not_a_start_failure(docker_client: Mock) -> None:
    container = docker_client.containers.create.return_value
    container.wait.side_effect = DockerException("connection lost")
    container.logs.return_value = b"partial progress"

    result = run_mbpp_tests("pass", [], [])

    assert result["message"] == "Public tests could not complete."
    assert "Docker error: connection lost" in result["output"]
    assert "partial progress" in result["output"]


def test_cleanup_errors_are_reported_without_losing_test_error(docker_client: Mock) -> None:
    container = docker_client.containers.create.return_value
    container.wait.return_value = {"StatusCode": 1}
    container.logs.return_value = b"AssertionError"
    container.stop.side_effect = DockerException("stop failed")
    container.remove.side_effect = DockerException("remove failed")
    docker_client.close.side_effect = DockerException("close failed")

    result = run_mbpp_tests("assert False", [], [])

    assert result["success"] is False
    assert result["exit_code"] == 1
    assert "AssertionError" in result["output"]
    assert "Cleanup failed" in result["message"]
    assert all(error in result["output"] for error in (
        "stop failed", "remove failed", "close failed",
    ))
    container.remove.assert_called_once_with(force=True)
    docker_client.containers.list.assert_not_called()


def test_keyboard_interrupt_propagates_after_cleanup(docker_client: Mock) -> None:
    container = docker_client.containers.create.return_value
    container.wait.side_effect = KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        run_mbpp_tests("pass", [], [])

    container.remove.assert_called_once_with(force=True)
    docker_client.close.assert_called_once_with()


def test_task_deadline_stops_before_container_creation(monkeypatch, docker_client):
    monkeypatch.setenv("AGENT_SMITH_DEADLINE", "0")
    result = run_mbpp_tests("pass", [], [])
    assert not result["success"]
    assert "deadline" in result["output"].lower()
    docker_client.containers.create.assert_not_called()


def test_task_deadline_limits_wait(monkeypatch, docker_client):
    import time
    monkeypatch.setenv("AGENT_SMITH_DEADLINE", str(time.monotonic() + 4))
    result = run_mbpp_tests("pass", [], [], timeout_seconds=30)
    assert result["success"]
    assert 0 < docker_client.containers.create.return_value.wait.call_args.kwargs["timeout"] <= 2


def test_creation_response_lost_checks_only_owned_name(docker_client):
    docker_client.containers.create.side_effect = DockerException("connection lost")
    run_mbpp_tests("pass", [], [])
    name = docker_client.containers.create.call_args.kwargs["name"]
    docker_client.containers.get.assert_called_once_with(name)
    docker_client.containers.get.return_value.remove.assert_called_once_with(force=True)
    docker_client.containers.list.assert_not_called()
