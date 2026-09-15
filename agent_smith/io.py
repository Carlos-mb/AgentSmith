"""JSON input and output helpers for Pydantic models."""

from agent_smith.logging_config import get_logger

import json
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

logger = get_logger('agent_smith.io')


ModelType = TypeVar("ModelType", bound=BaseModel)


def read_json_file(path: str | Path) -> Any:
    """Read JSON data from a file."""
    logger.debug("Entrando en read_json_file")
    file_path = Path(path)
    logger.debug("Leyendo JSON: %s", file_path)

    try:
        with file_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError as exc:
        logger.error("No existe el archivo de entrada: %s", file_path)
        raise RuntimeError(f"Input file not found: {file_path}") from exc
    except json.JSONDecodeError as exc:
        logger.error("JSON inválido en %s, línea %s", file_path, exc.lineno)
        raise RuntimeError(f"Invalid JSON file: {file_path}: {exc}") from exc
    except UnicodeDecodeError as exc:
        logger.error("El archivo no es UTF-8: %s", file_path)
        raise RuntimeError(
            f"Input file is not valid UTF-8: {file_path}"
        ) from exc
    except OSError as exc:
        logger.error("Fallo de lectura %s: %s", file_path, type(exc).__name__)
        raise RuntimeError(f"Could not read input file: {file_path}: {exc}") \
            from exc

    logger.debug("JSON leído correctamente: %s", file_path)
    return data


def load_model(
    path: str | Path,
    model_class: type[ModelType],
) -> ModelType:
    """Read JSON data and validate it with a Pydantic model."""
    logger.debug("Entrando en load_model")
    data = read_json_file(path)

    try:
        model = model_class.model_validate(data)
        logger.debug("Validación %s correcta", model_class.__name__)
        return model
    except ValidationError as exc:
        logger.error("Datos incompatibles con %s: %s",
                     model_class.__name__, path)
        raise RuntimeError(
            f"Invalid {model_class.__name__} in {path}: {exc}"
        ) from exc


def write_model(path: str | Path, model: BaseModel) -> None:
    """Write a Pydantic model to a formatted JSON file."""
    logger.debug("Entrando en write_model")
    file_path = Path(path)
    logger.debug("Escribiendo %s en %s", type(model).__name__, file_path)

    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            model.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        logger.error("Fallo de escritura %s: %s",
                     file_path, type(exc).__name__)
        raise RuntimeError(
            f"Could not write output file: {file_path}: {exc}"
        ) from exc
    logger.debug("Archivo de resultado escrito correctamente: %s", file_path)
