"""Curriculum and UP contracts shared by reference, curriculum and generator modules."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.models.artifacts import ArtifactRef
from app.core.models.competency import CompetencyRef

UPStatus = Literal["built", "deferred", "draft"]
ProjectFormat = Literal["individual", "group", "pair", "workshop", "unknown"]


def _split_text(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        values = value
    else:
        values = str(value).replace(";", "\n").splitlines()
    return [item.strip(" \t-") for item in values if str(item).strip(" \t-")]


class ProjectSummary(BaseModel):
    """Compact project view used as neighboring context."""

    model_config = ConfigDict(extra="forbid")

    order: int
    title: str
    description: str = ""
    learning_outcomes: list[str] = Field(default_factory=list)
    block_name: str | None = None
    competency_refs: list[CompetencyRef] = Field(default_factory=list)


class CurriculumContext(BaseModel):
    """Generation context built from a persisted curriculum plan."""

    model_config = ConfigDict(extra="forbid")

    plan_id: int | None = None
    plan_title: str = ""
    direction: str = ""
    block_name: str
    block_goals: list[str] = Field(default_factory=list)
    current_project_order: int
    current_project_title: str = ""
    current_project_description: str = ""
    current_project_learning_outcomes: list[str] = Field(default_factory=list)
    current_project_skills: list[str] = Field(default_factory=list)
    current_project_competency_refs: list[CompetencyRef] = Field(default_factory=list)
    current_project_audience_level: str | None = None
    current_project_required_tools: list[str] = Field(default_factory=list)
    current_project_required_software: list[str] = Field(default_factory=list)
    current_project_format: ProjectFormat = "individual"
    current_project_group_size: int = 1
    current_project_workload_hours: float = 0.0
    current_project_platform_name: str | None = None
    current_project_gitlab_link: str | None = None
    previous_projects: list[ProjectSummary] = Field(default_factory=list)
    next_projects: list[ProjectSummary] = Field(default_factory=list)
    all_block_learning_outcomes: list[str] = Field(default_factory=list)
    previous_block_projects: list[ProjectSummary] = Field(default_factory=list)
    next_block_projects: list[ProjectSummary] = Field(default_factory=list)
    storytelling_type: str = "sjm"
    sjm_context: str | None = None
    expert_development_notes: str | None = None
    additional_materials: str | None = None

    def current_project_payload(self) -> dict[str, Any]:
        """Compact project dict consumed by methodology producers and generator stages."""
        return {
            "id": self.current_project_platform_name or self.current_project_title,
            "title": self.current_project_title,
            "description": self.current_project_description,
            "learning_outcomes": self.current_project_learning_outcomes,
            "skills": self.current_project_skills,
            "competency_refs": [ref.model_dump(mode="json") for ref in self.current_project_competency_refs],
            "workload_hours": self.current_project_workload_hours,
            "format": self.current_project_format,
            "block_name": self.block_name,
        }


class UPProject(BaseModel):
    """One row/project in a curriculum skeleton."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    block: str = ""
    block_goal: str = ""
    order: int
    title: str
    description: str = ""
    outcomes_know: list[str] = Field(default_factory=list)
    outcomes_can: list[str] = Field(default_factory=list)
    outcomes_skills: list[str] = Field(default_factory=list)
    competency_refs: list[CompetencyRef] = Field(default_factory=list)
    required_tools: list[str] = Field(default_factory=list)
    required_software: list[str] = Field(default_factory=list)
    materials: str = ""
    storytelling: str = ""
    format: ProjectFormat = "individual"
    group_size: int = Field(default=1, ge=1)
    hours_astro: float = Field(default=0.0, ge=0.0)
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_curriculum_names(cls, data: Any) -> Any:
        """Accept Spravochnik rows and old CG payloads without storing string skills."""
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        if "competency_refs" not in payload:
            raw = payload.pop("skills", None) or payload.pop("current_project_skills", None) or []
            payload["competency_refs"] = [CompetencyRef.from_text(str(item)) for item in raw if str(item).strip()]
        for key in ("outcomes_know", "outcomes_can", "outcomes_skills", "required_tools", "required_software"):
            if key in payload:
                payload[key] = _split_text(payload[key])
        if payload.get("format") == "индивидуальный":
            payload["format"] = "individual"
        return payload

    @field_validator("title")
    @classmethod
    def title_is_not_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("project title must not be empty")
        return value

    @property
    def learning_outcomes(self) -> list[str]:
        return [*self.outcomes_know, *self.outcomes_can, *self.outcomes_skills]

    def to_summary(self) -> ProjectSummary:
        return ProjectSummary(
            order=self.order,
            title=self.title,
            description=self.description,
            learning_outcomes=self.learning_outcomes,
            block_name=self.block or None,
            competency_refs=self.competency_refs,
        )


class UPBlock(BaseModel):
    """Thematic block inside an UP skeleton."""

    model_config = ConfigDict(extra="forbid")

    name: str
    code: str = "UNK"
    goals: list[str] = Field(default_factory=list)
    projects: list[UPProject] = Field(default_factory=list)

    def all_learning_outcomes(self) -> list[str]:
        seen: dict[str, None] = {}
        for project in self.projects:
            for outcome in project.learning_outcomes:
                seen.setdefault(outcome, None)
        return list(seen)


class UPSkeleton(BaseModel):
    """Typed boundary from curriculum planner to downstream generators."""

    model_config = ConfigDict(extra="forbid")

    status: UPStatus = "draft"
    title: str = "Черновик учебного плана"
    direction: str = ""
    version: str = "v1"
    rows: list[UPProject] = Field(default_factory=list)
    blocks: list[UPBlock] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def derive_blocks_from_rows(self) -> "UPSkeleton":
        """Keep block and row views consistent while JSON stays compact."""
        if self.blocks or not self.rows:
            return self
        grouped: dict[str, list[UPProject]] = {}
        goals: dict[str, list[str]] = {}
        for row in self.rows:
            key = row.block or "Без блока"
            grouped.setdefault(key, []).append(row)
            if row.block_goal:
                goals.setdefault(key, [])
                if row.block_goal not in goals[key]:
                    goals[key].append(row.block_goal)
        self.blocks = [UPBlock(name=name, goals=goals.get(name, []), projects=projects) for name, projects in grouped.items()]
        return self

    def project_by_title(self, title: str) -> UPProject | None:
        needle = title.casefold()
        for project in self.rows:
            if project.title.casefold() == needle:
                return project
        return None

    def competency_ids(self) -> list[str]:
        seen: dict[str, None] = {}
        for project in self.rows:
            for ref in project.competency_refs:
                seen.setdefault(ref.competency_id, None)
        return list(seen)

    def build_context(
        self,
        project_order: int,
        *,
        block_name: str | None = None,
        cross_block_depth: int = 2,
        plan_id: int | None = None,
    ) -> CurriculumContext | None:
        """Build generator context for a project without reparsing curriculum CSV."""
        for block_index, block in enumerate(self.blocks):
            if block_name and block.name != block_name:
                continue
            projects = sorted(block.projects, key=lambda item: item.order)
            for project_index, project in enumerate(projects):
                if project.order != project_order:
                    continue
                return CurriculumContext(
                    plan_id=plan_id,
                    plan_title=self.title,
                    direction=self.direction,
                    block_name=block.name,
                    block_goals=block.goals,
                    current_project_order=project.order,
                    current_project_title=project.title,
                    current_project_description=project.description,
                    current_project_learning_outcomes=project.learning_outcomes,
                    current_project_skills=[ref.canonical_name for ref in project.competency_refs],
                    current_project_competency_refs=project.competency_refs,
                    current_project_audience_level=_metadata_text(project, "audience_level"),
                    current_project_required_tools=project.required_tools,
                    current_project_required_software=project.required_software,
                    current_project_format=project.format,
                    current_project_group_size=project.group_size,
                    current_project_workload_hours=project.hours_astro,
                    current_project_platform_name=_metadata_text(project, "platform_name"),
                    current_project_gitlab_link=_metadata_text(project, "gitlab_link"),
                    previous_projects=[item.to_summary() for item in projects[:project_index]],
                    next_projects=[item.to_summary() for item in projects[project_index + 1 :]],
                    all_block_learning_outcomes=block.all_learning_outcomes(),
                    previous_block_projects=_cross_block_projects(self.blocks, block_index - 1, -cross_block_depth),
                    next_block_projects=_cross_block_projects(self.blocks, block_index + 1, cross_block_depth),
                    storytelling_type=_metadata_text(project, "storytelling_type") or "sjm",
                    sjm_context=project.storytelling or None,
                    expert_development_notes=_metadata_text(project, "expert_notes"),
                    additional_materials=project.materials or None,
                )
        return None


def _metadata_text(project: UPProject, key: str) -> str | None:
    value = project.metadata.get(key)
    text = str(value).strip() if value is not None else ""
    return text or None


def _cross_block_projects(blocks: list[UPBlock], index: int, depth: int) -> list[ProjectSummary]:
    if index < 0 or index >= len(blocks) or depth == 0:
        return []
    projects = sorted(blocks[index].projects, key=lambda item: item.order)
    selected = projects[:depth] if depth > 0 else projects[depth:]
    return [project.to_summary() for project in selected]
