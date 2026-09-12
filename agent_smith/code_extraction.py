"""Extract Python blocks and describe the pending JSON tool-call conversion."""

from agent_smith.logging_config import get_logger

logger = get_logger('agent_smith.code_extraction')

import ast


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


def extract_json_hermes_code(llm_output: str) -> str:
    """Convert complete JSON/Hermes tool calls into Python source.

    Pending implementation. Each <tool_call> payload must contain a string name
    and an arguments object. Return empty source when no call is present and
    raise ValueError for recognized malformed calls. Conversion performs no I/O.
    """
    logger.debug("Entrando en extract_json_hermes_code")
    # Pseudocódigo detallado:
    # 1. Buscar bloques completos <tool_call>...</tool_call> en el texto recibido,
    #    conservando su orden. Es el único formato no Python previsto inicialmente;
    #    no añadir XML/ReAct hasta que los modelos utilizados lo necesiten.
    # 2. Si no aparece ninguna apertura ni cierre, devolver "". Si aparece una
    #    etiqueta incompleta, un cierre suelto o anidamiento, elevar ValueError con
    #    un diagnóstico concreto. No inventar el cierre ni reparar el contenido.
    #    El stop configurado debe ir después del cierre, nunca retirarlo.
    # 3. Extraer el texto de cada bloque y decodificarlo con json.loads. Rechazar
    #    JSON inválido, valores no finitos y una raíz que no sea objeto. No usar
    #    eval, exec, pickle ni ejecutar valores para averiguar qué significan.
    # 4. Leer name y arguments. Exigir name string no vacío; arguments debe ser un
    #    objeto con claves string. Conservar sus valores JSON (null -> None,
    #    true/false -> bool, números, texto, listas y objetos). No comprobar aquí
    #    parámetros obligatorios ni tipos del esquema MCP: lo harán SDK/servidor.
    # 5. Convertir name y arguments a literales Python con repr. Para una
    #    herramienta emitir print(mcp_call_tool(<literal name>, <literal args>)).
    #    Así nombres con guiones o iguales a un builtin siguen siendo accesibles
    #    y el resultado real llega a stdout; no insertar name como código Python.
    # 6. Reservar el nombre final_answer para la función local: exigir únicamente
    #    arguments={"answer": texto} y emitir final_answer(<literal del texto>).
    #    No convertirlo en llamada MCP ni permitir llamadas posteriores a esa
    #    entrega dentro del mismo bloque de respuesta.
    # 7. Unir las instrucciones con saltos de línea; devolver sólo código, sin
    #    delimitadores Markdown ni observaciones inventadas. No contactar al MCP
    #    durante la conversión y no ejecutar el resultado aquí.
    # 8. Si falla una llamada reconocida, rechazar la respuesta completa con
    #    ValueError, sin ejecutar un prefijo válido. El selector añade el feedback
    #    y ast.parse; el bucle enviará el Python al sandbox cuando corresponda.
    logger.warning("Funcionalidad pendiente; se mantiene NotImplementedError")
    raise NotImplementedError("JSON tool-call extraction is not implemented yet.")


def extract_agent_code(
    llm_output: str, response_format: str = "python"
) -> tuple[str, str]:
    """Use the implemented Python extractor; report other formats explicitly."""
    logger.debug("Entrando en extract_agent_code")
    if response_format == "python":
        return extract_python_code(llm_output)
    logger.warning("Funcionalidad pendiente; se mantiene NotImplementedError")
    raise NotImplementedError(f"Response format is not implemented: {response_format}")
