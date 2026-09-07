"""MCP server exposing the mandatory SWE-bench repository tools."""

from typing import Any

from mcp.server.fastmcp import FastMCP


mcp = FastMCP("Agent Smith SWE-bench tools")


@mcp.tool()
def read_file(filepath: str, start_line: int, end_line: int) -> str:
    """Read an inclusive file range with one-based line numbers.

    Pseudocode: delegate unchanged arguments to ``swebench_tools.read_file``.
    """
    raise NotImplementedError("The read_file MCP wrapper is not implemented yet.")


@mcp.tool()
def edit_file(filepath: str, old_str: str, new_str: str) -> str:
    """Replace one exact unique string and validate the resulting file.

    Pseudocode: delegate unchanged arguments to ``swebench_tools.edit_file``.
    """
    raise NotImplementedError("The edit_file MCP wrapper is not implemented yet.")


@mcp.tool()
def list_files(directory: str, pattern: str) -> list[str]:
    """List sorted files below an authorized directory using a glob pattern.

    Pseudocode: delegate unchanged arguments to ``swebench_tools.list_files``.
    """
    raise NotImplementedError("The list_files MCP wrapper is not implemented yet.")


@mcp.tool()
def search_code(pattern: str, file_pattern: str) -> str:
    """Search matching files and return absolute path, line, and content.

    Pseudocode: delegate unchanged arguments to ``swebench_tools.search_code``.
    """
    raise NotImplementedError("The search_code MCP wrapper is not implemented yet.")


@mcp.tool()
def search_function_or_class_definition_in_code(name: str) -> str:
    """Find function or class definitions for a Python identifier.

    Pseudocode: delegate the name to the same function in ``swebench_tools``.
    """
    raise NotImplementedError("The definition-search MCP wrapper is not implemented yet.")


@mcp.tool()
def find_references(name: str, filepath: str, line: int) -> str:
    """Find references to the symbol identified at a source location.

    Pseudocode: delegate unchanged arguments to ``swebench_tools.find_references``.
    """
    raise NotImplementedError("The find_references MCP wrapper is not implemented yet.")


@mcp.tool()
def run_tests() -> dict[str, Any]:
    """Run the exact SWE-bench evaluation script for the active task.

    Pseudocode: return ``swebench_tools.run_tests()`` without extra stdout.
    """
    raise NotImplementedError("The run_tests MCP wrapper is not implemented yet.")


@mcp.tool()
def get_patch() -> str:
    """Return the unified git diff for all task-repository changes.

    Pseudocode: return ``swebench_tools.get_patch()`` without transformation.
    """
    raise NotImplementedError("The get_patch MCP wrapper is not implemented yet.")


@mcp.tool()
def run_command(command: str, workdir: str) -> dict[str, Any]:
    """Run a bounded shell command in an authorized container directory.

    Pseudocode: delegate unchanged arguments to ``swebench_tools.run_command``.
    """
    raise NotImplementedError("The run_command MCP wrapper is not implemented yet.")


if __name__ == "__main__":
    mcp.run(transport="stdio")
