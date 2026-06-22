from __future__ import annotations

import re

from app.core.models import CurriculumContext, ProjectSummary
from app.modules.generator.stages.head import generate_head
from app.modules.generator.stages.practice import PracticeDraft, PracticeDraftTask, generate_practice
from app.modules.generator.stages.theory import generate_theory


def test_practice_stage_generates_planned_tasks_with_artifact_chain() -> None:
    context = _context()
    head = generate_head(context)
    theory = generate_theory(context, markdown=head.markdown)
    result = generate_practice(
        context,
        markdown=theory.markdown,
        engine_context={"task_plan": head.task_plan.model_dump(mode="json"), "theory_parts": [p.model_dump(mode="json") for p in theory.parts]},
    )

    assert len(result.tasks) == head.task_plan.tasks_count
    assert "## Глава 3. Практика" in result.markdown
    assert "### Задание 1." in result.markdown
    assert "materials/task_01_source_notes.md" in result.tasks[0].input_data
    assert result.tasks[1].artifact_location.endswith("/task-02/README.md")
    assert result.tasks[0].artifact_location in result.tasks[1].input_data
    assert result.artifact_chain_plan.steps[1].depends_on == result.tasks[0].artifact_location
    assert result.evidence_specs[0].path == "materials/task_01_source_notes.md"
    assert all(task.p2p_criteria for task in result.tasks)
    assert all(task.expected_artifact and task.artifact_location in task.expected_artifact for task in result.tasks)


def test_practice_stage_sanitizes_no_code_boundary_and_processed_materials() -> None:
    context = _context(direction="PJM", title="Документы заказчика")
    head = generate_head(context)
    theory = generate_theory(context, markdown=head.markdown)
    draft = PracticeDraft(
        tasks=[
            PracticeDraftTask(
                title="Написать код pipeline",
                situation="Заказчик просит готовый документ.",
                input_data="Готовая матрица решений лежит в `materials/final_matrix.xlsx`.",
                goal="Изучить код и деплой.",
                approach_bullets=["```python\nprint('bad')\n```", "Посчитать $$P = Q/T$$."],
                expected_artifact="Файл размещён.",
                p2p_criteria=["Проверить красиво."],
            )
        ]
    )
    result = generate_practice(
        context,
        markdown=theory.markdown,
        engine_context={"task_plan": {"tasks_count": 2}, "theory_parts": [p.model_dump(mode="json") for p in theory.parts]},
        draft=draft,
    )
    chapter = result.markdown.split("## Глава 3. Практика", 1)[1]

    assert len(result.tasks) == 2
    assert "materials/final_matrix.xlsx" not in result.tasks[0].input_data
    assert "materials/task_01_source_notes.md" in result.tasks[0].input_data
    assert result.tasks[0].artifact_location in result.tasks[1].input_data
    assert not re.search(r"```|\$\$|\bкод[а-я]*\b|pipeline|депло[йя][а-я]*", chapter, flags=re.I)
    assert all(task.p2p_checkable for task in result.tasks)
    assert all(len(task.p2p_criteria) >= 3 for task in result.tasks)


def _context(*, direction: str = "Backend", title: str = "REST API") -> CurriculumContext:
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
        sjm_context="Ты — аналитик команды сервиса. Заказчик просит согласовать контракт API с соседней командой за 2 дня.",
        additional_materials="materials/context.md",
    )
