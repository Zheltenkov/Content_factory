from __future__ import annotations

from app.core.models import CurriculumContext, ProjectSummary
from app.modules.generator.stages.head import generate_head
from app.modules.generator.stages.practice import PracticeTask, generate_practice
from app.modules.generator.stages.practice_review import review_practice
from app.modules.generator.stages.theory import generate_theory


def test_practice_review_critic_finds_and_repairs_bad_task() -> None:
    context = _context()
    head = generate_head(context)
    theory = generate_theory(context, markdown=head.markdown)
    bad = PracticeTask(
        title="Почитать API",
        situation="Документы есть.",
        constraints_or_risk="",
        input_data="Готовая матрица решений лежит в `materials/final_matrix.xlsx`.",
        goal="Изучить API.",
        approach_bullets=["Почитать материалы."],
        expected_artifact="Файл размещён.",
        artifact_location="",
        p2p_criteria=["Проверить хорошо."],
        covered_outcomes=[],
        theory_support=[],
    )

    result = review_practice(
        context,
        markdown=theory.markdown,
        engine_context={"practice_tasks": [bad.model_dump(mode="json")], "theory_parts": [p.model_dump(mode="json") for p in theory.parts]},
    )
    fixed = result.tasks[0]
    issue_kinds = {issue.kind for issue in result.issues}

    assert {"p2p_check", "raw_input", "goal", "artifact"} <= issue_kinds
    assert result.repaired_issue_count >= 4
    assert "materials/final_matrix.xlsx" not in fixed.input_data
    assert "materials/task_01_source_notes.md" in fixed.input_data
    assert fixed.artifact_location.endswith("/task-01/README.md")
    assert fixed.artifact_location in fixed.expected_artifact
    assert fixed.goal.startswith(("Сформировать", "Проанализировать", "Описать"))
    assert len(fixed.p2p_criteria) >= 3
    assert "## Глава 3. Практика" in result.markdown
    assert "### Задание 1." in result.markdown


def test_practice_review_generates_bonus_section_when_requested() -> None:
    context = _context()
    head = generate_head(context)
    theory = generate_theory(context, markdown=head.markdown)
    practice = generate_practice(
        context,
        markdown=theory.markdown,
        engine_context={"task_plan": {"tasks_count": 2}, "theory_parts": [p.model_dump(mode="json") for p in theory.parts]},
    )

    result = review_practice(
        context,
        markdown=practice.markdown,
        engine_context={"practice_tasks": [task.model_dump(mode="json") for task in practice.tasks], "theory_parts": [p.model_dump(mode="json") for p in theory.parts]},
        generate_bonus=True,
    )

    assert len(result.bonus_tasks) == 1
    assert result.bonus_tasks[0].artifact_location.endswith("/bonus-01/README.md")
    assert "## Бонус" in result.markdown
    assert "### Бонусное задание 1." in result.markdown
    assert result.tasks[-1].artifact_location in result.bonus_tasks[0].input_data


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
        current_project_skills=["REST API", "OpenAPI", "Git"],
        current_project_audience_level="beginner",
        current_project_required_tools=["Git"],
        current_project_required_software=["OpenAPI"],
        current_project_workload_hours=8,
        current_project_platform_name="BE02_REST",
        previous_projects=[ProjectSummary(order=1, title="HTTP intro", learning_outcomes=["Понимает HTTP"])],
        next_projects=[ProjectSummary(order=3, title="Docker deploy", learning_outcomes=["Разворачивает сервис"])],
        sjm_context="Ты — аналитик команды сервиса. Заказчик просит согласовать контракт API с соседней командой за 2 дня.",
        additional_materials="materials/context.md",
    )
