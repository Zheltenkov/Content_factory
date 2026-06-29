"""Thin reference module service over shared curriculum catalog storage."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.curriculum.repo import CatalogSkill, CurriculumCatalogRepo
from app.modules.curriculum.stages.pipeline import run_catalog_pipeline

CatalogStatus = Literal["active", "candidate", "deprecated"]
ReviewStatus = Literal["open", "resolved", "ignored"]
ArtifactFamily = Literal["analysis", "document", "configuration", "design", "production", "practice"]
ArtifactScopeType = Literal["taxonomy_node", "skill_group", "coverage_area", "any"]
ArtifactTemplateStatus = Literal["active", "draft", "deprecated"]
ArchiveKind = Literal["group", "skill", "indicator"]


class ReferenceService:
    """Application-layer adapter for catalog read/edit workflows."""

    def __init__(self, repo: CurriculumCatalogRepo) -> None:
        self.repo = repo

    def summary(self) -> dict[str, int]:
        return self.repo.reference_summary()

    def competencies(self, *, query: str = "", status: str | None = None, limit: int = 100) -> list[dict[str, object]]:
        return self.repo.list_reference_competencies(query=query, status=status, limit=limit)

    def groups(self, *, query: str = "", status: str | None = None, limit: int = 100) -> list[dict[str, object]]:
        return self.competencies(query=query, status=status, limit=limit)

    def group(self, group_id: int) -> dict[str, object] | None:
        return self.competency(group_id)

    def create_group(self, payload: "ReferenceGroupCreate") -> dict[str, object] | None:
        return self.repo.create_reference_group(
            title=payload.title,
            description=payload.description,
            status=payload.status,
        )

    def create_group_skill(self, group_id: int, payload: "ReferenceGroupSkillCreate") -> dict[str, object] | None:
        return self.repo.create_group_skill(
            group_id,
            canonical_name=payload.canonical_name,
            skill_type=payload.skill_type,
            status=payload.status,
            aliases=payload.aliases,
        )

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

    def skill(self, skill_id: int) -> dict[str, object] | None:
        return self.repo.get_reference_skill(skill_id)

    def create_indicator(self, skill_id: int, payload: "ReferenceIndicatorCreate") -> dict[str, object] | None:
        return self.repo.create_reference_indicator(
            skill_id,
            text=payload.text,
            dimension_code=payload.dimension_code,
            notes=payload.notes,
        )

    def patch_indicator(self, indicator_id: int, patch: "ReferenceIndicatorPatch") -> dict[str, object] | None:
        return self.repo.update_reference_indicator(
            indicator_id,
            text=patch.text,
            dimension_code=patch.dimension_code,
            notes=patch.notes,
        )

    def delete_indicator(self, indicator_id: int) -> bool:
        return self.repo.delete_reference_indicator(indicator_id)

    def profiles(self, *, include_service: bool = False, limit: int = 100) -> list[dict[str, object]]:
        return self.repo.list_reference_profiles(include_service=include_service, limit=limit)

    def profile(self, profile_id: int) -> dict[str, object] | None:
        return self.repo.get_reference_profile(profile_id)

    def reviews(
        self,
        *,
        status: ReviewStatus | None = "open",
        severity: str | None = None,
        reason_code: str | None = None,
        entity_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, object]]:
        return self.repo.list_review_queue(
            status=status,
            severity=severity,
            reason_code=reason_code,
            entity_type=entity_type,
            limit=limit,
        )

    def resolve_review(self, review_id: int, patch: "ReferenceReviewPatch") -> bool:
        return self.repo.resolve_review_item(review_id, status=patch.status, note=patch.note)

    def candidate_competencies(self, *, limit: int = 100) -> dict[str, object]:
        return self.repo.list_candidate_competencies(limit=limit)

    def apply_candidate_action(self, payload: "ReferenceCandidateCompetencyAction") -> dict[str, object]:
        if payload.action == "rename":
            return self.repo.rename_candidate_competency(payload.competency_id, payload.new_title or "")
        if payload.action == "merge":
            if payload.target_competency_id is None:
                return {"status": "target_required", "competency_id": payload.competency_id}
            return self.repo.merge_candidate_competency(payload.competency_id, payload.target_competency_id)
        if payload.action == "move_skill":
            if payload.target_competency_id is None or payload.competency_skill_id is None:
                return {"status": "target_required", "competency_id": payload.competency_id}
            return self.repo.move_candidate_competency_skill(payload.competency_skill_id, payload.target_competency_id)
        return self.repo.resolve_candidate_competency(payload.competency_id, payload.action, payload.resolution_note)

    def archive(self, *, query: str = "", scope: str = "all", limit: int = 100) -> dict[str, object]:
        return self.repo.reference_archive(query=query, scope=scope, limit=limit)

    def restore_archive_item(self, payload: "ReferenceArchiveRestore") -> dict[str, object]:
        return self.repo.restore_reference_archive_item(payload.kind, payload.id)

    def artifact_templates(self, *, active_only: bool = False) -> list[dict[str, object]]:
        return self.repo.list_artifact_templates(active_only=active_only)

    def artifact_template(self, template_id: int) -> dict[str, object] | None:
        return self.repo.get_artifact_template(template_id)

    def save_artifact_template(self, payload: "ReferenceArtifactTemplateUpsert") -> dict[str, object]:
        return self.repo.upsert_artifact_template(
            code=payload.code or payload.title,
            title=payload.title,
            artifact_family=payload.artifact_family,
            artifact_description=payload.artifact_description,
            project_name_pattern=payload.project_name_pattern,
            materials_pattern=payload.materials_pattern,
            storytelling_pattern=payload.storytelling_pattern,
            validation_criteria=payload.validation_criteria,
            priority=payload.priority,
            status=payload.status,
            source=payload.source,
            scopes=[
                {"scope_type": payload.scope_type, "scope_name": scope_name, "weight": payload.scope_weight}
                for scope_name in (payload.scope_names or ([] if payload.scope_type == "any" else [""]))
            ],
        )

    def set_artifact_template_status(self, template_id: int, payload: "ReferenceArtifactTemplateStatusPatch") -> dict[str, object] | None:
        return self.repo.set_artifact_template_status(template_id, payload.status)


class IntakeService:
    """Synchronous adapter for the legacy Spravochnik brief intake workflow."""

    def __init__(self, repo: CurriculumCatalogRepo) -> None:
        self.repo = repo

    def run(self, payload: "IntakeJobCreate") -> dict[str, object]:
        brief = payload.brief_text.strip()
        if not brief:
            raise ValueError("brief_text is required")
        job = self.repo.create_intake_job(
            brief_text=brief,
            source_kind=payload.source_kind,
            source_name=payload.source_name,
            file_path=payload.file_path,
            use_council=payload.use_council,
        )
        job_id = int(job["id"])
        try:
            self.repo.update_intake_job(
                job_id,
                status="running",
                current_stage="brief_to_catalog",
                progress_note="Извлекаем навыки, DAG и учебный план из брифа",
                started_at=datetime.now(UTC),
            )
            result = run_catalog_pipeline(brief, use_llm=payload.use_llm)
            brief_id = self.repo.create_profile_brief(brief, spec=result.spec)
            saved = [self.repo.save_competency(item, source_note=f"intake:{brief_id}") for item in result.competencies]
            plan = self.repo.save_curriculum_plan(result.up, source_policy="intake", author_ref=f"intake:{job_id}")
            saved_items = [
                {
                    "skill_id": link.skill_id,
                    "competency_id": link.competency_id,
                    "name": competency.canonical_name,
                    "group": competency.group or competency.coverage_area,
                    "created_competency": link.created_competency,
                    "created_review": link.created_review,
                    "indicator_count": len(competency.indicators),
                }
                for competency, link in zip(result.competencies, saved)
            ]
            result_payload = {
                "brief_id": brief_id,
                "spec": result.spec,
                "competency_count": len(result.competencies),
                "saved_skill_ids": [item.skill_id for item in saved],
                "saved_items": saved_items,
                "review_count": sum(1 for item in saved if item.created_review),
                "curriculum_plan": {"plan_id": plan.plan_id, "project_count": plan.project_count},
                "reports": result.reports,
            }
            return self.repo.update_intake_job(
                job_id,
                brief_id=brief_id,
                status="succeeded",
                current_stage="done",
                progress_note="Бриф разобран, каталог и УП обновлены",
                result_payload=result_payload,
                finished_at=datetime.now(UTC),
            ) or {"id": job_id, "status": "succeeded", "result_payload": result_payload}
        except Exception as exc:
            self.repo.update_intake_job(
                job_id,
                status="failed",
                current_stage="failed",
                progress_note="Ошибка обработки брифа",
                error_text=str(exc),
                finished_at=datetime.now(UTC),
            )
            raise

    def jobs(self, *, limit: int = 8) -> list[dict[str, object]]:
        return self.repo.list_intake_jobs(limit=limit)

    def job(self, job_id: int) -> dict[str, object] | None:
        return self.repo.get_intake_job(job_id)


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


class ReferenceGroupCreate(BaseModel):
    """Create an empty catalog-admin group (competency) from the reference panel."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    description: str = ""
    status: CatalogStatus = "active"


class ReferenceGroupSkillCreate(BaseModel):
    """Create a skill inside a catalog-admin group/competency."""

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


class ReferenceIndicatorCreate(BaseModel):
    """Create an editable indicator row for a skill."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    dimension_code: str = "unspecified"
    notes: str = "reference-ui"


class ReferenceIndicatorPatch(BaseModel):
    """Patch an editable indicator row."""

    model_config = ConfigDict(extra="forbid")

    text: str | None = None
    dimension_code: str | None = None
    notes: str | None = None


class ReferenceReviewPatch(BaseModel):
    """Decision over one review queue item."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["resolved", "ignored", "open"]
    note: str = ""


class ReferenceCandidateCompetencyAction(BaseModel):
    """Legacy catalog-admin candidate competency action."""

    model_config = ConfigDict(extra="forbid")

    action: Literal["accept", "reject", "review", "rename", "merge", "move_skill"]
    competency_id: int
    resolution_note: str = ""
    new_title: str | None = None
    target_competency_id: int | None = None
    competency_skill_id: int | None = None


class ReferenceArchiveRestore(BaseModel):
    """Restore one archived catalog group, skill or indicator."""

    model_config = ConfigDict(extra="forbid")

    kind: ArchiveKind
    id: int


class ReferenceArtifactTemplateUpsert(BaseModel):
    """Editable UP artifact template from catalog-admin."""

    model_config = ConfigDict(extra="forbid")

    code: str = ""
    title: str = Field(min_length=1)
    artifact_family: ArtifactFamily = "practice"
    artifact_description: str = ""
    project_name_pattern: str = ""
    materials_pattern: str = ""
    storytelling_pattern: str = ""
    validation_criteria: str = ""
    priority: int = 100
    status: ArtifactTemplateStatus = "active"
    source: str = "methodologist"
    scope_type: ArtifactScopeType = "coverage_area"
    scope_names: list[str] = Field(default_factory=list)
    scope_weight: float = 1.0


class ReferenceArtifactTemplateStatusPatch(BaseModel):
    """Activate/deprecate a UP artifact template."""

    model_config = ConfigDict(extra="forbid")

    status: ArtifactTemplateStatus


class IntakeJobCreate(BaseModel):
    """Brief payload accepted by the restored `/intake` backend adapter."""

    model_config = ConfigDict(extra="forbid")

    brief_text: str = Field(min_length=1)
    source_kind: Literal["text", "file"] = "text"
    source_name: str | None = None
    file_path: str | None = None
    use_council: bool = True
    use_llm: bool = False


def skill_payload(skill: CatalogSkill) -> dict[str, Any]:
    return {
        "skill_id": skill.skill_id,
        "canonical_name": skill.canonical_name,
        "normalized_name": skill.normalized_name,
        "skill_type": skill.skill_type,
        "status": skill.status,
        "aliases": list(skill.aliases),
    }
