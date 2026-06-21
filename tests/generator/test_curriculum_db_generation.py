from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.core.models import UPProject, UPSkeleton
from app.main import create_app
from app.modules.curriculum.repo import CurriculumCatalogRepo, create_catalog_schema
from app.modules.generator.router import get_generator_repo


def test_generator_e2e_uses_curriculum_plan_from_db() -> None:
    repo = _repo()
    saved = repo.save_curriculum_plan(
        UPSkeleton(
            status="built",
            title="Backend curriculum",
            direction="Backend",
            rows=[
                _project(1, "HTTP intro", block="API"),
                _project(2, "REST API", block="API", platform_name="BE02_REST"),
                _project(3, "Docker deploy", block="Deploy"),
            ],
        )
    )
    app = create_app()
    app.dependency_overrides[get_generator_repo] = lambda: repo
    client = TestClient(app)

    response = client.post(
        "/generator/runs/from-curriculum",
        json={"plan_id": saved.plan_id, "project_order": 2},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["context"]["plan_id"] == saved.plan_id
    assert payload["context"]["current_project_title"] == "REST API"
    assert payload["context"]["previous_projects"][0]["title"] == "HTTP intro"
    assert payload["context"]["next_block_projects"][0]["title"] == "Docker deploy"
    assert payload["document"]["project_id"] == "BE02_REST"
    assert payload["document"]["metadata"]["source"] == "curriculum_db"
    assert "REST API" in payload["document"]["markdown"]
    assert "check-list.yml" in payload["document"]["markdown"]
    assert payload["rubric_json"]["passed"] is True
    assert payload["gate_review"]["human_review_required"] is False


def _repo() -> CurriculumCatalogRepo:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    create_catalog_schema(engine)
    return CurriculumCatalogRepo(engine)


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
