"""Helpers used by the MBPP MCP server."""

import sys
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

    sections = []
    sections.extend(item.strip() for item in test_imports if item.strip())
    sections.append(code.strip())
    sections.extend(item.strip() for item in test_list if item.strip())
    return "\n\n".join(section for section in sections if section) + "\n"


def truncate_output(output: str) -> str:
    """Limit tool output so one failed test does
    not consume the whole prompt."""
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
    """Run public MBPP tests in Docker and report execution and cleanup failures.

    The per-test wait timeout is implemented. End-to-end task deadline handling
    during creation, startup, logs, and cleanup remains pending integration.
    """
    # Pendiente al conectar el agente: leer AGENT_SMITH_DEADLINE sólo en el
    # servidor de confianza. Acotar creación, arranque, wait y lectura de logs
    # por el tiempo total restante, reservando tiempo para detener/eliminar el
    # contenedor propio. Un wait timeout por sí solo no cubre toda la operación.
    # Al cancelar MCP, terminar también la ejecución Docker y conservar logs.
    # No compartir un presupuesto mutable con el bucle. Los tests Docker no
    # sustituyen los controles del trabajador que ejecuta Python del modelo.
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
    started = False
    result = None

    try:
        client = docker.from_env()
        container = client.containers.create(
            DEFAULT_DOCKER_IMAGE,
            command=["python", "-u", "-c", program],
            network_disabled=True,
            mem_limit="128m",
            cpu_period=100_000,
            cpu_quota=50_000,
        )
        container.start()
        started = True

        wait_result = container.wait(timeout=timeout_seconds)
        exit_code = int(wait_result.get("StatusCode", 1))

        output = container.logs(stdout=True, stderr=True).decode(
            "utf-8", errors="replace"
        )
        output = truncate_output(output.strip())

        if exit_code == 0:
            result = {
                "success": True,
                "message": "All public tests passed.",
                "output": output,
                "exit_code": exit_code,
            }

        else:
            result = {
                "success": False,
                "message": "Public tests failed.",
                "output": output or "The test process failed without output.",
                "exit_code": exit_code,
            }

    except ImageNotFound:
        result = {
            "success": False,
            "message": "Public tests could not start.",
            "output": (
                f"Docker image '{DEFAULT_DOCKER_IMAGE}' was not found. "
                f"Run: docker pull {DEFAULT_DOCKER_IMAGE}"
            ),
            "exit_code": None,
        }
    except Exception as exc:
        text = str(exc)
        if started and (
            isinstance(exc, TimeoutError)
            or "timeout" in text.lower() or "timed out" in text.lower()
        ):
            output = f"Execution timed out after {timeout_seconds} seconds."
        else:
            kind = "Docker" if isinstance(exc, DockerException) else "Execution"
            output = f"{kind} error: {text}"

        if started:
            try:
                partial = container.logs(stdout=True, stderr=True).decode(
                    "utf-8", errors="replace"
                )
                output += "\nOutput is partial:\n" + truncate_output(partial.strip())
            except Exception as log_error:
                output += f"\nCould not read partial output: {log_error}"

        result = {
            "success": False,
            "message": (
                "Public tests could not complete."
                if started else "Public tests could not start."
            ),
            "output": output,
            "exit_code": None,
        }
    finally:
        cleanup_errors = []
        if container is not None:
            try:
                container.stop(timeout=1)
            except Exception as exc:
                cleanup_errors.append(f"Could not stop the test container: {exc}")
            try:
                container.remove(force=True)
            except Exception as exc:
                cleanup_errors.append(f"Could not remove the test container: {exc}")

        if client is not None:
            try:
                client.close()
            except Exception as exc:
                cleanup_errors.append(f"Could not close the Docker client: {exc}")

        if cleanup_errors:
            cleanup_message = "Cleanup failed:\n" + "\n".join(cleanup_errors)
            if result is None:
                # Keep KeyboardInterrupt/SystemExit propagating after cleanup.
                print(cleanup_message, file=sys.stderr)
            else:
                result["success"] = False
                result["message"] += " Cleanup failed."
                result["output"] += "\n" + cleanup_message

    return result
