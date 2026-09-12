"""Exercise the common loop with known code and scripted completion metadata."""

import asyncio
import time
from types import SimpleNamespace

from agent_smith.agent_loop import run_agent_loop
from agent_smith.models import AgentLimits, SandboxConfig
from agent_smith.providers import CompletionResponse
from agent_smith.sandbox import SandboxSession


class ScriptedProvider:
    config = SimpleNamespace(response_format="python")

    def __init__(self, replies):
        self.replies = iter(replies)
        self.histories = []

    async def complete(self, messages, **kwargs):
        self.histories.append(list(messages))
        text = next(self.replies)
        return CompletionResponse(text, 100, 50, 1, "https://example.invalid/v1", "fixture", 0, 1)


def run(replies, **limits):
    provider = ScriptedProvider(replies)
    async def scenario():
        sandbox = SandboxSession(SandboxConfig(allowed_directories=[]))
        try:
            await sandbox.start()
            result = await run_agent_loop(
                task_id="fixture", benchmark="mbpp", system_prompt="system", task_prompt="task",
                provider=provider, sandbox=sandbox,
                limits=AgentLimits(max_iterations=limits.get("iterations", 3),
                                   max_input_tokens=limits.get("input", 6000),
                                   max_output_tokens=limits.get("output", 1500), max_time_seconds=10),
                started_at=time.monotonic(),
            )
            return result
        finally:
            await sandbox.close()
    return asyncio.run(scenario()), provider


def test_extraction_feedback_and_final_step_boundary():
    result, provider = run(["No code.", "```python\nx = 4\nprint(x)\n```",
                            "```python\nfinal_answer(str(x))\n```"], output=150, input=300)
    assert result.success and result.solution == "4"
    assert result.iterations == 3 and result.total_requests == 3
    assert result.total_input_tokens == 300 and result.total_output_tokens == 150
    assert result.steps[0].sandbox_input == ""
    assert "No valid Python code" in provider.histories[1][-1]["content"]
    assert provider.histories[2][-1]["content"] == "Observation:\n4\n"


def test_runtime_error_becomes_observation_for_next_iteration():
    result, provider = run(["```python\nx = 4\nraise ValueError('fix me')\n```",
                            "```python\nfinal_answer(str(x + 1))\n```"])
    assert result.success and result.solution == "5"
    assert "ValueError: fix me" in provider.histories[1][-1]["content"]


def test_worker_timeout_preserves_step_and_stops_task():
    # SystemExit propagation is covered by supervisor tests; a lost worker gives a partial result.
    result, provider = run(["```python\nprint('before')\nwhile True: pass\n```"], iterations=1)
    assert not result.success and len(provider.histories) == 1
    assert result.total_input_tokens == 100
    assert "before" in result.steps[0].sandbox_output
    assert result.error


def test_budget_exhaustion_keeps_existing_steps():
    result, provider = run(["```python\nprint('one')\n```"], output=50)
    assert not result.success and result.iterations == 1
    assert result.total_output_tokens == 50
    assert "budget" in result.error
