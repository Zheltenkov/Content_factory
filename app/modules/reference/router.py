"""HTTP API for the shared competency reference catalog."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.curriculum.repo import CurriculumCatalogRepo, default_curriculum_repo
from app.modules.reference.service import (
    IntakeJobCreate,
    IntakeService,
    ReferenceArchiveRestore,
    ReferenceArtifactTemplateStatusPatch,
    ReferenceArtifactTemplateUpsert,
    ReferenceCandidateCompetencyAction,
    ReferenceCandidateDecision,
    ReferenceCompetencyPatch,
    ReferenceGroupCreate,
    ReferenceGroupSkillCreate,
    ReferenceIndicatorCreate,
    ReferenceIndicatorPatch,
    ReferenceReviewPatch,
    ReferenceService,
    ReferenceSkillPatch,
    ReferenceSkillUpsert,
    ReviewStatus,
    skill_payload,
)

router = APIRouter(prefix="/reference", tags=["reference"])
intake_router = APIRouter(tags=["intake"])


def get_reference_repo() -> CurriculumCatalogRepo:
    return default_curriculum_repo()


def get_reference_service(repo: CurriculumCatalogRepo = Depends(get_reference_repo)) -> ReferenceService:
    return ReferenceService(repo)


def get_intake_service(repo: CurriculumCatalogRepo = Depends(get_reference_repo)) -> IntakeService:
    return IntakeService(repo)


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


@router.get("/groups")
def list_groups(
    q: str = "",
    status_filter: str | None = None,
    limit: int = 100,
    service: ReferenceService = Depends(get_reference_service),
) -> list[dict[str, object]]:
    return service.groups(query=q, status=status_filter, limit=limit)


@router.post("/groups", status_code=status.HTTP_201_CREATED)
def create_group(
    payload: ReferenceGroupCreate,
    service: ReferenceService = Depends(get_reference_service),
) -> dict[str, object]:
    group = service.create_group(payload)
    if group is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="group already exists")
    return group


@router.get("/groups/{group_id}")
def get_group(
    group_id: int,
    service: ReferenceService = Depends(get_reference_service),
) -> dict[str, object]:
    group = service.group(group_id)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="group not found")
    return group


@router.patch("/groups/{group_id}")
def patch_group(
    group_id: int,
    payload: ReferenceCompetencyPatch,
    service: ReferenceService = Depends(get_reference_service),
) -> dict[str, object]:
    group = service.patch_competency(group_id, payload)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="group not found")
    return group


@router.post("/groups/{group_id}/skills", status_code=status.HTTP_201_CREATED)
def create_group_skill(
    group_id: int,
    payload: ReferenceGroupSkillCreate,
    service: ReferenceService = Depends(get_reference_service),
) -> dict[str, object]:
    skill = service.create_group_skill(group_id, payload)
    if skill is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="group not found")
    return skill


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


@router.get("/skills/{skill_id}")
def get_skill(
    skill_id: int,
    service: ReferenceService = Depends(get_reference_service),
) -> dict[str, object]:
    skill = service.skill(skill_id)
    if skill is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="skill not found")
    return skill


@router.post("/skills/{skill_id}/indicators", status_code=status.HTTP_201_CREATED)
def create_indicator(
    skill_id: int,
    payload: ReferenceIndicatorCreate,
    service: ReferenceService = Depends(get_reference_service),
) -> dict[str, object]:
    indicator = service.create_indicator(skill_id, payload)
    if indicator is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="skill not found")
    return indicator


@router.patch("/indicators/{indicator_id}")
def patch_indicator(
    indicator_id: int,
    payload: ReferenceIndicatorPatch,
    service: ReferenceService = Depends(get_reference_service),
) -> dict[str, object]:
    indicator = service.patch_indicator(indicator_id, payload)
    if indicator is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="indicator not found")
    return indicator


@router.delete("/indicators/{indicator_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_indicator(
    indicator_id: int,
    service: ReferenceService = Depends(get_reference_service),
) -> None:
    if not service.delete_indicator(indicator_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="indicator not found")


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


@router.get("/profiles/{profile_id}")
def get_profile(
    profile_id: int,
    service: ReferenceService = Depends(get_reference_service),
) -> dict[str, object]:
    profile = service.profile(profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="profile not found")
    return profile


@router.get("/reviews")
def list_reviews(
    status_filter: ReviewStatus | Literal["all"] = "open",
    severity: str | None = None,
    reason_code: str | None = None,
    entity_type: str | None = None,
    limit: int = 100,
    service: ReferenceService = Depends(get_reference_service),
) -> list[dict[str, object]]:
    status_value = None if status_filter == "all" else status_filter
    return service.reviews(
        status=status_value,
        severity=severity or None,
        reason_code=reason_code or None,
        entity_type=entity_type or None,
        limit=limit,
    )


@router.patch("/reviews/{review_id}")
def resolve_review(
    review_id: int,
    payload: ReferenceReviewPatch,
    service: ReferenceService = Depends(get_reference_service),
) -> dict[str, object]:
    if not service.resolve_review(review_id, payload):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="review item not found")
    return {"review_id": review_id, "status": payload.status}


@router.post("/candidates/{competency_id}/decision")
def decide_candidate(
    competency_id: int,
    payload: ReferenceCandidateDecision,
    service: ReferenceService = Depends(get_reference_service),
) -> dict[str, object]:
    result = service.decide_candidate(competency_id, payload)
    if result.get("status") == "missing":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="competency candidate not found")
    return result


@router.get("/candidate-competencies")
def list_candidate_competencies(
    limit: int = 100,
    service: ReferenceService = Depends(get_reference_service),
) -> dict[str, object]:
    return service.candidate_competencies(limit=limit)


@router.post("/candidate-competencies/actions")
def apply_candidate_competency_action(
    payload: ReferenceCandidateCompetencyAction,
    service: ReferenceService = Depends(get_reference_service),
) -> dict[str, object]:
    result = service.apply_candidate_action(payload)
    if result.get("status") in {"missing", "target_missing"}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(result["status"]))
    if result.get("status") in {"target_required", "empty_title", "same_competency"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(result["status"]))
    if result.get("status") == "conflict":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="competency title conflict")
    return result


@router.get("/archive")
def list_archive(
    q: str = "",
    scope: Literal["all", "groups", "skills", "indicators"] = "all",
    limit: int = 100,
    service: ReferenceService = Depends(get_reference_service),
) -> dict[str, object]:
    return service.archive(query=q, scope=scope, limit=limit)


@router.post("/archive/actions")
def restore_archive_item(
    payload: ReferenceArchiveRestore,
    service: ReferenceService = Depends(get_reference_service),
) -> dict[str, object]:
    result = service.restore_archive_item(payload)
    if result.get("status") == "missing":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="archive item not found")
    return result


@router.get("/artifact-templates")
def list_artifact_templates(
    active_only: bool = False,
    service: ReferenceService = Depends(get_reference_service),
) -> list[dict[str, object]]:
    return service.artifact_templates(active_only=active_only)


@router.get("/artifact-templates/{template_id}")
def get_artifact_template(
    template_id: int,
    service: ReferenceService = Depends(get_reference_service),
) -> dict[str, object]:
    template = service.artifact_template(template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="artifact template not found")
    return template


@router.post("/artifact-templates", status_code=status.HTTP_201_CREATED)
def save_artifact_template(
    payload: ReferenceArtifactTemplateUpsert,
    service: ReferenceService = Depends(get_reference_service),
) -> dict[str, object]:
    return service.save_artifact_template(payload)


@router.patch("/artifact-templates/{template_id}/status")
def patch_artifact_template_status(
    template_id: int,
    payload: ReferenceArtifactTemplateStatusPatch,
    service: ReferenceService = Depends(get_reference_service),
) -> dict[str, object]:
    template = service.set_artifact_template_status(template_id, payload)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="artifact template not found")
    return template


@intake_router.post("/intake", status_code=status.HTTP_201_CREATED)
@intake_router.post("/intake/jobs", status_code=status.HTTP_201_CREATED)
def run_intake_job(
    payload: IntakeJobCreate,
    service: IntakeService = Depends(get_intake_service),
) -> dict[str, object]:
    try:
        return service.run(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@intake_router.get("/intake/jobs")
def list_intake_jobs(
    limit: int = 8,
    service: IntakeService = Depends(get_intake_service),
) -> list[dict[str, object]]:
    return service.jobs(limit=limit)


@intake_router.get("/intake/jobs/{job_id}/status")
def get_intake_job(
    job_id: int,
    service: IntakeService = Depends(get_intake_service),
) -> dict[str, object]:
    job = service.job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="intake job not found")
    return job
