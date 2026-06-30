"""Typed structured-output helper with JSON parsing and repair retry."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.llm.client import LLMAPIError, create_llm_client

T = TypeVar("T", bound=BaseModel)


class StructuredOutputError(RuntimeError):
    """Raised when an LLM response cannot be parsed into the requested schema."""


@dataclass(frozen=True)
class StructuredPrompt:
    """Prompt payload for one typed-output call."""

    user: str
    system: str = "Return only valid JSON matching the requested schema."
    kwargs: dict[str, Any] = field(default_factory=dict)


def complete_typed(
    prompt: str | StructuredPrompt | dict[str, str],
    schema: type[T],
    *,
    client: Any | None = None,
    retries: int = 1,
    **kwargs: Any,
) -> T:
    """Call an LLM and return a validated Pydantic object."""
    resolved_client = client or create_llm_client()
    resolved_prompt = _coerce_prompt(prompt)
    call_kwargs = {**resolved_prompt.kwargs, **kwargs}
    response_format = _response_format_for(
        schema,
        getattr(resolved_client, "model", None),
        getattr(resolved_client, "provider", None),
    )
    last_error: Exception | None = None
    last_response: Any = None

    for attempt in range(max(0, retries) + 1):
        system = resolved_prompt.system
        user = resolved_prompt.user if attempt == 0 else _repair_prompt(resolved_prompt.user, last_response, last_error)
        try:
            raw = resolved_client.complete(system=system, user=user, response_format=response_format, **call_kwargs)
            last_response = raw
            return parse_typed(raw, schema)
        except (ValidationError, json.JSONDecodeError, StructuredOutputError) as exc:
            last_error = exc
            if attempt >= retries:
                raise StructuredOutputError(f"LLM output does not match {schema.__name__}: {exc}") from exc
        except Exception as exc:  # noqa: BLE001 - provider adapters expose heterogeneous errors
            raise exc if isinstance(exc, LLMAPIError) else LLMAPIError(f"LLM structured call failed: {exc}") from exc

    raise StructuredOutputError(f"LLM output does not match {schema.__name__}: {last_error}")


def parse_typed(response: Any, schema: type[T]) -> T:
    """Parse JSON-ish response content and validate it with Pydantic."""
    if isinstance(response, schema):
        return response
    payload = _extract_json_payload(response)
    return schema.model_validate(payload)


def supports_json_schema_model(model_name: str | None) -> bool:
    """Return whether the configured model is known to support strict JSON schema."""
    normalized = str(model_name or "").lower()
    for prefix in ("openrouter/", "openai/"):
        if normalized.startswith(prefix):
            normalized = normalized.removeprefix(prefix)
    return any(
        normalized.startswith(name)
        for name in ("gpt-4o", "gpt-5", "o1", "o3", "o4")
    )


def _coerce_prompt(prompt: str | StructuredPrompt | dict[str, str]) -> StructuredPrompt:
    if isinstance(prompt, StructuredPrompt):
        return prompt
    if isinstance(prompt, str):
        return StructuredPrompt(user=prompt)
    return StructuredPrompt(user=prompt["user"], system=prompt.get("system", StructuredPrompt.system))


def _response_format_for(
    schema: type[BaseModel], model_name: str | None, provider: str | None = None
) -> str | dict[str, Any]:
    # Proxied providers (polza/openrouter -> Azure) reject pydantic's $ref/strict schema,
    # so they fall back to json_object + pydantic parse; direct providers keep json_schema.
    if str(provider or "").lower() in {"polza", "openrouter"}:
        return "json_object"
    if not supports_json_schema_model(model_name):
        return "json_object"
    return {
        "type": "json_schema",
        "json_schema": {
            "name": schema.__name__,
            "strict": True,
            "schema": _strict_json_schema(schema),
        },
    }


def _strict_json_schema(schema: type[BaseModel]) -> dict[str, Any]:
    raw = schema.model_json_schema()

    def clean(value: Any) -> Any:
        if isinstance(value, dict):
            cleaned = {key: clean(item) for key, item in value.items() if key != "title"}
            if cleaned.get("type") == "object" or "properties" in cleaned:
                cleaned.setdefault("type", "object")
                cleaned["additionalProperties"] = False
                cleaned["required"] = list((cleaned.get("properties") or {}).keys())
            return cleaned
        if isinstance(value, list):
            return [clean(item) for item in value]
        return value

    return clean(raw)


def _extract_json_payload(response: Any) -> Any:
    if not isinstance(response, str):
        return response
    text = response.strip()
    if text.startswith("```json"):
        text = text[7:].strip()
    elif text.startswith("```"):
        text = text[3:].strip()
    if text.endswith("```"):
        text = text[:-3].strip()
    return json.loads(text)


def _repair_prompt(original_user: str, bad_response: Any, error: Exception | None) -> str:
    return (
        "Previous response failed schema validation.\n"
        f"Validation error: {error}\n"
        f"Previous response:\n{bad_response}\n\n"
        f"Original task:\n{original_user}\n\n"
        "Return only corrected JSON. Do not include markdown fences."
    )
