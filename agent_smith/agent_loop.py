"""One custom Thought -> Code -> Observation loop shared by both benchmarks."""

from __future__ import annotations

from typing import Sequence

from agent_smith.models import AgentLimits, SolutionOutput, StepMetrics
from agent_smith.providers import CompletionResponse, ProviderPool
from agent_smith.sandbox import SandboxExecution, SandboxSession


def build_observation(
    execution: SandboxExecution | None,
    extraction_feedback: str,
) -> str:
    """Build the explicit observation returned to the model.

    Pseudocode:
        - If extraction produced no code, return the extraction failure verbatim.
        - Include recovery warnings before normal execution output.
        - State when execution timed out and label any retained partial output.
        - State exactly how much output was truncated.
        - Include syntax, policy, tool, or runtime errors without hiding them.
        - Never invent output for an execution that did not happen.
    """
    raise NotImplementedError("Agent observations are not implemented yet.")


def _build_step_metrics(
    step_number: int,
    completion: CompletionResponse,
    sandbox_input: str,
    sandbox_output: str,
) -> StepMetrics:
    """Translate one real provider/execution cycle into ``StepMetrics``.

    Pseudocode:
        - Copy provider-reported token counts and measured request time.
        - Preserve the raw model text before code extraction.
        - Preserve the exact code and exact sandbox observation.
        - Copy URL, model, and retry count without secrets.
        - Use a one-based step number.
    """
    raise NotImplementedError("Step metric construction is not implemented yet.")


def _find_limit_error(
    steps: Sequence[StepMetrics],
    elapsed_seconds: float,
    limits: AgentLimits,
) -> str | None:
    """Return an English error when cumulative run limits are exhausted.

    Pseudocode:
        - Compare step count with the iteration limit.
        - Sum real input and output tokens across all completed steps.
        - Compare monotonic elapsed time with the wall-clock limit.
        - Return the first precise limit message, otherwise ``None``.
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
    """Build a metrics-consistent final result for success or failure.

    Pseudocode:
        - Copy steps to a list and set ``iterations`` to its length.
        - Sum token totals from those same steps.
        - Use the measured request count, including provider retries.
        - Preserve the full system prompt and final English error.
        - Never use fabricated placeholder metrics.
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
    limits: AgentLimits,
) -> SolutionOutput:
    """Run the complete agent loop until ``final_answer`` or a hard limit.

    Pseudocode:
        1. Record a monotonic start time and create the initial message history.
        2. Before each iteration, stop if any cumulative limit is exhausted.
        3. Request one completion and count every underlying API request.
        4. Extract Python, XML, JSON/Hermes, or ReAct through
           ``extract_agent_code``.
        5. If extraction fails, record a step with no sandbox input and feed the
           explicit feedback back to the model.
        6. Otherwise execute the code in the persistent sandbox and record the
           exact input and observation.
        7. Append the real assistant response and observation to the history.
        8. When ``final_answer`` is captured, return it as the solution.
        9. Convert ordinary provider, MCP, and sandbox failures into a valid
           failed ``SolutionOutput``; let KeyboardInterrupt/SystemExit propagate.
        10. Guarantee ``iterations == len(steps)`` and exact cumulative totals.
    """
    raise NotImplementedError("The agent loop is not implemented yet.")
