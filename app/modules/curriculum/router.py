"""HTTP API for persistent curriculum plans."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.core.models import UPProject, UPSkeleton
from app.modules.curriculum.repo import CurriculumCatalogRepo, CurriculumProjectRecord, default_curriculum_repo

router = APIRouter(prefix="/curriculum", tags=["curriculum"])


class CurriculumPlanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: UPSkeleton
    profile_id: int | None = None
    source_policy: str = "accepted_only"
    author_ref: str | None = None


class CurriculumPlanPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["built", "deferred", "draft"] | None = None
    title: str | None = None
    direction: str | None = None
    version: str | None = None
    metadata: dict[str, Any] | None = None


class CurriculumProjectPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block: str | None = None
    block_goal: str | None = None
    order: int | None = Field(default=None, ge=1)
    title: str | None = None
    description: str | None = None
    outcomes_know: list[str] | None = None
    outcomes_can: list[str] | None = None
    outcomes_skills: list[str] | None = None
    required_tools: list[str] | None = None
    required_software: list[str] | None = None
    materials: str | None = None
    storytelling: str | None = None
    format: Literal["individual", "group", "pair", "workshop", "unknown"] | None = None
    group_size: int | None = Field(default=None, ge=1)
    hours_astro: float | None = Field(default=None, ge=0.0)
    metadata: dict[str, Any] | None = None


class CurriculumPlanCreated(BaseModel):
    plan_id: int
    project_count: int


class CurriculumPlanResponse(BaseModel):
    plan_id: int
    plan: UPSkeleton


class CurriculumProjectResponse(BaseModel):
    project_id: int
    plan_id: int
    row_number: int
    project: UPProject


def get_curriculum_repo() -> CurriculumCatalogRepo:
    return default_curriculum_repo()


@router.get("/plans")
def list_plans(
    status_filter: str | None = None,
    limit: int = 50,
    repo: CurriculumCatalogRepo = Depends(get_curriculum_repo),
) -> list[dict[str, object]]:
    return repo.list_curriculum_plans(status=status_filter, limit=limit)


@router.post("/plans", response_model=CurriculumPlanCreated, status_code=status.HTTP_201_CREATED)
def create_plan(
    payload: CurriculumPlanCreate,
    repo: CurriculumCatalogRepo = Depends(get_curriculum_repo),
) -> CurriculumPlanCreated:
    result = repo.save_curriculum_plan(
        payload.plan,
        profile_id=payload.profile_id,
        source_policy=payload.source_policy,
        author_ref=payload.author_ref,
    )
    return CurriculumPlanCreated(plan_id=result.plan_id, project_count=result.project_count)


@router.get("/plans/{plan_id}", response_model=CurriculumPlanResponse)
def get_plan(plan_id: int, repo: CurriculumCatalogRepo = Depends(get_curriculum_repo)) -> CurriculumPlanResponse:
    plan = repo.load_curriculum_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="curriculum plan not found")
    return CurriculumPlanResponse(plan_id=plan_id, plan=plan)


@router.put("/plans/{plan_id}", response_model=CurriculumPlanResponse)
def replace_plan(
    plan_id: int,
    payload: CurriculumPlanCreate,
    repo: CurriculumCatalogRepo = Depends(get_curriculum_repo),
) -> CurriculumPlanResponse:
    replaced = repo.replace_curriculum_plan(
        plan_id,
        payload.plan,
        profile_id=payload.profile_id,
        source_policy=payload.source_policy,
        author_ref=payload.author_ref,
    )
    if not replaced:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="curriculum plan not found")
    return get_plan(plan_id, repo)


@router.patch("/plans/{plan_id}", response_model=CurriculumPlanResponse)
def patch_plan(
    plan_id: int,
    payload: CurriculumPlanPatch,
    repo: CurriculumCatalogRepo = Depends(get_curriculum_repo),
) -> CurriculumPlanResponse:
    existing = repo.load_curriculum_plan(plan_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="curriculum plan not found")
    update = payload.model_dump(exclude_none=True)
    if "metadata" in update:
        update["metadata"] = {**existing.metadata, **update["metadata"]}
    patched = existing.model_copy(update=update)
    repo.replace_curriculum_plan(plan_id, patched)
    return get_plan(plan_id, repo)


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan(plan_id: int, repo: CurriculumCatalogRepo = Depends(get_curriculum_repo)) -> None:
    if not repo.delete_curriculum_plan(plan_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="curriculum plan not found")


@router.post("/plans/{plan_id}/projects", response_model=CurriculumProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    plan_id: int,
    project: UPProject,
    repo: CurriculumCatalogRepo = Depends(get_curriculum_repo),
) -> CurriculumProjectResponse:
    record = repo.add_curriculum_project(plan_id, project)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="curriculum plan not found")
    return _project_response(record)


@router.get("/projects/{project_id}", response_model=CurriculumProjectResponse)
def get_project(project_id: int, repo: CurriculumCatalogRepo = Depends(get_curriculum_repo)) -> CurriculumProjectResponse:
    record = repo.get_curriculum_project(project_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="curriculum project not found")
    return _project_response(record)


@router.put("/projects/{project_id}", response_model=CurriculumProjectResponse)
def replace_project(
    project_id: int,
    project: UPProject,
    repo: CurriculumCatalogRepo = Depends(get_curriculum_repo),
) -> CurriculumProjectResponse:
    record = repo.update_curriculum_project(project_id, project)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="curriculum project not found")
    return _project_response(record)


@router.patch("/projects/{project_id}", response_model=CurriculumProjectResponse)
def patch_project(
    project_id: int,
    payload: CurriculumProjectPatch,
    repo: CurriculumCatalogRepo = Depends(get_curriculum_repo),
) -> CurriculumProjectResponse:
    existing = repo.get_curriculum_project(project_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="curriculum project not found")
    update = payload.model_dump(exclude_none=True)
    if "metadata" in update:
        update["metadata"] = {**existing.project.metadata, **update["metadata"]}
    patched = existing.project.model_copy(update=update)
    record = repo.update_curriculum_project(project_id, patched)
    assert record is not None
    return _project_response(record)


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, repo: CurriculumCatalogRepo = Depends(get_curriculum_repo)) -> None:
    if not repo.delete_curriculum_project(project_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="curriculum project not found")


def _project_response(record: CurriculumProjectRecord) -> CurriculumProjectResponse:
    return CurriculumProjectResponse(
        project_id=record.project_id,
        plan_id=record.plan_id,
        row_number=record.row_number,
        project=record.project,
    )
