"""LLM call observability with run/stage/token metadata."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.llm.client import TokenUsage


def stable_input_hash(payload: Any) -> str:
    """Return a stable short hash for reproducible prompt traces."""
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class LLMTraceEvent(BaseModel):
    """JSON-safe trace event for one LLM invocation."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    run_id: str
    stage: str
    input_hash: str
    model: str | None = None
    tokens: TokenUsage | None = None
    latency_ms: float
    status: Literal["success", "error"] = "success"
    output_schema: str | None = Field(default=None, alias="schema")
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LLMTraceRecorder:
    """In-memory recorder; a DB/exporter sink can consume ``events`` later."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def append(self, event: LLMTraceEvent) -> None:
        self.events.append(event.model_dump(mode="json", by_alias=True))


class ObservedLLMClient:
    """Transparent proxy that records complete() calls from any LLM client."""

    def __init__(
        self,
        inner: Any,
        recorder: LLMTraceRecorder,
        *,
        run_id: str,
        stage: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._inner = inner
        self._recorder = recorder
        self._run_id = run_id
        self._stage = stage
        self._metadata = metadata or {}

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    @property
    def model(self) -> str | None:
        return getattr(self._inner, "model", None)

    def scoped(self, *, stage: str | None = None, run_id: str | None = None, **metadata: Any) -> "ObservedLLMClient":
        return ObservedLLMClient(
            self._inner,
            self._recorder,
            run_id=run_id or self._run_id,
            stage=stage or self._stage,
            metadata={**self._metadata, **{k: v for k, v in metadata.items() if v is not None}},
        )

    def complete(
        self,
        system: str,
        user: str,
        response_format: str | dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> str:
        started = time.perf_counter()
        try:
            result = self._inner.complete(system=system, user=user, response_format=response_format, **kwargs)
        except Exception as exc:
            self._record(system, user, response_format, started, "error", str(exc))
            raise
        self._record(system, user, response_format, started, "success", None)
        return result

    def _record(
        self,
        system: str,
        user: str,
        response_format: Any,
        started: float,
        status: Literal["success", "error"],
        error: str | None,
    ) -> None:
        usage = getattr(self._inner, "_last_token_usage", None)
        tokens = usage if isinstance(usage, TokenUsage) else TokenUsage.model_validate(usage) if usage else None
        schema = None
        if isinstance(response_format, str):
            schema = response_format
        elif isinstance(response_format, dict):
            schema = str(response_format.get("json_schema", {}).get("name") or response_format.get("type"))
        self._recorder.append(
            LLMTraceEvent(
                run_id=self._run_id,
                stage=self._stage,
                input_hash=stable_input_hash({"system": system, "user": user, "response_format": response_format}),
                model=self.model,
                tokens=tokens,
                latency_ms=(time.perf_counter() - started) * 1000,
                status=status,
                output_schema=schema,
                error=error,
                metadata=dict(self._metadata),
            )
        )
