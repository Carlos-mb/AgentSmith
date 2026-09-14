# Validated SWE-bench tasks — 14 September 2026

Two tasks solved end to end and validated by moulinette without `--skip-metrics`.
Each directory holds its `task.json`, `solution.json` and the validator output.

| Task | Model | Iterations | Input tokens | Output tokens | Time | Result |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `sympy__sympy-13480` | `gemini-3.5-flash-lite` | 8 | 27,767 | 455 | 23.6 s | PASSED |
| `sympy__sympy-23534` | `dots-3-note-preview:free` | 16 | 98,430 | 2,693 | 58.2 s | PASSED |

`sympy__sympy-13480` belongs to the pool the exam draws from; `sympy__sympy-23534`
does not, so it measures the agent but does not count towards the exam's three tasks.

## sympy__sympy-23534 — `dots-studio/dots-3-note-preview:free`

| Measure | Value | Limit |
| --- | ---: | ---: |
| Iterations | 16 | 30 |
| Input tokens | 98,430 | 300,000 |
| Output tokens | 2,693 | 10,000 |
| Wall-clock time | 58.2 s | 900 s |

```
Resolution status: RESOLVED_FULL
Correctness: PASSED
Metrics: VALID
Overall: PASSED
```

Model: `dots-studio/dots-3-note-preview:free` through OpenRouter, selected because
another project reported passing SWE-bench with it and it is still on the free tier.
The full validator output is in `validation.txt`.

The agent located the definition, read the surrounding code, reproduced the wrong
behaviour with `run_command`, edited one line, checked the type had changed to
`UndefinedFunction`, ran the task's `eval_script` and the project's own test file,
then submitted `final_answer(get_patch())`. The patch is the real fix:

```diff
-            result.append(symbols(name, **args))
+            result.append(symbols(name, cls=cls, **args))
```

Reproduce with:

```bash
# in moulinette/
uv run --python 3.10 moulinette_eval dump swebench --task-id sympy__sympy-23534 --output task.json
# in student/
AGENT_SMITH_MODELS_CONFIG=configs/models_template.json \
uv run --env-file .env --offline --no-sync --python 3.10 python -m agent_swebench \
  --task-file task.json --output solution.json \
  --model-name dots-studio/dots-3-note-preview:free \
  --provider-url https://openrouter.ai/api/v1
# in moulinette/
uv run --python 3.10 moulinette_eval validate swebench task.json solution.json
```

The task image was already present locally, so the measured time excludes the
image download. One task is not a pass rate: the exam draws three tasks from a
pool of six and requires two.


## sympy__sympy-13480 — `gemini-3.5-flash-lite`

The `.subs` on `coth(log(tan(x)))` failure. The agent found the block, read it,
fixed the typo, reproduced the call without the exception, ran the task's
`eval_script` twice and submitted:

```diff
-                    if cotm is S.ComplexInfinity:
+                    if cothm is S.ComplexInfinity:
```

Eight iterations and 9% of the input budget. Its image was pulled beforehand, so
the measured time excludes the download.

This run only became possible after adding the `<tool_use>` dialect to extraction:
on the previous attempt a model diagnosed the same typo correctly but expressed
every call in that format, and 23 of 29 iterations executed nothing.
