"""MCP server exposing the mandatory SWE-bench repository tools."""

from typing import Any

from mcp.server.fastmcp import FastMCP


mcp = FastMCP("Agent Smith SWE-bench tools")


@mcp.tool()
def read_file(filepath: str, start_line: int, end_line: int) -> str:
    """Recibir ruta/rango; devolver líneas numeradas del helper.

    Pseudocódigo pendiente:
    1. Delegar los argumentos sin cambios a swebench_tools.read_file.
    2. Devolver su resultado intacto; errores ordinarios pasan al SDK como errores
       MCP. No suprimir KeyboardInterrupt/SystemExit.
    3. No abrir Docker aquí; el helper libera sus recursos. Ningún print de
       depuración en stdout del servidor stdio.
    """
    raise NotImplementedError("The read_file MCP wrapper is not implemented yet.")


@mcp.tool()
def edit_file(filepath: str, old_str: str, new_str: str) -> str:
    """Recibir ruta y textos; devolver feedback de edición, sintaxis y lint.

    La coincidencia única es política nuestra; subject V.5.1 no fija multiplicidad.

    Pseudocódigo pendiente:
    1. Delegar los argumentos sin cambios a swebench_tools.edit_file.
    2. Devolver su resultado intacto; errores ordinarios pasan al SDK como errores
       MCP. No suprimir KeyboardInterrupt/SystemExit.
    3. No abrir Docker aquí; el helper libera sus recursos. Ningún print de
       depuración en stdout del servidor stdio.
    """
    raise NotImplementedError("The edit_file MCP wrapper is not implemented yet.")


@mcp.tool()
def list_files(directory: str, pattern: str) -> list[str]:
    """Recibir directorio/glob; devolver lista de rutas ordenadas.

    Pseudocódigo pendiente:
    1. Delegar los argumentos sin cambios a swebench_tools.list_files.
    2. Devolver su resultado intacto; errores ordinarios pasan al SDK como errores
       MCP. No suprimir KeyboardInterrupt/SystemExit.
    3. No abrir Docker aquí; el helper libera sus recursos. Ningún print de
       depuración en stdout del servidor stdio.
    """
    raise NotImplementedError("The list_files MCP wrapper is not implemented yet.")


@mcp.tool()
def search_code(pattern: str, file_pattern: str) -> str:
    """Recibir patrón/filtro; devolver coincidencias con ruta y línea.

    Pseudocódigo pendiente:
    1. Delegar los argumentos sin cambios a swebench_tools.search_code.
    2. Devolver su resultado intacto; errores ordinarios pasan al SDK como errores
       MCP. No suprimir KeyboardInterrupt/SystemExit.
    3. No abrir Docker aquí; el helper libera sus recursos. Ningún print de
       depuración en stdout del servidor stdio.
    """
    raise NotImplementedError("The search_code MCP wrapper is not implemented yet.")


@mcp.tool()
def search_function_or_class_definition_in_code(name: str) -> str:
    """Recibir nombre; devolver definiciones candidatas con ruta y línea.

    Pseudocódigo pendiente:
    1. Delegar name a search_function_or_class_definition_in_code del módulo
       swebench_tools, sin transformarlo.
    2. Devolver su resultado intacto; errores ordinarios pasan al SDK como errores
       MCP. No suprimir KeyboardInterrupt/SystemExit.
    3. No abrir Docker aquí; el helper libera sus recursos. Ningún print de
       depuración en stdout del servidor stdio.
    """
    raise NotImplementedError("The definition-search MCP wrapper is not implemented yet.")


@mcp.tool()
def find_references(name: str, filepath: str, line: int) -> str:
    """Recibir nombre, archivo y línea; devolver usos candidatos y limitaciones.

    La búsqueda textual propuesta no garantiza resolver todos los símbolos.

    Pseudocódigo pendiente:
    1. Delegar los argumentos sin cambios a swebench_tools.find_references.
    2. Devolver su resultado intacto; errores ordinarios pasan al SDK como errores
       MCP. No suprimir KeyboardInterrupt/SystemExit.
    3. No abrir Docker aquí; el helper libera sus recursos. Ningún print de
       depuración en stdout del servidor stdio.
    """
    raise NotImplementedError("The find_references MCP wrapper is not implemented yet.")


@mcp.tool()
def run_tests() -> dict[str, Any]:
    """Sin argumentos; devolver salida real del eval_script, sin deducir éxito.

    Pseudocódigo pendiente:
    1. Delegar los argumentos sin cambios a swebench_tools.run_tests.
    2. Devolver su resultado intacto; errores ordinarios pasan al SDK como errores
       MCP. No suprimir KeyboardInterrupt/SystemExit.
    3. No abrir Docker aquí; el helper libera sus recursos. Ningún print de
       depuración en stdout del servidor stdio.
    """
    raise NotImplementedError("The run_tests MCP wrapper is not implemented yet.")


@mcp.tool()
def get_patch() -> str:
    """Sin argumentos; devolver diff íntegro, incluida cadena vacía.

    Pseudocódigo pendiente:
    1. Delegar los argumentos sin cambios a swebench_tools.get_patch.
    2. Devolver su resultado intacto; errores ordinarios pasan al SDK como errores
       MCP. No suprimir KeyboardInterrupt/SystemExit.
    3. No abrir Docker aquí; el helper libera sus recursos. Ningún print de
       depuración en stdout del servidor stdio.
    """
    raise NotImplementedError("The get_patch MCP wrapper is not implemented yet.")


@mcp.tool()
def run_command(command: str, workdir: str) -> dict[str, Any]:
    """Recibir command/workdir; devolver stdout, stderr, exit_code y timed_out.

    Pseudocódigo pendiente:
    1. Delegar los argumentos sin cambios a swebench_tools.run_command.
    2. Devolver su resultado intacto; errores ordinarios pasan al SDK como errores
       MCP. No suprimir KeyboardInterrupt/SystemExit.
    3. No abrir Docker aquí; el helper libera sus recursos. Ningún print de
       depuración en stdout del servidor stdio.
    """
    raise NotImplementedError("The run_command MCP wrapper is not implemented yet.")


if __name__ == "__main__":
    mcp.run(transport="stdio")
