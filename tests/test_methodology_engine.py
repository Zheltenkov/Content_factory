from __future__ import annotations

from app.core.methodology.rules import DocImage, GeneratedDoc
from app.modules.generator.engine import EngineStage, GeneratorMethodologyEngine


def test_engine_runs_harness_hooks_and_passes_clean_doc() -> None:
    engine = GeneratorMethodologyEngine("_base")

    result = engine.run(
        [
            EngineStage("curriculum.planner", lambda ctx, _: {"curriculum.projects": ["A", "B"]}),
            EngineStage("generator.theory", lambda _ctx, augment: f"# Theory\n\n{augment}"),
        ],
        {"curriculum.projects": ["A", "B"]},
    )

    assert "generator.theory" in result.prompt_augments
    assert "curriculum.competency_weights" in result.context
    assert result.rubric_json["passed"] is True
    assert result.gate_review is not None
    assert result.gate_review.human_review_required is False


def test_engine_routes_hard_skill_issue_to_gate_human_review() -> None:
    engine = GeneratorMethodologyEngine("_base")
    bad_doc = GeneratedDoc(
        markdown="# Evaluation",
        images=[DocImage("bad.png", 400, 300, 50_000, "png", dpi=120)],
    )

    result = engine.run([EngineStage("generator.evaluation", lambda _ctx, _augment: bad_doc)])

    assert any(issue.code == "visual_quality.resolution" for issue in result.rule_issues)
    assert result.rubric_json["hard_count"] >= 1
    assert result.gate_review is not None
    assert result.gate_review.status == "failed"
    assert result.gate_review.human_review_required is True
    assert "visual_quality.resolution" in {issue.code for issue in result.gate_review.issues}
