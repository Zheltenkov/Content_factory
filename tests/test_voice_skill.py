from __future__ import annotations

from pathlib import Path

from app.core.methodology.harness import Harness, resolve_profile
from app.core.methodology.rules import GeneratedDoc

ROOT = Path(__file__).resolve().parent.parent / "app/core/methodology/profiles"


def test_voice_augments_generator_prompts_with_regulation_style() -> None:
    harness = Harness(resolve_profile("_base", ROOT))

    text = harness.augment("generator.theory")

    assert "peer" in text
    assert "профессиональные термины" in text
    assert "плейсхолдеры" in text


def test_voice_style_guard_accepts_clear_peer_text() -> None:
    harness = Harness(resolve_profile("_base", ROOT))
    doc = GeneratedDoc(
        markdown=(
            "# Введение\n\n"
            "Ты соберешь небольшой сервис и проверишь его через тесты. "
            "Сначала настрой окружение, затем запусти приложение и сравни результат с примером."
        )
    )

    assert harness.validate("generator.style_guard", doc) == []


def test_voice_style_guard_flags_bureaucracy_and_placeholders() -> None:
    harness = Harness(resolve_profile("_base", ROOT))
    doc = GeneratedDoc(
        markdown=(
            "# {{project_title}}\n\n"
            "В рамках данного проекта осуществляется выполнение задания посредством настройки сервиса. "
            "TODO: вставьте финальное описание."
        )
    )

    issues = harness.validate("generator.style_guard", doc)

    assert {issue.code for issue in issues} == {"voice.bureaucratic", "voice.placeholder"}
    assert all(issue.severity == "soft" for issue in issues)
