from __future__ import annotations

from app.core.models import CurriculumContext
from app.modules.generator.refine import refine_document, regenerate_markdown


def test_refine_stage_improves_draft_and_reuses_methodology_gate() -> None:
    context = _context()
    markdown = "\n".join(
        [
            "# REST API",
            "",
            "## Глава 1. Введение и инструкция",
            "",
            "Описание проекта.",
            "",
            "## Глава 2. Теория",
            "## Глава 2. Теория",
            "",
            "КРИТИЧЕСКИ ВАЖНО: служебная инструкция не должна попасть в README.",
            "",
            "Повторяемый абзац про контракт API.",
            "",
            "Повторяемый абзац про контракт API.",
            "",
            "## Глава 3. Практика",
            "",
            "Сделай проверяемый артефакт.",
            "",
            "check-list.yml",
            "```yaml",
            "- text: README содержит минимум 3 главы",
            "- text: API возвращает статус 200 без ошибок",
            "```",
        ]
    )

    result = refine_document(
        context,
        markdown=markdown,
        engine_context=_asset_state(),
    )

    assert "duplicate_chapter_headers_removed" in result.edit_actions
    assert "instruction_leaks_removed" in result.edit_actions
    assert "chapter_bridges_added" in result.edit_actions
    assert result.markdown.count("## Глава 2. Теория") == 1
    assert "КРИТИЧЕСКИ ВАЖНО" not in result.markdown
    assert result.markdown.count("Повторяемый абзац про контракт API.") == 1
    assert result.quality_gate.methodology_review["stage"] == "evaluation"
    assert result.quality_gate.passed is True


def test_refine_stage_triggers_regeneration_from_comments() -> None:
    context = _context()
    markdown = "\n".join(
        [
            "# REST API",
            "",
            "## Глава 1. Введение и инструкция",
            "",
            "Сырой текст нужно заменить.",
            "",
            "## Глава 2. Теория",
            "",
            "Теория есть.",
            "",
            "## Глава 3. Практика",
            "",
            "Практика есть.",
        ]
    )

    result = refine_document(
        context,
        markdown=markdown,
        engine_context=_asset_state(),
        comments="Замени «Сырой текст нужно заменить.» на «Проверяемый текст связан с артефактом README.»",
    )

    assert result.regeneration_report.changed is True
    assert result.regeneration_report.apply_mode == "typed_patch"
    assert result.regeneration_report.applied_patch_count == 1
    assert "Проверяемый текст связан с артефактом README." in result.markdown
    assert "Сырой текст нужно заменить." not in result.markdown


def test_regeneration_fallback_repairs_placeholder_when_patch_is_unusable() -> None:
    markdown = "# Demo\n\n## Глава 2. Теория\n\nTODO\n"

    report = regenerate_markdown(markdown, "Заполни пропуск описанием результата проекта.")

    assert report.changed is True
    assert report.apply_mode in {"typed_patch", "deterministic_fallback"}
    assert "TODO" not in report.regenerated_markdown
    assert report.regenerated_markdown.strip()


def _asset_state() -> dict:
    return {
        "theory_parts": [{"index": 1, "title": "Контракт API", "body": "Теория API"}],
        "formula_assets": {
            "formulas": [{"label": "Q", "latex": "Q=1"}],
            "tables": [],
            "visuals": [{"label": "Flow", "mermaid": "flowchart TD\nA-->B"}],
        },
        "code_examples": [{"label": "Example", "language": "python", "code": "print('ok')"}],
        "dataset_files": [{"path": "materials/source.csv"}],
    }


def _context() -> CurriculumContext:
    return CurriculumContext(
        plan_id=1,
        plan_title="Backend curriculum",
        direction="Backend",
        block_name="API",
        block_goals=["Собрать сервис с понятным API"],
        current_project_order=2,
        current_project_title="REST API",
        current_project_description="Команда проектирует сервис и оформляет контракт взаимодействия.",
        current_project_learning_outcomes=["Проектирует REST API", "Описывает OpenAPI-контракт"],
        current_project_skills=["Python", "REST API", "SQL"],
        current_project_audience_level="beginner",
        current_project_required_tools=["Git"],
        current_project_required_software=["OpenAPI"],
        current_project_workload_hours=8,
        current_project_platform_name="BE02_REST",
        sjm_context="Ты — аналитик команды сервиса. Заказчик просит согласовать контракт API.",
    )
