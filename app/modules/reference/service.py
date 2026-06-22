"""Thin reference module service over shared curriculum catalog storage."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.curriculum.repo import CatalogSkill, CurriculumCatalogRepo

CatalogStatus = Literal["active", "candidate", "deprecated"]
ReviewStatus = Literal["open", "resolved", "ignored"]


class ReferenceService:
    """Application-layer adapter for catalog read/edit workflows."""

    def __init__(self, repo: CurriculumCatalogRepo) -> None:
        self.repo = repo

    def summary(self) -> dict[str, int]:
        return self.repo.reference_summary()

    def competencies(self, *, query: str = "", status: str | None = None, limit: int = 100) -> list[dict[str, object]]:
        return self.repo.list_reference_competencies(query=query, status=status, limit=limit)

    def competency(self, competency_id: int) -> dict[str, object] | None:
        return self.repo.get_reference_competency(competency_id)

    def patch_competency(self, competency_id: int, patch: "ReferenceCompetencyPatch") -> dict[str, object] | None:
        return self.repo.update_reference_competency(
            competency_id,
            title=patch.title,
            description=patch.description,
            status=patch.status,
        )

    def skills(self, *, query: str = "", limit: int = 100, include_deprecated: bool = False) -> list[CatalogSkill]:
        return self.repo.list_skills(query=query, limit=limit, include_deprecated=include_deprecated)

    def upsert_skill(self, payload: "ReferenceSkillUpsert") -> CatalogSkill:
        return self.repo.upsert_skill(
            payload.canonical_name,
            skill_type=payload.skill_type,
            status=payload.status,
            aliases=payload.aliases,
            alias_source="reference-ui",
        )

    def patch_skill(self, skill_id: int, patch: "ReferenceSkillPatch") -> CatalogSkill | None:
        return self.repo.update_skill(
            skill_id,
            canonical_name=patch.canonical_name,
            skill_type=patch.skill_type,
            status=patch.status,
            aliases=patch.aliases,
        )

    def profiles(self, *, include_service: bool = False, limit: int = 100) -> list[dict[str, object]]:
        return self.repo.list_reference_profiles(include_service=include_service, limit=limit)

    def profile(self, profile_id: int) -> dict[str, object] | None:
        return self.repo.get_reference_profile(profile_id)

    def reviews(self, *, status: ReviewStatus | None = "open", limit: int = 100) -> list[dict[str, object]]:
        return self.repo.list_review_queue(status=status, limit=limit)

    def resolve_review(self, review_id: int, patch: "ReferenceReviewPatch") -> bool:
        return self.repo.resolve_review_item(review_id, status=patch.status, note=patch.note)


class ReferenceCompetencyPatch(BaseModel):
    """Editable competency fields exposed by the reference panel."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    description: str | None = None
    status: CatalogStatus | None = None


class ReferenceSkillUpsert(BaseModel):
    """Create or update-by-name payload for catalog skills."""

    model_config = ConfigDict(extra="forbid")

    canonical_name: str = Field(min_length=1)
    skill_type: str = "unknown"
    status: CatalogStatus = "active"
    aliases: list[str] = Field(default_factory=list)


class ReferenceSkillPatch(BaseModel):
    """Editable skill fields exposed by the reference panel."""

    model_config = ConfigDict(extra="forbid")

    canonical_name: str | None = None
    skill_type: str | None = None
    status: CatalogStatus | None = None
    aliases: list[str] | None = None


class ReferenceReviewPatch(BaseModel):
    """Decision over one review queue item."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["resolved", "ignored"]
    note: str = ""


def skill_payload(skill: CatalogSkill) -> dict[str, Any]:
    return {
        "skill_id": skill.skill_id,
        "canonical_name": skill.canonical_name,
        "normalized_name": skill.normalized_name,
        "skill_type": skill.skill_type,
        "status": skill.status,
        "aliases": list(skill.aliases),
    }
