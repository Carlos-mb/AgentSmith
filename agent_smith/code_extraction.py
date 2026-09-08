"""Extracción Python actual y conversores pendientes según los modelos elegidos."""

import ast


def extract_python_code(llm_output: str) -> tuple[str, str]:
    """Recibe texto del modelo y devuelve (codigo, diagnostico).

    Formato principal: un bloque cerrado ```python ... ```; también se acepta
    la etiqueta py ya existente. El marcador <end_code> va DESPUÉS del cierre:
    la API puede retirarlo como stop sin romper el bloque. No usar ``` como stop.
    Se busca el bloque, se extrae su cuerpo y se comprueba con ast.parse, sin
    ejecutarlo. Una respuesta vacía, un bloque ausente o sin cierre y una sintaxis
    inválida devuelven código vacío con un diagnóstico distinto. Una extracción
    correcta devuelve diagnóstico vacío. No se reparan ni recuperan bloques.
    Python sin etiqueta o sin bloque no forma parte del soporte actual.
    No crea recursos que haya que cerrar.
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


def extract_xml_code(llm_output: str) -> str:
    """Pendiente; implementar sólo si un modelo elegido necesita este XML.

    1. Recibir la respuesta de ese modelo y documentar su formato real. XML es
       un ejemplo del subject, no otro formato obligatorio por sí mismo.
    2. Leer invoke y parameter con ElementTree; rechazar DTD y entidades,
       nombres no identificadores públicos Python y parámetros repetidos.
    3. Convertir valores a tipos básicos conforme al formato documentado del
       modelo; no adivinar tipos con eval. Serializarlos con repr para emitir
       print(herramienta(**argumentos)): el resultado real debe llegar a stdout
       y desde allí a la observación. Sólo asignarlo a result no basta.
    4. Devolver código o "" si no es este formato; lanzar ValueError con
       diagnóstico si el formato reconocido es inválido. No abre recursos.
    """
    raise NotImplementedError("XML tool-call extraction is not implemented yet.")


def extract_json_hermes_code(llm_output: str) -> str:
    """Pendiente; implementar sólo si un modelo elegido necesita JSON/Hermes.

    1. Recibir texto y localizar los payloads tool_call documentados para ese
       modelo. Decodificarlos con json.loads, nunca eval.
    2. Exigir name identificador Python público y arguments objeto con claves
       string; representar los valores básicos mediante repr.
    3. Emitir print(herramienta(**argumentos)) por llamada para que el resultado
       real pase a la observación del sandbox.
    4. Devolver código o "" si no es este formato; si está mal formado, propagar
       ValueError al extractor común. No abre recursos. Si el proveedor retira
       </tool_call> al usarlo como stop, definir su recuperación con feedback
       antes de activar ese stop; no declarar que ya está soportado.
    """
    raise NotImplementedError("JSON tool-call extraction is not implemented yet.")


def extract_react_code(llm_output: str) -> str:
    """Pendiente; implementar sólo si un modelo elegido necesita ReAct.

    1. Recibir texto y leer Action / Action Input conforme al formato comprobado
       del modelo; no usar una Observation inventada por el modelo como real.
    2. Exigir nombre identificador público y argumentos JSON objeto; no añadir
       fallback automático a texto libre ni ejecutar valores para interpretarlos.
    3. Emitir print(herramienta(**argumentos)) usando repr para los literales.
    4. Devolver código o "" si el formato está ausente; lanzar ValueError si se
       reconoce pero es inválido. El llamante explica el error. Sin recursos.
    """
    raise NotImplementedError("ReAct tool-call extraction is not implemented yet.")


def extract_agent_code(
    llm_output: str, response_format: str = "python"
) -> tuple[str, str]:
    """Pendiente: seleccionar el formato configurado, sin cascada de intentos.

    1. Recibir respuesta y response_format del proveedor seleccionado. Para
       python devolver extract_python_code(llm_output), conservando su feedback.
    2. Añadir mediante if/elif sólo los conversores necesarios para los modelos
       que se comparen. XML, JSON/Hermes y ReAct anteriores son candidatos
       pendientes, no tres entregables independientes. No anunciar compatibilidad
       multiformato hasta implementar y probar los formatos realmente utilizados.
    3. Rechazar formatos sin soporte con ("", diagnóstico). Para uno soportado,
       convertir y validar el Python con ast.parse, nunca ejecutarlo aquí.
    4. Devolver (código, aviso del formato convertido y de cualquier recuperación
       expresamente soportada), o ("", diagnóstico de ValueError/SyntaxError).
       El bucle añade siempre el aviso a la observación. No abre recursos.
    """
    raise NotImplementedError("Multi-format code extraction is not implemented yet.")
