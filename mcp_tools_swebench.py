"""MCP server exposing the mandatory SWE-bench repository tools."""

from typing import Any

from mcp.server.fastmcp import FastMCP


mcp = FastMCP("Agent Smith SWE-bench tools")


@mcp.tool()
def read_file(filepath: str, start_line: int, end_line: int) -> str:
    """Read an inclusive range as numbered lines from the task repository.

    Pending implementation. Ordinary tool errors are reported by the MCP SDK.
    """
    # Pseudocódigo detallado:
    # 1. Al implementarlo, importar agent_smith.swebench_tools en este módulo.
    #    Conservar este decorador @mcp.tool y esta firma: el SDK obtiene de ellos
    #    el nombre, los argumentos y el docstring en inglés del manual dinámico.
    # 2. Llamar swebench_tools.read_file con los argumentos
    #    recibidos (filepath, start_line, end_line), sin renombrarlos ni transformarlos.
    # 3. Devolver su resultado intacto. La lógica y los recursos Docker pertenecen
    #    a swebench_tools; no abrir otro cliente ni duplicar su validación aquí.
    # 4. Dejar que los errores ordinarios lleguen al SDK para formar el error MCP.
    #    No ocultar NotImplementedError, KeyboardInterrupt ni SystemExit.
    # 5. No imprimir mensajes de depuración en stdout: es el transporte stdio.
    raise NotImplementedError("The read_file MCP wrapper is not implemented yet.")


@mcp.tool()
def edit_file(filepath: str, old_str: str, new_str: str) -> str:
    """Replace one exact occurrence and report syntax and lint diagnostics.

    Pending implementation. Zero or multiple matches are rejected before
    writing; the subject does not specify this local multiplicity policy.
    """
    # Pseudocódigo detallado:
    # 1. Al implementarlo, importar agent_smith.swebench_tools en este módulo.
    #    Conservar este decorador @mcp.tool y esta firma: el SDK obtiene de ellos
    #    el nombre, los argumentos y el docstring en inglés del manual dinámico.
    # 2. Llamar swebench_tools.edit_file con los argumentos
    #    recibidos (filepath, old_str, new_str), sin renombrarlos ni transformarlos.
    # 3. Devolver su resultado intacto. La lógica y los recursos Docker pertenecen
    #    a swebench_tools; no abrir otro cliente ni duplicar su validación aquí.
    # 4. Dejar que los errores ordinarios lleguen al SDK para formar el error MCP.
    #    No ocultar NotImplementedError, KeyboardInterrupt ni SystemExit.
    # 5. No imprimir mensajes de depuración en stdout: es el transporte stdio.
    raise NotImplementedError("The edit_file MCP wrapper is not implemented yet.")


@mcp.tool()
def list_files(directory: str, pattern: str) -> list[str]:
    """List matching repository files as sorted absolute POSIX paths.

    Pending implementation. Ordinary tool errors are reported by the MCP SDK.
    """
    # Pseudocódigo detallado:
    # 1. Al implementarlo, importar agent_smith.swebench_tools en este módulo.
    #    Conservar este decorador @mcp.tool y esta firma: el SDK obtiene de ellos
    #    el nombre, los argumentos y el docstring en inglés del manual dinámico.
    # 2. Llamar swebench_tools.list_files con los argumentos
    #    recibidos (directory, pattern), sin renombrarlos ni transformarlos.
    # 3. Devolver su resultado intacto. La lógica y los recursos Docker pertenecen
    #    a swebench_tools; no abrir otro cliente ni duplicar su validación aquí.
    # 4. Dejar que los errores ordinarios lleguen al SDK para formar el error MCP.
    #    No ocultar NotImplementedError, KeyboardInterrupt ni SystemExit.
    # 5. No imprimir mensajes de depuración en stdout: es el transporte stdio.
    raise NotImplementedError("The list_files MCP wrapper is not implemented yet.")


@mcp.tool()
def search_code(pattern: str, file_pattern: str) -> str:
    """Search repository text as '/absolute/path:<line> <content>' matches.

    Pending implementation. Ordinary tool errors are reported by the MCP SDK.
    """
    # Pseudocódigo detallado:
    # 1. Al implementarlo, importar agent_smith.swebench_tools en este módulo.
    #    Conservar este decorador @mcp.tool y esta firma: el SDK obtiene de ellos
    #    el nombre, los argumentos y el docstring en inglés del manual dinámico.
    # 2. Llamar swebench_tools.search_code con los argumentos
    #    recibidos (pattern, file_pattern), sin renombrarlos ni transformarlos.
    # 3. Devolver su resultado intacto. La lógica y los recursos Docker pertenecen
    #    a swebench_tools; no abrir otro cliente ni duplicar su validación aquí.
    # 4. Dejar que los errores ordinarios lleguen al SDK para formar el error MCP.
    #    No ocultar NotImplementedError, KeyboardInterrupt ni SystemExit.
    # 5. No imprimir mensajes de depuración en stdout: es el transporte stdio.
    raise NotImplementedError("The search_code MCP wrapper is not implemented yet.")


@mcp.tool()
def search_function_or_class_definition_in_code(name: str) -> str:
    """Find candidate Python definitions with the standard search format.

    Pending implementation. The initial search is textual and may also match
    apparent definitions inside multiline strings.
    """
    # Pseudocódigo detallado:
    # 1. Al implementarlo, importar agent_smith.swebench_tools en este módulo.
    #    Conservar este decorador @mcp.tool y esta firma: el SDK obtiene de ellos
    #    el nombre, los argumentos y el docstring en inglés del manual dinámico.
    # 2. Llamar swebench_tools.search_function_or_class_definition_in_code con los argumentos
    #    recibidos (name), sin renombrarlos ni transformarlos.
    # 3. Devolver su resultado intacto. La lógica y los recursos Docker pertenecen
    #    a swebench_tools; no abrir otro cliente ni duplicar su validación aquí.
    # 4. Dejar que los errores ordinarios lleguen al SDK para formar el error MCP.
    #    No ocultar NotImplementedError, KeyboardInterrupt ni SystemExit.
    # 5. No imprimir mensajes de depuración en stdout: es el transporte stdio.
    raise NotImplementedError("The definition-search MCP wrapper is not implemented yet.")


@mcp.tool()
def find_references(name: str, filepath: str, line: int) -> str:
    """Find textual usage candidates anchored at a file and line.

    Pending implementation. Equal names may refer to different symbols and
    aliases may be missed; this is not complete semantic reference analysis.
    """
    # Pseudocódigo detallado:
    # 1. Al implementarlo, importar agent_smith.swebench_tools en este módulo.
    #    Conservar este decorador @mcp.tool y esta firma: el SDK obtiene de ellos
    #    el nombre, los argumentos y el docstring en inglés del manual dinámico.
    # 2. Llamar swebench_tools.find_references con los argumentos
    #    recibidos (name, filepath, line), sin renombrarlos ni transformarlos.
    # 3. Devolver su resultado intacto. La lógica y los recursos Docker pertenecen
    #    a swebench_tools; no abrir otro cliente ni duplicar su validación aquí.
    # 4. Dejar que los errores ordinarios lleguen al SDK para formar el error MCP.
    #    No ocultar NotImplementedError, KeyboardInterrupt ni SystemExit.
    # 5. No imprimir mensajes de depuración en stdout: es el transporte stdio.
    raise NotImplementedError("The find_references MCP wrapper is not implemented yet.")


@mcp.tool()
def run_tests() -> dict[str, Any]:
    """Execute the task-supplied evaluation script and return its real output.

    Pending implementation. Ordinary tool errors are reported by the MCP SDK.
    """
    # Pseudocódigo detallado:
    # 1. Al implementarlo, importar agent_smith.swebench_tools en este módulo.
    #    Conservar este decorador @mcp.tool y esta firma: el SDK obtiene de ellos
    #    el nombre, los argumentos y el docstring en inglés del manual dinámico.
    # 2. Llamar swebench_tools.run_tests() sin argumentos; el helper
    #    obtiene el contexto de tarea del entorno privado del servidor MCP.
    # 3. Devolver su resultado intacto. La lógica y los recursos Docker pertenecen
    #    a swebench_tools; no abrir otro cliente ni duplicar su validación aquí.
    # 4. Dejar que los errores ordinarios lleguen al SDK para formar el error MCP.
    #    No ocultar NotImplementedError, KeyboardInterrupt ni SystemExit.
    # 5. No imprimir mensajes de depuración en stdout: es el transporte stdio.
    #    No deducir success por el código de salida ni por texto como "passed".
    raise NotImplementedError("The run_tests MCP wrapper is not implemented yet.")


@mcp.tool()
def get_patch() -> str:
    """Return the full, unmodified git diff, including an empty result.

    Pending implementation. Ordinary tool errors are reported by the MCP SDK.
    """
    # Pseudocódigo detallado:
    # 1. Al implementarlo, importar agent_smith.swebench_tools en este módulo.
    #    Conservar este decorador @mcp.tool y esta firma: el SDK obtiene de ellos
    #    el nombre, los argumentos y el docstring en inglés del manual dinámico.
    # 2. Llamar swebench_tools.get_patch() sin argumentos; el helper
    #    obtiene el contexto de tarea del entorno privado del servidor MCP.
    # 3. Devolver su resultado intacto. La lógica y los recursos Docker pertenecen
    #    a swebench_tools; no abrir otro cliente ni duplicar su validación aquí.
    # 4. Dejar que los errores ordinarios lleguen al SDK para formar el error MCP.
    #    No ocultar NotImplementedError, KeyboardInterrupt ni SystemExit.
    # 5. No imprimir mensajes de depuración en stdout: es el transporte stdio.
    #    No truncar, hacer strip ni añadir texto al diff al devolverlo por MCP.
    raise NotImplementedError("The get_patch MCP wrapper is not implemented yet.")


@mcp.tool()
def run_command(command: str, workdir: str) -> dict[str, Any]:
    """Return stdout, stderr, exit_code, and timed_out for a container command.

    Pending implementation. Ordinary tool errors are reported by the MCP SDK.
    """
    # Pseudocódigo detallado:
    # 1. Al implementarlo, importar agent_smith.swebench_tools en este módulo.
    #    Conservar este decorador @mcp.tool y esta firma: el SDK obtiene de ellos
    #    el nombre, los argumentos y el docstring en inglés del manual dinámico.
    # 2. Llamar swebench_tools.run_command con los argumentos
    #    recibidos (command, workdir), sin renombrarlos ni transformarlos.
    # 3. Devolver su resultado intacto. La lógica y los recursos Docker pertenecen
    #    a swebench_tools; no abrir otro cliente ni duplicar su validación aquí.
    # 4. Dejar que los errores ordinarios lleguen al SDK para formar el error MCP.
    #    No ocultar NotImplementedError, KeyboardInterrupt ni SystemExit.
    # 5. No imprimir mensajes de depuración en stdout: es el transporte stdio.
    raise NotImplementedError("The run_command MCP wrapper is not implemented yet.")


if __name__ == "__main__":
    mcp.run(transport="stdio")
