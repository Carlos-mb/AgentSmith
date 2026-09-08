"""One custom Thought -> Code -> Observation loop shared by both benchmarks."""

from __future__ import annotations

from typing import Any, Sequence

from agent_smith.models import SolutionOutput, StepMetrics
from agent_smith.providers import CompletionResponse, ProviderPool
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


def _build_step_metrics(
    step_number: int,
    completion: CompletionResponse,
    sandbox_input: str,
    sandbox_output: str,
) -> StepMetrics:
    """Recibir la generación y ejecución de un paso; devolver StepMetrics.

    1. Numerar desde 1. Copiar texto bruto, código efectivamente enviado y observación.
    2. completion contiene la suma de tokens y tiempos de TODOS los intentos de
       este paso; retries = request_count - 1. No usar sólo la última petición.
    3. Copiar URL pública sin credenciales y modelo. Si hubo fallo definitivo,
       el proveedor conserva la misma información en last_completion; texto vacío
       significa que no llegó texto, nunca una respuesta inventada.
    4. Si completion.usage_complete es falso (campo interno pendiente descrito en
       CompletionResponse), marcarlo expresamente en sandbox_output: los
       enteros son subtotales conocidos, no el consumo total ni un cero medido.
       El resultado final también debe fallar con ese aviso. No abre recursos.
    """
    raise NotImplementedError("Step metric construction is not implemented yet.")


def _find_limit_error(
    budget: dict[str, Any],
    *,
    before_request: bool = True,
) -> str | None:
    """Recibir presupuesto y fase; devolver error en inglés o None.

    1. Leer limits, started_at, steps y los contadores del mismo budget compartido.
       Comparar time.monotonic() con deadline; nunca reiniciar el reloj en el bucle.
    2. Rechazar uso desconocido y totales estrictamente mayores que los límites.
       No recortar los valores medidos para hacerlos encajar.
    3. Si before_request=True, además impedir otro paso cuando len(steps) alcanza
       max_iterations o no quedan tokens. complete revisa cada reintento sin
       contarlo como otra iteración, incluyendo el historial reenviado.
    4. Con before_request=False, permitir finalizar el último paso válido aunque
       agote exactamente las iteraciones/tokens. Aplicar esta fase después de API,
       antes del sandbox y antes de aceptar final_answer. Sin recursos propios.
    """
    raise NotImplementedError("Agent limit checks are not implemented yet.")


def _build_solution_output(
    *,
    task_id: str,
    benchmark: str,
    success: bool,
    solution: str,
    system_prompt: str,
    steps: Sequence[StepMetrics],
    total_requests: int,
    total_time_seconds: float,
    error: str | None,
) -> SolutionOutput:
    """Recibir resultado, pasos y métricas medidas; devolver SolutionOutput.

    1. Copiar steps, iterations=len(steps), prompt íntegro y solución capturada.
    2. Sumar los tokens de los pasos, incluidos intentos fallidos con uso conocido;
       deben coincidir con budget. Usar total_requests real, incluidos reintentos.
    3. total_time_seconds se mide desde la entrada CLI hasta acabar la limpieza:
       el adaptador actualiza el resultado provisional del bucle tras cerrar todo.
    4. En fallo conservar pasos, tiempos y error; no sustituirlos por el placeholder
       del CLI. Si falta uso, success=False, solution="" y error aclara que los
       tokens son subtotales conocidos y que no se puede certificar el presupuesto.
    5. El esquema público exige enteros y no tiene un indicador de uso desconocido:
       esta política explícita de fallo no equivale a métricas completas; seleccionar
       proveedores verificables antes de evaluar. No crea recursos.
    """
    raise NotImplementedError("Solution output construction is not implemented yet.")


def run_agent_loop(
    *,
    task_id: str,
    benchmark: str,
    system_prompt: str,
    task_prompt: str,
    providers: ProviderPool,
    sandbox: SandboxSession,
    budget: dict[str, Any],
) -> SolutionOutput:
    """Recibir tarea, prompts, conexiones abiertas y budget; devolver resultado.

    Presupuesto común pendiente: un diccionario, sin otra jerarquía. El CLI toma
    started_at=time.monotonic() al entrar en main, antes de leer JSON/configuración.
    El adaptador crea budget con started_at, deadline=started_at+limits.max_time_seconds,
    limits, steps=[], total_requests=0, input_tokens=0, output_tokens=0 y
    usage_complete=True. Proveedor y bucle comparten ese objeto; los tiempos de
    preparación, herramientas, esperas y limpieza forman parte de la misma tarea.

    1. Crear historial con los prompts exactos. Revisar _find_limit_error antes
       de pedir una respuesta. complete(messages, budget=budget) revisa también
       cada envío y recibe el tiempo y la salida disponibles.
    2. Cada ciclo con alguna petición produce UN StepMetrics, incluso si agota
       reintentos. complete mantiene last_completion y los contadores antes de
       propagar fallos. Sin petición no inventar un paso. Registrar primero las
       métricas recibidas; revisarlas antes de ejecutar contenido del modelo.
    3. Extraer con extract_agent_code usando el response_format del modelo activo;
       sólo python está implementado hoy. Sin código, guardar sandbox_input="" y
       diagnóstico. Con código, ejecutar sandbox.execute(code, deadline=deadline).
    4. Crear observación real con build_observation y completar el paso. Añadir
       al historial la respuesta del asistente y esa observación, incluidos avisos.
    5. Revisar de nuevo límites antes de continuar o aceptar final_answer; no
       declarar éxito si la llamada o ejecución terminó fuera de presupuesto.
       final_answer no demuestra aprobar tests ocultos: success expresa al agente.
    6. Devolver _build_solution_output. En errores ordinarios conservar el paso
       parcial y el error; KeyboardInterrupt/SystemExit suben al adaptador para
       limpieza y al CLI. No cerrar conexiones prestadas ni hacer otra petición
       para explicar un fallo. El adaptador cierra sus recursos incluso si se acaba
       el tiempo, registra el tiempo real de limpieza y convierte exceso en fallo.
    """
    raise NotImplementedError("The agent loop is not implemented yet.")
