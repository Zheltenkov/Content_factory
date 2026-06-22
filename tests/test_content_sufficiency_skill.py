from __future__ import annotations

from pathlib import Path

from app.core.methodology.harness import Harness, resolve_profile
from app.core.methodology.rules import GeneratedDoc

ROOT = Path(__file__).resolve().parent.parent / "app/core/methodology/profiles"


def test_content_sufficiency_augments_theory_and_practice() -> None:
    harness = Harness(resolve_profile("_base", ROOT))

    theory = harness.augment("generator.theory")
    practice = harness.augment("generator.practice")

    for text in (theory, practice):
        assert "ключевые шаги проекта" in text
        assert "образовательных результатов" in text
        assert "практические элементы" in text


def test_content_sufficiency_is_scoped_to_generation_content_stages() -> None:
    harness = Harness(resolve_profile("_base", ROOT))

    intro = harness.augment("generator.intro")

    assert "ключевые шаги проекта" not in intro
    assert "образовательных результатов" not in intro


def test_content_sufficiency_machine_validator_is_checker_scoped() -> None:
    profile = resolve_profile("_base", ROOT)
    skill = profile.skills["content_sufficiency"]
    harness = Harness(profile)
    empty = GeneratedDoc(markdown="# Теория\n\nИщите все сами. Практики нет.")
    broken = GeneratedDoc(markdown="# Теория", metadata={"theory_parts": [], "practice_tasks": [{"title": "x"}]})

    assert skill.check is not None
    assert any(item.id == "content_sufficiency" for item in harness.bind.get(("post.validate", "checker.content_sufficiency"), []))
    assert all(item.id != "content_sufficiency" for item in harness.bind.get(("post.validate", "generator.evaluation"), []))
    assert not any(issue.skill_id == "content_sufficiency" for issue in harness.validate("generator.evaluation", empty))
    assert any(issue.skill_id == "content_sufficiency" for issue in harness.validate("checker.content_sufficiency", broken))
