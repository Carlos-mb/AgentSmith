"""Tests for the MBPP and SWE-bench command-line programs."""

import json

from agent_mbpp import main as mbpp_main
from agent_smith.io import load_model
from agent_smith.models import SolutionOutput
from agent_swebench import main as swebench_main


def test_mbpp_cli_writes_valid_solution_output(tmp_path):
    task_path = tmp_path / "mbpp_task.json"
    output_path = tmp_path / "mbpp_solution.json"
    task_path.write_text(
        json.dumps(
            {
                "task_id": 2,
                "task_definition": "Return the common elements.",
                "function_definition": "def similar_elements(a, b):",
                "test_imports": [],
                "test_list": [],
            }
        ),
        encoding="utf-8",
    )

    exit_code = mbpp_main(
        [
            "--task-file",
            str(task_path),
            "--output",
            str(output_path),
            "--model-name",
            "test-model",
            "--provider-url",
            "https://example.invalid/v1",
        ]
    )

    result = load_model(output_path, SolutionOutput)

    assert exit_code == 0
    assert result.task_id == "2"
    assert result.benchmark == "mbpp"
    assert result.success is False


def test_swebench_cli_writes_valid_solution_output(tmp_path):
    task_path = tmp_path / "swebench_task.json"
    output_path = tmp_path / "swebench_solution.json"
    task_path.write_text(
        json.dumps(
            {
                "instance_id": "sympy__sympy-23534",
                "problem_statement": "Fix the reported issue.",
                "docker_image": "example/image:latest",
                "eval_script": "pytest",
                "hints_text": "",
                "repo": "sympy/sympy",
            }
        ),
        encoding="utf-8",
    )

    exit_code = swebench_main(
        [
            "--task-file",
            str(task_path),
            "--output",
            str(output_path),
            "--model-name",
            "test-model",
            "--provider-url",
            "https://example.invalid/v1",
        ]
    )

    result = load_model(output_path, SolutionOutput)

    assert exit_code == 0
    assert result.task_id == "sympy__sympy-23534"
    assert result.benchmark == "swebench"
    assert result.success is False
