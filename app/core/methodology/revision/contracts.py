"""Typed contracts for human-in-the-loop methodology revisions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ChangeTargetStage = Literal["context", "task_planning", "title", "annotation", "skeleton", "theory", "practice", "dataset", "final"]
ChangeScope = Literal["local_section_only", "task_only", "materials_only"]
ConflictSeverity = Literal["warning", "hard"]
RevisionStatus = Literal["applied", "skipped", "rejected"]
RevisionTargetKind = Literal["field", "markdown_section", "material_file", "unsupported"]
CheckpointStatus = Literal["pending", "approved", "rejected", "rolled_back"]
AssistantCommandType = Literal["approve", "request_changes", "simplify_task", "add_example", "fix_failed_criteria", "regenerate_section"]


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class MethodologistChangeRequest(BaseModel):
    """A scoped edit requested by a methodologist after a gate/checkpoint pause."""

    model_config = ConfigDict(str_strip_whitespace=True)

    target_stage: ChangeTargetStage = "final"
    target_selector: str = Field(default="", max_length=300)
    scope: ChangeScope = "local_section_only"
    instruction: str = Field(min_length=3, max_length=4000)
    issue_codes: list[str] = Field(default_factory=list)
    forbidden_changes: list[str] = Field(default_factory=list)
    expected_outcome: str = Field(default="", max_length=1000)

    @field_validator("issue_codes", "forbidden_changes", mode="before")
    @classmethod
    def _coerce_string_list(cls, value: object) -> object:
        if value is None:
            return []
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value


class ChangeRequestConflict(BaseModel):
    """Deterministic conflict that can block a requested revision."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    severity: ConflictSeverity = "hard"
    details: dict[str, Any] = Field(default_factory=dict)


class ScopedRevisionResult(BaseModel):
    """Result of applying one methodologist change request."""

    model_config = ConfigDict(extra="forbid")

    action_id: str
    status: RevisionStatus
    target_kind: RevisionTargetKind
    target_stage: str
    target_selector: str = ""
    target_id: str = ""
    target_label: str = ""
    scope: str
    changed: bool = False
    changed_chars: int = 0
    recommended_resume_node: str | None = None
    issues: list[str] = Field(default_factory=list)
    diff_preview: list[str] = Field(default_factory=list)
    before_hash: str = ""
    after_hash: str = ""


class ScopedResumePlan(BaseModel):
    """Auditable plan for resuming a workflow after accepted revisions."""

    model_config = ConfigDict(extra="forbid")

    original_resume_from_index: int
    resume_from_index: int
    original_resume_node: str = ""
    resume_node: str = ""
    moved_back: bool = False
    invalidated_nodes: list[str] = Field(default_factory=list)
    applied_action_ids: list[str] = Field(default_factory=list)
    ignored_action_ids: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class HumanApprovalCheckpoint(BaseModel):
    """A reviewable artifact snapshot that can be approved, revised or rolled back."""

    model_config = ConfigDict(extra="forbid")

    id: str
    stage: str
    node_id: str
    title: str
    summary: str
    resume_from_node: str
    allowed_targets: list[str] = Field(default_factory=list)
    artifact: dict[str, Any] = Field(default_factory=dict)
    artifact_hash: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class MethodologyAssistantParseContext(BaseModel):
    """Runtime state used to bind a free-form methodologist message to a target."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    checkpoint: dict[str, Any] = Field(default_factory=dict)
    target_registry: dict[str, Any] = Field(default_factory=dict)
    review_state: dict[str, Any] = Field(default_factory=dict)
    selected_target_id: str = ""


class MethodologyAssistantCommand(BaseModel):
    """Validated command parsed from a methodologist chat message."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    command: AssistantCommandType
    raw_text: str = Field(min_length=1, max_length=4000)
    checkpoint_id: str = ""
    checkpoint_stage: str = ""
    node_id: str = ""
    workflow_node_id: str = ""
    target_stage: ChangeTargetStage = "final"
    target_selector: str = Field(default="", max_length=300)
    target_id: str = Field(default="", max_length=300)
    scope: ChangeScope = "local_section_only"
    instruction: str = Field(default="", max_length=4000)
    issue_codes: list[str] = Field(default_factory=list)
    forbidden_changes: list[str] = Field(default_factory=list)
    expected_outcome: str = Field(default="", max_length=1000)
    confidence: float = Field(default=0.75, ge=0.0, le=1.0)
    source: Literal["deterministic"] = "deterministic"

    def to_change_request(self) -> MethodologistChangeRequest:
        if self.command in {"approve", "regenerate_section"}:
            raise ValueError(f"{self.command} command is not a scoped change request")
        return MethodologistChangeRequest(
            target_stage=self.target_stage,
            target_selector=self.target_selector,
            scope=self.scope,
            instruction=self.instruction or self.raw_text,
            issue_codes=self.issue_codes,
            forbidden_changes=self.forbidden_changes,
            expected_outcome=self.expected_outcome,
        )
