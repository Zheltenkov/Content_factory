from __future__ import annotations

from pathlib import Path

from app.core.methodology.harness import Harness, resolve_profile
from app.core.methodology.rules import ArtifactRef, GeneratedDoc

ROOT = Path(__file__).resolve().parent.parent / "app/core/methodology/profiles"


def _doc(markdown: str) -> GeneratedDoc:
    return GeneratedDoc(
        markdown=markdown,
        artifacts=[
            ArtifactRef(
                artifact_id="checklist",
                kind="checklist",
                family="practice",
                path="check-list.yml",
                metadata={"content": "checks:\n  - criteria: Команда pytest запускается без ошибок\n"},
            )
        ],
    )


def test_software_constraints_augments_intro_prompt() -> None:
    harness = Harness(resolve_profile("_base", ROOT))

    intro = harness.augment("generator.intro")
    theory = harness.augment("generator.theory")

    assert "официальные каналы установки" in intro
    assert "доступны в России" in intro
    assert "официальные каналы установки" not in theory


def test_software_constraints_accepts_official_available_dependencies() -> None:
    harness = Harness(resolve_profile("_base", ROOT))
    doc = _doc(
        (
            "## ПО\n\n"
            "Используй Python 3.12 и Docker 26.1. Устанавливай их с официального сайта "
            "или официальной документации. Инструменты доступны в России, подходят для кампуса "
            "и распространяются по open-source лицензии."
        )
    )

    assert harness.validate("generator.evaluation", doc) == []


def test_software_constraints_flags_piracy_unofficial_sources_and_access_risk() -> None:
    harness = Harness(resolve_profile("_base", ROOT))
    doc = _doc(
        (
            "## ПО\n\n"
            "Для проекта нужен Docker и Python. Скачайте сборку с форума, используйте crack "
            "для активации; сервис работает только через VPN."
        )
    )

    issues = harness.validate("generator.evaluation", doc)
    codes = {issue.code for issue in issues}

    assert "software_constraints.piracy" in codes
    assert "software_constraints.unofficial" in codes
    assert "software_constraints.russia_unavailable" in codes
    assert "software_constraints.version_missing" in codes
    assert any(issue.severity == "hard" for issue in issues)
    assert any(issue.severity == "soft" for issue in issues)
