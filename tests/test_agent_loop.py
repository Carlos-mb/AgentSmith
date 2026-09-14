"""Exercise the common loop with known code and scripted completion metadata."""

import asyncio
import time
from types import SimpleNamespace

from agent_smith.agent_loop import run_agent_loop, trim_history, MINIMUM_HISTORY_MESSAGES
from agent_smith.models import AgentLimits, SandboxConfig
from agent_smith.providers import CompletionResponse
from agent_smith.sandbox import SandboxSession


class ScriptedProvider:

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


def _history(pairs, content="x" * 400):
    messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "tarea"}]
    for number in range(pairs):
        messages.append({"role": "assistant", "content": f"respuesta {number} {content}"})
        messages.append({"role": "user", "content": f"observacion {number} {content}"})
    return messages


def test_a_generous_budget_keeps_the_whole_history():
    messages = _history(10)
    assert trim_history(messages, 1_000_000) == messages


def test_a_tight_budget_keeps_the_task_and_the_most_recent_exchanges():
    trimmed = trim_history(_history(20), 2_000)

    assert trimmed[0]["content"] == "s"
    assert trimmed[1]["content"] == "tarea"
    assert trimmed[-1]["content"].startswith("observacion 19")
    assert len(trimmed) < 2 + 20 * 2


def test_the_last_exchanges_survive_even_an_impossible_budget():
    trimmed = trim_history(_history(20), 0)

    assert len(trimmed) == 2 + MINIMUM_HISTORY_MESSAGES
    assert trimmed[-1]["content"].startswith("observacion 19")


def test_a_bigger_budget_keeps_more_history_than_a_smaller_one():
    messages = _history(20)
    assert len(trim_history(messages, 20_000)) > len(trim_history(messages, 3_000))


def test_trimming_does_not_alter_the_original_list():
    messages = _history(10)
    trim_history(messages, 1_000)
    assert len(messages) == 22
