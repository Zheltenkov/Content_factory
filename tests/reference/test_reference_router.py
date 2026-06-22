from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.core.models import Competency
from app.main import create_app
from app.modules.curriculum.repo import CurriculumCatalogRepo, create_catalog_schema
from app.modules.reference.router import get_reference_repo


def test_reference_catalog_read_edit_and_review_queue() -> None:
    client, repo = _client()
    link = repo.save_competency(_competency(), source_note="pytest:reference")

    summary = client.get("/reference/summary")
    assert summary.status_code == 200
    assert summary.json()["competencies"] == 1
    assert summary.json()["open_reviews"] == 1

    listed = client.get("/reference/competencies")
    assert listed.status_code == 200
    competency_id = listed.json()[0]["id"]
    assert listed.json()[0]["title"] == "Backend"

    detail = client.get(f"/reference/competencies/{competency_id}")
    assert detail.status_code == 200
    assert detail.json()["skills"][0]["name"] == "Проектирование REST API"
    assert detail.json()["skills"][0]["indicators"][0]["text"].startswith("Проектирует")

    patched = client.patch(
        f"/reference/competencies/{competency_id}",
        json={"title": "Backend Engineering", "description": "Обновлено вручную", "status": "active"},
    )
    assert patched.status_code == 200
    assert patched.json()["title"] == "Backend Engineering"
    assert patched.json()["description"] == "Обновлено вручную"

    skill = client.patch(f"/reference/skills/{link.skill_id}", json={"aliases": ["REST проектирование"]})
    assert skill.status_code == 200
    assert skill.json()["aliases"] == ["REST проектирование"]

    reviews = client.get("/reference/reviews")
    assert reviews.status_code == 200
    review_id = reviews.json()[0]["id"]
    resolved = client.patch(f"/reference/reviews/{review_id}", json={"status": "resolved", "note": "confirmed"})
    assert resolved.status_code == 200
    assert client.get("/reference/reviews").json() == []


def test_reference_manifest_and_static_panel_are_registered() -> None:
    client, _repo = _client()

    modules = client.get("/api/modules").json()
    reference = next(item for item in modules if item["id"] == "reference")

    assert reference["tables"] == ["competency", "skill", "indicator_row", "review_queue"]
    assert reference["ui_panel"] == "reference/panel.html"
    assert client.get("/static/reference/panel.html").status_code == 200


def _client() -> tuple[TestClient, CurriculumCatalogRepo]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    create_catalog_schema(engine)
    repo = CurriculumCatalogRepo(engine)
    app = create_app()
    app.dependency_overrides[get_reference_repo] = lambda: repo
    return TestClient(app), repo


def _competency() -> Competency:
    return Competency(
        competency_id="C1",
        canonical_name="Проектирование REST API",
        group="Backend",
        coverage_area="Backend",
        aliases=["REST API design"],
        indicators=[{"text": "Проектирует REST API с OpenAPI-контрактом", "bloom": "create"}],
        confidence=0.95,
        atomicity="atomic",
        resolution="new",
        status="accepted",
    )
