*This project has been created as part of the 42 curriculum by cmelero-.*

# Agent Smith

## Description

Agent Smith is a Python project for an autonomous code agent. It targets MBPP,
which contains small Python programming tasks, and SWE-bench, which requires
patches for issues in real repositories.

The intended agent follows `Thought -> Code -> Observation`: an LLM proposes
Python code, a separate worker executes it, and the agent uses the observed result
to decide its next step. The complete agent is still pending.

## Current status

The source currently contains these implemented pieces:

- Public Pydantic task, configuration, step and solution models, with JSON helpers.
- MBPP, SWE-bench and sandbox CLI argument parsing.
- Python code extraction and observation formatting.
- Import allowlist matching and the data declarations `SandboxExecution` and
  `FinalAnswerSignal`.
- MCP connection configuration and formatting of a discovered MCP manual.
- The MBPP `run_tests` helper and its stdio MCP server, which run public tests
  in Docker and distinguish test failures from execution or cleanup errors.

The sandbox configuration loader, callable `final_answer`, worker, execution
controls, MCP session operations and wrappers, sandbox CLI entry point and REPL,
provider requests, common agent loop and SWE-bench execution still contain
`NotImplementedError`. Their docstrings describe the intended behavior in
English, and detailed Spanish pseudocode explains the implementation steps.
These stubs are not working features. The benchmark entry points report that
execution is pending instead of writing invented solution results.

Existing tests cover several implemented components and include fixed-candidate
MCP/Docker integration probes. Those probes do not exercise the complete agent
or prove that the sandbox is safe. Historical test counts are not evidence for
the current source; record the interpreter, selected files and result for each
new test run. No benchmark result is claimed here.

## System architecture

The planned execution has three separate processes:

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

The same agent loop serves both benchmarks. Each benchmark adapter supplies its
task description, tools and limits, then calls that loop. The first implementation
milestone is one complete MBPP task; MCP/REPL and SWE-bench follow.

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

Provider integration is pending. The planned client uses one active compatible
provider configuration, an API key list and bounded key rotation. Keys come from
environment variables or local configuration. Free access and current conditions
must be verified before selecting a provider; this README does not endorse a
provider or claim that any model is currently free.

## Sandbox design

The first version plans standard-library controls for imports, explicit builtins,
file opening, exposed network entry points, worker memory, execution time and
output. The existing import helpers will be reused. The next implementation block
is resolving allowed paths and creating controlled file opening.

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

These planned controls do not establish resistance to hostile Python, and the
complete worker is not implemented yet. Passing the subject's security evaluation
remains uncertain. Development with generated or unknown code requires a separate
disposable environment without personal files or credentials. Landlock, Linux
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
already exists; integration with the complete task deadline remains pending.

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
does not yet launch a functioning agent or REPL. The sandbox parser can be tested
independently, but `sandbox_cli.main` remains a stub, so `uv run sandbox --help`
does not work yet. The planned sandbox CLI owner will open and close MCP itself,
and lend that session to the supervisor for the REPL.

Run tests for the block being changed. For the retained import helpers:

```bash
uv run --offline --no-sync --python 3.10 python -m pytest tests/test_sandbox_imports.py
```

When working in the Git checkout, also run `git diff --check`. Reserve the complete
suite for integration work. Docker tests need a Docker daemon and the configured
image; do not run generated or unknown candidates on the host.

The available moulinette includes public models and benchmark validation code.
The three `exam_*.sh` scripts are absent from the supplied checkout. Local tests
and moulinette validation are distinct from the full examination, including its
mandatory sandbox and tool checks.

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

AI assistance in the current review covers inspection of the code and supplied
requirements, removal of obsolete scaffolding, detailed implementation pseudocode,
English docstrings and documentation consistency. This review does not implement
the pending features or supply benchmark measurements. The author must complete
and understand the implementation and maintain an accurate account of further AI
assistance before submission.
