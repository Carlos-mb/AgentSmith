"""Regression test for invalid MBPP input before agent execution."""

from agent_mbpp import main as mbpp_main


def test_mbpp_cli_handles_invalid_task_file(tmp_path, capsys):
    """Invalid JSON must report an error without writing a solution file."""
    task_path = tmp_path / "invalid_task.json"
    output_path = tmp_path / "mbpp_solution.json"

    task_path.write_text("not json", encoding="utf-8")

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

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Error: Invalid JSON file" in captured.err
    assert not output_path.exists()
