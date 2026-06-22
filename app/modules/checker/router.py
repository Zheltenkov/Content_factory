"""HTTP API for checker axes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from app.core.models import GeneratedDoc
from app.modules.checker.service import evaluate_deterministic

router = APIRouter(prefix="/checker", tags=["checker"])


class CheckerEvaluateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    markdown: str = Field(min_length=1)
    project_id: str | None = None
    profile_id: str = "_base"
    program_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.post("/evaluate")
def evaluate(payload: CheckerEvaluateRequest) -> dict[str, Any]:
    doc = GeneratedDoc(markdown=payload.markdown, project_id=payload.project_id, metadata=payload.metadata)
    result = evaluate_deterministic(doc, profile_id=payload.profile_id, program_type=payload.program_type)
    return result.model_dump(mode="json")
