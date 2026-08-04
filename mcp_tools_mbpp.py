"""MCP server that exposes the tools required by the MBPP agent."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from agent_smith.mbpp_tools import run_mbpp_tests


mcp = FastMCP("Agent Smith MBPP tools")


@mcp.tool()
def run_tests(
    code: str,
    test_imports: list[str],
    test_list: list[str],
    timeout_seconds: int = 10,
) -> dict[str, Any]:
    """Run a candidate Python solution against the public MBPP tests.

    Args:
        code: Complete Python solution proposed for the task.
        test_imports: Import statements supplied with the MBPP task.
        test_list: Public assertion statements supplied with the MBPP task.
        timeout_seconds: Maximum time allowed for this test execution.

    Returns:
        A dictionary containing success, message, output, and exit_code.
    """
    return run_mbpp_tests(
        code=code,
        test_imports=test_imports,
        test_list=test_list,
        timeout_seconds=timeout_seconds,
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
