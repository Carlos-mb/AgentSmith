"""JSON input and output helpers for Pydantic models."""

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError


def read_json_file(path: str | Path) -> dict[str, Any]:
    """Read a JSON object from a file."""
    file_path = Path(path)

    try:
        with file_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError as exc:
        raise RuntimeError(f"Input file not found: {file_path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON file: {file_path}: {exc}") from exc
    except OSError as exc:
        raise RuntimeError(f"Could not read input file: {file_path}: {exc}") \
            from exc

    if not isinstance(data, dict):
        raise RuntimeError(f"Expected a JSON object in: {file_path}")

    return data


def load_model(path: str, model_class: type[BaseModel]) -> BaseModel:
    """Read JSON data and validate it with a Pydantic model."""
    data = read_json_file(path)

    try:
        return model_class.model_validate(data)
    except ValidationError as exc:
        raise RuntimeError(
            f"Invalid {model_class.__name__} in {path}: {exc}"
        ) from exc


def write_model(path: str | Path, model: BaseModel) -> None:
    """Write a Pydantic model to a formatted JSON file."""
    file_path = Path(path)

    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            model.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise RuntimeError(f"Could not write output file: {file_path}: {exc}") \
             from exc
