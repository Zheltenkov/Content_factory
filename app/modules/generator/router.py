"""HTTP API for generator runs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field

from app.core.methodology.gate.models import StageReviewResult
from app.core.models import CurriculumContext, GeneratedDoc, RuleIssue
from app.modules.curriculum.repo import CurriculumCatalogRepo, default_curriculum_repo
from app.modules.generator.runtime import (
    GENERATOR_RUNS,
    build_archive,
    recent_payload,
    run_result_payload,
    status_payload,
)
from app.modules.generator.service import CurriculumContextNotFound, GeneratorService

router = APIRouter(prefix="/generator", tags=["generator"])


class GenerateFromCurriculumRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: int = Field(ge=1)
    project_order: int = Field(ge=1)
    profile_id: str = "_base"
    program_type: str | None = None
    overrides: dict[str, Any] = Field(default_factory=dict)


class GeneratorRunResponse(BaseModel):
    run_id: str
    request_id: str
    context: CurriculumContext
    document: GeneratedDoc
    rule_issues: list[RuleIssue]
    rubric_json: dict[str, object]
    gate_review: StageReviewResult | None


class GeneratorRunStartResponse(BaseModel):
    run_id: str
    request_id: str
    status: str
    status_url: str
    cancel_url: str
    archive_url: str


class GeneratorReviewActionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    action: str | None = None
    comment: str | None = None
    message: str | None = None
    selected_target_id: str | None = None
    target_stage: str | None = None
    target_selector: str | None = None
    scope: str | None = None
    instruction: str | None = None
    issue_codes: list[str] = Field(default_factory=list)
    forbidden_changes: list[str] = Field(default_factory=list)
    expected_outcome: str | None = None


class GeneratorRegenerationScope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)


class GeneratorRegenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instruction: str = Field(min_length=1)
    scopes: list[GeneratorRegenerationScope] = Field(default_factory=list)


def get_generator_repo() -> CurriculumCatalogRepo:
    return default_curriculum_repo()


@router.post("/runs/from-curriculum", response_model=GeneratorRunResponse)
def generate_from_curriculum(
    payload: GenerateFromCurriculumRequest,
    repo: CurriculumCatalogRepo = Depends(get_generator_repo),
) -> GeneratorRunResponse:
    stored = GENERATOR_RUNS.create(payload.model_dump(mode="json"))
    service = GeneratorService(repo)
    try:
        run = service.generate_from_curriculum(
            plan_id=payload.plan_id,
            project_order=payload.project_order,
            profile_id=payload.profile_id,
            program_type=payload.program_type,
            overrides=payload.overrides,
            run_id=stored.run_id,
        )
    except CurriculumContextNotFound as exc:
        GENERATOR_RUNS.fail(stored.run_id, str(exc))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        GENERATOR_RUNS.fail(stored.run_id, str(exc))
        raise
    GENERATOR_RUNS.complete(stored.run_id, run)
    return GeneratorRunResponse.model_validate(run_result_payload(stored.run_id, run))


@router.post("/runs/from-curriculum/async", response_model=GeneratorRunStartResponse)
def start_generation_from_curriculum(
    payload: GenerateFromCurriculumRequest,
    background_tasks: BackgroundTasks,
    repo: CurriculumCatalogRepo = Depends(get_generator_repo),
) -> GeneratorRunStartResponse:
    stored = GENERATOR_RUNS.create(payload.model_dump(mode="json"))
    background_tasks.add_task(_execute_generation, stored.run_id, payload, repo)
    return GeneratorRunStartResponse(
        run_id=stored.run_id,
        request_id=stored.run_id,
        status=stored.status,
        status_url=f"/generator/runs/{stored.run_id}/status",
        cancel_url=f"/generator/runs/{stored.run_id}/cancel",
        archive_url=f"/generator/runs/{stored.run_id}/archive",
    )


@router.get("/runs/recent")
def recent_generator_runs(limit: int = 8) -> dict[str, object]:
    return {"items": [recent_payload(run) for run in GENERATOR_RUNS.recent(limit)]}


@router.get("/runs/{run_id}/status")
def generator_run_status(run_id: str) -> dict[str, object]:
    run = _run_or_404(run_id)
    return status_payload(run)


@router.post("/runs/{run_id}/cancel")
def cancel_generator_run(run_id: str, payload: GeneratorReviewActionRequest | None = None) -> dict[str, object]:
    run = GENERATOR_RUNS.cancel(run_id, payload.comment if payload else None)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="generator run not found")
    return status_payload(run)


@router.get("/runs/{run_id}/archive")
def download_generator_archive(run_id: str) -> Response:
    run = _run_or_404(run_id)
    try:
        body = build_archive(run)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return Response(
        content=body,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="generator-{run_id}.zip"'},
    )


@router.post("/runs/{run_id}/review/actions")
def generator_review_action(run_id: str, payload: GeneratorReviewActionRequest) -> dict[str, object]:
    action = payload.action or "request_changes"
    run = GENERATOR_RUNS.record_review_action(run_id, action, _review_payload(payload))
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="generator run not found")
    return status_payload(run)


@router.post("/runs/{run_id}/review/reject")
def reject_generator_run(run_id: str, payload: GeneratorReviewActionRequest) -> dict[str, object]:
    return _record_legacy_review_action(run_id, "reject", payload)


@router.post("/runs/{run_id}/review/request-changes")
def request_generator_changes(run_id: str, payload: GeneratorReviewActionRequest) -> dict[str, object]:
    return _record_legacy_review_action(run_id, "request_changes", payload)


@router.post("/runs/{run_id}/review/preview-changes")
def preview_generator_changes(run_id: str, payload: GeneratorReviewActionRequest | None = None) -> dict[str, object]:
    return _record_legacy_review_action(run_id, "preview_changes", payload or GeneratorReviewActionRequest())


@router.post("/runs/{run_id}/review/approve-diff")
def approve_generator_diff(run_id: str, payload: GeneratorReviewActionRequest | None = None) -> dict[str, object]:
    return _record_legacy_review_action(run_id, "approve_diff", payload or GeneratorReviewActionRequest())


@router.post("/runs/{run_id}/review/assistant")
def generator_assistant_command(run_id: str, payload: GeneratorReviewActionRequest) -> dict[str, object]:
    message = payload.message or payload.comment or payload.instruction or ""
    if not message.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="assistant message is required")
    command = GENERATOR_RUNS.parse_assistant_command(run_id, message, payload.selected_target_id or "")
    if command is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="generator run not found")
    run = _run_or_404(run_id)
    data = status_payload(run)
    data["assistant_command"] = command
    return data


@router.post("/runs/{run_id}/regenerate")
def regenerate_generator_run(run_id: str, payload: GeneratorRegenerationRequest) -> dict[str, object]:
    try:
        run = GENERATOR_RUNS.regenerate(run_id, payload.instruction, [item.model_dump(mode="json") for item in payload.scopes])
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="generator run not found")
    return status_payload(run)


def _execute_generation(run_id: str, payload: GenerateFromCurriculumRequest, repo: CurriculumCatalogRepo) -> None:
    service = GeneratorService(repo)
    try:
        run = service.generate_from_curriculum(
            plan_id=payload.plan_id,
            project_order=payload.project_order,
            profile_id=payload.profile_id,
            program_type=payload.program_type,
            overrides=payload.overrides,
            run_id=run_id,
        )
    except Exception as exc:  # noqa: BLE001 - background boundary must persist a failed status
        GENERATOR_RUNS.fail(run_id, str(exc))
        return
    GENERATOR_RUNS.complete(run_id, run)


def _record_legacy_review_action(run_id: str, action: str, payload: GeneratorReviewActionRequest) -> dict[str, object]:
    run = GENERATOR_RUNS.record_review_action(run_id, action, _review_payload(payload))
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="generator run not found")
    return status_payload(run)


def _review_payload(payload: GeneratorReviewActionRequest) -> dict[str, Any]:
    data = payload.model_dump(mode="json", exclude_none=True)
    if payload.comment and not data.get("instruction"):
        data["instruction"] = payload.comment
    return data


def _run_or_404(run_id: str):
    run = GENERATOR_RUNS.get(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="generator run not found")
    return run
