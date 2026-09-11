"""One pending asynchronous Thought -> Code -> Observation loop for both tasks."""

from __future__ import annotations

from agent_smith.models import AgentLimits, SolutionOutput
from agent_smith.providers import ProviderClient
from agent_smith.sandbox import SandboxExecution, SandboxSession


def build_observation(
    execution: SandboxExecution | None,
    extraction_feedback: str,
) -> str:
    """Build the observation returned to the LLM."""

    if execution is None:
        return extraction_feedback

    parts = []

    if extraction_feedback:
        parts.append(extraction_feedback)

    if execution.output:
        parts.append(execution.output)

    if execution.error:
        parts.append("Error: " + execution.error)

    if execution.timed_out:
        parts.append(
            "Timeout. Execution timed out. Output may be partial."
        )

    if execution.final_answer is not None:
        parts.append("Final answer:\n" + execution.final_answer)

    return "\n".join(parts)


async def run_agent_loop(
    *,
    task_id: str,
    benchmark: str,
    system_prompt: str,
    task_prompt: str,
    provider: ProviderClient,
    sandbox: SandboxSession,
    limits: AgentLimits,
    started_at: float,
) -> SolutionOutput:
    """Run one sequential task and preserve real observations and partial metrics.

    The caller supplies open resources and the task's original monotonic start
    time. This pending loop owns its counters and borrows the provider and sandbox.
    The benchmark adapter closes resources and updates the final elapsed time.
    """
    # 1. Calcular deadline=started_at+limits.max_time_seconds. No iniciar otro reloj:
    #    started_at viene del CLI, antes de cargar la tarea o configurar conexiones.
    #    Crear messages con system_prompt como system y task_prompt como user.
    # 2. Crear variables locales: steps=[], total_requests=0, entrada_total=0,
    #    salida_total=0, uso_completo=True, solucion="", error=None y success=False.
    #    Son del bucle: no compartir un diccionario mutable con el proveedor.
    # 3. Antes de cada iteración comprobar el tiempo, len(steps) y tokens acumulados.
    #    Si se ha alcanzado max_iterations o no quedan tokens, terminar con error.
    #    Si cualquier petición anterior dejó usage incompleto, no pedir otra.
    # 4. Calcular entrada_restante y salida_restante restando esos totales a limits.
    #    Esperar await provider.complete(messages, max_input_tokens=...,
    #    max_output_tokens=..., deadline=deadline). No iniciar otra generación en
    #    paralelo. El proveedor verifica cada reintento con esos valores restantes.
    # 5. La respuesta de complete agrupa TODOS los intentos de esta iteración.
    #    Añadir request_count, input_tokens y output_tokens a los totales UNA vez.
    #    Actualizar uso_completo con su indicador. No volver a sumar al crear steps
    #    ni leer un contador mutable dentro del proveedor.
    # 6. Si request_count=0, guardar el error de preparación/límite y salir sin crear
    #    un paso ficticio. Si hubo envío, crear un StepMetrics numerado len(steps)+1:
    #    copiar tokens, latencia, URL/modelo, llm_output=text y retries; empezar con
    #    sandbox_input="" y sandbox_output="" porque aún no se ha ejecutado nada.
    #    Añadirlo a steps inmediatamente para conservarlo si la fase siguiente falla.
    # 7. Si completion.error existe, poner el error real en sandbox_output y terminar.
    #    Si faltan tokens, aclarar en ese paso y en el error final que los totales son
    #    sólo subtotales conocidos. No presentar un cero de relleno como medición.
    #    También detenerse si el tiempo o los tokens reales excedieron el presupuesto;
    #    conservar las cifras medidas enteras, sin recortarlas al límite.
    # 8. Extraer código con extract_agent_code(completion.text,
    #    response_format=provider.config.response_format). Desempaquetar la tupla
    #    recibida como code, feedback; no acceder a atributos del resultado.
    #    Un formato pendiente debe dar un error honesto, nunca Python inventado.
    # 9. Sin código válido: execution=None y observación=build_observation(None,
    #    feedback). No llamar al trabajador. Esta iteración sí consume tokens y paso.
    #    Con código: guardar el texto extraído íntegro en step.sandbox_input y llamar
    #    await sandbox.execute(code, deadline=deadline) una sola vez. Las variables
    #    del trabajador continúan del paso anterior. No repetir bloques para repararlas.
    # 10. Construir observación con build_observation(execution, feedback) y guardarla
    #     en step.sandbox_output. Incluye stdout/stderr parciales, errores y timeout.
    #     No sustituir una salida vacía por un resultado esperado o tests inventados.
    # 11. Añadir al historial la respuesta original como assistant y la observación
    #     real como user. Mantener su orden Thought -> Code -> Observation. La petición
    #     siguiente volverá a contar todo este historial como entrada.
    # 12. Si execution no es None y trae final_answer, guardar ya el texto íntegro
    #     en solucion para conservarlo también si falla una comprobación posterior.
    #     Tras ejecutar, comprobar tiempo/tokens otra vez. Un límite agotado EXACTAMENTE
    #     puede permitir finalizar el último paso válido; superarlo impide éxito.
    #     No declarar error por len(steps)==max_iterations antes de examinar la
    #     respuesta final de ese paso, pero tampoco iniciar un paso adicional.
    # 13. Sólo si execution no es None, comprobar worker_failed; si es True,
    #     guardar fallo y terminar. Conservar su
    #     salida parcial: el trabajador perdido no se reinicia para recuperar variables.
    #     Un error ordinario del código o timeout no fatal se devuelve al modelo como
    #     observación para la siguiente iteración, si queda presupuesto.
    # 14. Si execution no es None y execution.final_answer no es None, examinar
    #     la respuesta final ya conservada en solucion.
    #     Aceptar success=True sólo sin error de ejecución, consumo desconocido,
    #     timeout o exceso de presupuesto. final_answer es local, nunca llamada MCP.
    #     Este éxito significa que el agente finalizó; los tests del evaluador deciden
    #     si la solución resuelve la tarea. No truncar ni reformatear código o patch.
    # 15. Capturar errores ordinarios de extracción o ejecución: conservar el paso
    #     abierto y explicar el fallo, sin otra llamada LLM para redactarlo. Terminar
    #     con resultado parcial. No convertir KeyboardInterrupt/SystemExit en éxito;
    #     el finally del adaptador libera recursos si la interrupción se propaga.
    # 16. Crear un único SolutionOutput al terminar: copiar IDs, benchmark, prompt
    #     completo, solucion, success, error y steps; iterations=len(steps), contadores
    #     locales y tiempo monotonic()-started_at. En fallo conservar la solución
    #     parcial real, si llegó, sin fabricar un patch o una respuesta alternativa.
    #     Si usage es incompleto, success=False y error debe decirlo expresamente.
    # 17. Devolver el resultado sin cerrar recursos prestados. El adaptador cerrará
    #     sandbox/MCP y, en SWE-bench, Docker; después actualizará tiempo y fallos de
    #     cierre. No reejecutar la tarea ni poner métricas a cero tras un fallo.
    raise NotImplementedError("The agent loop is not implemented yet.")
