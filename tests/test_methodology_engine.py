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
    assert result.workflow is not None
    assert result.workflow.status == "completed"
    assert [item.node_id for item in result.stage_results] == ["task_planning", "theory"]


def test_engine_records_workflow_checkpoints_and_skips_conditioned_stage() -> None:
    engine = GeneratorMethodologyEngine("_base", run_id="run-g1")

    result = engine.run(
        [
            EngineStage("generator.context", lambda _ctx, _augment: {"seed": {"title": "Project"}}, node_id="context"),
            EngineStage(
                "generator.translate",
                lambda _ctx, _augment: {"translated_markdown": "should not run"},
                node_id="translate",
                run_if=lambda ctx: ctx.get("target_language") != "ru",
            ),
        ],
        {"target_language": "ru"},
    )

    assert result.run_id == "run-g1"
    assert result.workflow is not None
    assert result.workflow.status == "completed"
    assert [(item.node_id, item.status) for item in result.stage_results] == [
        ("context", "success"),
        ("translate", "skipped"),
    ]
    assert result.stage_results[0].input_hash
    assert result.stage_results[0].output_artifact["seed"]["title"]["preview"] == "Project"
    assert result.context["workflow"]["progress_total"] == 2


def test_engine_routes_hard_skill_issue_to_gate_human_review() -> None:
    engine = GeneratorMethodologyEngine("_base")
    bad_doc = GeneratedDoc(
        markdown="# Evaluation",
        images=[DocImage("bad.png", 400, 300, 50_000, "png", dpi=120)],
    )

    result = engine.run([EngineStage("generator.evaluation", lambda _ctx, _augment: bad_doc, node_id="evaluation", gate_stage="evaluation")])

    assert any(issue.code == "visual_quality.resolution" for issue in result.rule_issues)
    assert result.rubric_json["hard_count"] >= 1
    assert result.gate_review is not None
    assert result.gate_review.status == "failed"
    assert result.gate_review.human_review_required is True
    assert "visual_quality.resolution" in {issue.code for issue in result.gate_review.issues}
    assert result.workflow is not None
    assert result.workflow.status == "needs_review"
    assert result.stage_reviews["generator.evaluation"].human_review_required is True
