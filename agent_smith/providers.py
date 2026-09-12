"""One configurable HTTP client, measured usage, and bounded key rotation."""

from __future__ import annotations

from agent_smith.logging_config import get_logger, register_secrets

logger = get_logger('agent_smith.providers')

import asyncio
import os
import time
from urllib.parse import urlparse

import httpx
from agent_smith.io import load_model
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

from pydantic import BaseModel, Field


class ProviderConfig(BaseModel):
    """Store one compatible chat-completions configuration without API secrets."""

    api_url: str
    model_name: str
    api_key_environment_variables: list[str] = Field(default_factory=list)
    timeout_seconds: float = Field(default=60.0, gt=0)
    max_retries: int = Field(default=2, ge=0)
    temperature: float = Field(default=0.1, ge=0, le=2)
    stop_sequences: list[str] = Field(default_factory=lambda: ["<end_code>"])
    response_format: str = "python"
    reasoning_effort: str | None = None
    reasoning_enabled: bool | None = None
    max_output_per_request: int = Field(default=600, gt=0)
    output_limit_parameter: Literal["max_tokens", "max_completion_tokens"] = "max_tokens"


class ProvidersConfig(BaseModel):
    """Store the model configurations available for explicit CLI selection."""

    providers: list[ProviderConfig] = Field(default_factory=list)


@dataclass(frozen=True)
class CompletionResponse:
    """Return text, measured usage, and any error from one completion operation.

    Metrics include every HTTP attempt made by that operation. When usage is
    incomplete, token counts are known subtotals and must not imply zero usage.
    This internal result does not change the public SolutionOutput JSON schema.
    """

    text: str
    input_tokens: int
    output_tokens: int
    request_time_ms: float
    api_url: str
    model_name: str
    retries: int
    request_count: int
    usage_complete: bool = True
    error: str | None = None


def estimate_input_tokens(messages: list[dict[str, str]]) -> int:
    """Approximate preflight estimate, NEVER a measurement for result metrics.

    Adapt the reference client's characters/4 estimate, using UTF-8 bytes and
    framing headroom. Actual usage is checked after every reply: this is not a
    remote tokenizer and cannot guarantee its count before sending.
    """
    logger.debug("Entrando en estimate_input_tokens")
    estimate = 64 + sum((len(m["content"].encode("utf-8")) + 3) // 4 + 32 for m in messages)
    logger.debug("Entrada estimada: %s tokens en %s mensajes; no es usage medido", estimate, len(messages))
    return estimate


class ProviderClient:
    """Keep one provider and its keys; return metrics without shared budgets."""

    def __init__(self, config: ProviderConfig, environment: Mapping[str, str] | None = None):
        logger.debug("Entrando en ProviderClient.__init__")
        self.config = config.model_copy(deep=True)
        parsed = urlparse(config.api_url)
        if (parsed.scheme != "https" and not (
                parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1", "::1"))):
            raise ValueError("Use HTTPS for remote providers.")
        if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Provider URL must not contain credentials, query or fragment.")
        environment = os.environ if environment is None else environment
        self.api_keys = list(dict.fromkeys(
            environment[name] for name in config.api_key_environment_variables
            if environment.get(name)
        ))
        if not self.api_keys:
            logger.error("No hay claves configuradas para el proveedor")
            raise RuntimeError("Missing API key; set one of: " + ", ".join(config.api_key_environment_variables))
        self.key_index = 0
        register_secrets(self.api_keys)
        logger.info("Proveedor preparado: modelo=%s, claves disponibles=%s", config.model_name, len(self.api_keys))

    @classmethod
    def from_environment(
        cls, default_api_url: str, default_model_name: str,
        config_path: str | Path | None = None,
        environment: Mapping[str, str] | None = None,
    ) -> "ProviderClient":
        logger.debug("Entrando en ProviderClient.from_environment")
        if config_path is not None:
            logger.debug("Buscando configuración explícita en %s", config_path)
            configurations = load_model(config_path, ProvidersConfig)
            matches = [c for c in configurations.providers
                       if c.api_url.rstrip("/") == default_api_url.rstrip("/")
                       and c.model_name == default_model_name]
            if len(matches) != 1:
                logger.error("La selección URL/modelo tiene %s coincidencias; se esperaba una", len(matches))
                raise ValueError("Expected exactly one configuration matching CLI URL and model.")
            config = matches[0]
        else:
            logger.debug("Sin archivo de modelos: usando configuración compatible por defecto")
            config = ProviderConfig(
                api_url=default_api_url, model_name=default_model_name,
                api_key_environment_variables=["PROVIDER_API_KEY", "PROVIDER_API_KEY_2"],
            )
        return cls(config, environment)

    async def complete(
        self, messages: list[dict[str, str]], *, max_input_tokens: int,
        max_output_tokens: int, deadline: float,
    ) -> CompletionResponse:
        logger.debug("Entrando en ProviderClient.complete")
        input_tokens = output_tokens = requests = 0
        elapsed_ms = 0.0
        text = ""
        model_name = self.config.model_name
        error = None
        usage_complete = True
        for attempt in range(1 + self.config.max_retries):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                error = "Task deadline reached before LLM request."
                break
            if estimate_input_tokens(messages) > max_input_tokens - input_tokens:
                error = "Remaining input budget is below the prompt estimate."
                break
            allowance = min(max_output_tokens - output_tokens, self.config.max_output_per_request)
            if allowance <= 0:
                error = "Output token budget exhausted."
                break
            payload = self._build_payload(messages, max_output_tokens=allowance)
            logger.info(
                "Petición LLM %s/%s: modelo=%s, clave índice=%s, salida máxima=%s, tiempo restante=%.2fs",
                attempt + 1, 1 + self.config.max_retries, self.config.model_name,
                self.key_index, allowance, remaining,
            )
            started = time.monotonic()
            requests += 1
            try:
                status, body, retry_after = await self._send_request(
                    payload, self.api_keys[self.key_index],
                    min(remaining, self.config.timeout_seconds),
                )
            except (httpx.HTTPError, TimeoutError, ValueError) as exc:
                elapsed_ms += (time.monotonic() - started) * 1000
                usage_complete = False
                error = f"LLM request failed ({type(exc).__name__}); token usage is unknown."
                break
            duration = (time.monotonic() - started) * 1000
            logger.info("Respuesta HTTP %s recibida en %.1f ms", status, duration)
            elapsed_ms += duration
            response = self._parse_response(body, duration)
            model_name = response.model_name
            input_tokens += response.input_tokens
            output_tokens += response.output_tokens
            usage_complete = usage_complete and response.usage_complete
            text = response.text
            error = response.error
            if status == 429:
                self.key_index = (self.key_index + 1) % len(self.api_keys)
                logger.warning("HTTP 429: siguiente índice de clave=%s; comprobando si es posible reintentar", self.key_index)
            if status != 200:
                error = f"Provider returned HTTP {status}."
                details = body.get("error") if isinstance(body, dict) else None
                if isinstance(details, dict) and isinstance(details.get("message"), str):
                    message = details["message"]
                    for key in self.api_keys:
                        message = message.replace(key, "[redacted]")
                    error += " " + message
            if not usage_complete:
                logger.error("Falta usage: se conserva el subtotal y no se reintenta con consumo desconocido")
                error = (error or "Invalid provider usage.") + " Token totals are known subtotals only."
                break
            if input_tokens > max_input_tokens or output_tokens > max_output_tokens:
                error = "Provider usage exceeded the remaining token budget."
                break
            if status == 200:
                break
            if status not in (429, 500, 502, 503, 504) or attempt == self.config.max_retries:
                break
            delay = min(max(retry_after or 0.5, 0), 5.0)
            if time.monotonic() + delay >= deadline:
                error = "Retry would exceed the task deadline."
                break
            logger.warning("Reintentando HTTP después de %.2fs; se mantiene el proveedor", delay)
            await asyncio.sleep(delay)
            logger.debug("Espera de %.2fs completada; pasando al siguiente intento HTTP", delay)
        if error:
            logger.error("Petición LLM detenida: %s", error)
        logger.debug(
            "Fin de complete: peticiones=%s, entrada=%s, salida=%s, usage completo=%s",
            requests, input_tokens, output_tokens, usage_complete,
        )
        return CompletionResponse(
            text, input_tokens, output_tokens, elapsed_ms, self.config.api_url,
            model_name, max(0, requests - 1), requests, usage_complete, error,
        )

    def _build_payload(self, messages, *, max_output_tokens: int) -> dict[str, Any]:
        logger.debug("Entrando en ProviderClient._build_payload")
        if max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive.")
        payload = {
            "model": self.config.model_name, "messages": messages,
            self.config.output_limit_parameter: max_output_tokens,
            "stream": False, "temperature": self.config.temperature,
        }
        if self.config.stop_sequences:
            payload["stop"] = list(self.config.stop_sequences)
        if self.config.reasoning_effort is not None:
            payload["reasoning_effort"] = self.config.reasoning_effort
        if self.config.reasoning_enabled is not None:
            payload["reasoning"] = {"enabled": self.config.reasoning_enabled}
        if urlparse(self.config.api_url).hostname == "openrouter.ai":
            # Ask OpenRouter to honor stop/output settings rather than discard them.
            payload["provider"] = {"require_parameters": True}
        logger.debug(
            "Parámetros LLM: temperatura=%s, límite=%s, stop=%s, razonamiento enabled=%s/effort=%s",
            self.config.temperature, max_output_tokens, self.config.stop_sequences,
            self.config.reasoning_enabled, self.config.reasoning_effort,
        )
        return payload

    async def _send_request(self, payload, api_key: str, timeout_seconds: float):
        logger.debug("Entrando en ProviderClient._send_request")
        endpoint = self.config.api_url.rstrip("/")
        if not endpoint.endswith("/chat/completions"):
            endpoint += "/chat/completions"
        logger.debug("Enviando POST al proveedor; timeout=%.2fs; sin registrar cabeceras", timeout_seconds)
        for number, message in enumerate(payload["messages"], start=1):
            logger.debug(
                "IA ENVIADO [mensaje %s, rol=%s]:\n%s",
                number, message["role"], message["content"],
            )
        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=False) as client:
            response = await asyncio.wait_for(client.post(
                endpoint, json=payload, headers={"Authorization": f"Bearer {api_key}"},
            ), timeout=timeout_seconds)
            logger.debug("IA RECIBIDO [HTTP %s, cuerpo completo]:\n%s", response.status_code, response.text)
            try:
                retry_after = float(response.headers.get("Retry-After", ""))
            except ValueError:
                retry_after = None
            try:
                body = response.json()
            except ValueError:
                body = {}
                logger.warning("La respuesta HTTP no contiene JSON válido")
            logger.debug("HTTP recibido y cuerpo decodificado; cerrando cliente HTTP")
            return response.status_code, body, retry_after

    def _parse_response(self, payload: dict[str, Any], request_time_ms: float) -> CompletionResponse:
        logger.debug("Entrando en ProviderClient._parse_response")
        text = ""
        error = None
        complete = True
        counts = []
        if not isinstance(payload, dict):
            payload = {}
        usage = payload.get("usage") or {}
        if not isinstance(usage, dict):
            usage = {}
        for name in ("prompt_tokens", "completion_tokens"):
            value = usage.get(name)
            if type(value) is not int or value < 0:
                complete = False
                value = 0
            counts.append(value)
        try:
            text = payload["choices"][0]["message"]["content"]
            if not isinstance(text, str):
                raise ValueError("Expected text content.")
        except (KeyError, IndexError, TypeError, ValueError):
            text = ""
            error = "Provider response did not contain text content."
        if not complete:
            error = (error or "") + " Token usage is incomplete."
        # Routers can choose a different model on each request. Preserve what
        # the API actually reports; the configured ID remains the request target.
        model_name = payload.get("model")
        if not isinstance(model_name, str) or not model_name.strip():
            model_name = self.config.model_name
        logger.debug("Modelo solicitado=%s; modelo informado por la API=%s", self.config.model_name, model_name)
        logger.debug("Usage: entrada=%s, salida=%s, completo=%s; texto=%s caracteres", counts[0], counts[1], complete, len(text))
        if error:
            logger.warning("Respuesta LLM no utilizable: %s", error)
        return CompletionResponse(
            text, counts[0], counts[1], request_time_ms, self.config.api_url,
            model_name, 0, 1, complete, error,
        )
