*This project has been created as part of the 42 curriculum by <login1>, <login2>.*

# Agent Smith

## Description

Pending: explain the project goal. Replace the login placeholders above.

## Instructions

Python 3.10 and uv are required. The agent CLIs currently write explicit
unimplemented results; they do not solve tasks. The sandbox CLI is still pending.
Complete the run instructions and usable free-provider/model configurations.
The files in `configs/` are templates; the example provider is not a real endpoint.

The planned adapters read optional `AGENT_SMITH_MODELS_CONFIG` and
`AGENT_SMITH_SANDBOX_CONFIG` paths, while keeping the current CLI arguments.
API keys come from external environment variables; never commit their values.
Select only verified free quotas; paid plans, purchased credits and billing-enabled
accounts are outside the subject. This review made no model API calls.
Until the exam's retry wording is clarified, use `max_retries=0` for examination.

## System architecture

Pending: describe the shared loop, thin benchmark adapters, separate sandbox
worker, MCP client and independent tool servers. Spanish implementation steps
remain inside the unfinished functions, with their `NotImplementedError` intact.

## Agent loop

Pending: implement cumulative budgets, key rotation, complete usage accounting
and real observations. Only Python extraction currently works; add and test the
additional response formats required by the models actually compared.

## Sandbox design

Pending: implement the Linux worker's filesystem/network isolation, restricted
imports/builtins, memory/time limits, persistent variables and interactive REPL.
The proposed user/mount/network namespaces still need full isolation tests in
the target environment. Running MBPP tests in Docker does not implement this sandbox.

## Tool implementation details

MBPP `run_tests` is implemented. The nine SWE-bench tools, general MCP client,
streamable HTTP integration and dynamic sandbox wrappers remain pending.
The local MCP test currently checks discovery; real invocation also needs testing.

## Benchmark results and analysis

Pending: complete `BENCHMARK_REPORT.md` and include its real backing
`solution.json` files. No model benchmark results have been produced in this review.

## Resources

Pending: add technical references and describe AI assistance by task and file.
This review edited pending pseudocode and small MBPP timeout/JSON input diagnostics; it
did not implement the unfinished agent or run model benchmarks.
