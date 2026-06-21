from __future__ import annotations

from pathlib import Path

from app.core.methodology.harness import Harness, resolve_profile

ROOT = Path(__file__).resolve().parent.parent / "app/core/methodology/profiles"


def test_autotests_requires_docker_for_technical_python_project() -> None:
    harness = Harness(resolve_profile("_base", ROOT))

    ctx = harness.prepare(
        "curriculum.planner",
        {"curriculum.projects": [{"id": "api", "type": "technical", "language": "Python"}]},
    )

    policy = ctx["curriculum.autotest_policy"][0]
    assert policy["project_id"] == "api"
    assert policy["required"] is True
    assert policy["verification"] == "autotests"
    assert policy["docker_image"] == "python"
    assert "tests/" in policy["hidden_artifacts"]
    assert ctx["curriculum.autotest_issues"] == []


def test_autotests_routes_theoretical_project_to_checklist() -> None:
    harness = Harness(resolve_profile("_base", ROOT))

    ctx = harness.prepare(
        "curriculum.planner",
        {"curriculum.projects": [{"id": "research", "type": "research"}]},
    )

    assert ctx["curriculum.autotest_policy"] == [
        {"project_id": "research", "required": False, "verification": "checklist", "checklist": "check-list.yml"}
    ]


def test_autotests_flags_unsupported_technical_language() -> None:
    harness = Harness(resolve_profile("_base", ROOT))

    ctx = harness.prepare(
        "curriculum.planner",
        {"curriculum.projects": [{"id": "web", "type": "technical", "language": "JavaScript"}]},
    )

    assert ctx["curriculum.autotest_policy"][0]["required"] is True
    assert ctx["curriculum.autotest_policy"][0]["docker_image"] == "basic"
    assert ctx["curriculum.autotest_issues"] == [
        {"code": "autotests.unsupported_language", "project_id": "web", "languages": ["javascript"]}
    ]


def test_autotests_is_planner_only_producer() -> None:
    harness = Harness(resolve_profile("_base", ROOT))

    assert harness.producers_bound_to("generator.") == []
