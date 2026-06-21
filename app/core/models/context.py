"""Profile and methodology context contracts for orchestration boundaries."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.models.artifacts import ArtifactRef
from app.core.models.competency import Competency, CompetencyEdge, EvidenceSource
from app.core.models.curriculum import UPProject, UPSkeleton
from app.core.models.methodology import GeneratedDoc


class ProfilePackage(BaseModel):
    """Catalog slice passed from reference/curriculum modules to downstream workflows."""

    model_config = ConfigDict(extra="forbid")

    profile_id: str
    title: str
    version: str = "v1"
    competencies: list[Competency] = Field(default_factory=list)
    prerequisites: list[CompetencyEdge] = Field(default_factory=list)
    evidence_sources: list[EvidenceSource] = Field(default_factory=list)
    source: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def competency_map(self) -> dict[str, Competency]:
        return {item.competency_id: item for item in self.competencies}


class MethodologyContext(BaseModel):
    """Typed state shared by methodology skills, generator, checker and gate."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    run_id: str | None = None
    profile: ProfilePackage | None = None
    up: UPSkeleton | None = None
    current_project: UPProject | None = None
    generated_doc: GeneratedDoc | None = None
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    values: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def produced(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    def with_value(self, key: str, value: Any) -> "MethodologyContext":
        return self.model_copy(update={"values": {**self.values, key: value}})
