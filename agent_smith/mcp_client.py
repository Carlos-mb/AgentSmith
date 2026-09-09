"""MCP connection configuration and manual generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse


@dataclass
class MCPManual:
    """Discovered MCP capabilities and the manual shown to the model."""

    instructions: str
    tools: list[dict[str, Any]]
    resources: list[dict[str, Any]]
    resource_templates: list[dict[str, Any]]
    prompts: list[dict[str, Any]]

    def as_text(self) -> str:
        """Return the MCP manual as text."""

        lines = []

        if self.instructions:
            lines.append("SERVER INSTRUCTIONS")
            lines.append(self.instructions)
            lines.append("")

        lines.append("TOOLS")

        for tool in sorted(self.tools, key=lambda item: item.get("name", "")):
            name = tool.get("name", "")
            description = tool.get("description", "")
            schema = tool.get("inputSchema", {})
            properties = schema.get("properties", {})
            required = schema.get("required", [])

            lines.append("")
            lines.append("Tool: " + name)

            if description:
                lines.append("Description: " + description)

            lines.append("Parameters:")

            for parameter_name, parameter in properties.items():
                parameter_type = parameter.get("type", "unknown")

                line = "- " + parameter_name + ": " + str(parameter_type)

                if parameter_name in required:
                    line += " (required)"
                else:
                    line += " (optional)"

                if "default" in parameter:
                    line += ", default=" + repr(parameter["default"])

                lines.append(line)
            if not name.isidentifier() or name in {
                                                    "final_answer",
                                                    "mcp_call_tool",
                                                    "read_resource",
                                                    "get_prompt",
                                                }:
                lines.append(
                    "Call with mcp_call_tool(name, arguments)."
                )

        lines.append("")
        lines.append("RESOURCES")
        lines.append("Use read_resource(uri).")

        for resource in sorted(
            self.resources,
            key=lambda item: item.get("name", ""),
        ):
            lines.append(
                "- "
                + resource.get("name", "")
                + ": "
                + str(resource.get("uri", ""))
            )

        lines.append("")
        lines.append("RESOURCE TEMPLATES")

        for template in sorted(
            self.resource_templates,
            key=lambda item: item.get("name", ""),
        ):
            lines.append(
                "- "
                + template.get("name", "")
                + ": "
                + str(template.get("uriTemplate", ""))
            )

        lines.append("")
        lines.append("PROMPTS")
        lines.append("Use get_prompt(name, arguments).")

        for prompt in sorted(
            self.prompts,
            key=lambda item: item.get("name", ""),
        ):
            lines.append("- " + prompt.get("name", ""))

        lines.append("")
        lines.append(
            "final_answer is provided by the sandbox "
            "and is never replaced by an MCP tool."
        )
        return "\n".join(lines)


class MCPClient:
    """Store MCP configuration without opening a connection.

    Connection management and SDK operations are not implemented yet.
    """

    def __init__(
        self,
        *,
        stdio_command: Sequence[str] | None = None,
        server_url: str | None = None,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        """Validate the transport and keep independent configuration copies."""

        if stdio_command is not None and server_url is not None:
            raise ValueError("Exactly one MCP transport must be provided.")

        if stdio_command is None and server_url is None:
            raise ValueError("Exactly one MCP transport must be provided.")

        self.stdio_command: list[str] | None = None
        self.server_url: str | None = None

        if stdio_command is not None:
            if isinstance(stdio_command, (str, bytes)):
                raise ValueError(
                    "stdio_command must be a sequence of arguments."
                )

            if not isinstance(stdio_command, Sequence):
                raise ValueError(
                    "stdio_command must be a sequence of arguments."
                )

            if not stdio_command:
                raise ValueError("stdio_command cannot be empty.")

            for argument in stdio_command:
                if not isinstance(argument, str):
                    raise ValueError("All stdio arguments must be strings.")

            if not stdio_command[0].strip():
                raise ValueError("The stdio executable cannot be empty.")

            self.stdio_command = list(stdio_command)

        else:
            if not isinstance(server_url, str):
                raise ValueError("server_url must be a string.")

            parsed_url = urlparse(server_url)

            if (
                parsed_url.scheme not in ("http", "https")
                or not parsed_url.netloc
            ):
                raise ValueError(
                    "server_url must be a valid HTTP or HTTPS URL."
                )

            self.server_url = server_url

        self.environment = (
            dict(environment) if environment is not None else {}
        )
