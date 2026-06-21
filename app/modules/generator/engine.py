"""Thin generator engine adapter for methodology harness and gate."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.methodology.gate import MethodologyGate, StageReviewResult
from app.core.methodology.harness import Harness, resolve_profile
from app.core.methodology.rules import GeneratedDoc, RuleIssue

StageFn = Callable[[dict[str, Any], str], GeneratedDoc | dict[str, Any] | str | None]
PROFILES_ROOT = Path(__file__).resolve().parents[2] / "core" / "methodology" / "profiles"


@dataclass(frozen=True, slots=True)
class EngineStage:
    """One namespaced generator/curriculum/checker stage executable by the engine."""

    name: str
    run: StageFn


@dataclass(slots=True)
class GeneratorEngineResult:
    """Execution result with methodology artifacts ready for trace/UI."""

    context: dict[str, Any]
    documents: dict[str, GeneratedDoc] = field(default_factory=dict)
    prompt_augments: dict[str, str] = field(default_factory=dict)
    rule_issues: list[RuleIssue] = field(default_factory=list)
    rubric_json: dict[str, Any] = field(default_factory=dict)
    gate_review: StageReviewResult | None = None


class GeneratorMethodologyEngine:
    """Run stages through harness hooks and finish with MethodologyGate evaluation."""

    def __init__(
        self,
        profile_id: str = "_base",
        *,
        program_type: str | None = None,
        profile_root: Path = PROFILES_ROOT,
        gate: MethodologyGate | None = None,
    ) -> None:
        self.profile = resolve_profile(profile_id, profile_root, program_type=program_type)
        self.harness = Harness(self.profile)
        self.gate = gate or MethodologyGate()

    def run(self, stages: Iterable[EngineStage], context: dict[str, Any] | None = None) -> GeneratorEngineResult:
        ctx = dict(context or {})
        documents: dict[str, GeneratedDoc] = {}
        augments: dict[str, str] = {}
        issues: list[RuleIssue] = []

        for stage in stages:
            ctx = self.harness.prepare(stage.name, ctx)
            augment = self.harness.augment(stage.name, ctx)
            if augment:
                augments[stage.name] = augment
            output = stage.run(ctx, augment)
            ctx, doc = _merge_output(ctx, output)
            if doc is None:
                continue
            documents[stage.name] = doc
            issues.extend(self.harness.validate(stage.name, doc, ctx))

        rubric = rule_issues_to_rubric(issues)
        ctx["rubric_json"] = rubric
        review = self.gate.review("evaluation", ctx)
        return GeneratorEngineResult(
            context=ctx,
            documents=documents,
            prompt_augments=augments,
            rule_issues=issues,
            rubric_json=rubric,
            gate_review=review,
        )


def rule_issues_to_rubric(issues: Iterable[RuleIssue]) -> dict[str, Any]:
    """Serialize deterministic skill issues into MethodologyGate rubric_json."""

    items = [issue.model_dump(mode="json") for issue in issues]
    hard = [item for item in items if item.get("severity") == "hard"]
    soft = [item for item in items if item.get("severity") == "soft"]
    return {
        "issues": items,
        "passed": not hard,
        "hard_count": len(hard),
        "soft_count": len(soft),
        "skills": sorted({str(item.get("skill_id")) for item in items if item.get("skill_id")}),
    }


def _merge_output(ctx: dict[str, Any], output: GeneratedDoc | dict[str, Any] | str | None) -> tuple[dict[str, Any], GeneratedDoc | None]:
    if output is None:
        return ctx, None
    if isinstance(output, GeneratedDoc):
        return _attach_doc(ctx, output), output
    if isinstance(output, str):
        doc = GeneratedDoc(markdown=output)
        return _attach_doc(ctx, doc), doc
    if isinstance(output, dict):
        next_ctx = {**ctx, **output}
        raw_doc = output.get("generated_doc")
        if isinstance(raw_doc, GeneratedDoc):
            return _attach_doc(next_ctx, raw_doc), raw_doc
        markdown = output.get("markdown")
        if isinstance(markdown, str):
            doc = GeneratedDoc(
                markdown=markdown,
                images=list(output.get("images") or []),
                artifacts=list(output.get("artifacts") or []),
                project_id=output.get("project_id"),
                metadata=dict(output.get("metadata") or {}),
            )
            return _attach_doc(next_ctx, doc), doc
        return next_ctx, None
    raise TypeError(f"Unsupported stage output: {type(output)!r}")


def _attach_doc(ctx: dict[str, Any], doc: GeneratedDoc) -> dict[str, Any]:
    return {**ctx, "generated_doc": doc, "markdown": doc.markdown}
