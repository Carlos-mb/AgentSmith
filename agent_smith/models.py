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
    """Límites de una tarea completa; conservar el modelo y sus campos.

    Pseudocódigo pendiente:
    1. El adaptador crea límites del benchmark y los coloca en budget (agent_loop).
    2. El CLI toma started_at antes de leer JSON; deadline incluye preparación,
       bucle, peticiones/reintentos, MCP y limpieza, sin reinicios del reloj.
    3. Comprobar consumo acumulado antes/después de pedir API y antes de ejecutar
       o aceptar respuesta final. No confundir agotar con exceder el último paso.
    4. Mantener max_iterations configurable sin superar subject VI.1: MBPP
       10/6.000/1.500/120 s; SWE-bench 30/300.000/10.000/900 s. Coinciden con
       moulinette/moulinette/models.py. Su README conserva límites MBPP antiguos.
    5. No crea recursos. Las métricas incompletas se comunican como fallo explícito,
       no como ceros de consumo real; política en ProviderPool.complete.
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
