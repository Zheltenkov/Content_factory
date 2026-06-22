"""HTTP API for checker axes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from app.core.models import GeneratedDoc
from app.modules.curriculum.repo import default_curriculum_repo
from app.modules.checker.reverse_extraction import ReverseExtractionResult, ReverseExtractionService
from app.modules.checker.service import evaluate_deterministic

router = APIRouter(prefix="/checker", tags=["checker"])
_REVERSE_SERVICE = ReverseExtractionService()


class CheckerEvaluateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    markdown: str = Field(min_length=1)
    project_id: str | None = None
    profile_id: str = "_base"
    program_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReverseExtractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    markdown: str = Field(min_length=1)
    source_ref: str = "reverse://api"
    expected_tasks_count: int | None = Field(default=None, ge=0)
    expected_competencies: list[str] = Field(default_factory=list)
    expected_skills: list[str] = Field(default_factory=list)
    persist_review: bool = False


@router.post("/evaluate")
def evaluate(payload: CheckerEvaluateRequest) -> dict[str, Any]:
    doc = GeneratedDoc(markdown=payload.markdown, project_id=payload.project_id, metadata=payload.metadata)
    result = evaluate_deterministic(doc, profile_id=payload.profile_id, program_type=payload.program_type)
    return result.model_dump(mode="json")


@router.post("/reverse-extract", response_model=ReverseExtractionResult)
def reverse_extract(payload: ReverseExtractRequest) -> ReverseExtractionResult:
    repo = default_curriculum_repo() if payload.persist_review else None
    return _REVERSE_SERVICE.extract(
        payload.markdown,
        repo=repo,
        source_ref=payload.source_ref,
        expected_tasks_count=payload.expected_tasks_count,
        expected_competencies=payload.expected_competencies,
        expected_skills=payload.expected_skills,
    )
