from __future__ import annotations

from types import SimpleNamespace

from app.core.methodology import MethodologyGate, MethodologyGatePolicy
from app.core.methodology.gate.models import StageReviewIssue, StageReviewResult
from app.core.models import RuleIssue


def test_evaluation_review_aggregates_rubric_json_hard_issues() -> None:
    review = MethodologyGate().review(
        "evaluation",
        {
            "rubric_json": {
                "score": 37,
                "max_score": 39,
                "issues": [
                    RuleIssue(
                        skill_id="document_integrity",
                        code="document_integrity.table_broken",
                        severity="hard",
                        message="Broken table",
                    )
                ],
            }
        },
    )

    assert review.status == "failed"
    assert review.human_review_required is True
    assert review.metrics["rubric_issues_count"] == 1
    assert review.metrics["rubric_hard_count"] == 1
    assert review.evidence["rubric_summary"] == {"score": 37, "max_score": 39}
    assert review.issues[0].code == "document_integrity.table_broken"
    assert review.issues[0].severity == "critical"


def test_evaluation_review_keeps_soft_rubric_issues_as_warning() -> None:
    review = MethodologyGate().review(
        "evaluation",
        {
            "rubric_json": {
                "issues": [
                    {
                        "skill_id": "visual_quality",
                        "code": "visual_quality.dpi_unknown",
                        "severity": "soft",
                        "message": "DPI is unknown",
                    }
                ]
            }
        },
    )

    assert review.status == "warning"
    assert review.human_review_required is False
    assert review.metrics["rubric_soft_count"] == 1
    assert review.issues[0].severity == "minor"


def test_evaluation_review_raises_human_review_for_didactic_abstain() -> None:
    review = MethodologyGate().review(
        "evaluation",
        {
            "rubric_json": {"issues": []},
            "didactic_json": {"overall": None, "confidence": 0.2, "needs_human_review": True},
        },
    )

    assert review.status == "failed"
    assert review.human_review_required is True
    assert review.metrics["didactic_needs_human_review"] is True
    assert review.issues[0].code == "evaluation.didactic_needs_human_review"


def test_missing_rubric_is_critical() -> None:
    review = MethodologyGate().review("evaluation", {})

    assert review.status == "failed"
    assert review.human_review_required is True
    assert {issue.code for issue in review.issues} == {"evaluation.rubric_missing"}


def test_practice_review_detects_task_count_and_material_contracts() -> None:
    first = SimpleNamespace(
        title="Observation",
        input_data="Готовый отчет — см. файл `materials/final_report.md`",
        artifact_location="project/part-03/task-01/observations.md",
    )
    second = SimpleNamespace(
        title="Decision matrix",
        input_data="Сырые заметки — см. файл `materials/task_02_source_notes.md`",
        artifact_location="project/part-03/task-02/matrix.md",
    )

    review = MethodologyGate().review(
        "practice",
        {
            "markdown": "## Глава 3. Практика\n\n### Задача 1. Test\n\nBody",
            "practice_tasks": [first, second],
            "task_plan": SimpleNamespace(tasks_count=3),
        },
    )

    assert review.status == "warning"
    assert {
        "practice.tasks_count_mismatch",
        "practice.solution_materials_leak",
        "practice.non_raw_input_materials",
        "practice.task_dependency_missing",
    } <= {issue.code for issue in review.issues}


def test_dataset_generation_requires_files_and_evidence_specs() -> None:
    task = SimpleNamespace(input_data="Сырые заметки — см. файл `materials/task_01_source_notes.md`.")

    review = MethodologyGate().review(
        "dataset_generation",
        {
            "practice_tasks": [task],
            "dataset_files": [],
            "evidence_specs": [],
        },
    )

    assert review.status == "warning"
    assert {
        "dataset_generation.files_missing",
        "dataset_generation.evidence_specs_missing",
    } <= {issue.code for issue in review.issues}


def test_gate_policy_modes_match_critical_review_behavior() -> None:
    review = StageReviewResult(
        stage="evaluation",
        status="failed",
        issues=[StageReviewIssue(code="evaluation.rubric_missing", message="missing", severity="critical")],
        human_review_required=True,
    )

    observed = MethodologyGatePolicy(mode="observe").decide(review)
    approval = MethodologyGatePolicy(mode="approval").decide(review)
    strict = MethodologyGatePolicy(mode="strict").decide(review)

    assert observed.action == "warn"
    assert observed.can_continue is True
    assert approval.action == "pause"
    assert approval.blocking is True
    assert strict.action == "fail"
    assert strict.can_continue is False
