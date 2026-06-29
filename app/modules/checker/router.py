"""HTTP API for checker axes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from app.core.models import GeneratedDoc
from app.modules.curriculum.repo import default_curriculum_repo
from app.modules.checker.reverse_extraction import ReverseExtractionResult, ReverseExtractionService
from app.modules.checker.service import CheckerImprovementService, evaluate_deterministic

router = APIRouter(prefix="/checker", tags=["checker"])
_REVERSE_SERVICE = ReverseExtractionService()
_IMPROVEMENT_SERVICE = CheckerImprovementService()


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


class CheckerImproveExtractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    markdown: str | None = None
    readme_text: str | None = None
    curriculum_project: dict[str, Any] | None = None
    curriculum_context: dict[str, Any] | None = None

    def readme(self) -> str:
        return (self.markdown or self.readme_text or "").strip()


class CheckerImproveGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    seed: dict[str, Any] = Field(default_factory=dict)


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


@router.post("/improve/extract")
def improve_extract(payload: CheckerImproveExtractRequest) -> dict[str, Any]:
    try:
        extracted = _IMPROVEMENT_SERVICE.extract(
            payload.readme(),
            curriculum_project=payload.curriculum_project,
            curriculum_context=payload.curriculum_context,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {
        "request_id": extracted.request_id,
        "partial_seed": extracted.partial_seed,
        "classification": extracted.classification,
        "metadata": extracted.metadata,
    }


@router.post("/improve/generate")
def improve_generate(payload: CheckerImproveGenerateRequest) -> dict[str, Any]:
    try:
        run = _IMPROVEMENT_SERVICE.generate(payload.request_id, payload.seed)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {
        "request_id": run.extract_request_id,
        "generation_request_id": run.generation_request_id,
        "status": run.status,
    }


@router.get("/improve/status/{generation_request_id}")
def improve_status(generation_request_id: str) -> dict[str, Any]:
    try:
        run = _IMPROVEMENT_SERVICE.status(generation_request_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {
        "request_id": run.extract_request_id,
        "generation_request_id": run.generation_request_id,
        "status": run.status,
        "phase": run.phase,
        "progress": run.progress,
        "result": run.result_payload(),
    }


@router.get("/improve/diff/{request_id}")
def improve_diff(request_id: str) -> dict[str, Any]:
    try:
        return _IMPROVEMENT_SERVICE.diff(request_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/improve/download/{generation_request_id}")
def improve_download(generation_request_id: str) -> Response:
    try:
        markdown = _IMPROVEMENT_SERVICE.download(generation_request_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(
        markdown.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="README_improved.md"'},
    )
