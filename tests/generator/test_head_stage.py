from __future__ import annotations

import re

from app.core.config import get_thresholds
from app.core.models import CurriculumContext, ProjectSummary
from app.modules.generator.stages.head import HeadDraft, generate_head


def test_head_stage_builds_title_annotation_toc_and_task_plan() -> None:
    result = generate_head(_context())
    lo, hi = get_thresholds().require_range("structural.annotation_chars")

    assert result.title == "REST API"
    assert len(result.title.split()) <= 3
    assert lo <= result.annotation.chars <= hi
    assert "REST API" in result.annotation.text
    assert "результат" in result.annotation.text.lower()
    assert result.task_plan.tasks_count == 6
    assert result.task_plan.complexity == "easy"
    assert result.context_analysis.is_first_project is False
    assert result.markdown.startswith("# REST API")
    assert "## Содержание" in result.markdown
    assert "- [Глава 1. Введение и инструкция]" in result.markdown
    assert "## Глава 1. Введение и инструкция" in result.markdown
    assert "### Введение" in result.markdown
    assert "### Инструкция" in result.markdown
    assert "## Глава 2. Теория" in result.markdown
    assert "## Глава 3. Практика" in result.markdown


def test_head_stage_normalizes_no_code_instruction_boundary() -> None:
    context = _context(direction="PJM", title="Документы заказчика")
    result = generate_head(
        context,
        draft=HeadDraft(
            title="Очень длинный общий учебный проект",
            annotation="",
            intro_text="",
            instruction_text="Нужно написать код, выполнить деплой и затем описать решение.",
        ),
    )

    assert len(result.title.split()) <= 3
    assert not re.search(r"\bкод[а-я]*\b", result.intro.instruction_text, flags=re.I)
    assert not re.search(r"\bдепло[йя][а-я]*\b", result.intro.instruction_text, flags=re.I)
    for keyword in ("обязательно", "допускается", "запрещено"):
        assert keyword in result.intro.instruction_text.lower()


def _context(*, direction: str = "Backend", title: str = "Разработка REST API для сервиса") -> CurriculumContext:
    return CurriculumContext(
        plan_id=1,
        plan_title="Backend curriculum",
        direction=direction,
        block_name="API",
        block_goals=["Собрать сервис с понятным API"],
        current_project_order=2,
        current_project_title=title,
        current_project_description="Команда проектирует сервис и оформляет контракт взаимодействия.",
        current_project_learning_outcomes=["Проектирует REST API", "Описывает OpenAPI-контракт"],
        current_project_skills=["REST API", "OpenAPI", "Git"],
        current_project_audience_level="beginner",
        current_project_required_tools=["Git"],
        current_project_required_software=["OpenAPI"],
        current_project_workload_hours=8,
        previous_projects=[ProjectSummary(order=1, title="HTTP intro", learning_outcomes=["Понимает HTTP"])],
        next_projects=[ProjectSummary(order=3, title="Docker deploy", learning_outcomes=["Разворачивает сервис"])],
        sjm_context="Ты работаешь в команде сервиса и согласуешь контракт API с соседней командой.",
        additional_materials="materials/context.md",
    )
