"""Thin MBPP adapter around the shared Agent Smith loop."""

from __future__ import annotations

import argparse

from agent_smith.models import AgentLimits, MBPPTaskInput, SolutionOutput


def build_mbpp_system_prompt(mcp_manual: str) -> str:
    """Build the complete MBPP system prompt logged in ``SolutionOutput``.

    Pseudocode:
        - Explain the Thought -> Code -> Observation cycle.
        - Include the dynamic MCP manual without rewriting its schemas.
        - Demonstrate one Python tool call followed by waiting for observation.
        - Require ``final_answer(solution_code)`` only after public tests pass.
        - Explain that final_answer is a sandbox builtin, not an MCP tool.
        - Describe all accepted response formats and the preferred Python fence.
        - Forbid invented observations, network lookup, and hidden-test guessing.
    """
    raise NotImplementedError("The MBPP system prompt is not implemented yet.")


def build_mbpp_task_prompt(task: MBPPTaskInput) -> str:
    """Format one MBPP definition, signature, imports, and public tests.

    Pseudocode:
        - Include the task identifier and natural-language definition.
        - Preserve the required function signature exactly.
        - List supplied imports and tests as untrusted task data.
        - Ask for the smallest general implementation, not a hardcoded answer.
    """
    raise NotImplementedError("The MBPP task prompt is not implemented yet.")


def _build_mbpp_limits(max_iterations: int) -> AgentLimits:
    """Build limits that never exceed the current subject contract.

    Pseudocode:
        - Reject non-positive input.
        - Cap requested iterations at 10.
        - Set cumulative input/output limits to 6,000/1,500 tokens.
        - Set the complete task timeout to 120 seconds.
    """
    raise NotImplementedError("MBPP limit construction is not implemented yet.")


def run_mbpp_agent(
    task: MBPPTaskInput,
    args: argparse.Namespace,
) -> SolutionOutput:
    """Solve one MBPP task through MCP, sandbox, and the shared loop.

    Pseudocode:
        1. Build ``ProviderPool`` from provider URL, model name, and environment.
        2. Start ``mcp_tools_mbpp.py`` with the current Python interpreter.
        3. Discover ``run_tests`` and generate its dynamic manual.
        4. Start a ``SandboxSession`` with safe default configuration.
        5. Build and retain the exact system and task prompts.
        6. Call ``run_agent_loop`` with the MBPP hard limits.
        7. Accept only the string captured by ``final_answer`` as solution code.
        8. Close sandbox and MCP in ``finally``/context managers.
        9. On an ordinary failure, return a valid failed ``SolutionOutput`` with
           real partial metrics instead of crashing the CLI.
    """
    raise NotImplementedError("The MBPP agent is not implemented yet.")
