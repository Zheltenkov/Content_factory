"""HTTP API for the shared competency reference catalog."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.curriculum.repo import CurriculumCatalogRepo, default_curriculum_repo
from app.modules.reference.service import (
    ReferenceCompetencyPatch,
    ReferenceReviewPatch,
    ReferenceService,
    ReferenceSkillPatch,
    ReferenceSkillUpsert,
    ReviewStatus,
    skill_payload,
)

router = APIRouter(prefix="/reference", tags=["reference"])


def get_reference_repo() -> CurriculumCatalogRepo:
    return default_curriculum_repo()


def get_reference_service(repo: CurriculumCatalogRepo = Depends(get_reference_repo)) -> ReferenceService:
    return ReferenceService(repo)


@router.get("/summary")
def summary(service: ReferenceService = Depends(get_reference_service)) -> dict[str, int]:
    return service.summary()


@router.get("/competencies")
def list_competencies(
    q: str = "",
    status_filter: str | None = None,
    limit: int = 100,
    service: ReferenceService = Depends(get_reference_service),
) -> list[dict[str, object]]:
    return service.competencies(query=q, status=status_filter, limit=limit)


@router.get("/competencies/{competency_id}")
def get_competency(
    competency_id: int,
    service: ReferenceService = Depends(get_reference_service),
) -> dict[str, object]:
    competency = service.competency(competency_id)
    if competency is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="competency not found")
    return competency


@router.patch("/competencies/{competency_id}")
def patch_competency(
    competency_id: int,
    payload: ReferenceCompetencyPatch,
    service: ReferenceService = Depends(get_reference_service),
) -> dict[str, object]:
    competency = service.patch_competency(competency_id, payload)
    if competency is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="competency not found")
    return competency


@router.get("/skills")
def list_skills(
    q: str = "",
    limit: int = 100,
    include_deprecated: bool = False,
    service: ReferenceService = Depends(get_reference_service),
) -> list[dict[str, object]]:
    return [skill_payload(skill) for skill in service.skills(query=q, limit=limit, include_deprecated=include_deprecated)]


@router.post("/skills", status_code=status.HTTP_201_CREATED)
def upsert_skill(
    payload: ReferenceSkillUpsert,
    service: ReferenceService = Depends(get_reference_service),
) -> dict[str, object]:
    return skill_payload(service.upsert_skill(payload))


@router.patch("/skills/{skill_id}")
def patch_skill(
    skill_id: int,
    payload: ReferenceSkillPatch,
    service: ReferenceService = Depends(get_reference_service),
) -> dict[str, object]:
    skill = service.patch_skill(skill_id, payload)
    if skill is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="skill not found")
    return skill_payload(skill)


@router.get("/profiles")
def list_profiles(
    include_service: bool = False,
    limit: int = 100,
    service: ReferenceService = Depends(get_reference_service),
) -> list[dict[str, object]]:
    return service.profiles(include_service=include_service, limit=limit)


@router.get("/reviews")
def list_reviews(
    status_filter: ReviewStatus | Literal["all"] = "open",
    limit: int = 100,
    service: ReferenceService = Depends(get_reference_service),
) -> list[dict[str, object]]:
    status_value = None if status_filter == "all" else status_filter
    return service.reviews(status=status_value, limit=limit)


@router.patch("/reviews/{review_id}")
def resolve_review(
    review_id: int,
    payload: ReferenceReviewPatch,
    service: ReferenceService = Depends(get_reference_service),
) -> dict[str, object]:
    if not service.resolve_review(review_id, payload):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="review item not found")
    return {"review_id": review_id, "status": payload.status}
