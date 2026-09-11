"""Extract Python blocks and describe the pending JSON tool-call conversion."""

import ast


def extract_python_code(llm_output: str) -> tuple[str, str]:
    """Return Python source and extraction feedback without executing it.

    Accept a closed python or py fenced block and check its body with ast.parse.
    Empty responses, missing blocks, missing closing fences, and invalid syntax
    return empty source with a diagnostic. Valid source has empty feedback.
    Raw Python and unlabelled blocks are unsupported; malformed blocks are not
    repaired. An optional <end_code> marker belongs after the closing fence.
    """

    code: str = ""
    feedback: str = ""
    if (llm_output.strip() == ""):
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
            return "", "Python code block is missing its closing fence; not executed."

    if code != "":
        try:
            ast.parse(code)
            feedback = ""
        except SyntaxError as exc:
            code = ""
            feedback = f"Python syntax error on line {exc.lineno}: {exc.msg}"

    return code, feedback


def extract_json_hermes_code(llm_output: str) -> str:
    """Convert complete JSON/Hermes tool calls into Python source.

    Pending implementation. Each <tool_call> payload must contain a string name
    and an arguments object. Return empty source when no call is present and
    raise ValueError for recognized malformed calls. Conversion performs no I/O.
    """
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
    raise NotImplementedError("JSON tool-call extraction is not implemented yet.")


def extract_agent_code(
    llm_output: str, response_format: str = "python"
) -> tuple[str, str]:
    """Select the configured extractor and return source with honest feedback.

    Pending implementation. Python remains the primary format; JSON/Hermes is
    the first planned conversion. Unsupported or malformed formats must return
    an explicit diagnostic, without fallback or automatic repair.
    """
    # Pseudocódigo detallado:
    # 1. Recibir el texto bruto y response_format de la configuración activa.
    #    Con "python", devolver directamente extract_python_code(llm_output);
    #    conservar su código y feedback, sin cambiar el extractor ya útil.
    # 2. Con "json_hermes", llamar extract_json_hermes_code sólo cuando esté
    #    implementado. Hoy sigue pendiente: no capturar NotImplementedError y
    #    transformarlo en código vacío ni anunciar soporte que aún no existe.
    # 3. Para otro valor devolver ("", diagnóstico que nombre el formato no
    #    soportado). No probar una cascada de extractores ni adivinar el modelo.
    # 4. Si el conversor reconoce una llamada inválida y eleva ValueError,
    #    devolver ("", mensaje del error). Si devuelve "", explicar que no se
    #    encontró un bloque JSON/Hermes completo. Nunca devolver éxito ficticio.
    # 5. Con Python convertido, llamar ast.parse. Ante SyntaxError, devolver código
    #    vacío y mensaje/línea del error; no ejecutarlo ni repararlo automáticamente.
    # 6. Devolver (código, "JSON/Hermes tool calls converted to Python.") cuando
    #    todo sea válido. El bucle añade siempre este aviso a la observación real.
    #    No copiar al feedback ninguna Observation propuesta por el modelo.
    raise NotImplementedError("Multi-format code extraction is not implemented yet.")
