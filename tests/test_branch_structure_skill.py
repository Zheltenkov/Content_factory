from __future__ import annotations

from pathlib import Path

from app.core.methodology.harness import Harness, resolve_profile

ROOT = Path(__file__).resolve().parent.parent / "app/core/methodology/profiles"


def test_branch_structure_produces_clean_project_order() -> None:
    harness = Harness(resolve_profile("_base", ROOT))
    ctx = harness.prepare(
        "curriculum.planner",
        {
            "curriculum.projects": [
                {"id": "intro", "difficulty": "intro"},
                {"id": "api", "difficulty": "basic"},
                {"id": "db", "difficulty": "intermediate"},
            ]
        },
    )

    assert ctx["curriculum.branch_order"] == ["intro", "api", "db"]
    assert ctx["curriculum.branch_structure"]["issues"] == []
    assert set(ctx["curriculum.competency_weights"]) == {"intro", "api", "db"}
    assert sum(ctx["curriculum.competency_weights"].values()) == 100


def test_branch_structure_flags_and_reorders_broken_sequence() -> None:
    harness = Harness(resolve_profile("_base", ROOT))
    ctx = harness.prepare(
        "curriculum.planner",
        {
            "curriculum.projects": [
                {"id": "deploy", "difficulty": "advanced"},
                {"id": "intro", "difficulty": "intro"},
                {"id": "api", "difficulty": "basic"},
            ]
        },
    )

    assert ctx["curriculum.branch_order"] == ["intro", "api", "deploy"]
    assert ctx["curriculum.branch_structure"]["issues"][0]["code"] == "branch_structure.rank_drop"


def test_branch_structure_is_planner_only_producer() -> None:
    profile = resolve_profile("_base", ROOT)
    skill = profile.skills["branch_structure"]
    harness = Harness(profile)

    assert skill.produces == ["curriculum.branch_order", "curriculum.branch_structure"]
    assert skill.prepare is not None
    assert harness.producers_bound_to("generator.") == []
