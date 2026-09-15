# Benchmark report — SWE-bench model comparison

Eight models on the same three SWE-bench tasks, plus a prompt ablation. Every
number below is read from a `solution.json` in `benchmark_runs/`, and every
result was checked with `moulinette_eval validate swebench`, never with
`--skip-metrics`. Failures are reported as they happened.

## 1. Setup

**Agent.** This repository at commit `c5853a8`: one Thought → Code →
Observation loop, nine MCP tools, the task container held open by the agent's
stdin. Exam limits: 30 iterations, 300,000 input tokens, 10,000 output tokens,
900 seconds. Every model uses the same prompt and `configs/models_template.json`:
at most 600 output tokens per request; Gemini 120 s timeout and 4 retries,
OpenRouter 60 s and 2 retries.

**Models and providers.** Both free tiers, two API keys each.

| Provider | Endpoint | Models |
| --- | --- | --- |
| Google AI Studio | `generativelanguage.googleapis.com/v1beta/openai` | `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`, `gemini-3.5-flash`, `gemini-3.8-flash` |
| OpenRouter | `openrouter.ai/api/v1` | `dots-studio/dots-3-note-preview:free`, `inclusionai/ling-3.0-flash-vl:free`, `nvidia/nemotron-3.5-lightning:free`, `google/gemma-4-31b-it:free` |

**Tasks.** `sympy__sympy-13480`, `sympy__sympy-18189`, `django__django-11066`.

Why these three:

- They belong to the six-task pool the exam draws from (`EXAM_POOL` in
  moulinette's `swebench/interact.py`), so the comparison measures tasks that
  can actually be graded.
- Two repositories with different test runners (sympy's `bin/test`, Django's
  `runtests.py`), so one project's quirks do not decide the ranking.
- All three pass with the reference model, so a failure points at the model or
  the provider, not at an impossible task.
- Their images are the smallest in the pool, about 4 GB each, against 5.3 GB for
  `scikit-learn__scikit-learn-13439` and 7.6 GB for `pydata__xarray-4629`. The
  disk filled once while images were being pulled. The sixth pool task,
  `sympy__sympy-14711`, has not been run.

**When.** `gemini-3.5-flash-lite` on 14 September 2026; the other seven models
and the ablation on 15 September 2026. One run per model × task.

## 2. Results

Iterations / input tokens / output tokens / wall-clock time. Each cell is backed
by `benchmark_runs/swebench_20260914/<path>/solution.json` next to its
`validation.txt`.

| Model | `sympy__sympy-13480` | `sympy__sympy-18189` | `django__django-11066` |
| --- | --- | --- | --- |
| `gemini-3.5-flash-lite` | **PASS** · 8 / 27,767 / 455 / 24 s | **PASS** · 7 / 23,054 / 411 / 83 s | **PASS** · 7 / 26,604 / 413 / 13 s |
| `dots-3-note-preview` | **PASS** · 10 / 31,534 / 1,136 / 37 s | **PASS** · 11 / 35,957 / 1,391 / 38 s | **PASS** · 6 / 20,621 / 829 / 25 s |
| `ling-3.0-flash-vl` | **PASS** · 8 / 22,535 / 445 / 20 s | FAIL¹ · 11 / 46,190 / 488 / 41 s | **PASS** · 6 / 22,237 / 351 / 14 s |
| `gemini-3.1-flash-lite` | **PASS** · 17 / 135,665 / 3,265 / 145 s | FAIL² · 22 / 299,603 / 9,999 / 235 s | **PASS** · 15 / 80,720 / 1,199 / 48 s |
| `gemini-3.5-flash` | FAIL³ · 17 / 104,954 / 4,477 / 224 s | FAIL³ · 11 / 64,288 / 1,472 / 82 s | FAIL³ · 1 / 0 / 0 / 4 s |
| `gemini-3.8-flash` | FAIL³ · 1 / 1,703 / 35 / 56 s | FAIL⁴ · 16 / 124,758 / 4,593 / 880 s | FAIL³ · 5 / 12,518 / 1,287 / 242 s |
| `nemotron-3.5-lightning` | FAIL⁵ · 0 / 0 / 0 / 61 s | FAIL⁵ · 11 / 61,147 / 6,600 / 362 s | FAIL¹ · 3 / 8,643 / 1,274 / 26 s |
| `gemma-4-31b-it` | FAIL³ · 1 / 0 / 0 / 3 s | FAIL³ · 1 / 0 / 0 / 2 s | FAIL³ · 1 / 0 / 0 / 2 s |

¹ Submitted a final answer that was not a diff; the agent refuses that as a
success. ² Input budget exhausted. ³ Provider error: HTTP 503 or 429. ⁴ Task
deadline reached. ⁵ A request timed out.

Paths: `gemini-3.5-flash-lite` → `<task>/`; every other model →
`comparison/<model>/<task>/`, where the directory is the model id with `/` and
`:` replaced by `_`. The task directories are `sympy-13480`, `sympy-18189` and
`django-11066`.

Totals over the three tasks:

| Model | Passed | Iterations | Input tokens | Output tokens | Time |
| --- | ---: | ---: | ---: | ---: | ---: |
| `gemini-3.5-flash-lite` | 3/3 | 22 | 77,425 | 1,279 | 120 s |
| `dots-3-note-preview` | 3/3 | 27 | 88,112 | 3,356 | 100 s |
| `ling-3.0-flash-vl` | 2/3 | 25 | 90,962 | 1,284 | 75 s |
| `gemini-3.1-flash-lite` | 2/3 | 54 | 515,988 | 14,463 | 428 s |
| `gemini-3.5-flash` | 0/3 | 29 | 169,242 | 5,949 | 310 s |
| `gemini-3.8-flash` | 0/3 | 22 | 138,979 | 5,915 | 1,178 s |
| `nemotron-3.5-lightning` | 0/3 | 14 | 69,790 | 7,874 | 449 s |
| `gemma-4-31b-it` | 0/3 | 3 | 0 | 0 | 7 s |

## 3. Provider reliability

Read from the per-step fields `request_time_ms` and `retries`.

- **Average time per step** includes that step's retries.
- **Availability** is usable responses (steps with text) divided by all
  attempts (steps plus retries).
- **Runs ended by the provider** counts HTTP errors and request timeouts.

| Model | Steps | Retries | Steps with no usable text | Availability | Avg time per step | Runs ended by the provider |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `gemini-3.5-flash-lite` | 22 | 1 | 0 | 95.7% | 4.3 s | 0/3 |
| `dots-3-note-preview` | 27 | 0 | 0 | 100% | 2.8 s | 0/3 |
| `ling-3.0-flash-vl` | 25 | 3 | 0 | 89.3% | 1.5 s | 0/3 |
| `gemini-3.1-flash-lite` | 54 | 117 | 29 | 14.6% | 6.7 s | 0/3 |
| `gemini-3.5-flash` | 29 | 34 | 3 | 41.3% | 8.7 s | 3/3 (one 503, two 429) |
| `gemini-3.8-flash` | 22 | 24 | 2 | 43.5% | 50.1 s | 2/3 (503) |
| `nemotron-3.5-lightning` | 14 | 0 | 0 | 100%* | 23.1 s | 2/3 (timeout) |
| `gemma-4-31b-it` | 3 | 6 | 3 | 0% | 0.3 s | 3/3 (429) |

\* Overstated. A request that times out ends the run before it is recorded as a
step, so nemotron's two timeouts are missing from both columns.

What stands out:

- **`gemini-3.1-flash-lite` answers with empty text more often than not.** 29
  of its 54 steps had no usable text even after four retries; in
  `sympy-13480`, ten steps in a row. The retries also count against the input
  budget, which is how `sympy-18189` used all 300,000 input tokens in 22
  iterations.
- **`gemini-3.8-flash` is too slow for the time limit.** It averages 50 s per
  step, and 30 iterations at that pace take 1,500 s against a 900 s limit. It
  hit the deadline on `sympy-18189` after 16 iterations.
- **`gemma-4-31b-it` was rate-limited upstream all day.** Every request got a
  429 before generating anything. That is a provider result, not a model
  result.
- **The same model varies with the hour.** `gemini-3.5-flash-lite` averaged
  10.7 s per step on `sympy-18189` on 14 September. In the six ablation runs on
  15 September it made 54 steps with no retries at all. On the afternoon of 14
  September, Google's endpoint returned 503s almost continuously; the runs from
  that afternoon were discarded and repeated for this report.

## 4. Intermediary metrics

Measured on every passing run: the ten in section 2 and the six in section 5.

**a) First step that reads or edits a file of the final patch** (exploration
efficiency). The first `read_file` or `edit_file` whose `sandbox_input` names a
file that appears in the submitted diff.

| Model | 13480 | 18189 | 11066 |
| --- | ---: | ---: | ---: |
| `gemini-3.5-flash-lite` | 2 | 1 | 2 |
| `dots-3-note-preview` | 2 | 3 | 2 |
| `ling-3.0-flash-vl` | 2 | — | 2 |
| `gemini-3.1-flash-lite` | 2 | — | 2 |
| ablation runs (6) | 2, 2 | 2, 2 | 2, 3 |

**b) Iterations between "tests first pass" and `final_answer`** (submission
discipline; zero is ideal). "Tests first pass" is the first step after the last
edit that either calls `run_tests` or runs a test command through `run_command`
whose output shows a passing summary (sympy `tests finished: … passed` with no
failures, a unittest `OK` line). A `run_tests` call on the final code counts as
passing because it runs the same `eval_script` moulinette runs, and these tasks
passed moulinette. Its own output cannot confirm this; see section 7.

| Run | Iterations after tests pass | Input tokens spent after tests pass |
| --- | ---: | ---: |
| `gemini-3.5-flash-lite` · 13480 | 3 | 16,628 of 27,767 (60%) |
| `gemini-3.5-flash-lite` · 18189 | 2 | 7,489 of 23,054 (32%) |
| `gemini-3.5-flash-lite` · 11066 | 2 | 8,487 of 26,604 (32%) |
| `dots-3-note-preview` · 13480 | 3 | 14,829 of 31,534 (47%) |
| `dots-3-note-preview` · 18189 | 1 | 4,098 of 35,957 (11%) |
| `dots-3-note-preview` · 11066 | 1 | 5,085 of 20,621 (25%) |
| `ling-3.0-flash-vl` · 13480 | 2 | 9,085 of 22,535 (40%) |
| `ling-3.0-flash-vl` · 11066 | 1 | 5,398 of 22,237 (24%) |
| `gemini-3.1-flash-lite` · 11066 | 2 | 10,134 of 80,720 (13%) |
| `gemini-3.1-flash-lite` · 13480 | — | never tested the final code |
| ablation, without warning (3 runs) | 1, 2, 2 | 33%, 25%, 20% |
| ablation, with warning (3 runs) | 2, 2, 2 | 50%, 22%, 29% |

Ablation rows are in task order 13480 / 18189 / 11066. Without the warning:
3,739 of 11,435, 9,144 of 37,188 and 9,641 of 48,997. With it: 8,533 of 17,136,
9,842 of 45,236 and 9,179 of 31,246.

**What the metrics say.**

- **Finding the file is not the bottleneck.** Every passing run touches the
  file it will patch by step 1–3, 2 in most cases. Differences in iteration
  counts come from what happens *after* the edit.
- **Submission is.** No run submits in the step right after its tests pass.
  Between 1 and 3 iterations, costing 11% to 60% of the task's input tokens,
  go into re-running tests, printing `git diff` and calling `get_patch` before
  `final_answer`. Those late steps are the most expensive ones, because each
  resends the whole grown history. This is the clearest efficiency gain left
  in the agent.
- **Models verify through `run_command` instead of `run_tests`.** In 5 of the
  10 passing matrix runs, the model never called `run_tests` after its last
  edit and ran the test file itself instead. A likely reason is in section 7:
  `run_tests` output hides the result.

## 5. Ablation

### 5.1 SWE-bench: the prompt's "the sandbox cannot import the project" warning

**Change.** The system prompt (`agent_smith/swebench_agent.py`,
`build_swebench_system_prompt`) carries three lines telling the model that an
`import` of anything under `/testbed` fails inside the sandbox and that it must
use `run_command` instead. They were added after a model spent 4 of 12
iterations attempting `import sympy`. For the ablation, those three lines were
removed in a temporary copy of the agent. Everything else was identical: same
commit, model (`gemini-3.5-flash-lite`), tasks, limits and day. Each run's
`solution.json` stores its `system_prompt`, which confirms which version ran.

| Task | Without the warning | With the warning (current agent) |
| --- | --- | --- |
| `sympy__sympy-13480` | **PASS** · 5 / 11,435 / 148 / 13 s | **PASS** · 6 / 17,136 / 329 / 15 s |
| `sympy__sympy-18189` | **PASS** · 10 / 37,188 / 869 / 19 s | **PASS** · 11 / 45,236 / 985 / 141 s |
| `django__django-11066` | **PASS** · 13 / 48,997 / 592 / 16 s | **PASS** · 9 / 31,246 / 261 / 12 s |
| **Total** | 3/3 · 28 / 97,620 / 1,609 / 48 s | 3/3 · 26 / 93,618 / 1,575 / 168 s |
| Attempts to import the project | 0 | 0 |

Evidence: `benchmark_runs/swebench_20260914/ablation/without_import_warning/`
and `…/ablation/with_import_warning/`, then `gemini-3.5-flash-lite/<task>/`.

The 141 s on `sympy-18189` is not the model. Step 8 ran
`python setup.py test`, which ran until `run_command`'s 120 s limit; the eleven
model requests took 12 s in total.

**What was learned.**

- **For this model the warning does nothing measurable.** Without it,
  `gemini-3.5-flash-lite` still never tried to import the project, and the
  totals differ by 2 iterations and 4% of input tokens, in opposite directions
  on different tasks.
- **Run-to-run noise is as large as the difference.** The 14 September runs
  used the same agent and model and took 8 / 7 / 7 iterations; the "with
  warning" runs took 6 / 11 / 9. With one sample per cell, a change smaller
  than about four iterations per task cannot be told apart from chance.
- **The warning does not stop the models that do import.** In the matrix,
  `gemini-3.8-flash` tried to import the project 4 times on `sympy-18189`, and
  `gemini-3.1-flash-lite` once on `sympy-13480` (the sandbox refused:
  `ImportError: Import not allowed: sympy`). Both had the warning in their
  prompt.
- **Decision: keep it.** It is three lines, costs nothing measurable, and was
  added for a failure observed with another model, which this data cannot rule
  out.

### 5.2 MBPP: original versus simplified prompt (12 September)

An earlier ablation of the same kind on MBPP task 396, with
`inclusionai/ling-3.0-flash-vl:free`. The simplified prompt (226 words against
294) keeps the same tools, the raw-string solution and the test-then-submit
loop. It drops the 20-word limit on the Thought, the rule against explanatory
comments, the note about preserving backslashes, and "do not also define the
function in the worker".

| Prompt | Result | Iterations | Input / output tokens | Time |
| --- | --- | ---: | --- | ---: |
| Original | **PASS** | 4 | 3,237 / 388 | 7.4 s |
| Simplified | FAIL: the candidate required every character to match | 3 | 2,140 / 262 | 5.6 s |

Evidence: `benchmark_runs/mbpp_comparison_20260912/01b_ling_original_prompt/`
and `04_ling_simple_prompt/`, with both prompts saved next to them. The shorter
prompt saved tokens and lost correctness. The original prompt stayed. This is
a single task and sample, so it shows a direction, not a rate.

## 6. Conclusions

**Selected: `gemini-3.5-flash-lite`.** It passed all nine of its runs: three on
14 September plus six in the ablation. It used the fewest input tokens of any
model (77,425 for the three tasks) and needed one retry in 76 steps. It is the
first entry in `configs/models_template.json`.

**Backup: `dots-studio/dots-3-note-preview:free`.** 3/3, with 100% availability
and no retries. It uses about 14% more input tokens and 2.6× the output tokens
of the selected model. What matters is that it sits on a different provider
with a separate quota, so an outage or an exhausted quota at Google does not
stop the agent.

**Usable third: `inclusionai/ling-3.0-flash-vl:free`.** It is the fastest per
step (1.5 s), cheap, and passed 2/3. Its failure was a submission without a
diff, which the agent records as a failure rather than a false pass.

**Discarded, based on this data:**

- `gemini-3.1-flash-lite`: it passes 2/3, but with 6.7× the input tokens of the
  selected model (515,988 against 77,425), because more than half its steps
  come back empty. It exhausted the input budget on `sympy-18189`.
- `gemini-3.5-flash` and `gemini-3.8-flash`: 0/3, with availability of 41% and
  44% on the free tier. `gemini-3.8-flash` also cannot fit 30 iterations into
  900 s at 50 s per step.
- `nvidia/nemotron-3.5-lightning:free`: 0/3. It is slow (23 s per step), two
  requests timed out, and it once submitted without a diff.
- `google/gemma-4-31b-it:free`: no usable response at all; the free route was
  rate-limited upstream.

**Limits of these conclusions.** There is one run per cell on free tiers whose
availability changes by the hour. The rows for `gemini-3.5-flash`,
`gemini-3.8-flash` and `gemma-4-31b-it` measure the providers that day at
least as much as the models. Section 5.1 shows the same configuration varying
by up to four iterations per task.

**Cost.** Every run used free tiers and cost nothing. The token columns are
what a paid tier would bill.

## 7. Known limitations of the agent found while measuring

- **`run_tests` hides the test result from the model.** Its output is capped at
  4,000 characters, keeping the beginning and the end. Here, the beginning is
  the `git status` and mode-change noise the `eval_script` prints, and the end
  is deprecation warnings. The test summary falls in the omitted middle, and
  the reported `exit_code` belongs to the script's last command, not to the
  tests. This probably explains why models re-test through `run_command`, and
  part of the post-pass iterations in section 4b. Not changed yet.
- **A provider timeout ends the task with the bare message `TimeoutError:`.**
  On Python 3.10, the `asyncio.TimeoutError` raised by `asyncio.wait_for` is
  not a subclass of the built-in `TimeoutError` the client catches. The result
  file is still written and the run ends as designed, since a timed-out
  request has unknown usage and is not retried. Only the explanatory message
  and the step record are lost.

## 8. Reproducing a cell

```bash
# in student/
AGENT_SMITH_MODELS_CONFIG=configs/models_template.json \
uv run --env-file .env python -m agent_swebench \
  --task-file benchmark_runs/swebench_20260914/sympy-13480/task.json \
  --output solution.json \
  --model-name gemini-3.5-flash-lite \
  --provider-url https://generativelanguage.googleapis.com/v1beta/openai
# in moulinette/
uv run moulinette_eval validate swebench \
  ../student/benchmark_runs/swebench_20260914/sympy-13480/task.json \
  ../student/solution.json
```

OpenRouter models use `--provider-url https://openrouter.ai/api/v1`. The task
images were pulled beforehand, so the measured times exclude the download.
