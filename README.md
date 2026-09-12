*This project has been created as part of the 42 curriculum by cmelero-.*

# Agent Smith

## Description

Agent Smith is a Python project for an autonomous code agent. It targets MBPP,
which contains small Python programming tasks, and SWE-bench, which requires
patches for issues in real repositories.

The intended agent follows `Thought -> Code -> Observation`: an LLM proposes
Python code, a separate worker executes it, and the agent uses the observed result
to decide its next step. The MBPP execution path is implemented. On 2026-09-12,
tasks 396 and 163 passed moulinette correctness and metrics with Ling 3.0 Flash VL
through OpenRouter. The wider evaluation remains pending.

## Current status

Implemented: public JSON models and CLI arguments, restricted persistent Python
worker, process supervision, Python extraction, observations, MCP stdio discovery
and wrappers, Docker MBPP tests, configurable HTTP provider client, shared agent
loop, and MBPP adapter/CLI.

The controlled integration test runs the actual CLI, worker, MCP server and Docker
with scripted HTTP responses and known candidate code. It observes a failed test,
corrects the candidate, sees passing tests, then submits the persistent solution.
Its provider responses and token values are fixtures, not benchmark measurements.

The [model/prompt comparison](benchmark_runs/mbpp_comparison_20260912/README.md)
records all six new development attempts on the same task, including failures.
The reasons for retaining Ling and the original prompt are documented below.

Earlier unsuccessful OpenRouter/Gemini attempts remain in
[`benchmark_runs/mbpp_local_20260911`](benchmark_runs/mbpp_local_20260911), and the
[user's North baseline](benchmark_runs/mbpp_20260912_053114/solution.json) is also
preserved. Failures included API access/quota errors, incomplete code and incorrect
solutions despite passing public tests. These are development runs, not an exam batch.

The worker now receives `test_imports` and `test_list` before the agent loop. The
prompt asks for a short Thought and solution source in a raw triple-quoted string
to preserve backslashes. HTTP errors retain the provider's diagnostic message
while hiding configured keys. The input estimate has been corrected, temperature
defaults to 0.1 as in the reference, and missing-code feedback asks for the whole
block again. Each step now records the model reported by the API, which matters
when the explicitly selected free router changes models between requests.

MCP HTTP, the interactive sandbox/REPL, non-Python conversions, SWE-bench tools
and adapter, and the manual benchmark report are still pending. Their necessary
stubs retain `NotImplementedError`. Two validated MBPP tasks do not establish
success on the full benchmark or the security examination.

## Why Ling 3.0 Flash VL and the original prompt

We selected `inclusionai/ling-3.0-flash-vl:free` through OpenRouter because it
produced a solution for task 396 that passed both moulinette correctness and
metrics. It used 4 iterations, 3,237 input tokens, 388 output tokens and 7.39
seconds, within the unchanged MBPP limits. Its catalog entry advertised zero
input/output prices and support for the `stop` and `max_tokens` parameters when
checked on 2026-09-12. The decision rests on the observed result, not model size
alone.

| Trial on task 396 | Observed result |
| --- | --- |
| North, original prompt (user's baseline) | Failed correctness despite valid metrics. |
| Ling, original prompt | Passed correctness and metrics. |
| North or Ling, simplified prompt | Both failed correctness despite valid metrics. |
| Automatic free router, simplified prompt | Neither attempt completed successfully: one encountered a reasoning configuration error; the other returned no response text. |
| Inkling, original prompt | Rejected this client with HTTP 403; no solution was evaluated successfully. |

We retained the original prompt because the shorter version did not improve
correctness in these trials. We select Ling explicitly so each request targets
the same model. `openrouter/free` may choose different models between requests;
it does not guarantee the best model for a task. No paid router or automatic
provider fallback is used.

The [comparison evidence](benchmark_runs/mbpp_comparison_20260912/README.md)
includes all attempts, both prompts, configurations, model responses and
moulinette validations. These development samples support a practical starting
choice; they do not establish a general model ranking or guarantee passing the
exam.

At the user's request, we then drew another task at random using moulinette's
`dump mbpp` command and ran it once, with the same Ling configuration and the
identical system prompt. Task 163 asks for the area of a regular polygon. The
agent's first candidate passed its public tests through MCP/Docker, and its next
response submitted `final_answer(solution)`. Moulinette independently validated
the resulting JSON without `--skip-metrics`:

| Task | Iterations | Input tokens | Output tokens | Total time | Moulinette |
| --- | ---: | ---: | ---: | ---: | --- |
| 396: matching first/last characters | 4 | 3,237 | 388 | 7.389 s | PASSED / VALID / PASSED |
| 163: regular polygon area | 2 | 1,505 | 169 | 3.537 s | PASSED / VALID / PASSED |

Both runs used the limits of 10 iterations, 6,000 input tokens, 1,500 output
tokens and 120 seconds, including preparation and cleanup. The second run used
Python 3.10.12 for the CLI and moulinette, with Docker as configured. No candidate
was edited by hand and no model or prompt adjustment was made for task 163.
Its [evidence and commands](benchmark_runs/mbpp_second_task_20260912/README.md)
include the public task, full result, DEBUG exchanges and validator output.
Both tasks passed; this small development sample is not a benchmark pass rate.

## System architecture

The MBPP execution uses three separate processes:

1. An asynchronous coordinator owns the LLM client, task limits and sandbox
   supervisor. The benchmark adapter opens and closes MCP in the same task;
   the supervisor borrows the open SDK session to service worker requests.
2. A persistent Python worker executes consecutive code blocks in the same
   namespace. It receives configuration and exchanges sequential JSON messages
   with the supervisor. It does not receive API keys, SDK sessions or Docker
   clients.
3. An MCP server performs trusted tool operations, such as running tests inside
   Docker. Tools are discovered from the connected server.

Only one agent operation is active at a time. MCP connection setup, requests and
cleanup must stay in the same asynchronous task. There is no private SDK thread,
shared mutable provider budget or replay of previous code to recover state.
A fatal worker failure may end the task with its actual partial result. A REPL
restart must tell the user that variables have been lost.

The common loop accepts either benchmark; only the MBPP adapter is implemented.
The first live MBPP validation is complete; MCP/REPL and SWE-bench follow.

## Agent loop and limits

Each iteration requests a response, records its actual text and token metrics,
extracts Python, executes it once and feeds the observation back to the LLM.
Missing code, interpretation of malformed blocks, execution failures and truncated
logs need explicit observations. `final_answer` ends the loop and supplies the
solution: Python source for MBPP or the complete patch for SWE-bench.

The subject and the available moulinette models specify these task limits:

| Benchmark | Iterations | Input tokens | Output tokens | Total time |
| --- | ---: | ---: | ---: | ---: |
| MBPP | 10 | 6,000 | 1,500 | 120 seconds |
| SWE-bench | 30 | 300,000 | 10,000 | 900 seconds |

Tokens accumulate across the task, including reasoning tokens where applicable.
The loop must accumulate each request's metrics once. Total requests include
retries. Each solution must retain the full system prompt, raw model responses,
executed code and observations required by the public output contract.

The client selects one URL/model configuration, reads its named environment keys,
and rotates only those keys on HTTP 429. Retries are bounded by `max_retries`,
time and remaining tokens. A response without complete usage ends the task with
known subtotals and an explicit error; its unknown consumption is never reported
as a measured zero. A 429 without usage advances the key index but cannot trigger
another generation with unknown spend. HTTP retry acceptance during the exam
remains uncertain; set `max_retries` to 0 for a run without HTTP retries.

Before sending, the client estimates input size as UTF-8 bytes divided by four
(rounded up), plus chat framing headroom. This adapts the reference approximation
and replaces the initial estimate that counted every byte as a token and stopped
live runs too early. This remains an estimate,
not an exact remote tokenizer or a guarantee against crossing the input limit.
Only API usage goes into metrics. Actual excess usage is preserved and marks the
task failed. Reasoning subtotals already included in completion tokens are not
added twice. Fixed-model configurations request reasoning disabled and cap each
reply at 600 tokens, also bounded by the task's remaining output allowance.
The free router leaves reasoning at the selected model's default: some endpoints
reject disabling it. Reasoning tokens still consume the same task allowance.

`configs/models_template.json` contains four explicitly selectable configurations.
The OpenRouter catalog and access were checked on 2026-09-12:

- OpenRouter: `inclusionai/ling-3.0-flash-vl:free`, a larger candidate for the model
  comparison. It advertises zero prompt/completion prices and `stop`/`max_tokens`
  support and passed task 396 with the retained prompt.
  [Model](https://openrouter.ai/inclusionai/ling-3.0-flash-vl:free).
- OpenRouter: `openrouter/free`, which chooses a free model per request. Both
  recorded trials failed to finish the task. The API's `model` field is retained
  in step metrics; when it is absent, the requested ID is kept.
  [Free router](https://openrouter.ai/docs/guides/routing/routers/free-router).

- OpenRouter: `cohere/north-mini-code:free`. The public catalog lists zero input/
  output prices and `stop`/`max_tokens` support. Parameters are required in routing.
  Live access was confirmed after the account owner adjusted the workspace policy.
  The first attempt after that change failed benchmark correctness.
  [Catalog](https://openrouter.ai/api/v1/models),
  [model](https://openrouter.ai/cohere/north-mini-code:free).
- Gemini, checked on 2026-09-11: `gemini-2.5-flash-lite`, through Google's compatible endpoint with
  `reasoning_effort: "none"`. The pricing page lists a free tier. Live requests
  have returned code and measured usage; HTTP 503 and HTTP 429 failures also occurred.
  [Pricing](https://ai.google.dev/gemini-api/docs/pricing),
  [compatibility](https://ai.google.dev/gemini-api/docs/openai).

Availability and quotas can change. The project requires free access without
purchased credits or billing-enabled accounts. Extra keys do not imply extra
account/project quota. Provider selection remains explicit. Selecting
`openrouter/free` delegates model selection to OpenRouter; the program itself
does not switch configurations after a failure. Paid `openrouter/auto` is not used.

## Sandbox design

The first version implements standard-library controls for imports, explicit
builtins, file opening, exposed socket entry points, worker memory (`RLIMIT_AS`),
execution time and output. `RLIMIT_AS` bounds virtual address space, not exactly
resident RAM. Limits must apply successfully before the worker announces ready.

Path checks must resolve paths and check directory membership. An empty
`allowed_directories` list permits no access through the controlled file-opening
interface. File descriptors and options that bypass that interface must be
rejected. Restricted imports and a wrapper around `open` do not control every
operation that an allowed Python library can expose.

The worker's code timeout excludes time waiting for MCP. The total task deadline
includes those waits. Already received output must survive timeout or failure;
log truncation must be reported. The final answer and the git patch are preserved
in full.

`final_answer` is always local to the sandbox and is never an MCP tool. Worker
control exceptions must be communicated so that the coordinator can shut down;
`KeyboardInterrupt` and `SystemExit` must not be silently swallowed.

These controls do not establish resistance to hostile Python introspection,
filesystem races, or alternative library APIs. Passing the subject's security
evaluation remains uncertain. The current project instructions authorize
Agent Smith and moulinette tests, including their generated Python, in the normal
project environment with Docker where configured. Extra isolation is not a
prerequisite for those tests. This authorization does not extend to unrelated
actions on personal files or credentials. Landlock, Linux
namespaces, mounts, `chroot`, capability manipulation and their prerequisite probes
are outside the chosen first version.

## MCP and tools

The MCP client must support stdio and streamable HTTP, dynamic discovery of tools,
resources and prompts, and a manual generated from server metadata. The SDK and
server validate MCP operations. The worker sees simple callable wrappers that
exchange JSON with the supervisor; it does not own the MCP session.

The MBPP MCP server exposes `run_tests(code, test_imports, test_list,
timeout_seconds)`. Its helper creates a Docker container for the candidate and
public assertions, collects output and cleans up its own container. This helper
uses the remaining task deadline for its operations and bounded cleanup. Each
container has an unpredictable task label; after closing MCP, the adapter also
removes containers with that exact label to cover cancellation or server death.
Five seconds of the total task limit are reserved for cleanup. An unavailable
Docker daemon can still prevent confirmed deletion; cleanup errors mark failure.

The planned SWE-bench server owns one container per task and one command helper.
These nine required tools are still pending:

- `read_file(filepath, start_line, end_line)`
- `edit_file(filepath, old_str, new_str)`
- `list_files(directory, pattern)`
- `search_code(pattern, file_pattern)`
- `search_function_or_class_definition_in_code(name)`
- `find_references(name, filepath, line)`
- `run_tests()`
- `get_patch()`
- `run_command(command, workdir)`

SWE-bench commands run inside the task container. `run_tests` executes the supplied
`eval_script`; `get_patch` returns the complete diff. Initial reference search is
textual and cannot reliably distinguish all usages of symbols with the same name.

## Instructions

Use Python 3.10 and uv. Run commands from the `student` directory. For an initial
environment setup, install the dependencies declared in `pyproject.toml` with
`uv sync --python 3.10`. No API provider is needed to inspect CLI help:

```bash
uv run --offline --no-sync --python 3.10 python -m agent_mbpp --help
uv run --offline --no-sync --python 3.10 python -m agent_swebench --help
```

The required task flags are `--task-file`, `--output`, `--model-name` and
`--provider-url`. Sandbox arguments retain an optional configuration path and
mutually exclusive `--mcp-stdio` and `--mcp-server` options. Parsing these options
launches MBPP execution, but does not implement the sandbox REPL. The sandbox parser can be tested
independently, but `sandbox_cli.main` remains a stub, so `uv run sandbox --help`
does not work yet. The planned sandbox CLI owner will open and close MCP itself,
and lend that session to the supervisor for the REPL.

### First live MBPP run

Use the normal project environment and its configured Docker daemon. The worker's
environment contains no API keys or Docker configuration; the coordinator loads
provider keys. Install dependencies with `uv sync --python 3.10` and prepare the
Docker image with `docker pull python:3.10.12-slim`. Keep provider keys in the local,
gitignored `.env`, based on `.env.example`. The program reads environment variables;
`uv --env-file` loads the file for the run.

1. In the moulinette directory: `uv run --python 3.10 moulinette_eval dump mbpp --output ../cache/mbpp/live_task.json`.
2. In the student directory:

```bash
AGENT_SMITH_MODELS_CONFIG=configs/models_template.json \
uv run --env-file .env --offline --no-sync --python 3.10 python -m agent_mbpp \
  --task-file ../cache/mbpp/live_task.json \
  --output ../cache/mbpp/live_solution.json \
  --model-name inclusionai/ling-3.0-flash-vl:free \
  --provider-url https://openrouter.ai/api/v1
```

3. In the moulinette directory: `uv run --python 3.10 moulinette_eval validate mbpp ../cache/mbpp/live_task.json ../cache/mbpp/live_solution.json`.

Do not pass `--skip-metrics`. Keep both JSON files and the validator's output,
including failures. CLI exit code 0 means a result JSON was written; inspect its
`success` and `error`. Only moulinette validation decides benchmark correctness.
To explicitly select Gemini, use model `gemini-2.5-flash-lite` and provider URL
`https://generativelanguage.googleapis.com/v1beta/openai` with the same config file.

### Logging

Logging is disabled when `AGENT_SMITH_LOG_LEVEL` is unset or empty. To see the
execution as it happens, add this line to your local `.env` and run with
`uv run --env-file .env` as above:

```dotenv
AGENT_SMITH_LOG_LEVEL=DEBUG
```

Alternatively, prefix an existing command with `AGENT_SMITH_LOG_LEVEL=DEBUG`.
Remove the variable or leave it empty to return to silent execution. The accepted
levels are `DEBUG`, `INFO`, `WARNING`, `ERROR` and `CRITICAL` (case-insensitive).
An invalid nonempty level reports a configuration error and uses `ERROR`.

Messages are in Spanish and include time, process ID, module, function and line:

- `DEBUG`: function/method entry, decisions, provider parameters and HTTP status,
  token/time budgets, full prompts, model responses, executed code, observations,
  worker messages, MCP operations and Docker cleanup.
- `INFO`: task stages, iterations, requests, test results and completion.
- `WARNING` / `ERROR`: rejected operations, failed tests, retries, limits and errors.

Detailed exchanges have these DEBUG labels:

- `IA ENVIADO`: every message in each HTTP attempt, with its role and full text,
  including previous answers and observations sent back to the model.
- `IA RECIBIDO`: the full HTTP response body, including errors and non-JSON bodies.
- `MCP ENVIADO` / `MCP RECIBIDO`: operation arguments and complete SDK results,
  including initialization, discovery and tool errors.
- `DOCKER ENTRADA` / `DOCKER SALIDA`: the actual Python program (candidate,
  imports and assertions), exit code and combined stdout/stderr. On a timeout,
  `DOCKER SALIDA PARCIAL` shows whatever output could be recovered. DEBUG records
  the received Docker output before the existing observation truncation.

The coordinator, worker and bundled MCP servers write logs to **stderr**, in real
time. Append `2>debug.log` to the command to save them. JSON protocol messages,
code output returned as observations and result files keep their existing format;
diagnostic logs do not become model observations. Handled CLI errors follow the
selected log level and retain their exit codes. Explicit `--help` still prints help.

Configured provider keys are redacted from coordinator logs, and HTTP headers and
third-party SDK logs are excluded. DEBUG still includes the task's full text and
generated code. Only the log level is forwarded to the worker and MCP server;
provider keys remain in the coordinator. Pending features log their entry and
raise their existing `NotImplementedError`; logging does not implement them.

### Tests

From the student directory:

```bash
uv run --offline --no-sync --python 3.10 python -m pytest tests/test_sandbox_session.py tests/test_providers.py tests/test_agent_loop.py
uv run --offline --no-sync --python 3.10 python -m pytest tests/test_mbpp_cycle.py tests/test_mcp_mbpp.py tests/test_mbpp_tools.py
git diff --check
```

The second command needs Docker and the prepared image. Check skipped tests;
a skipped Docker test does not prove integration. `test_mbpp_cycle.py` uses fake
HTTP responses, actual processes and Docker, including cancellation during tests.
If the default uv cache is read-only, prefix commands with
`UV_CACHE_DIR=/tmp/agentsmith-uv-cache`; this does not change the interpreter.
Reserve the full suite for integration work.

The available moulinette includes public models and benchmark validation code.
The three `exam_*.sh` scripts are absent. Tests, moulinette validation and the full
examination are distinct. On 2026-09-12, the full integration suite passed
**198 tests in 26.44 seconds**, with Python 3.10.12 and Docker, without skips.
This includes logging levels, silence by default, key redaction, clean JSON
channels and controlled correction in both silent and DEBUG modes. No Agent Smith
MBPP containers remained after these tests. No live API request or moulinette
validation was repeated for this logging change. These tests do not prove a live
benchmark pass. The available
moulinette CLI runs under Python 3.10; its candidate-test image is `python:3.11-slim`,
while the agent's Docker tests use `python:3.10.12-slim`.

The subsequent DEBUG exchange expansion passed **77 focused tests in 14.34
seconds**, with Python 3.10.12 and Docker. Those checks cover full request history,
HTTP response bodies, redaction, MCP payloads and complete/partial Docker output;
the full suite was not repeated for this smaller change.

After adding API-reported model names for router requests, 21 provider/loop tests
passed in 11.90 seconds. The focused provider/loop/CLI/worker/MCP/Docker integration
passed 25 tests in 16.54 seconds while evaluating the simplified prompt. The
original prompt was then restored and checked against the successful live run's
full system prompt. Every new live result was validated by moulinette separately;
the public configurations were parsed and their router payload checked offline.
After restoring the original prompt, all 4 tests in `test_mbpp_cycle.py` passed
in 5.39 seconds with Docker, checking the final code's controlled correction cycle.

## Benchmark results and analysis

The manual [benchmark report](BENCHMARK_REPORT.md) is pending. It must compare at
least five models on the same set of at least three SWE-bench tasks, include the
required results and provider reliability metrics, analyse at least two
intermediary metrics, and show a before/after comparison using the same model and
tasks. Conclusions must follow the measured results. Keep the backing
`solution.json` evidence in the repository. No report generator is planned.

## Resources and AI assistance

Project requirements come from the supplied `en.subject.pdf`, with public JSON
contracts and validation limits checked against the available moulinette code.
Useful primary references for implementation are:

- [Python 3.10 documentation](https://docs.python.org/3.10/), especially `asyncio`,
  `subprocess`, `json`, `pathlib` and `resource`.
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) for MCP
  sessions, transports and server capabilities.
- [Pydantic documentation](https://docs.pydantic.dev/latest/) for data models.
- [Docker SDK for Python](https://docker-py.readthedocs.io/en/stable/) for container
  execution and cleanup.
- [uv documentation](https://docs.astral.sh/uv/) for the Python environment.

AI assistance covered inspecting the reference and subject, implementing the MBPP
worker/supervisor, MCP lifecycle, provider client, shared loop and adapter, writing
controlled tests, running live-provider development attempts and moulinette
validation, and updating documentation. Carlos must understand and defend these
changes. Recorded failures and measured usage are preserved; no evaluation pass
is claimed.
