from __future__ import annotations

from pathlib import Path

from app.core.methodology.harness import Harness, resolve_profile

ROOT = Path(__file__).resolve().parent.parent / "app/core/methodology/profiles"


def test_access_constructors_sequential_for_project_dependencies() -> None:
    harness = Harness(resolve_profile("_base", ROOT))

    ctx = harness.prepare(
        "curriculum.planner",
        {"curriculum.projects": [{"id": "intro"}, {"id": "api", "depends_on": ["intro"]}]},
    )

    assert ctx["curriculum.access_policy"][1] == {
        "project_id": "api",
        "mode": "after_completion",
        "depends_on": ["intro"],
        "reason": "project_dependencies",
    }
    assert ctx["curriculum.access_issues"] == []


def test_access_constructors_relaxed_customer_preference_opens_parallel() -> None:
    harness = Harness(resolve_profile("_base", ROOT))

    ctx = harness.prepare(
        "curriculum.planner",
        {
            "curriculum.customer_preference": "без жестких дедлайнов",
            "curriculum.projects": [{"id": "p1"}, {"id": "p2"}],
        },
    )

    assert {item["mode"] for item in ctx["curriculum.access_policy"]} == {"parallel"}


def test_access_constructors_small_group_uses_after_review() -> None:
    harness = Harness(resolve_profile("_base", ROOT))

    ctx = harness.prepare(
        "curriculum.planner",
        {"curriculum.group_size": 8, "curriculum.projects": [{"id": "solo"}]},
    )

    assert ctx["curriculum.access_policy"][0]["mode"] == "after_review"
    assert ctx["curriculum.access_policy"][0]["reason"] == "small_group"


def test_access_constructors_exam_gate_and_unknown_dependency_issue() -> None:
    harness = Harness(resolve_profile("_base", ROOT))

    ctx = harness.prepare(
        "curriculum.planner",
        {"curriculum.projects": [{"id": "final", "has_exam": True, "depends_on": ["missing"]}]},
    )

    assert ctx["curriculum.access_policy"][0]["mode"] == "after_exam"
    assert ctx["curriculum.access_issues"] == [
        {"code": "access_constructors.unknown_dependency", "project_id": "final", "dependency": "missing"}
    ]


def test_access_constructors_is_planner_only_producer() -> None:
    harness = Harness(resolve_profile("_base", ROOT))

    assert harness.producers_bound_to("generator.") == []
