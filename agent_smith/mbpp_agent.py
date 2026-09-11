"""Describe the pending MBPP adapter around the shared asynchronous loop."""

from __future__ import annotations

import argparse

from agent_smith.models import AgentLimits, MBPPTaskInput, SolutionOutput


def build_mbpp_system_prompt(
    mcp_manual: str, *, response_format: str = "python",
) -> str:
    """Build an English MBPP instruction prompt using the discovered MCP manual."""
    # 1. Empezar indicando que el agente resuelve la tarea mediante el ciclo
    #    Thought -> Code -> Observation. No conoce observaciones antes de ejecutar.
    # 2. Explicar que las variables Python persisten entre bloques y que print
    #    permite observar resultados. Añadir el texto completo de mcp_manual.
    # 3. Pedir una implementación que respete firma, imports y tests suministrados.
    #    Incluir un ejemplo breve: guardar código de solución en una variable,
    #    llamar run_tests con los argumentos de su firma real y mostrar con print.
    # 4. En el ejemplo, esperar la observación antes de corregir o finalizar. Cuando
    #    se hayan comprobado los tests públicos, llamar final_answer(solution_code).
    #    Explicar que es una función local del sandbox, nunca una herramienta MCP.
    # 5. Para response_format="python", pedir bloque ```python cerrado con ``` y
    #    después <end_code>. No poner el stop antes del cierre del bloque.
    #    Para otro formato, describir sólo la conversión realmente implementada;
    #    si sigue pendiente, dar error al construir el prompt, no prometer soporte.
    # 6. Prohibir buscar soluciones externas o afirmar que se han ejecutado tests
    #    sin observarlos. Los tests públicos no garantizan superar los ocultos.
    # 7. Devolver una sola cadena en inglés. No abrir MCP ni ejecutar el ejemplo:
    #    aquí se redactan instrucciones, no se hace una iteración del agente.
    raise NotImplementedError("The MBPP system prompt is not implemented yet.")


def build_mbpp_task_prompt(task: MBPPTaskInput) -> str:
    """Format the supplied MBPP definition, signature, imports, and public tests."""
    # 1. Incluir task.task_id para identificar la tarea y task.task_definition
    #    completo. No elegir soluciones predefinidas según el ID.
    # 2. Incluir task.function_definition literalmente: el modelo debe conservar
    #    nombre y argumentos de esa firma en el código entregado.
    # 3. Añadir dos apartados delimitados con task.test_imports y task.test_list,
    #    una entrada por línea. Son datos recibidos, no tests ocultos inventados.
    # 4. Si alguna lista está vacía, indicarlo como dato, sin fabricar comprobaciones
    #    que parezcan parte del benchmark. Pedir una solución general para la tarea.
    # 5. Devolver texto en inglés; no importar ni ejecutar nada de esos campos aquí.
    raise NotImplementedError("The MBPP task prompt is not implemented yet.")


def _build_mbpp_limits(max_iterations: int) -> AgentLimits:
    """Return the MBPP cumulative limits with the requested iteration ceiling."""
    # 1. Si max_iterations <= 0, elevar ValueError con un mensaje comprensible.
    # 2. Crear AgentLimits con max_iterations=min(max_iterations, 10),
    #    max_input_tokens=6000, max_output_tokens=1500 y max_time_seconds=120.
    # 3. Devolver ese modelo sin modificar argumentos ni crear un presupuesto global.
    #    Fuente: subject VI.1.1 y MetricsLimits.mbpp_defaults de la moulinette local.
    #    Su README muestra límites antiguos; no cambiar el código de la moulinette.
    raise NotImplementedError("MBPP limit construction is not implemented yet.")


async def run_mbpp_agent(
    task: MBPPTaskInput,
    args: argparse.Namespace,
    *,
    started_at: float,
) -> SolutionOutput:
    """Prepare MBPP resources, await the shared loop, and close owned resources."""
    # 1. Crear limits con _build_mbpp_limits(args.max_iterations) y calcular
    #    deadline=started_at+limits.max_time_seconds. Este tiempo incluye JSON, API,
    #    MCP, Docker de tests, ejecución del trabajador y cierre; no reiniciarlo.
    # 2. Preparar referencias client=None, sandbox=None y result=None para saber
    #    qué recursos requieren cierre aunque falle su arranque. Preparar también
    #    system_prompt="" hasta construirlo, sin inventar un prompt de una ejecución.
    # 3. Dentro de try, crear ProviderClient.from_environment con provider_url,
    #    model_name y AGENT_SMITH_MODELS_CONFIG como config_path opcional.
    #    Usar load_sandbox_config con AGENT_SMITH_SANDBOX_CONFIG si está definido,
    #    o None para los defaults; reutilizar así las comprobaciones de límites.
    # 4. Crear MCPClient(stdio_command=[sys.executable, ruta de mcp_tools_mbpp.py],
    #    environment=entorno_mcp). Resolver la ruta desde el proyecto, no desde cwd.
    #    entorno_mcp incluye AGENT_SMITH_DEADLINE y lo necesario para Python/Docker;
    #    no copiar os.environ entero ni transferir claves del proveedor al servidor.
    # 5. Hacer session, manual = await client.start(deadline=deadline). Comprobar que
    #    run_tests esté en manual.tools; usar descubrimiento real, no una lista que
    #    simule respuesta del servidor. Mantener apertura/uso/cierre MCP en ESTA tarea.
    # 6. Crear SandboxSession(config, mcp_session=session, manual=manual) y esperar
    #    await sandbox.start(). Acotar preparación/bucle mediante anyio.fail_after
    #    alrededor de sus awaits en la misma tarea. No usar wait_for para
    #    client.start/close ni el adaptador: movería contextos MCP a otra tarea.
    # 7. Construir system_prompt con manual.as_text() y provider.config.response_format;
    #    construir task_prompt con la tarea recibida. Si falta tiempo tras preparar,
    #    terminar con error sin llamar al modelo.
    # 8. Esperar run_agent_loop(task_id=str(task.task_id), benchmark="mbpp",
    #    system_prompt=..., task_prompt=..., provider=provider, sandbox=sandbox,
    #    limits=limits, started_at=started_at). Guardar el SolutionOutput devuelto.
    #    El bucle es idéntico al de SWE-bench y devuelve sus fallos con pasos parciales.
    # 9. Si falla una preparación antes del bucle, crear SolutionOutput de fallo con
    #    el error real, prompt alcanzado y tiempo transcurrido. Cero peticiones/tokens
    #    sólo es correcto aquí porque aún no se llamó al proveedor; no reutilizar
    #    este camino para sustituir un resultado parcial del bucle.
    # 10. En finally, intentar await sandbox.close() si se creó y luego await
    #     client.close() si se creó. Proteger y acotar el cierre frente a cancelación
    #     en la misma tarea. Un fallo de cierre no debe impedir el siguiente.
    #     Recoger errores de limpieza sin ocultar el original y marcar result como
    #     fallido. Si hubo KeyboardInterrupt/SystemExit, limpiar antes de propagar.
    # 11. Después de limpiar, actualizar result.total_time_seconds con monotonic()
    #     menos started_at. Si supera 120 s o hubo un cierre fallido, success=False
    #     y error debe explicarlo; conservar la solución y métricas realmente recibidas.
    # 12. Devolver result. No escribir JSON aquí: lo hace main con el resultado real.
    #
    # Pendiente en mbpp_tools: el deadline debe limitar arranque/wait/logs de Docker
    # y provocar eliminación del contenedor. Cerrar MCP no asegura parar un test
    # Docker que continúa en el servidor; esto se verifica en la integración real.
    raise NotImplementedError("The MBPP agent is not implemented yet.")
