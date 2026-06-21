from __future__ import annotations

from pathlib import Path

from app.core.methodology.harness import Harness, resolve_profile
from app.core.methodology.rules import ArtifactRef, GeneratedDoc

ROOT = Path(__file__).resolve().parent.parent / "app/core/methodology/profiles"

BLOCKS = """## General Rules

- Работай в ветке develop.
- Весь код и материалы проекта должны находиться в репозитории GitLab.
- Следуй правилам Школы 21 и инструкции p2p-проверки.

## Disclaimer

Этот проект является учебным материалом Школы 21. Используй его только в рамках образовательного процесса.

## Feedback

Если ты заметил ошибку или хочешь предложить улучшение, заполни форму обратной связи по ссылке из проекта.
"""


def _checklist() -> ArtifactRef:
    return ArtifactRef(
        artifact_id="checklist",
        kind="checklist",
        family="practice",
        path="check-list.yml",
        metadata={"content": "checks:\n  - criteria: Команда pytest запускается без ошибок\n"},
    )


def _doc(markdown: str, *, active: bool = True) -> GeneratedDoc:
    return GeneratedDoc(
        markdown=markdown,
        artifacts=[_checklist()],
        metadata={"template_blocks_required": active},
    )


def test_template_blocks_augments_finalize_prompt_verbatim() -> None:
    harness = Harness(resolve_profile("_base", ROOT))

    text = harness.augment("generator.finalize")

    assert "## General Rules" in text
    assert "## Disclaimer" in text
    assert "## Feedback" in text


def test_template_blocks_accepts_unchanged_blocks() -> None:
    harness = Harness(resolve_profile("_base", ROOT))

    issues = harness.validate("generator.evaluation", _doc(f"# Project\n\n{BLOCKS}"))

    assert not [issue for issue in issues if issue.skill_id == "template_blocks"]


def test_template_blocks_flags_missing_and_changed_blocks() -> None:
    harness = Harness(resolve_profile("_base", ROOT))
    markdown = """# Project

## General Rules

- Работай как хочешь.

## Feedback

Если ты заметил ошибку или хочешь предложить улучшение, заполни форму обратной связи по ссылке из проекта.
"""

    issues = [issue for issue in harness.validate("generator.evaluation", _doc(markdown)) if issue.skill_id == "template_blocks"]
    codes = {issue.code for issue in issues}

    assert "template_blocks.changed" in codes
    assert "template_blocks.missing" in codes


def test_template_blocks_ignores_partial_documents_without_activation() -> None:
    harness = Harness(resolve_profile("_base", ROOT))

    issues = harness.validate("generator.evaluation", _doc("# Partial", active=False))

    assert not [issue for issue in issues if issue.skill_id == "template_blocks"]
