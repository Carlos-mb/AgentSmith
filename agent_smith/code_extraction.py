"""Extract Python blocks and describe the pending JSON tool-call conversion."""

from agent_smith.logging_config import get_logger

logger = get_logger('agent_smith.code_extraction')

import ast
import json
import re


def extract_python_code(llm_output: str) -> tuple[str, str]:
    """Return Python source and extraction feedback without executing it.

    Accept a closed python or py fenced block and check its body with ast.parse.
    Empty responses, missing blocks, missing closing fences, and invalid syntax
    return empty source with a diagnostic. Valid source has empty feedback.
    Raw Python and unlabelled blocks are unsupported; malformed blocks are not
    repaired. An optional <end_code> marker belongs after the closing fence.
    """
    logger.debug("Entrando en extract_python_code")

    code: str = ""
    feedback: str = ""
    if (llm_output.strip() == ""):
        logger.warning("Extracción rechazada: respuesta vacía")
        feedback = "Model response was empty."
        return code, feedback

    feedback = "No valid Python code was found in the model response."

    code_starts = llm_output.find("```python")
    if (code_starts == -1):
        code_starts = llm_output.find("```py")
        if (code_starts != -1):
            code_starts = code_starts + 5
    else:
        code_starts = code_starts + 9

    if code_starts != -1:
        code_ends = llm_output.find("```", code_starts)
        if (code_ends != -1):
            code = llm_output[code_starts:code_ends].strip()
        else:
            logger.warning("Bloque Python incompleto: falta el cierre; no se ejecutará")
            return "", "Python code block is missing its closing fence; not executed."

    if code != "":
        try:
            ast.parse(code)
            feedback = ""
            logger.debug("Bloque Python completo y sintaxis válida: %s caracteres", len(code))
        except SyntaxError as exc:
            logger.warning("Sintaxis Python inválida en línea %s: %s", exc.lineno, exc.msg)
            code = ""
            feedback = f"Python syntax error on line {exc.lineno}: {exc.msg}"

    if not code:
        logger.warning("No se ha extraído código ejecutable: %s", feedback)
    return code, feedback


def _literal(value: str) -> str:
    """Render an argument value as a Python literal, keeping integers integers."""
    logger.debug("Entrando en _literal")
    text = value.strip()
    if re.fullmatch(r"-?\d+", text):
        return text
    return repr(value)


def convert_tool_calls(llm_output: str) -> str:
    """Convert <tool_call> blocks into the equivalent Python calls.

    The subject asks the extraction layer to fit what the models were trained
    on. The free models used here fall back to this tool-call dialect as soon
    as they have seen a tool result, so converting it is what keeps them
    usable. Returns empty source when the response contains no complete call.
    """
    logger.debug("Entrando en convert_tool_calls")
    calls = re.findall(r"<tool_call>(.*?)</tool_call>", llm_output, re.DOTALL)
    if not calls:
        return ""

    statements = []
    for call in calls:
        body = call.strip()
        name = body.splitlines()[0].strip() if body else ""
        if not name.isidentifier():
            raise ValueError(f"Tool call without a usable name: {name!r}")

        # Los marcadores <arg_value> y </arg_value> se tratan como opcionales a
        # proposito: con valores largos los modelos se dejan uno de los dos, y
        # antes perdiamos la iteracion entera. El valor es lo que hay tras la
        # clave, hasta la siguiente clave o el fin de la llamada.
        arguments = []
        for chunk in re.split(r"<arg_key>", body)[1:]:
            key, separator, rest = chunk.partition("</arg_key>")
            if not separator:
                raise ValueError(f"Tool call {name} has an argument name that is never closed.")
            key = key.strip()
            if not key.isidentifier():
                raise ValueError(f"Tool call {name} has an unusable argument name: {key!r}")

            opened = "<arg_value>" in rest
            value = rest.split("<arg_value>", 1)[1] if opened else rest
            closed = "</arg_value>" in value
            if closed:
                value = value.rsplit("</arg_value>", 1)[0]
            if not (opened and closed):
                # Falta un marcador: los saltos que lo rodeaban no son del valor.
                value = value.strip()
            arguments.append(f"{key}={_literal(value)}")

        logger.info("Convertida una llamada en formato tool_call: %s", name)
        statements.append(f"print({name}({', '.join(arguments)}))")

    return "\n".join(statements)


def convert_tool_use(llm_output: str) -> str:
    """Convert <tool_use> blocks with JSON arguments into Python calls.

    Un tercer dialecto observado en vivo. En esa ejecución el modelo diagnosticó
    bien el bug y escribió la edición correcta, pero en este formato, y no se
    ejecutó nada en 23 de 29 iteraciones. El nombre del servidor se ignora: la
    herramienta ya es una función local del sandbox.
    """
    logger.debug("Entrando en convert_tool_use")
    statements = []
    for block in re.findall(r"<tool_use>(.*?)</tool_use>", llm_output, re.DOTALL):
        found = re.search(r"<tool_name>(.*?)</tool_name>", block, re.DOTALL)
        name = found.group(1).strip() if found else ""
        if not name.isidentifier():
            raise ValueError(f"Tool use without a usable name: {name!r}")

        found = re.search(r"<arguments>(.*?)</arguments>", block, re.DOTALL)
        try:
            arguments = json.loads(found.group(1).strip() or "{}") if found else {}
        except ValueError as exc:
            raise ValueError(f"Tool use {name} has invalid JSON arguments: {exc}")
        if not isinstance(arguments, dict):
            raise ValueError(f"Tool use {name} did not pass an object of arguments.")

        rendered = []
        for key, value in arguments.items():
            if not key.isidentifier():
                raise ValueError(f"Tool use {name} has an unusable argument name: {key!r}")
            rendered.append(f"{key}={value!r}")

        logger.info("Convertida una llamada en formato tool_use: %s", name)
        statements.append(f"print({name}({', '.join(rendered)}))")

    return "\n".join(statements)


CONVERTED_TOOL_CALL_FEEDBACK = (
    "No ```python block was found; the tool call was converted to Python and executed."
)


def extract_agent_code(llm_output: str) -> tuple[str, str]:
    """Return executable Python from a fenced block, or from tool calls."""
    logger.debug("Entrando en extract_agent_code")
    code, feedback = extract_python_code(llm_output)
    if code:
        return code, feedback

    for convertir in (convert_tool_calls, convert_tool_use):
        try:
            converted = convertir(llm_output)
        except ValueError as exc:
            logger.warning("Llamada de herramienta malformada: %s", exc)
            return "", f"Malformed tool call: {exc}"
        if converted:
            # La hoja exige avisar cuando un bloque mal formado se interpreta igual.
            return converted, CONVERTED_TOOL_CALL_FEEDBACK
    return code, feedback
