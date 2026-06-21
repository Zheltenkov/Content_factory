from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import create_engine

from app.core.models import Competency
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
