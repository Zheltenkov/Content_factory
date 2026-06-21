from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.core.models import UPProject, UPSkeleton
from app.main import create_app
from app.modules.curriculum.repo import CurriculumCatalogRepo, create_catalog_schema
from app.modules.curriculum.router import get_curriculum_repo


def test_curriculum_plan_and_project_crud_router() -> None:
    client = _client()
    plan = _plan("Initial plan", [_project(1, "REST API проект")])

    created = client.post("/curriculum/plans", json={"plan": plan.model_dump(mode="json"), "author_ref": "pytest"})
    assert created.status_code == 201
    plan_id = created.json()["plan_id"]

    listed = client.get("/curriculum/plans")
    assert listed.status_code == 200
    assert listed.json()[0]["plan_id"] == plan_id

    fetched = client.get(f"/curriculum/plans/{plan_id}")
    assert fetched.status_code == 200
    assert fetched.json()["plan"]["title"] == "Initial plan"

    patched = client.patch(f"/curriculum/plans/{plan_id}", json={"title": "Patched plan", "metadata": {"owner": "qa"}})
    assert patched.status_code == 200
    assert patched.json()["plan"]["title"] == "Patched plan"
    assert patched.json()["plan"]["metadata"]["owner"] == "qa"

    replaced_plan = _plan("Replacement plan", [_project(1, "SQL проект")])
    replaced = client.put(f"/curriculum/plans/{plan_id}", json={"plan": replaced_plan.model_dump(mode="json")})
    assert replaced.status_code == 200
    assert replaced.json()["plan"]["rows"][0]["title"] == "SQL проект"

    project_created = client.post(f"/curriculum/plans/{plan_id}/projects", json=_project(2, "Docker проект").model_dump(mode="json"))
    assert project_created.status_code == 201
    project_id = project_created.json()["project_id"]

    project = client.get(f"/curriculum/projects/{project_id}")
    assert project.status_code == 200
    assert project.json()["project"]["title"] == "Docker проект"

    project_patch = client.patch(f"/curriculum/projects/{project_id}", json={"title": "Docker compose проект"})
    assert project_patch.status_code == 200
    assert project_patch.json()["project"]["title"] == "Docker compose проект"

    project_put = client.put(f"/curriculum/projects/{project_id}", json=_project(3, "CI проект").model_dump(mode="json"))
    assert project_put.status_code == 200
    assert project_put.json()["project"]["title"] == "CI проект"

    project_deleted = client.delete(f"/curriculum/projects/{project_id}")
    assert project_deleted.status_code == 204
    assert client.get(f"/curriculum/projects/{project_id}").status_code == 404

    deleted = client.delete(f"/curriculum/plans/{plan_id}")
    assert deleted.status_code == 204
    assert client.get(f"/curriculum/plans/{plan_id}").status_code == 404


def test_curriculum_router_is_registered_in_builtin_manifest() -> None:
    client = _client()

    modules = client.get("/api/modules").json()
    curriculum = next(item for item in modules if item["id"] == "curriculum")

    assert curriculum["tables"] == ["curriculum_plan", "curriculum_project"]


def test_curriculum_csv_import_export_and_panel_render() -> None:
    client = _client()
    csv_text = "\n".join(
        [
            "Тематический блок;Цели блока;№;Название проекта;Краткое описание проекта;Образовательные результаты;Список навыков;Обязательные инструменты;SJM;Трудоемкость, астр.часы",
            "Backend;Собрать сервис;1;REST API;Сервис с API;Проектирует endpoint;REST API;OpenAPI;Команда запускает API;12",
        ]
    )

    imported = client.post(
        "/curriculum/plans/import-csv",
        json={"csv_text": csv_text, "title": "CSV plan", "direction": "Backend"},
    )
    assert imported.status_code == 201
    plan_id = imported.json()["plan_id"]

    cascade = client.get(f"/curriculum/plans/{plan_id}/cascade")
    assert cascade.status_code == 200
    assert cascade.json()["blocks"][0]["name"] == "Backend"
    assert cascade.json()["blocks"][0]["projects"][0]["title"] == "REST API"

    exported = client.get(f"/curriculum/plans/{plan_id}/export.csv")
    assert exported.status_code == 200
    assert "Название проекта" in exported.text
    assert "REST API" in exported.text

    panel = client.get("/static/curriculum/panel.html")
    assert panel.status_code == 200
    assert 'id="planSelect"' in panel.text
    assert "/static/curriculum/panel.js" in panel.text


def _client() -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    create_catalog_schema(engine)
    repo = CurriculumCatalogRepo(engine)
    app = create_app()
    app.dependency_overrides[get_curriculum_repo] = lambda: repo
    return TestClient(app)


def _plan(title: str, rows: list[UPProject]) -> UPSkeleton:
    return UPSkeleton(status="built", title=title, direction="Backend", rows=rows, metadata={"audience_level": "junior"})


def _project(order: int, title: str) -> UPProject:
    return UPProject(
        block="Backend",
        block_goal="Собрать backend-сервис",
        order=order,
        title=title,
        description=f"{title}: практический проект.",
        outcomes_know=["Знает HTTP"],
        outcomes_can=["Проектирует сервис"],
        outcomes_skills=["Реализует проект"],
        competency_refs=[{"competency_id": f"C{order}", "canonical_name": title, "weight": 100, "role": "primary"}],
        required_tools=["Git"],
        materials="Материалы из УП",
        storytelling="Командный сервис.",
        format="individual",
        group_size=1,
        hours_astro=8,
        metadata={"platform_name": f"S21-BE-{order:02d}"},
    )
