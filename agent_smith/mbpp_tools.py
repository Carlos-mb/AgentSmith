"""Helpers used by the MBPP MCP server."""

from typing import Any

import docker
from docker.errors import DockerException, ImageNotFound


DEFAULT_DOCKER_IMAGE = "python:3.10.12-slim"
DEFAULT_TIMEOUT_SECONDS = 10
MAX_OUTPUT_CHARACTERS = 12_000


def build_test_program(
    code: str,
    test_imports: list[str],
    test_list: list[str],
) -> str:
    """Combine a candidate solution with the public MBPP tests."""
    sections = [code.strip()]
    sections.extend(item.strip() for item in test_imports if item.strip())
    sections.extend(item.strip() for item in test_list if item.strip())
    return "\n\n".join(section for section in sections if section) + "\n"


def truncate_output(output: str) -> str:
    """Limit tool output so one failed test does not consume the whole prompt."""
    if len(output) <= MAX_OUTPUT_CHARACTERS:
        return output

    removed = len(output) - MAX_OUTPUT_CHARACTERS
    return (
        output[:MAX_OUTPUT_CHARACTERS]
        + f"\n\n[Output truncated: {removed} characters were removed.]"
    )


def run_mbpp_tests(
    code: str,
    test_imports: list[str],
    test_list: list[str],
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Run a candidate MBPP solution against its public tests in Docker."""
    if not code.strip():
        return {
            "success": False,
            "message": "Public tests were not executed.",
            "output": "The candidate solution is empty.",
            "exit_code": None,
        }

    if timeout_seconds <= 0:
        return {
            "success": False,
            "message": "Public tests were not executed.",
            "output": "timeout_seconds must be greater than zero.",
            "exit_code": None,
        }

    program = build_test_program(code, test_imports, test_list)
    client = None
    container = None

    try:
        client = docker.from_env()
        container = client.containers.create(
            DEFAULT_DOCKER_IMAGE,
            command=["python", "-c", program],
            network_disabled=True,
            mem_limit="128m",
            cpu_period=100_000,
            cpu_quota=50_000,
        )
        container.start()

        wait_result = container.wait(timeout=timeout_seconds)
        exit_code = int(wait_result.get("StatusCode", 1))

        stdout = container.logs(stdout=True, stderr=False).decode(
            "utf-8", errors="replace"
        )
        stderr = container.logs(stdout=False, stderr=True).decode(
            "utf-8", errors="replace"
        )

        output = stderr.strip() if exit_code != 0 else stdout.strip()
        output = truncate_output(output)

        if exit_code == 0:
            return {
                "success": True,
                "message": "All public tests passed.",
                "output": output,
                "exit_code": exit_code,
            }

        return {
            "success": False,
            "message": "Public tests failed.",
            "output": output or "The test process failed without output.",
            "exit_code": exit_code,
        }

    except ImageNotFound:
        return {
            "success": False,
            "message": "Public tests could not start.",
            "output": (
                f"Docker image '{DEFAULT_DOCKER_IMAGE}' was not found. "
                f"Run: docker pull {DEFAULT_DOCKER_IMAGE}"
            ),
            "exit_code": None,
        }
    except DockerException as exc:
        return {
            "success": False,
            "message": "Public tests could not start.",
            "output": f"Docker error: {exc}",
            "exit_code": None,
        }
    except Exception as exc:
        text = str(exc)
        if "timeout" in text.lower() or "timed out" in text.lower():
            output = f"Execution timed out after {timeout_seconds} seconds."
        else:
            output = f"Execution error: {text}"

        return {
            "success": False,
            "message": "Public tests failed.",
            "output": output,
            "exit_code": None,
        }
    finally:
        if container is not None:
            try:
                container.stop(timeout=1)
            except Exception:
                pass
            try:
                container.remove(force=True)
            except Exception:
                pass

        if client is not None:
            try:
                client.close()
            except Exception:
                pass
