"""Pydantic models used by the Agent Smith command-line programs."""

from datetime import datetime

from pydantic import BaseModel, Field


def current_timestamp() -> str:
    """Return the current local date and time in ISO 8601 format."""
    return datetime.now().isoformat()


class StepMetrics(BaseModel):
    """Metrics collected during one agent iteration."""

    step: int = Field(..., description="1-indexed iteration number")
    input_tokens: int = Field(..., description="Tokens sent to the LLM")
    output_tokens: int = Field(..., description="Tokens returned by the LLM")
    request_time_ms: float = Field(..., description="LLM request time in milliseconds")
    api_url: str = Field(default="", description="LLM provider base URL")
    model_name: str = Field(default="", description="LLM model name")
    llm_output: str = Field(default="", description="Raw LLM response")
    sandbox_input: str = Field(default="", description="Code sent to the sandbox")
    sandbox_output: str = Field(default="", description="Sandbox execution result")
    retries: int = Field(default=0, description="Retries used for this request")
    timestamp: str = Field(default_factory=current_timestamp)


class SolutionOutput(BaseModel):
    """Result written by an MBPP or SWE-bench agent."""

    task_id: str
    benchmark: str
    success: bool
    solution: str
    system_prompt: str = ""
    iterations: int
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_time_seconds: float
    steps: list[StepMetrics] = Field(default_factory=list)
    error: str | None = None
    timestamp: str = Field(default_factory=current_timestamp)


class SandboxConfig(BaseModel):
    """Configuration for sandbox restrictions and resource limits."""

    authorized_imports: list[str] = Field(
        default_factory=lambda: [
            "math",
            "math.*",
            "collections",
            "collections.*",
            "itertools",
            "re",
            "json",
            "typing",
            "typing.*",
            "functools",
            "operator",
            "heapq",
            "bisect",
            "copy",
            "string",
            "random",
            "datetime",
            "datetime.*",
            "array",
            "cmath",
        ]
    )
    allowed_directories: list[str] = Field(
        default_factory=lambda: ["/testbed", "/tmp/agent"]
    )
    max_execution_time_seconds: int = 30
    max_memory_mb: int = 512


class AgentLimits(BaseModel):
    """Hard limits applied to one complete agent run.

    Pseudocode:
        - Build one instance with the limits for the selected benchmark.
        - Check the elapsed time before every provider request and execution.
        - Check cumulative tokens after every provider response.
        - Stop with a valid failed ``SolutionOutput`` when any limit is reached.

    The current subject and executable moulinette agree on 10 iterations,
    6,000 input tokens, 1,500 output tokens, and 120 seconds for MBPP; and
    30 iterations, 300,000 input tokens, 10,000 output tokens, and 900 seconds
    for SWE-bench.
    """

    max_iterations: int = Field(..., gt=0)
    max_input_tokens: int = Field(..., ge=0)
    max_output_tokens: int = Field(..., ge=0)
    max_time_seconds: float = Field(..., gt=0)


class MBPPTaskInput(BaseModel):
    """Input data for one MBPP task."""

    task_id: int
    task_definition: str
    function_definition: str
    test_imports: list[str] = Field(default_factory=list)
    test_list: list[str] = Field(default_factory=list)


class SWEBenchTaskInput(BaseModel):
    """Input data for one SWE-bench task."""

    instance_id: str
    problem_statement: str
    docker_image: str
    eval_script: str
    hints_text: str = ""
    repo: str = ""
