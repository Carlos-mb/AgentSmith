"""MCP connection configuration and manual generation."""

from __future__ import annotations

from agent_smith.logging_config import LOG_LEVEL_ENV, get_logger

from contextlib import AsyncExitStack
from datetime import timedelta
import keyword
import logging
import builtins
import os
import sys
import time

import anyio
from dataclasses import dataclass
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client
from mcp.types import PaginatedRequestParams

logger = get_logger('agent_smith.mcp_client')


@dataclass
class MCPManual:
    """Store discovered MCP metadata and render the model's tool manual.

    All lists contain JSON-compatible dictionaries supplied by the MCP SDK.
    This object owns no connection and never validates or executes tool calls.
    """

    instructions: str
    tools: list[dict[str, Any]]
    resources: list[dict[str, Any]]
    resource_templates: list[dict[str, Any]]
    prompts: list[dict[str, Any]]

    def as_text(self) -> str:
        """Render instructions, tool parameters, resources, and prompt names.

        Tools are sorted by name; parameter order follows each input schema.
        The sandbox supplies the local final_answer function independently.
        """
        logger.debug("Entrando en MCPManual.as_text")
        logger.debug(
            "Generando manual: herramientas=%s, recursos=%s, plantillas=%s, "
            "prompts=%s",
            len(self.tools), len(self.resources),
            len(self.resource_templates), len(self.prompts),
        )

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
            if (not name.isidentifier() or keyword.iskeyword(name)
                    or hasattr(builtins, name) or name in {
                        "final_answer", "mcp_call_tool", "read_resource",
                        "get_prompt", "__name__",
                    }):
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
        manual = "\n".join(lines)
        logger.debug("Manual MCP generado: %s caracteres", len(manual))
        return manual


class MCPClient:
    """Open and close MCP in the same asynchronous task as its caller."""

    def __init__(
        self,
        *,
        stdio_command: Sequence[str] | None = None,
        server_url: str | None = None,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        """Validate one transport and copy its configuration without I/O.

        Accept a stdio argument sequence or an HTTP(S) server URL, exclusively.
        The environment mapping is reserved for the separate MCP server.
        Invalid configuration raises ValueError before any connection exists.
        """
        logger.debug("Entrando en MCPClient.__init__")

        if stdio_command is not None and server_url is not None:
            raise ValueError("Exactly one MCP transport must be provided.")

        if stdio_command is None and server_url is None:
            raise ValueError("Exactly one MCP transport must be provided.")

        self.stdio_command: list[str] | None = None
        self.server_url: str | None = None

        if stdio_command is not None:
            if not stdio_command:
                raise ValueError("stdio_command cannot be empty.")

            if not stdio_command[0].strip():
                raise ValueError("The stdio executable cannot be empty.")

            self.stdio_command = list(stdio_command)

        else:
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

        self._stack = None
        self._session = None
        logger.debug("Configuración MCP preparada: transporte=%s",
                     "stdio" if self.stdio_command else "HTTP")

    async def start(
        self, *, deadline: float | None = None,
    ) -> tuple[ClientSession, MCPManual]:
        """Open the transport and discover its capabilities with the SDK."""
        logger.debug("Entrando en MCPClient.start")
        logger.info("Abriendo MCP y solicitando capacidades al servidor")
        if self._stack is not None:
            raise RuntimeError("MCP client is already started.")
        remaining = 30.0 if deadline is None else deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Task expired before MCP startup.")
        self._stack = AsyncExitStack()
        try:
            if self.stdio_command is not None:
                environment = dict(self.environment)
                environment.setdefault(LOG_LEVEL_ENV,
                                       os.environ.get(LOG_LEVEL_ENV, ""))
                parameters = StdioServerParameters(
                    command=self.stdio_command[0], args=self.stdio_command[1:],
                    env=environment,
                )
                read, write = await self._stack.enter_async_context(
                    stdio_client(parameters, errlog=sys.stderr),
                )
            else:
                read, write, _ = await self._stack.enter_async_context(
                    streamable_http_client(self.server_url),
                )
            self._session = await self._stack.enter_async_context(
                ClientSession(
                    read, write,
                    read_timeout_seconds=timedelta(seconds=remaining),
                ))
            # These scopes cover requests only, never the lifetime of SDK
            # contexts.
            timeout = (remaining if deadline is None
                       else max(0, deadline - time.monotonic()))
            with anyio.fail_after(timeout):
                logger.debug("MCP ENVIADO [initialize]: inicialización "
                             "mediante el SDK")
                initialized = await self._session.initialize()
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("MCP RECIBIDO [initialize]:\n%s",
                                 initialized.model_dump_json(
                                     indent=2, by_alias=True))
                logger.debug("MCP initialize completado; descubriendo "
                             "herramientas, recursos y prompts")
                capabilities = initialized.capabilities
                tools, resources, templates, prompts = [], [], [], []
                for capability, method, field, destination in (
                    (capabilities.tools, self._session.list_tools, "tools",
                     tools),
                    (capabilities.resources, self._session.list_resources,
                     "resources", resources),
                    (capabilities.resources,
                     self._session.list_resource_templates,
                     "resourceTemplates", templates),
                    (capabilities.prompts, self._session.list_prompts,
                     "prompts", prompts),
                ):
                    if capability is None:
                        logger.debug("El servidor no anuncia la capacidad "
                                     "de %s", field)
                        continue
                    cursor = None
                    while True:
                        logger.debug("MCP ENVIADO [listado %s]: cursor=%r",
                                     field, cursor)
                        page = await method(
                            params=PaginatedRequestParams(cursor=cursor))
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug(
                                "MCP RECIBIDO [listado %s]:\n%s", field,
                                page.model_dump_json(indent=2, by_alias=True))
                        destination.extend(
                            item.model_dump(mode="json", by_alias=True)
                            for item in getattr(page, field)
                        )
                        cursor = page.nextCursor
                        if not cursor:
                            break
                    logger.debug("Descubrimiento %s completado: %s elementos",
                                 field, len(destination))
            logger.info("MCP conectado y descubrimiento completado")
            return self._session, MCPManual(
                initialized.instructions or "", tools, resources, templates,
                prompts,
            )
        except BaseException:
            logger.exception("Fallo al iniciar MCP; cerrando contextos "
                             "abiertos")
            await self.close()
            raise

    async def close(self) -> None:
        """Close SDK contexts in their owning task, in reverse order."""
        logger.debug("Entrando en MCPClient.close")
        logger.info("Cerrando sesión y transporte MCP")
        stack = self._stack
        try:
            if stack is not None:
                await stack.aclose()
        finally:
            self._stack = self._session = None
        logger.debug("Contextos MCP cerrados")
