"""Execution decisions derived from deterministic methodology reviews."""

from __future__ import annotations

import os
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.methodology.gate.models import StageReviewResult

GateAction = Literal["continue", "warn", "pause", "fail"]
GateMode = Literal["observe", "approval", "strict"]


class MethodologyGateDecision(BaseModel):
    """UI- and orchestration-friendly action for a review result."""

    model_config = ConfigDict(extra="forbid")

    stage: str
    action: GateAction
    mode: GateMode = "observe"
    status: str = "passed"
    title: str = ""
    summary: str = ""
    issues: list[dict[str, Any]] = Field(default_factory=list)
    human_review_required: bool = False
    can_continue: bool = True
    blocking: bool = False
    metrics: dict[str, Any] = Field(default_factory=dict)

    def flow_issue_messages(self) -> list[str]:
        if self.action == "continue":
            return []
        return [f"methodology_gate:{self.action}:{self.stage}: {self.summary or self.title or self.status}"]


class MethodologyGateInterrupt(RuntimeError):
    """Controlled stop raised by blocking gate policies."""

    def __init__(self, message: str, *, context: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.context = context or {}


class MethodologyGatePolicy:
    """Convert reviews into observe/approval/strict execution actions."""

    def __init__(self, mode: GateMode = "observe") -> None:
        self.mode = mode

    @classmethod
    def from_env(cls) -> "MethodologyGatePolicy":
        raw = os.getenv("METHODOLOGY_GATE_MODE", "observe").strip().lower()
        mode: GateMode = raw if raw in {"observe", "approval", "strict"} else "observe"  # type: ignore[assignment]
        return cls(mode)

    def decide(self, review: StageReviewResult) -> MethodologyGateDecision:
        counts = review.severity_counts()
        has_critical = counts.get("critical", 0) > 0
        has_major = counts.get("major", 0) > 0

        action: GateAction = "continue"
        if review.status in {"passed", "skipped"}:
            action = "continue"
        elif self.mode == "strict" and has_critical:
            action = "fail"
        elif self.mode == "approval" and (has_critical or review.human_review_required):
            action = "pause"
        elif review.status in {"warning", "failed"} or has_major:
            action = "warn"

        blocking = action in {"pause", "fail"}
        return MethodologyGateDecision(
            stage=review.stage,
            action=action,
            mode=self.mode,
            status=review.status,
            title=self._title(review.stage, action),
            summary=self._summary(review, action, counts),
            issues=[issue.model_dump(mode="json") for issue in review.issues],
            human_review_required=review.human_review_required or action == "pause",
            can_continue=not blocking,
            blocking=blocking,
            metrics={"severity_counts": counts, "issues_count": len(review.issues), **review.metrics},
        )

    @staticmethod
    def interrupt(decision: MethodologyGateDecision) -> MethodologyGateInterrupt:
        error_type = "MethodologyGatePause" if decision.action == "pause" else "MethodologyGateFail"
        return MethodologyGateInterrupt(
            decision.summary or decision.title,
            context={
                "phase": decision.stage,
                "error_type": error_type,
                "methodology_gate_decision": decision.model_dump(mode="json"),
            },
        )

    @staticmethod
    def _title(stage: str, action: GateAction) -> str:
        titles = {
            "continue": "Методологическая проверка пройдена",
            "warn": "Есть методологические предупреждения",
            "pause": "Нужна проверка методолога",
            "fail": "Методологический gate остановил этап",
        }
        return f"{titles[action]}: {stage}"

    @staticmethod
    def _summary(review: StageReviewResult, action: GateAction, counts: dict[str, int]) -> str:
        if action == "continue":
            return "Этап соответствует текущим методологическим контрактам."
        parts = [f"{severity}: {count}" for severity in ("critical", "major", "minor", "info") if (count := counts.get(severity, 0))]
        details = ", ".join(parts) or f"status: {review.status}"
        if action == "pause":
            return f"Этап требует ручной проверки перед продолжением ({details})."
        if action == "fail":
            return f"Этап не прошел strict-gate ({details})."
        return f"Генерация продолжена, но есть замечания методолога ({details})."
