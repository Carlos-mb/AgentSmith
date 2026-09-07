"""Tests for JSON input and output helpers."""

import json

import pytest

from agent_smith.io import load_model, read_json_file, write_model
from agent_smith.models import MBPPTaskInput


def test_read_json_file_returns_dictionary(tmp_path):
    input_path = tmp_path / "task.json"
    input_path.write_text('{"task_id": 1}', encoding="utf-8")

    assert read_json_file(input_path) == {"task_id": 1}


def test_read_json_file_rejects_missing_file(tmp_path):
    input_path = tmp_path / "missing.json"

    with pytest.raises(RuntimeError, match="Input file not found"):
        read_json_file(input_path)


def test_read_json_file_rejects_invalid_json(tmp_path):
    input_path = tmp_path / "task.json"
    input_path.write_text("not json", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Invalid JSON file"):
        read_json_file(input_path)


def test_read_json_file_rejects_json_array(tmp_path):
    input_path = tmp_path / "task.json"
    input_path.write_text("[]", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Expected a JSON object"):
        read_json_file(input_path)


def test_load_model_rejects_missing_required_field(tmp_path):
    input_path = tmp_path / "task.json"
    task_data = {
        "task_id": 2,
        "function_definition": "def similar_elements(a, b):",
        "test_imports": [],
        "test_list": [],
    }
    input_path.write_text(json.dumps(task_data), encoding="utf-8")

    with pytest.raises(RuntimeError, match="Invalid MBPPTaskInput"):
        load_model(input_path, MBPPTaskInput)


def test_load_and_write_model(tmp_path):
    task_path = tmp_path / "task.json"
    output_path = tmp_path / "output" / "task.json"
    task_data = {
        "task_id": 2,
        "task_definition": "Return the common elements.",
        "function_definition": "def similar_elements(a, b):",
        "test_imports": [],
        "test_list": ["assert similar_elements((1,), (1,)) == (1,)"],
    }
    task_path.write_text(json.dumps(task_data), encoding="utf-8")

    task = load_model(task_path, MBPPTaskInput)
    write_model(output_path, task)
    reloaded_task = load_model(output_path, MBPPTaskInput)

    assert reloaded_task == task
