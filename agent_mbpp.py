"""Command-line entry point for the MBPP agent."""

import argparse
import sys
from pathlib import Path
from typing import Sequence

from agent_smith.io import load_model
from agent_smith.models import MBPPTaskInput


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


def main(argv: Sequence[str] | None = None) -> int:
    """Validate CLI input and report that real MBPP execution is still pending."""
    # Pseudocódigo para conectar el agente cuando sus partes estén implementadas:
    # 1. Al entrar, antes de parsear o leer JSON, tomar started_at=time.monotonic().
    #    Ese instante pasa al adaptador para incluir la preparación en el límite total.
    # 2. Conservar parse_arguments y load_model: sus validaciones ya funcionan.
    # 3. Sustituir únicamente el NotImplementedError por una llamada a
    #    asyncio.run(run_mbpp_agent(task, args, started_at=started_at)).
    #    Usar un solo asyncio.run para toda la tarea; el adaptador abre, utiliza y
    #    cierra MCP dentro de esa misma ejecución asíncrona. No hacerlo por paso.
    # 4. Recibir el SolutionOutput real y escribirlo con write_model(args.output,
    #    result), incluido un resultado de tarea fallida con sus métricas parciales.
    #    No escribir un resultado de ejemplo mientras la ejecución siga pendiente.
    # 5. Tras escribir, devolver 0 para indicar que el CLI produjo el resultado;
    #    result.success expresa si el agente finalizó. Devolver 1 ante errores que
    #    impiden cargar la tarea, iniciar el programa o escribir su salida.
    # 6. Mantener errores legibles por stderr sin secretos. Una interrupción debe
    #    dejar que el finally del adaptador cierre sus recursos antes de propagarse.
    args = parse_arguments(argv)

    try:
        task = load_model(args.task_file, MBPPTaskInput)
        raise NotImplementedError("MBPP agent execution is not implemented yet.")
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
