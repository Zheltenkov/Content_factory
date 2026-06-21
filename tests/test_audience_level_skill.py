from __future__ import annotations

from pathlib import Path

from app.core.methodology.harness import Harness, resolve_profile

ROOT = Path(__file__).resolve().parent.parent / "app/core/methodology/profiles"


def test_audience_level_pool_defaults_to_empty_frontier() -> None:
    harness = Harness(resolve_profile("_base", ROOT))

    ctx = harness.prepare("curriculum.planner", {"curriculum.projects": []})

    assert ctx["curriculum.level_source"] == "pool"
    assert ctx["curriculum.assumed_known"] == []
    assert ctx["curriculum.experienced_share"] == 0.30
    assert ctx["curriculum.audience_level"]["assumed_known"] == []


def test_audience_level_branch_of_branch_uses_previous_competencies() -> None:
    harness = Harness(resolve_profile("_base", ROOT))

    ctx = harness.prepare(
        "curriculum.planner",
        {
            "curriculum.level_source": "branch_of_branch",
            "curriculum.previous_branches": [
                {"competencies": [{"competency_id": "python.basic"}, {"id": "git.flow"}]},
                {"outcomes": ["testing.basics", "python.basic"]},
            ],
        },
    )

    assert ctx["curriculum.level_source"] == "branch_of_branch"
    assert ctx["curriculum.assumed_known"] == ["python.basic", "git.flow", "testing.basics"]


def test_audience_level_kids_override_none_stays_empty() -> None:
    harness = Harness(resolve_profile("kids", ROOT, program_type="main"))

    ctx = harness.prepare("curriculum.planner", {})

    assert ctx["curriculum.level_source"] == "pool"
    assert ctx["curriculum.assumed_known"] == []
    assert harness.producers_bound_to("generator.") == []
