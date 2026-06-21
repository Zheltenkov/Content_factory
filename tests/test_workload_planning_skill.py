from __future__ import annotations

from pathlib import Path

from app.core.methodology.harness import Harness, resolve_profile

ROOT = Path(__file__).resolve().parent.parent / "app/core/methodology/profiles"


def test_workload_planning_calculates_days_xp_reviews_and_p2p_time() -> None:
    harness = Harness(resolve_profile("_base", ROOT))

    ctx = harness.prepare(
        "curriculum.planner",
        {"curriculum.projects": [{"id": "api", "workload_hours": 20, "difficulty": "advanced"}]},
    )

    assert ctx["curriculum.workload_plan"] == [
        {
            "project_id": "api",
            "workload_hours": 20,
            "calendar_days": 10,
            "xp": 200,
            "reviews_required": 3,
            "p2p_minutes": 45,
        }
    ]
    assert ctx["curriculum.workload_issues"] == []


def test_workload_planning_flags_mismatches_and_out_of_band_hours() -> None:
    harness = Harness(resolve_profile("_base", ROOT))

    ctx = harness.prepare(
        "curriculum.planner",
        {
            "curriculum.projects": [
                {"id": "tiny", "workload_hours": 4, "calendar_days": 99, "xp": 10, "reviews_required": 1}
            ]
        },
    )
    codes = {issue["code"] for issue in ctx["curriculum.workload_issues"]}

    assert "workload_planning.hours_out_of_band" in codes
    assert "workload_planning.calendar_days_mismatch" in codes
    assert "workload_planning.xp_mismatch" in codes
    assert "workload_planning.reviews_required_mismatch" in codes


def test_workload_planning_flags_missing_hours_without_crashing() -> None:
    harness = Harness(resolve_profile("_base", ROOT))

    ctx = harness.prepare("curriculum.planner", {"curriculum.projects": [{"id": "unknown"}]})

    assert ctx["curriculum.workload_plan"][0]["project_id"] == "unknown"
    assert ctx["curriculum.workload_issues"] == [
        {"code": "workload_planning.hours_missing", "project_id": "unknown"}
    ]


def test_workload_planning_is_planner_only_producer() -> None:
    harness = Harness(resolve_profile("_base", ROOT))

    assert harness.producers_bound_to("generator.") == []
