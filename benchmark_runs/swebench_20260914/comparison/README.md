# Model comparison — incomplete

Material for `BENCHMARK_REPORT.md`. Each directory holds one model's
`solution.json` and moulinette output for one task, over the same three tasks.

## Status

Only one model has a complete, passing set of three: `gemini-3.5-flash-lite`,
whose runs live in the parent directory rather than here.

Everything recorded here was measured while Google's endpoint was returning
HTTP 503 and read timeouts almost continuously, so these rows measure the
provider's availability that afternoon at least as much as the models:

| Model | Task | Result | Iterations | Input tokens | Time |
| --- | --- | --- | ---: | ---: | ---: |
| `gemini-3.1-flash-lite` | `sympy__sympy-13480` | FAILED — HTTP 503 | 5 | 15,007 | 75 s |
| `gemini-3.1-flash-lite` | `sympy__sympy-18189` | FAILED — HTTP 503 | 13 | 63,942 | 180 s |
| `gemini-3.1-flash-lite` | `django__django-11066` | FAILED — HTTP 503 | 5 | 13,189 | 59 s |
| `gemini-3.5-flash` | `sympy__sympy-13480` | FAILED — HTTP 503 | 2 | 1,703 | 34 s |
| `gemini-3.5-flash` | `sympy__sympy-18189` | FAILED — ReadTimeout | 2 | 2,594 | 148 s |
| `gemini-3.5-flash` | `django__django-11066` | FAILED — ReadTimeout | 1 | 0 | 121 s |

An earlier attempt in the same session had `gemini-3.1-flash-lite` **pass**
`sympy__sympy-13480` in 6 iterations with 19,461 input tokens and 765 output
tokens in 65 s. That result is reported here from the run log only: the script
that collects this matrix overwrote its `solution.json` and validator output
with the later failing attempt before the bug was fixed. The cell needs
re-running to have evidence behind it.

## What is still needed

The graded report asks for at least five models over at least three common
tasks, with provider reliability and two intermediary metrics. Missing:

- Re-run `gemini-3.1-flash-lite` on all three once Google's endpoint is healthy.
- Two more models. `dots-studio/dots-3-note-preview:free` is the strongest
  candidate — it passed `sympy__sympy-23534` — but OpenRouter's free daily quota
  was exhausted. `nvidia/nemotron-3.5-lightning:free` and
  `google/gemma-4-31b-it:free` are configured and untested.
