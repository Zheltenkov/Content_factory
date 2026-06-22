"""Checker orchestration for deterministic structural and content checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.methodology.gate import MethodologyGate, StageReviewResult
from app.core.methodology.harness import Harness, resolve_profile
from app.core.methodology.rubric import rule_issues_to_rubric
from app.core.methodology.rules import GeneratedDoc, RuleIssue
from app.modules.checker.structural import StructuralAxisResult, evaluate_document

CONTENT_STAGE = "checker.content_sufficiency"
PROFILES_ROOT = Path(__file__).resolve().parents[2] / "core" / "methodology" / "profiles"


class ContentSufficiencyResult(BaseModel):
    """Deterministic C4 checks over generated theory/practice metadata."""

    model_config = ConfigDict(extra="forbid")

    stage: str = CONTENT_STAGE
    profile_id: str
    issues: list[RuleIssue] = Field(default_factory=list)
    rubric_json: dict[str, Any] = Field(default_factory=dict)
    gate_review: StageReviewResult

    @property
    def passed(self) -> bool:
        return bool(self.rubric_json.get("passed")) and not self.gate_review.human_review_required


class CheckerDeterministicResult(BaseModel):
    """Combined deterministic checker payload before didactic jury."""

    model_config = ConfigDict(extra="forbid")

    structural: StructuralAxisResult
    content: ContentSufficiencyResult
    rubric_json: dict[str, Any]
    gate_review: StageReviewResult

    @property
    def passed(self) -> bool:
        return self.structural.passed and self.content.passed and not self.gate_review.human_review_required


def evaluate_content_sufficiency(
    doc: GeneratedDoc,
    *,
    profile_id: str = "_base",
    program_type: str | None = None,
    context: dict[str, Any] | None = None,
    gate: MethodologyGate | None = None,
    profile_root: Path = PROFILES_ROOT,
) -> ContentSufficiencyResult:
    """Run C4 theory/practice checks via methodology harness."""

    profile = resolve_profile(profile_id, profile_root, program_type=program_type)
    issues = Harness(profile).validate(CONTENT_STAGE, doc, dict(context or {}))
    rubric = rule_issues_to_rubric(issues)
    review = (gate or MethodologyGate()).review("evaluation", {"generated_doc": doc, "markdown": doc.markdown, "rubric_json": rubric})
    return ContentSufficiencyResult(profile_id=profile_id, issues=issues, rubric_json=rubric, gate_review=review)


def evaluate_deterministic(
    doc: GeneratedDoc,
    *,
    profile_id: str = "_base",
    program_type: str | None = None,
    context: dict[str, Any] | None = None,
    gate: MethodologyGate | None = None,
    profile_root: Path = PROFILES_ROOT,
) -> CheckerDeterministicResult:
    """Run structural C2 and C4 content checks and merge their rubric_json."""

    structural = evaluate_document(
        doc,
        profile_id=profile_id,
        program_type=program_type,
        context=context,
        gate=gate,
        profile_root=profile_root,
    )
    content = evaluate_content_sufficiency(
        doc,
        profile_id=profile_id,
        program_type=program_type,
        context=context,
        gate=gate,
        profile_root=profile_root,
    )
    all_issues = [*structural.issues, *content.issues]
    rubric = rule_issues_to_rubric(all_issues)
    review = (gate or MethodologyGate()).review("evaluation", {"generated_doc": doc, "markdown": doc.markdown, "rubric_json": rubric})
    return CheckerDeterministicResult(structural=structural, content=content, rubric_json=rubric, gate_review=review)
