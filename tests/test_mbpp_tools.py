"""Tests for the MBPP test execution helper."""

import docker
import pytest
from docker.errors import DockerException, ImageNotFound

from agent_smith.mbpp_tools import (
    DEFAULT_DOCKER_IMAGE,
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
    """The helper must put the solution before imports and assertions."""
    program = build_test_program(
        code="def add(a, b):\n    return a + b",
        test_imports=["import math"],
        test_list=["assert add(2, 3) == 5"],
    )

    assert program.index("def add") < program.index("import math")
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
