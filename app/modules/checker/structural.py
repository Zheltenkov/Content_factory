"""C2 structural checker axis: methodology-skill wiring, not legacy rubric port."""

from __future__ import annotations

from collections.abc import Sequence
from importlib import import_module
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.methodology.gate import MethodologyGate, StageReviewResult
from app.core.methodology.harness import Harness, resolve_profile
from app.core.methodology.rubric import rule_issues_to_rubric
from app.core.methodology.rules import GeneratedDoc, RuleIssue
from app.core.models import ArtifactRef

CHECKER_STAGE = "checker.evaluation"
PROFILES_ROOT = Path(__file__).resolve().parents[2] / "core" / "methodology" / "profiles"


class StructuralAxisResult(BaseModel):
    """Structural-axis payload consumed by checker UI, service and MethodologyGate."""

    model_config = ConfigDict(extra="forbid")

    stage: str = CHECKER_STAGE
    profile_id: str
    program_type: str | None = None
    active_skills: list[str] = Field(default_factory=list)
    issues: list[RuleIssue] = Field(default_factory=list)
    rubric_json: dict[str, Any] = Field(default_factory=dict)
    gate_review: StageReviewResult
    signals: dict[str, Any] = Field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return bool(self.rubric_json.get("passed")) and not self.gate_review.human_review_required


def evaluate_readme(
    markdown: str,
    *,
    profile_id: str = "_base",
    program_type: str | None = None,
    project_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    artifacts: Sequence[ArtifactRef] | None = None,
    context: dict[str, Any] | None = None,
    gate: MethodologyGate | None = None,
    profile_root: Path = PROFILES_ROOT,
) -> StructuralAxisResult:
    """Evaluate a ready README through methodology skills bound to checker.evaluation."""

    doc = GeneratedDoc(
        markdown=markdown,
        project_id=project_id,
        metadata={**dict(metadata or {}), "readme_structure_required": True},
        artifacts=list(artifacts or []),
    )
    return evaluate_document(
        doc,
        profile_id=profile_id,
        program_type=program_type,
        context=context,
        gate=gate,
        profile_root=profile_root,
    )


def evaluate_document(
    doc: GeneratedDoc,
    *,
    profile_id: str = "_base",
    program_type: str | None = None,
    context: dict[str, Any] | None = None,
    gate: MethodologyGate | None = None,
    profile_root: Path = PROFILES_ROOT,
) -> StructuralAxisResult:
    """Run structural methodology skills and aggregate RuleIssue into rubric_json."""

    profile = resolve_profile(profile_id, profile_root, program_type=program_type)
    harness = Harness(profile)
    doc = doc.model_copy(update={"metadata": {**doc.metadata, "readme_structure_required": True}})
    doc, signals = _attach_checker_signals(doc)
    ctx = {
        **dict(context or {}),
        "markdown": doc.markdown,
        "generated_doc": doc,
        "checker_signals": signals,
    }
    issues = harness.validate(CHECKER_STAGE, doc, ctx)
    rubric = rule_issues_to_rubric(issues)
    review = (gate or MethodologyGate()).review("evaluation", {**ctx, "rubric_json": rubric})
    return StructuralAxisResult(
        profile_id=profile_id,
        program_type=profile.program_type,
        active_skills=[skill.id for skill in harness.bind.get(("post.validate", CHECKER_STAGE), [])],
        issues=issues,
        rubric_json=rubric,
        gate_review=review,
        signals=signals,
    )


def run(markdown: str | GeneratedDoc, **kwargs: Any) -> StructuralAxisResult:
    """Convenience entrypoint for service/router code."""

    if isinstance(markdown, GeneratedDoc):
        return evaluate_document(markdown, **kwargs)
    return evaluate_readme(markdown, **kwargs)


def _attach_checker_signals(doc: GeneratedDoc) -> tuple[GeneratedDoc, dict[str, Any]]:
    signals = _collect_signals(doc)
    if not signals:
        return doc, {}
    metadata = {**doc.metadata, "checker_signals": signals}
    return doc.model_copy(update={"metadata": metadata}), signals


def _collect_signals(doc: GeneratedDoc) -> dict[str, Any]:
    """Use C1 signals.py when it exists; C2 itself does not duplicate signal heuristics."""

    try:
        module = import_module("app.modules.checker.signals")
    except ModuleNotFoundError:
        return {}
    for name in ("collect_signals", "extract_signals", "analyze", "scan"):
        func = getattr(module, name, None)
        if not callable(func):
            continue
        for args in ((doc,), (doc.markdown, doc.metadata), (doc.markdown,)):
            try:
                result = func(*args)
            except TypeError:
                continue
            return _as_dict(result)
    return {}


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return dict(value)
    return {"value": value}
