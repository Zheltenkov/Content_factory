"""Provider-neutral LLM client with one production transport contract."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict


class LLMConfigurationError(RuntimeError):
    """Raised when a production LLM client cannot be configured from env."""


class LLMAPIError(RuntimeError):
    """Raised when an LLM provider call fails."""


class TokenUsage(BaseModel):
    """Provider-neutral token usage snapshot."""

    model_config = ConfigDict(extra="forbid")

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class LLMRequest:
    """Complete-call payload passed to concrete transports."""

    model: str
    system: str
    user: str
    response_format: str | dict[str, Any] | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMResponse:
    """Normalized response returned by transports."""

    content: str
    model: str | None = None
    tokens: TokenUsage | dict[str, Any] | None = None
    raw: Any = None


class LLMTransport(Protocol):
    """Low-level adapter for an OpenAI-compatible or mocked provider."""

    def complete(self, request: LLMRequest) -> LLMResponse | str:
        """Return a text completion for the request."""


class LLMClient:
    """Single runtime client used by modules and structured output helpers."""

    supports_llm_roles = True

    def __init__(
        self,
        *,
        model: str,
        transport: LLMTransport | None = None,
        provider: str | None = None,
    ) -> None:
        self.model = model
        self.provider = provider
        self._transport = transport or OpenAICompatibleTransport.from_env(provider=provider, model=model)
        self._last_token_usage: TokenUsage | None = None
        self._last_raw_response: Any = None

    def complete(
        self,
        system: str,
        user: str,
        response_format: str | dict[str, Any] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> str:
        """Execute one LLM call and keep provider usage on the client."""
        request = LLMRequest(
            model=self.model,
            system=system,
            user=user,
            response_format=response_format,
            temperature=temperature,
            max_tokens=max_tokens,
            extra=dict(kwargs),
        )
        result = self._transport.complete(request)
        response = LLMResponse(content=result) if isinstance(result, str) else result
        if response.model:
            self.model = response.model
        self._last_raw_response = response.raw
        self._last_token_usage = (
            response.tokens
            if isinstance(response.tokens, TokenUsage)
            else TokenUsage.model_validate(response.tokens)
            if response.tokens
            else None
        )
        return response.content


class OpenAICompatibleTransport:
    """Minimal HTTP transport for OpenAI-compatible chat/completions APIs."""

    def __init__(self, *, endpoint: str, api_key: str, timeout_seconds: float = 60.0) -> None:
        self.endpoint = endpoint
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_env(cls, *, provider: str | None, model: str) -> "OpenAICompatibleTransport":
        """Create a transport from env for OpenAI or OpenRouter-compatible routes."""
        normalized = (provider or os.getenv("LLM_PROVIDER") or "openrouter").strip().lower()
        timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
        if normalized == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            endpoint = os.getenv("OPENAI_CHAT_COMPLETIONS_URL", "https://api.openai.com/v1/chat/completions")
        elif normalized == "openrouter":
            api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPEN_ROUTER_API_KEY")
            endpoint = os.getenv("OPENROUTER_CHAT_COMPLETIONS_URL", "https://openrouter.ai/api/v1/chat/completions")
        else:
            raise LLMConfigurationError(f"Unsupported LLM provider: {normalized}")
        if not api_key:
            raise LLMConfigurationError(f"Missing API key for provider={normalized} model={model}")
        return cls(endpoint=endpoint, api_key=api_key, timeout_seconds=timeout)

    def complete(self, request: LLMRequest) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
        }
        if request.response_format is not None:
            payload["response_format"] = (
                {"type": request.response_format} if isinstance(request.response_format, str) else request.response_format
            )
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        payload.update({key: value for key, value in request.extra.items() if value is not None})

        http_request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LLMAPIError(f"LLM provider HTTP {exc.code}: {detail}") from exc
        except Exception as exc:  # noqa: BLE001 - provider stack exposes heterogeneous errors
            raise LLMAPIError(f"LLM provider call failed: {exc}") from exc

        try:
            content = raw["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMAPIError("LLM response does not contain choices[0].message.content") from exc
        return LLMResponse(content=str(content), model=raw.get("model") or request.model, tokens=raw.get("usage"), raw=raw)


def create_llm_client(*, provider: str | None = None, model: str | None = None) -> LLMClient:
    """Create the default singleton-style client from environment settings."""
    resolved_provider = provider or os.getenv("LLM_PROVIDER") or "openrouter"
    resolved_model = (
        model
        or os.getenv("LLM_MODEL")
        or os.getenv("OPENROUTER_MODEL")
        or os.getenv("OPEN_ROUTER_MODEL")
        or os.getenv("OPENAI_MODEL")
        or "openai/gpt-5.4-mini"
    )
    return LLMClient(provider=resolved_provider, model=resolved_model)
