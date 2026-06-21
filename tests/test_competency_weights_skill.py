from __future__ import annotations

from pathlib import Path

from app.core.methodology.harness import Harness, resolve_profile

ROOT = Path(__file__).resolve().parent.parent / "app/core/methodology/profiles"


def test_competency_weights_produces_balanced_reference_weights() -> None:
    harness = Harness(resolve_profile("_base", ROOT))

    ctx = harness.prepare(
        "curriculum.planner",
        {
            "reference.competencies": [{"competency_id": "python.basic"}, {"competency_id": "git.flow"}],
            "curriculum.projects": [
                {"id": "p1", "workload_hours": 2, "competency_refs": ["python.basic", "git.flow"]},
                {"id": "p2", "workload_hours": 1, "competency_refs": ["python.basic"]},
            ],
        },
    )

    weights = ctx["curriculum.competency_weights"]
    assert set(weights) == {"python.basic", "git.flow"}
    assert sum(weights.values()) == 100
    assert weights["python.basic"] > weights["git.flow"]
    assert ctx["curriculum.competency_weight_issues"] == []


def test_competency_weights_flags_missing_reference_competency() -> None:
    harness = Harness(resolve_profile("_base", ROOT))

    ctx = harness.prepare(
        "curriculum.planner",
        {
            "reference.competencies": [{"competency_id": "python.basic"}],
            "curriculum.projects": [{"id": "p1", "competency_refs": ["python.basic", "git.flow"]}],
        },
    )

    assert sum(ctx["curriculum.competency_weights"].values()) == 100
    assert ctx["curriculum.competency_weight_issues"] == [
        {"code": "competency_weights.reference_missing", "competency_id": "git.flow"}
    ]


def test_competency_weights_empty_projects_do_not_write_context() -> None:
    harness = Harness(resolve_profile("_base", ROOT))

    ctx = harness.prepare("curriculum.planner", {"curriculum.projects": []})

    assert "curriculum.competency_weights" not in ctx
    assert harness.producers_bound_to("generator.") == []
