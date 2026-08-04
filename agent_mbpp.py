"""Command-line entry point for the MBPP agent."""

import argparse
import sys
from pathlib import Path
from typing import Sequence

from agent_smith.io import load_model, write_model
from agent_smith.models import MBPPTaskInput, SolutionOutput


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse MBPP command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Solve one MBPP task and write a solution JSON file."
    )
    parser.add_argument(
        "--task-file",
        required=True,
        type=Path,
        help="Path to the MBPP task JSON file.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Path where the solution JSON file will be written.",
    )
    parser.add_argument(
        "--model-name",
        required=True,
        help="Name of the LLM model to use.",
    )
    parser.add_argument(
        "--provider-url",
        required=True,
        help="Base URL of the LLM provider API.",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=10,
        help="Maximum number of agent iterations. Default: 10.",
    )
    return parser.parse_args(argv)


def build_pending_result(task: MBPPTaskInput) -> SolutionOutput:
    """Build a valid temporary result before the MBPP agent exists."""
    return SolutionOutput(
        task_id=str(task.task_id),
        benchmark="mbpp",
        success=False,
        solution="",
        system_prompt="",
        iterations=0,
        total_requests=0,
        total_input_tokens=0,
        total_output_tokens=0,
        total_time_seconds=0.0,
        error="MBPP agent execution is not implemented yet.",
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Load an MBPP task and write its solution output file."""
    args = parse_arguments(argv)

    try:
        task = load_model(args.task_file, MBPPTaskInput)

        # This temporary line will be replaced with: result = run_mbpp_agent(task, args)
        result = build_pending_result(task)

        write_model(args.output, result)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
