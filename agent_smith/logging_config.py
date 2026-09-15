"""Opt-in application logging on stderr, apart from worker/MCP JSON stdout."""

from __future__ import annotations

import logging
import argparse
import os
import sys
from typing import Iterable


LOG_LEVEL_ENV = "AGENT_SMITH_LOG_LEVEL"
_LEVELS = {name: getattr(logging, name) for name in (
    "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL",
)}
_secrets: set[str] = set()
_configured = False


def register_secrets(values: Iterable[str]) -> None:
    """Hide provider keys even if an error or response echoes them."""
    _secrets.update(value for value in values if value)


class _ApplicationFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # SDK debug logs can contain HTTP headers or raw protocol payloads.
        return (record.name == "agent_smith"
                or record.name.startswith("agent_smith."))


class _SecretFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        for secret in sorted(_secrets, key=len, reverse=True):
            text = text.replace(secret, "[REDACTED]")
        return text


def configure_logging() -> None:
    """Read the environment again at each entry point; no duplicate handlers.

    Empty/unset means silence. Invalid nonempty values enable ERROR and report
    the configuration mistake. This module does not log its own helper calls:
    doing so would recurse while formatting or configuring a log record.
    """
    global _configured
    requested = os.environ.get(LOG_LEVEL_ENV, "").strip().upper()
    level = (_LEVELS.get(requested, logging.ERROR) if requested
             else logging.CRITICAL + 1)
    register_secrets(os.environ.get(name, "") for name in (
        "PROVIDER_API_KEY", "PROVIDER_API_KEY_2", "OPENROUTER_API_KEY",
        "OPENROUTER_API_KEY_2", "GEMINI_API_KEY", "GEMINI_API_KEY_2",
    ))
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)
    handler.addFilter(_ApplicationFilter())
    handler.setFormatter(_SecretFormatter(
        "%(asctime)s %(levelname)s [pid=%(process)d] "
        "%(name)s.%(funcName)s:%(lineno)d | %(message)s",
        datefmt="%H:%M:%S",
    ))
    logging.basicConfig(level=level, handlers=[handler], force=True)
    logging.getLogger("agent_smith").setLevel(level)
    # Application messages describe these operations without exposing SDK
    # internals.
    for name in ("httpx", "httpcore", "docker", "urllib3", "mcp", "asyncio"):
        logging.getLogger(name).setLevel(logging.CRITICAL + 1)
    logging.raiseExceptions = False
    _configured = True
    if requested and requested not in _LEVELS:
        logging.getLogger("agent_smith.logging_config").error(
            "%s not valid; using ERROR. Values: DEBUG, INFO, WARNING, ERROR, "
            "CRITICAL.",
            LOG_LEVEL_ENV,
        )


def get_logger(name: str) -> logging.Logger:
    """Give every project module a logger under the application namespace."""
    if not _configured:
        configure_logging()
    if not name.startswith("agent_smith.") and name != "agent_smith":
        name = "agent_smith." + name
    return logging.getLogger(name)


class LoggingArgumentParser(argparse.ArgumentParser):
    """Keep argparse validation; make its errors follow the log level."""

    def error(self, message: str) -> None:
        get_logger("cli").error("Argumentos CLI inválidos: %s", message)
        self.exit(2)
