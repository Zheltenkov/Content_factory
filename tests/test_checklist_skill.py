from __future__ import annotations

from pathlib import Path

from app.core.methodology.harness import Harness, resolve_profile
from app.core.methodology.rules import ArtifactRef, GeneratedDoc

ROOT = Path(__file__).resolve().parent.parent / "app/core/methodology/profiles"


def _doc_with_checklist(content: str) -> GeneratedDoc:
    return GeneratedDoc(
        markdown="# Project",
        artifacts=[
            ArtifactRef(
                artifact_id="checklist",
                kind="checklist",
                family="practice",
                path="check-list.yml",
                metadata={"content": content},
            )
        ],
    )


def test_checklist_augments_practice_prompt_only() -> None:
    harness = Harness(resolve_profile("_base", ROOT))

    practice = harness.augment("generator.practice")
    theory = harness.augment("generator.theory")

    assert "check-list.yml" in practice
    assert "выполнено" in practice
    assert "check-list.yml" not in theory


def test_checklist_accepts_objective_yaml_items() -> None:
    harness = Harness(resolve_profile("_base", ROOT))
    doc = _doc_with_checklist(
        """
checks:
  - title: Запуск проекта
    criteria: Команда pytest запускается без ошибок
  - title: Покрытие
    criteria: Есть минимум 3 теста на функцию parse_config
"""
    )

    assert harness.validate("generator.evaluation", doc) == []


def test_checklist_flags_invalid_yaml() -> None:
    harness = Harness(resolve_profile("_base", ROOT))

    issues = harness.validate("generator.evaluation", _doc_with_checklist("checks: ["))

    assert [issue.code for issue in issues] == ["checklist.yaml_invalid"]


def test_checklist_flags_vague_non_objective_items() -> None:
    harness = Harness(resolve_profile("_base", ROOT))
    doc = _doc_with_checklist(
        """
checks:
  - title: Оформление
    criteria: Проект оформлен аккуратно и понятно
"""
    )

    codes = {issue.code for issue in harness.validate("generator.evaluation", doc)}

    assert "checklist.vague" in codes
    assert "checklist.not_objective" in codes
