"""Artifact references shared by generator, checker, curriculum and reference modules."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ArtifactFamily = Literal["readme", "lesson", "guide", "slides", "practice", "dataset", "report", "other"]


class ArtifactRef(BaseModel):
    """Stable reference to a generated, imported or source artifact."""

    model_config = ConfigDict(extra="forbid")

    artifact_id: str = Field(description="Stable id inside a run or persisted storage.")
    kind: str = Field(default="document", description="Logical artifact kind: markdown, csv, dataset, image, etc.")
    family: ArtifactFamily = "other"
    path: str | None = None
    uri: str | None = None
    target: str | None = None
    version: str | None = None
    checksum: str | None = None
    mime_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_location(self) -> "ArtifactRef":
        """Keep artifact identity useful without forcing storage too early."""
        if not (self.path or self.uri or self.target):
            raise ValueError("ArtifactRef requires path, uri or target")
        return self
