"""Application pipeline for T2.1 catalog intake stages."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_settings
from app.core.models import Competency, CompetencyEdge, EvidenceSource, ProfilePackage, UPSkeleton
from app.modules.curriculum.stages import stage_atomize, stage_brief_to_catalog, stage_catalog_to_dag, stage_dag_to_up, stage_normalize


class CatalogPipelineResult(BaseModel):
    """Typed bundle produced by brief -> catalog -> DAG -> UP stages."""

    model_config = ConfigDict(extra="forbid")

    spec: dict[str, Any] = Field(default_factory=dict)
    evidence_sources: list[EvidenceSource] = Field(default_factory=list)
    competencies: list[Competency] = Field(default_factory=list)
    prerequisites: list[CompetencyEdge] = Field(default_factory=list)
    dag_payload: dict[str, Any] = Field(default_factory=dict)
    up: UPSkeleton
    reports: dict[str, Any] = Field(default_factory=dict)

    def profile_package(self) -> ProfilePackage:
        return ProfilePackage(
            profile_id=str(self.spec.get("role") or "curriculum-intake"),
            title=str(self.spec.get("domain") or "Curriculum intake"),
            competencies=self.competencies,
            prerequisites=self.prerequisites,
            evidence_sources=self.evidence_sources,
            source="curriculum_pipeline",
            metadata={"spec": self.spec, "reports": self.reports},
        )


def run_catalog_pipeline(brief: str, *, client: Any | None = None, use_llm: bool | None = None) -> CatalogPipelineResult:
    settings = get_settings()
    brief_result = stage_brief_to_catalog.run(brief, client=client, use_llm=use_llm)
    atomized, atomize_report = stage_atomize.run(brief_result.competencies)
    normalized, normalize_report = stage_normalize.run(atomized, brief_result.spec)
    edges, dag_payload = stage_catalog_to_dag.run(normalized)
    up = stage_dag_to_up.run(brief_result.spec, normalized, dag_payload)
    return CatalogPipelineResult(
        spec=brief_result.spec,
        evidence_sources=brief_result.evidence_sources,
        competencies=normalized,
        prerequisites=edges,
        dag_payload=dag_payload,
        up=up,
        reports={
            "coverage": brief_result.coverage_audit,
            "atomize": atomize_report,
            "normalize": normalize_report,
            "settings": {"environment": settings.environment},
        },
    )
