# Validated SWE-bench tasks — 14 September 2026

Each directory holds that task's `task.json`, `solution.json` and the moulinette
output. Every run below was validated with `moulinette_eval validate swebench`,
without `--skip-metrics`.

## The exam's pool

The exam draws three tasks at random from a fixed pool of seven and requires two
to pass. Five of those seven pass here.

| Task | Model | Iterations | Input tokens | Output tokens | Time | Result |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `django__django-11066` | gemini-3.5-flash-lite | 7 | 26,604 | 413 | 13 s | **PASSED** |
| `sympy__sympy-18189` | gemini-3.5-flash-lite | 7 | 23,054 | 411 | 83 s | **PASSED** |
| `sympy__sympy-13480` | gemini-3.5-flash-lite | 8 | 27,767 | 455 | 24 s | **PASSED** |
| `pydata__xarray-4629` | gemini-3.5-flash-lite | 8 | 32,070 | 280 | 16 s | **PASSED** |
| `scikit-learn__scikit-learn-13439` | gemini-3.5-flash-lite | 14 | 74,031 | 2,359 | 60 s | **PASSED** |
| `django__django-12308` | gemini-3.5-flash-lite | 26 | 201,313 | 974 | 36 s | FAILED — patch submitted but it does not fix the issue |
| `scikit-learn__scikit-learn-11310` | gemini-3.5-flash-lite | 29 | 292,286 | 6,327 | 50 s | FAILED — input budget exhausted before a patch |

Outside the pool, `sympy__sympy-23534` also passes with
`dots-studio/dots-3-note-preview:free` (16 iterations, 98,430 input tokens, 58 s).
It measures the agent but cannot be drawn by the exam.

Across the six passing runs: **10.0 iterations on average and 16% of the input
budget**. Limits are 30 iterations, 300,000 input tokens, 10,000 output tokens
and 900 seconds.

Task images were pulled beforehand, so the measured times exclude the download.

## What each failure is

`django__django-12308` is an honest miss: the agent explored, edited and
submitted a diff, and moulinette judged the patch wrong. `scikit-learn-11310`
ran out of input budget at iteration 29 — the history window spends the
remaining allowance evenly across the remaining iterations, so a task needing
all thirty iterations with large observations consumes it exactly.

## Reproducing one

```bash
# in moulinette/
uv run --python 3.10 moulinette_eval dump swebench --task-id sympy__sympy-13480 --output task.json
# in student/
AGENT_SMITH_MODELS_CONFIG=configs/models_template.json \
uv run --env-file .env --offline --no-sync --python 3.10 python -m agent_swebench \
  --task-file task.json --output solution.json \
  --model-name gemini-3.5-flash-lite \
  --provider-url https://generativelanguage.googleapis.com/v1beta/openai
# in moulinette/
uv run --python 3.10 moulinette_eval validate swebench task.json solution.json
```

## What these runs changed in the agent

Every one of these was found by running the agent against a real task, not by
reading code:

- Models abandon the ```python fence once they see a tool result. Three text
  dialects are now converted (`<tool_call>`, `<tool_use>`) and so are the
  provider's own native `tool_calls` — translating those is what turned
  `pydata__xarray-4629` from a first-iteration death into a pass.
- An unusable model response is an observation, not the end of the task. That
  took `django__django-12308` from 2 iterations to 26.
- The Gemini timeout is 120 s: 60 s lost two tasks to `ReadTimeout`.
- A final answer must contain `diff --git`. A model once submitted `get_patch`'s
  own "No changes yet." message and the task was recorded as passed.
