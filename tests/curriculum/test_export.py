from __future__ import annotations

import csv
import io

from app.core.models import UPProject, UPSkeleton
from app.modules.curriculum.export import CSV_COLUMN_ALIASES, CurriculumExportV1, CurriculumProjectExportV1, up_to_curriculum_export
from app.modules.curriculum.repo import CURRICULUM_ALIAS_FIELD_TO_COLUMN


def test_curriculum_export_json_csv_json_roundtrip_is_equivalent() -> None:
    export = CurriculumExportV1(
        title="Backend curriculum",
        direction="Backend",
        projects=[
            CurriculumProjectExportV1(
                block_name="API",
                block_goals=["Спроектировать сервис"],
                order=1,
                title="REST API",
                description="Сервис с HTTP API.",
                outcomes_know=["Знает HTTP"],
                outcomes_can=["Проектирует endpoint"],
                outcomes_skills=["Реализует API"],
                required_software=["Python", "Docker"],
                additional_materials="materials/api.md",
                sjm="Команда запускает backend-сервис.",
                format="group",
                group_size=4,
                workload_hours=12.0,
                workload_days=4.08,
                total_workload_days=8.0,
                xp=120,
                passing_threshold=75.0,
                p2p_count=2,
                skills=["REST API", "HTTP"],
                platform_name="BSA01_REST",
                gitlab_link="https://gitlab.example/rest",
            )
        ],
    )

    csv_text = export.to_csv()
    header = next(csv.reader(io.StringIO(csv_text), delimiter=";"))
    restored = CurriculumExportV1.from_csv(csv_text, title=export.title, direction=export.direction)

    assert len(header) == 22
    assert restored.model_dump(mode="json") == export.model_dump(mode="json")


def test_curriculum_export_parses_legacy_program_template_outcome_columns() -> None:
    csv_text = "\n".join(
        [
            "Тематический блок,Цели блока,№ ,Название контентной единицы,Краткое описание,"
            "Образовательные результаты,Образовательные результаты,Образовательные результаты,"
            "Необходимое ПО,Дополнительные материалы для генерации,Сторителлинг,Формат,Кол-во в группе,"
            '"Трудоемкость, астр.часы","Трудоемкость, дни","Общая трудоемкость, дни",XP за проект,'
            "% прохождения проекта,Количество p2p проверок,Список навыков,"
            "Название проекта на платформе и в Gitlab,Ссылки на GitLab",
            "Аналитика,Жизненный цикл,1,BSA00_Decomposition,Декомпозиция системы,"
            "Знает этапы,Умеет декомпозировать,Владеет каталогом,draw.io,materials/context.md,"
            "Рабочий кейс,индивидуальный,,12,\"4,08\",8,120,75%,2,"
            "Business analysis, BSA00_Decomposition,https://gitlab.example/bsa00",
        ]
    )

    export = CurriculumExportV1.from_csv(csv_text, title="BSA", direction="Business Analytics")
    project = export.projects[0]

    assert project.outcomes_know == ["Знает этапы"]
    assert project.outcomes_can == ["Умеет декомпозировать"]
    assert project.outcomes_skills == ["Владеет каталогом"]
    assert project.required_software == ["draw.io"]
    assert project.workload_days == 4.08
    assert project.p2p_count == 2


def test_up_skeleton_exports_through_curriculum_export_v1() -> None:
    up = UPSkeleton(
        status="built",
        title="Backend curriculum",
        direction="Backend",
        rows=[
            UPProject(
                block="API",
                block_goal="Собрать backend-сервис",
                order=1,
                title="REST API",
                outcomes_know=["Знает HTTP"],
                outcomes_can=["Проектирует endpoint"],
                outcomes_skills=["Реализует API"],
                required_tools=["OpenAPI"],
                metadata={"platform_name": "S21-BE-01", "gitlab_link": "https://gitlab.example/api"},
            )
        ],
    )

    export = up_to_curriculum_export(up)
    csv_text = export.to_csv()
    restored = CurriculumExportV1.from_csv(csv_text, title=export.title, direction=export.direction).to_up_skeleton()

    assert export.projects[0].required_software == ["OpenAPI"]
    assert restored.rows[0].title == "REST API"
    assert restored.rows[0].outcomes_know == ["Знает HTTP"]
    assert restored.rows[0].metadata["gitlab_link"] == "https://gitlab.example/api"


def test_csv_and_db_alias_contracts_are_named_separately() -> None:
    assert "outcomes_know" in CSV_COLUMN_ALIASES
    assert "p2p_count" in CSV_COLUMN_ALIASES
    assert "expert_notes" in CURRICULUM_ALIAS_FIELD_TO_COLUMN
    assert "audience_level" in CURRICULUM_ALIAS_FIELD_TO_COLUMN
