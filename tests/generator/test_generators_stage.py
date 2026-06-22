from __future__ import annotations

import base64
import csv
import io
import zipfile

from app.core.models import CurriculumContext, ProjectSummary
from app.modules.generator.stages.generators import generate_assets
from app.modules.generator.stages.head import generate_head
from app.modules.generator.stages.practice import PracticeTask, generate_practice
from app.modules.generator.stages.practice_review import review_practice
from app.modules.generator.stages.theory import generate_theory


def test_generators_stage_creates_formula_dataset_and_code_artifacts() -> None:
    context = _backend_context()
    head = generate_head(context)
    theory = generate_theory(context, markdown=head.markdown)
    practice = generate_practice(
        context,
        markdown=theory.markdown,
        engine_context={"task_plan": {"tasks_count": 2}, "theory_parts": [part.model_dump(mode="json") for part in theory.parts]},
    )
    reviewed = review_practice(
        context,
        markdown=practice.markdown,
        engine_context={"practice_tasks": [task.model_dump(mode="json") for task in practice.tasks], "theory_parts": [part.model_dump(mode="json") for part in theory.parts]},
    )
    tasks = list(reviewed.tasks)
    tasks[0] = tasks[0].model_copy(
        update={
            "input_data": (
                tasks[0].input_data
                + "\nДоступен файл `events.csv`. Columns: id, endpoint, status_code, latency_ms, result. Rows: 4."
            )
        }
    )

    result = generate_assets(
        context,
        markdown=reviewed.markdown,
        engine_context={
            "practice_tasks": [task.model_dump(mode="json") for task in tasks],
            "theory_parts": [part.model_dump(mode="json") for part in theory.parts],
            "evidence_specs": [spec.model_dump(mode="json") for spec in practice.evidence_specs],
        },
    )
    events_csv = next(item for item in result.dataset_files if item.path == "materials/events.csv")
    rows = list(csv.DictReader(io.StringIO((events_csv.content_text or "").lstrip("\ufeff"))))

    assert result.formulas and result.formulas[0].latex
    assert result.tables and "| Зона решения |" in result.tables[0].md_table
    assert result.visuals and result.visuals[0].mermaid.startswith("flowchart TD")
    assert result.code_examples and result.code_examples[0].language in {"python", "sql"}
    assert len(rows) == 4
    assert rows[0]["endpoint"].startswith("/")
    assert "## Материалы к практике" in result.markdown
    assert "```mermaid" in result.markdown
    assert f"```{result.code_examples[0].language}" in result.markdown
    assert "$$" in result.markdown


def test_generators_stage_boundaries_skip_student_created_data_and_no_code_examples() -> None:
    context = _no_code_context()
    markdown = "\n".join(
        [
            "# Документы заказчика",
            "",
            "## Глава 2. Теория",
            "",
            "### 2.1. Контекст решения",
            "",
            "Теория описывает выбор подхода и проверку результата.",
            "",
            "**Пример:** Команда сравнивает варианты документа.",
            "",
            "## Глава 3. Практика",
        ]
    )
    task = PracticeTask(
        title="Подготовить отчет",
        situation="Заказчик просит оформить наблюдения.",
        constraints_or_risk="Нет готовой структуры.",
        input_data="Нужно создать файл `report.csv` с итоговыми строками для заказчика.",
        goal="Сформировать структуру отчета.",
        approach_bullets=["Выделить критерии.", "Описать поля.", "Согласовать формат."],
        expected_artifact="Документ в `docs/report.md`.",
        artifact_location="docs/report.md",
        p2p_criteria=["В документе есть критерии.", "Формат согласован.", "Нет готовых выводов без обоснования."],
    )

    result = generate_assets(
        context,
        markdown=markdown,
        engine_context={
            "practice_tasks": [task.model_dump(mode="json")],
            "theory_parts": [{"index": 1, "title": "Контекст решения", "body": "Теория описывает выбор подхода."}],
        },
    )

    assert not result.dataset_files
    assert "generators.dataset_files_empty" in result.issues
    assert not result.code_examples
    assert result.formulas and result.tables and result.visuals
    assert all("classDef" not in visual.mermaid and "%%{init" not in visual.mermaid for visual in result.visuals)


def test_generators_stage_xlsx_artifact_is_valid_zip_package() -> None:
    context = _backend_context()
    task = PracticeTask(
        title="Проверить таблицу API",
        situation="Команда получила выгрузку.",
        constraints_or_risk="Часть статусов ошибочна.",
        input_data="Доступен файл `checks.xlsx`. Columns: id, endpoint, status_code. Rows: 3.",
        goal="Проанализировать ошибки API.",
        approach_bullets=["Открыть выгрузку.", "Найти ошибки.", "Описать вывод."],
        expected_artifact="Отчет в `reports/checks.md`.",
        artifact_location="reports/checks.md",
        p2p_criteria=["Отчет содержит endpoint.", "Ошибки выделены.", "Есть вывод."],
    )

    result = generate_assets(
        context,
        markdown="# REST API\n\n## Глава 2. Теория\n\n### 2.1. API\n\nКонтекст API.\n\n**Пример:** Проверка.\n\n## Глава 3. Практика",
        engine_context={"practice_tasks": [task.model_dump(mode="json")], "theory_parts": [{"index": 1, "title": "API", "body": "API"}]},
    )
    xlsx = next(item for item in result.dataset_files if item.path == "materials/checks.xlsx")
    payload = base64.b64decode(xlsx.content_base64 or "")

    assert xlsx.encoding == "base64"
    assert zipfile.is_zipfile(io.BytesIO(payload))


def _backend_context() -> CurriculumContext:
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
        previous_projects=[ProjectSummary(order=1, title="HTTP intro", learning_outcomes=["Понимает HTTP"])],
        next_projects=[ProjectSummary(order=3, title="Docker deploy", learning_outcomes=["Разворачивает сервис"])],
        sjm_context="Ты — аналитик команды сервиса. Заказчик просит согласовать контракт API с соседней командой за 2 дня.",
        additional_materials="materials/context.md",
    )


def _no_code_context() -> CurriculumContext:
    return CurriculumContext(
        plan_id=1,
        plan_title="Product curriculum",
        direction="PJM",
        block_name="Discovery",
        block_goals=["Описать требования заказчика"],
        current_project_order=1,
        current_project_title="Документы заказчика",
        current_project_description="Команда формирует требования и согласует формат отчета.",
        current_project_learning_outcomes=["Формулирует требования", "Сравнивает варианты"],
        current_project_skills=["CJM", "Формирование требований"],
        current_project_audience_level="beginner",
        current_project_required_tools=["Miro"],
        current_project_required_software=[],
        current_project_workload_hours=6,
        sjm_context="Ты — координатор проекта. Заказчик прислал противоречивые ожидания к отчету.",
    )
