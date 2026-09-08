"""Thin MBPP adapter around the shared Agent Smith loop."""

from __future__ import annotations

import argparse

from agent_smith.models import AgentLimits, MBPPTaskInput, SolutionOutput


def build_mbpp_system_prompt(
    mcp_manual: str, *, response_format: str = "python",
) -> str:
    """Recibir manual MCP; devolver el prompt completo en inglés.

    1. Explicar Thought -> Code -> Observation e incluir el manual descubierto.
    2. Mostrar un ejemplo con print(run_tests(...)), esperar resultado real y
       después final_answer(solution_code) si los tests públicos pasan.
    3. Usar bloque cerrado ```python seguido de <end_code>; final_answer pertenece
       al sandbox. Describir sólo formatos implementados para el modelo activo.
    4. Prohibir observaciones inventadas y buscar soluciones externas. Aclarar
       que aprobar tests públicos no certifica tests ocultos. No crea recursos.
    """
    raise NotImplementedError("The MBPP system prompt is not implemented yet.")


def build_mbpp_task_prompt(task: MBPPTaskInput) -> str:
    """Recibir MBPPTaskInput; devolver definición, firma, imports y tests en texto.

    1. Incluir ID y definición completos; conservar la firma requerida literalmente.
    2. Delimitar imports y tests suministrados como datos de la tarea; no añadir
       tests ocultos ni inferir una solución por el ID.
    3. Pedir una implementación general pequeña. Sin E/S ni recursos que cerrar.
    """
    raise NotImplementedError("The MBPP task prompt is not implemented yet.")


def _build_mbpp_limits(max_iterations: int) -> AgentLimits:
    """Recibir max_iterations; devolver AgentLimits para MBPP.

    1. Rechazar valor no positivo; usar min(max_iterations, 10).
    2. Fijar entrada/salida acumuladas 6.000/1.500 y tiempo total 120 segundos.
    3. Fuente: subject VI.1.1 y moulinette/moulinette/models.py, mbpp_defaults.
       moulinette/README.md dice 4.000/1.000 y 60 s; está desactualizado frente al
       código ejecutable. No editar moulinette. Esta función no abre recursos.
    """
    raise NotImplementedError("MBPP limit construction is not implemented yet.")


def run_mbpp_agent(
    task: MBPPTaskInput,
    args: argparse.Namespace,
    *,
    started_at: float,
) -> SolutionOutput:
    """Recibir tarea, args y started_at tomado en main; devolver SolutionOutput.

    1. Construir límites y budget definido en agent_loop.run_agent_loop antes de
       configurar nada más. Todas las fases usan el mismo deadline monotonic.
    2. Crear ProviderPool.from_environment con URL/modelo CLI y ruta opcional
       AGENT_SMITH_MODELS_CONFIG. No cargar claves en el sandbox ni servidor MCP.
    3. Abrir MCPClient con sys.executable y mcp_tools_mbpp.py; pasar sólo entorno
       necesario y AGENT_SMITH_DEADLINE. start/discover reciben deadline y devuelven
       el manual real; comprobar run_tests sin sustituir descubrimiento dinámico.
    4. Abrir SandboxSession con config (AGENT_SMITH_SANDBOX_CONFIG opcional o
       defaults), start(deadline=deadline). Construir prompts pasando
       providers.config.response_format al constructor del system prompt; llamar
       run_agent_loop(..., budget=budget) sin crear otro presupuesto ni reloj.
    5. Conservar solución capturada y pasos. En finally cerrar sandbox y MCP en
       orden inverso; después medir tiempo desde started_at, incluido cierre.
    6. Si falla preparación, devolver error real con los pasos/contadores existentes
       (sin llamadas, cero es conocido); si falla bucle conservar su paso parcial.
       Añadir fallos de limpieza, nunca ocultarlos. Exceder el tiempo impide éxito.
    7. KeyboardInterrupt/SystemExit se propagan tras liberar recursos; el CLI
       conserva el registro parcial del presupuesto antes de salir.

    Pendiente también en mbpp_tools.run_mbpp_tests: aplicar AGENT_SMITH_DEADLINE a
    arranque, wait y lectura de logs, y parar/eliminar su contenedor al expirar.
    Cancelar sólo la sesión MCP no garantiza terminar un trabajo Docker en curso.
    La integración futura debe probar una llamada real session.call_tool('run_tests',
    ...) con solución y aserción simples; list_tools sólo prueba descubrimiento.
    """
    raise NotImplementedError("The MBPP agent is not implemented yet.")
