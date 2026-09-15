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
worker, process supervision, Python extraction, observations, MCP discovery and
wrappers through stdio and streamable HTTP, the interactive sandbox REPL, Docker
MBPP tests, configurable HTTP provider client, shared agent loop, and MBPP
adapter/CLI.

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

The SWE-bench tools and adapter are implemented: the tools pass the sandbox
exam's own test, and a controlled cycle test drives the real CLI, container, MCP
server and worker through exploration, an edit and `final_answer(get_patch())`.
All six tasks of the exam's pool pass moulinette with at least one model
([evidence](benchmark_runs/swebench_20260914/README.md)), and the model
comparison is in [BENCHMARK_REPORT.md](BENCHMARK_REPORT.md). Extraction takes a closed
```python block first and otherwise converts `<tool_call>` blocks into the
equivalent Python calls, telling the model in its observation that the call was
converted and executed. That conversion is not optional in practice: in a live
SWE-bench run the selected model switched to that dialect after its first
observation, and every later iteration produced nothing executable without it.
The subject's XML `<invoke>` and ReAct formats are still not handled; no model
used here has produced them.
Two validated MBPP tasks do not establish success on the full benchmark or the
security examination.

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
The first live MBPP validation is complete; SWE-bench follows.

### Why asyncio

`asyncio` is not a subject requirement; it is a consequence of the tool used to
speak MCP. The official `mcp` Python SDK (`ClientSession`, `stdio_client`,
`streamable_http_client`) exposes an async-only API: every connection is an
async context manager and every call (`initialize`, `list_tools`, `call_tool`)
is a coroutine. Reimplementing the MCP JSON-RPC protocol by hand would avoid
`asyncio`, but at the cost of rebuilding schema validation, pagination and the
streamable HTTP transport that the SDK already provides.

`asyncio` is confined to the coordinator task that owns the MCP session: setup,
every request, and cleanup happen in that single task, with no private SDK
thread and no event loop shared across components. The persistent worker that
executes generated Python and the sandbox itself stay fully synchronous; they
never receive an SDK session, an event loop or API keys. This keeps the async
surface to the smallest piece that actually needs it, instead of wrapping the
SDK in a synchronous facade with a dedicated thread, which would add
concurrency for no behavioural gain.

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

Each request sends the system prompt, the task and only the last three exchanges.
The whole list is resent every iteration, so keeping all of it costs quadratically:
one SWE-bench run spent 296,410 of its 300,000 input tokens that way, with a single
search observation accounting for 72,264 of them. With the window, thirty iterations
cost about 141,000 even if every observation hits its size cap. The window never
discards what the result file records: `steps` keeps every response and observation
in full. This follows the reference implementation, which trims to the same three
exchanges for both benchmarks. The two validated MBPP runs used four and two
iterations, below the window, so they are unaffected.

Tokens accumulate across the task, including reasoning tokens where applicable.
The loop must accumulate each request's metrics once. Total requests include
retries. Each solution must retain the full system prompt, raw model responses,
executed code and observations required by the public output contract.

The client selects one URL/model configuration, reads its named environment keys,
and rotates only those keys on HTTP 429. Retries are bounded by `max_retries`,
time and remaining tokens. A response without complete usage ends the task with
known subtotals and an explicit error; its unknown consumption is never reported
as a measured zero. A 429 is the exception: a rate-limited request is rejected
before the model generates anything, so its missing usage is a known zero. The
client advances the key index and retries with the next key, which is what makes
a second key useful at all; it never invents tokens for the rejected attempt.
Note that a provider's free-tier quota is usually per account, so extra keys on
the same account do not add quota. HTTP retry acceptance during the exam
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

`configs/models_template.json` contains nine explicitly selectable configurations,
chosen by cross-checking which models other passing projects reported against what the
free tiers still offer. Several models those reports relied on
(`openai/gpt-oss-120b:free`, `deepseek-v4-flash:free`, `glm-4.5-air:free`,
`qwen3-next-80b:free`) have since disappeared from OpenRouter's free tier.

Through Mistral's API, with `MISTRAL_API_KEY`:

- `codestral-2508` — **the SWE-bench model.** It scored 3/3 in the real
  `exam_swebench.sh`, including `sympy__sympy-14711`, and used less than half the
  tokens of `gemini-3.5-flash-lite` in the [benchmark report](BENCHMARK_REPORT.md).
  It stops at `<end_code>` and at `Observation:`; without the second stop it invented
  tool output until its token budget ran out (report section 5.4). On the free tier
  checked on 2026-09-15, `mistral-medium`, `mistral-small` and `devstral-medium` had a
  limit of zero requests per minute and `mistral-large` was not included.

Through Google's OpenAI-compatible endpoint, which has its own daily quota:

- `gemini-3.5-flash-lite` — **the first SWE-bench backup and the MBPP backup.** It
  passed 3/3 in the benchmark report, 2/3 twice in the real `exam_swebench.sh` (it has
  never passed `sympy__sympy-14711`) and 5/5 in the real `exam_mbpp.sh`.
- `gemini-3.1-flash-lite`, `gemini-3.5-flash` and `gemini-3.8-flash` — measured in the
  report and discarded.

Through OpenRouter, all on the free tier:

- `dots-studio/dots-3-note-preview:free` — **the second SWE-bench backup.** It passed
  3/3 in the report and passed `sympy__sympy-14711` once.
- `nvidia/nemotron-3.5-lightning:free` and `google/gemma-4-31b-it:free` — measured in
  the report and discarded (0/3).
- `inclusionai/ling-3.0-flash-vl:free` — **the MBPP model.** It validated tasks 396
  and 163 through moulinette and scored 5/5 twice in the real `exam_mbpp.sh`.

For the exam, pass `--model-name codestral-2508 --provider-url https://api.mistral.ai/v1`
to `exam_swebench.sh`, and `--model-name inclusionai/ling-3.0-flash-vl:free
--provider-url https://openrouter.ai/api/v1` to `exam_mbpp.sh`. The `.env` must contain
`AGENT_SMITH_MODELS_CONFIG=configs/models_template.json`, as `.env.example` does.

The three OpenRouter entries above declare no stop sequence because those models do not
support one. The client therefore only asks OpenRouter to honour parameters when a stop
sequence is actually configured; requesting it unconditionally would exclude them from
routing.

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

The MCP client supports stdio and streamable HTTP, dynamic discovery of tools,
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

The SWE-bench server exposes one command helper and the nine required tools:

- `read_file(filepath, start_line, end_line)`
- `edit_file(filepath, old_str, new_str)`
- `list_files(directory, pattern)`
- `search_code(pattern, file_pattern)`
- `search_function_or_class_definition_in_code(name)`
- `find_references(name, filepath, line)`
- `run_tests()`
- `get_patch()`
- `run_command(command, workdir)`

All nine run where the checkout lives. With `AGENT_SMITH_CONTAINER_ID` the helper
uses `docker exec` inside that task container; otherwise it works on the host
directory named by `TESTBED_PATH`, which is how the sandbox exam drives the tools.
Paths are always exchanged as `/testbed/...` and mapped onto the real root, so the
model sees the same layout either way and cannot reach outside it. `run_tests`
executes the supplied `eval_script`; `get_patch` returns the complete diff and is
never truncated. Reference search is textual and cannot reliably distinguish all
usages of symbols with the same name.

`SWEEnvironment` owns exactly one container per task: it makes the task image
available, runs it with `--network none` holding `/testbed`, and exports only the
container name, the eval script and the deadline to the MCP server.

The container's lifetime is tied to the agent's own standard input. It runs as
`docker run -i --rm ... cat`, holding the write end of that pipe. Closing the pipe
is what stops it, so a normal exit, a cancellation and a `kill -9` all remove the
container: the kernel closes the agent's descriptors, `cat` reaches end of input,
the container stops and `--rm` deletes it. A `finally` alone cannot survive SIGKILL,
which is why the container is not kept alive with `tail -f /dev/null`. Verified by
killing the real CLI mid-task and checking `docker ps`. `run_swebench_agent` reuses the same `run_agent_loop` as MBPP; only the
prompts, limits and resource lifecycle differ.

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
mutually exclusive `--mcp-stdio` and `--mcp-server` options. The sandbox opens
and closes its worker and optional MCP client in one asynchronous task:

```bash
uv run --offline --no-sync --python 3.10 sandbox
uv run --offline --no-sync --python 3.10 sandbox configs/sandbox_template.json
uv run --offline --no-sync --python 3.10 sandbox \
  --mcp-stdio "python mcp_tools_mbpp.py" configs/sandbox_template.json
uv run --offline --no-sync --python 3.10 sandbox \
  --mcp-server http://127.0.0.1:8000/mcp
```

Type Python code at the prompt. A block ends with a blank line, exactly as in the
standard Python REPL, so an `else`, `except` or `finally` clause stays in the same
entry. An exact `exit` at the main prompt or EOF closes the sandbox; on EOF a block
still being typed is executed first, which is what piping a file into the sandbox
needs. Entries share the
worker namespace. A fatal worker error restarts it and reports that variables
were lost. `final_answer` is printed and then the REPL continues.

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
uv run --offline --no-sync --python 3.10 python -m pytest tests/test_sandbox_cli.py tests/test_mcp_client.py
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

After adding the REPL and streamable HTTP transport, the full suite passed
**217 tests in 29.68 seconds** with the Python 3.10 command above. The HTTP test
starts a local FastMCP server, discovers an unknown tool, resource, resource
template and prompt, then calls them through the real worker wrappers. The REPL
tests cover multi-line input, persistence, syntax errors, EOF and recovery after
a lost worker. No live provider request or moulinette validation was run for this
change.

## Benchmark results and analysis

The [benchmark report](BENCHMARK_REPORT.md) compares nine models on the same
three SWE-bench tasks, with provider reliability, two intermediary metrics and
four ablations. `codestral-2508` is the selected model, with
`gemini-3.5-flash-lite` and `dots-studio/dots-3-note-preview:free` as backups on
two other providers.
Every figure is read from a `solution.json` kept under `benchmark_runs/`.

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