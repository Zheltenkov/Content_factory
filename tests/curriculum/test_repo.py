from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import create_engine

from app.core.models import Competency, UPProject, UPSkeleton
from app.modules.curriculum.repo import CurriculumCatalogRepo, create_catalog_schema


def test_catalog_repo_crud_alias_and_resolve() -> None:
    engine = create_engine("sqlite:///:memory:")
    create_catalog_schema(engine)
    repo = CurriculumCatalogRepo(engine)

    skill = repo.upsert_skill("SQL-запросы", aliases=["Работа с SQL"])
    resolved = repo.resolve_competency(_competency("C1", "Работа с SQL"))

    assert skill.skill_id > 0
    assert repo.get_skill(skill.skill_id).aliases == ("Работа с SQL",)
    assert resolved.catalog_id == skill.skill_id
    assert resolved.canonical_name == "SQL-запросы"
    assert resolved.resolution == "alias"

    updated = repo.update_skill(skill.skill_id, canonical_name="SQL аналитика", aliases=["SQL-запросы"])
    assert updated is not None
    assert updated.normalized_name == "sql аналитика"
    assert repo.list_skills(query="SQL")
    assert repo.delete_skill(skill.skill_id) is True
    assert repo.get_skill(skill.skill_id).status == "deprecated"


def test_catalog_repo_links_competency_indicators_and_review_queue() -> None:
    engine = create_engine("sqlite:///:memory:")
    create_catalog_schema(engine)
    repo = CurriculumCatalogRepo(engine)
    item = _competency("C1", "Пишет REST API", group="Backend", bloom="create")

    link = repo.save_competency(item, source_note="test:intake")
    links = repo.list_skill_competency_links(link.skill_id)
    reviews = repo.list_review_queue()

    assert link.status == "linked"
    assert link.created_competency is True
    assert link.created_indicator_rows == 1
    assert links[0]["competency_title"] == "Backend"
    assert links[0]["indicator_row_count"] == 1
    assert reviews[0]["entity_type"] == "competency"
    assert repo.set_competency_review_status(link.competency_id, accepted=True)["status"] == "accepted"
    assert repo.resolve_review_item(reviews[0]["id"], status="resolved", note="confirmed") is True
    assert repo.list_review_queue(status="resolved")[0]["resolution_note"] == "confirmed"


def test_curriculum_plan_roundtrip_persists_projects() -> None:
    engine = create_engine("sqlite:///:memory:")
    create_catalog_schema(engine)
    repo = CurriculumCatalogRepo(engine)
    up = UPSkeleton(
        status="built",
        title="Backend curriculum",
        direction="Backend",
        rows=[
            UPProject(
                block="API",
                block_goal="Спроектировать сервис",
                order=1,
                title="REST API проект",
                description="Собрать сервис с REST API.",
                outcomes_know=["Знает HTTP"],
                outcomes_can=["Проектирует endpoint"],
                outcomes_skills=["Реализует API"],
                competency_refs=[{"competency_id": "C1", "canonical_name": "REST API", "weight": 100, "role": "primary"}],
                required_tools=["OpenAPI"],
                required_software=["Python"],
                materials="OpenAPI spec",
                storytelling="Команда запускает API.",
                format="individual",
                group_size=1,
                hours_astro=12,
                metadata={"platform_name": "S21-BE-01", "gitlab_link": "https://gitlab.example/api", "xp": 120},
            )
        ],
        metadata={"audience_level": "junior"},
    )

    saved = repo.save_curriculum_plan(up, source_policy="accepted_only", author_ref="pytest")
    restored = repo.load_curriculum_plan(saved.plan_id)

    assert saved.project_count == 1
    assert restored is not None
    assert restored.title == "Backend curriculum"
    assert restored.rows[0].title == "REST API проект"
    assert restored.rows[0].competency_refs[0].competency_id == "C1"
    assert restored.rows[0].metadata["platform_name"] == "S21-BE-01"
    assert repo.delete_curriculum_plan(saved.plan_id) is True
    assert repo.load_curriculum_plan(saved.plan_id) is None


def test_curriculum_repo_get_context_builds_neighbor_context_from_db() -> None:
    engine = create_engine("sqlite:///:memory:")
    create_catalog_schema(engine)
    repo = CurriculumCatalogRepo(engine)
    up = UPSkeleton(
        status="built",
        title="Backend curriculum",
        direction="Backend",
        rows=[
            _project(1, "HTTP intro", block="API"),
            _project(2, "REST API", block="API", platform_name="BE02_REST"),
            _project(3, "Docker deploy", block="Deploy"),
        ],
    )

    saved = repo.save_curriculum_plan(up)
    context = repo.get_context(saved.plan_id, 2)

    assert context is not None
    assert context.plan_id == saved.plan_id
    assert context.block_name == "API"
    assert context.current_project_title == "REST API"
    assert context.previous_projects[0].title == "HTTP intro"
    assert context.next_projects == []
    assert context.next_block_projects[0].title == "Docker deploy"
    assert context.current_project_platform_name == "BE02_REST"


def test_curriculum_catalog_sql_is_owned_by_repo_only() -> None:
    root = Path("app/modules/curriculum")
    forbidden = re.compile(
        r"\b(SELECT\s+.+\s+FROM|INSERT\s+INTO|UPDATE\s+\w+|DELETE\s+FROM|CREATE\s+TABLE)\b|\.execute\(|sqlalchemy",
        re.IGNORECASE | re.DOTALL,
    )
    offenders: list[str] = []

    for path in root.rglob("*.py"):
        if path.name == "repo.py":
            continue
        text = path.read_text(encoding="utf-8")
        if forbidden.search(text):
            offenders.append(str(path))

    assert offenders == []


def _competency(tmp_id: str, name: str, *, group: str = "Data", bloom: str = "apply") -> Competency:
    return Competency(
        competency_id=tmp_id,
        canonical_name=name,
        group=group,
        coverage_area=group,
        indicators=[{"text": f"Демонстрирует: {name}", "bloom": bloom}],
        tools=[],
        confidence=0.9,
        atomicity="atomic",
        resolution="new",
        status="accepted",
    )


def _project(order: int, title: str, *, block: str, platform_name: str | None = None) -> UPProject:
    return UPProject(
        block=block,
        block_goal=f"Цель блока {block}",
        order=order,
        title=title,
        description=f"{title}: учебный проект.",
        outcomes_know=[f"Знает тему {title}"],
        outcomes_can=[f"Выполняет {title}"],
        outcomes_skills=[f"Применяет {title}"],
        competency_refs=[{"competency_id": f"C{order}", "canonical_name": title, "weight": 100, "role": "primary"}],
        required_tools=["Git"],
        required_software=["OpenAPI"],
        materials="materials/context.md",
        storytelling="Команда проектирует сервис.",
        hours_astro=8,
        metadata={"platform_name": platform_name or f"BE{order:02d}"},
    )
