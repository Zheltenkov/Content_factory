"""Typed contracts for methodology gate reviews."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

IssueSeverity = Literal["info", "minor", "major", "critical"]
ReviewStatus = Literal["passed", "warning", "failed", "skipped"]


class StageReviewIssue(BaseModel):
    """Single deterministic issue found after a workflow stage."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    severity: IssueSeverity = "minor"
    repair_hint: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class StageReviewResult(BaseModel):
    """Review result attached to flow trace and report JSON."""

    model_config = ConfigDict(extra="forbid")

    stage: str
    status: ReviewStatus
    issues: list[StageReviewIssue] = Field(default_factory=list)
    repair_instructions: list[str] = Field(default_factory=list)
    human_review_required: bool = False
    metrics: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)
    duration_ms: float = 0.0

    def flow_issue_messages(self) -> list[str]:
        return [f"methodology:{issue.severity}:{issue.code}: {issue.message}" for issue in self.issues]

    def severity_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for issue in self.issues:
            counts[issue.severity] = counts.get(issue.severity, 0) + 1
        return counts
