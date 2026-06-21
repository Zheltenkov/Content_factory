"""Unified educational competency model replacing CG string skills and Spravochnik skill rows."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

BloomLevel = Literal["remember", "understand", "apply", "analyze", "evaluate", "create"]
CompetencyStatus = Literal["candidate", "accepted", "needs_review", "rejected", "superseded"]
Atomicity = Literal["atomic", "composite", "non_skill", "unknown"]
ResolutionStatus = Literal["matched", "alias", "fuzzy", "new", "unresolved"]
BLOOM_RANK: dict[BloomLevel, int] = {
    "remember": 1,
    "understand": 2,
    "apply": 3,
    "analyze": 4,
    "evaluate": 5,
    "create": 6,
}


def _clean_list(values: list[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = str(item).strip()
        if text and text.casefold() not in seen:
            seen.add(text.casefold())
            out.append(text)
    return out


class CompetencyIndicator(BaseModel):
    """Observable indicator bound to a Bloom level."""

    model_config = ConfigDict(extra="forbid")

    text: str
    bloom: BloomLevel = "apply"

    @field_validator("text")
    @classmethod
    def text_is_not_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("indicator text must not be empty")
        return value


class EvidenceSource(BaseModel):
    """Evidence item used to justify a competency candidate or profile package."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(validation_alias=AliasChoices("evidence_id", "id"))
    claim: str = ""
    source_type: Literal["vacancy", "framework", "syllabus", "catalog", "other"] = "other"
    url: str | None = None
    snippet: str = ""
    retrieved_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CompetencyRef(BaseModel):
    """Compact reference used inside UP projects and generation context."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    competency_id: str = Field(validation_alias=AliasChoices("competency_id", "id", "tmp_id"))
    catalog_id: int | None = Field(default=None, validation_alias=AliasChoices("catalog_id", "canonical_skill_id", "skill_id"))
    canonical_name: str = Field(validation_alias=AliasChoices("canonical_name", "name", "title"))
    weight: float | None = Field(default=None, ge=0)
    role: Literal["primary", "supporting", "reinforcement", "assessment"] = "primary"
    bloom: BloomLevel | None = None

    @classmethod
    def from_text(cls, name: str, *, role: str = "primary") -> "CompetencyRef":
        clean = name.strip()
        return cls(competency_id=clean, canonical_name=clean, role=role)

    @classmethod
    def from_competency(cls, item: "Competency", *, role: str = "primary", weight: float | None = None) -> "CompetencyRef":
        return cls(
            competency_id=item.competency_id,
            catalog_id=item.catalog_id,
            canonical_name=item.canonical_name,
            role=role,
            weight=weight,
            bloom=item.bloom_level,
        )


class Competency(BaseModel):
    """Single educational competency shared by catalog, curriculum and generator."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    competency_id: str = Field(validation_alias=AliasChoices("competency_id", "tmp_id", "id"))
    catalog_id: int | None = Field(default=None, validation_alias=AliasChoices("catalog_id", "canonical_skill_id", "skill_id"))
    canonical_name: str = Field(validation_alias=AliasChoices("canonical_name", "name", "title"))
    source_name: str | None = None
    group: str = ""
    coverage_area: str | None = None
    aliases: list[str] = Field(default_factory=list)
    indicators: list[CompetencyIndicator] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    atomicity: Atomicity = "unknown"
    resolution: ResolutionStatus = "unresolved"
    status: CompetencyStatus = "candidate"
    match_score: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_payload(cls, data: Any) -> Any:
        """Map Spravochnik/CG legacy names into the single competency contract."""
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        nearest_name = payload.pop("nearest_name", None)
        canonical_group = payload.pop("canonical_group", None)
        decision = payload.pop("decision", None)
        if "canonical_name" not in payload and nearest_name:
            payload["canonical_name"] = nearest_name
        if "group" not in payload and canonical_group:
            payload["group"] = canonical_group
        if "status" not in payload and decision:
            payload["status"] = decision
        payload.setdefault("aliases", [])
        if payload.get("source_name"):
            payload["aliases"] = [*payload["aliases"], payload["source_name"]]
        return payload

    @model_validator(mode="after")
    def clean_values(self) -> "Competency":
        self.canonical_name = self.canonical_name.strip()
        if not self.canonical_name:
            raise ValueError("canonical_name must not be empty")
        self.group = self.group.strip()
        self.aliases = _clean_list([self.canonical_name, *self.aliases])
        self.tools = _clean_list(self.tools)
        self.evidence_ids = _clean_list(self.evidence_ids)
        return self

    @property
    def bloom_level(self) -> BloomLevel:
        """Highest Bloom level across indicators; defaults to remember."""
        if not self.indicators:
            return "remember"
        return max((indicator.bloom for indicator in self.indicators), key=lambda level: BLOOM_RANK[level])

    def as_ref(self, *, role: str = "primary", weight: float | None = None) -> CompetencyRef:
        return CompetencyRef.from_competency(self, role=role, weight=weight)


class CompetencyEdge(BaseModel):
    """Prerequisite or soft dependency between competencies."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(validation_alias=AliasChoices("source_id", "src"))
    target_id: str = Field(validation_alias=AliasChoices("target_id", "dst"))
    relation_type: Literal["hard", "soft"] = "hard"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    rationale: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
