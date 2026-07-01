from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.core.models import UPProject, UPSkeleton
from app.main import create_app
from app.modules.curriculum.repo import CurriculumCatalogRepo, create_catalog_schema
from app.modules.curriculum.router import get_curriculum_repo
from app.modules.reference.router import get_reference_repo


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
    cascade_project = cascade.json()["blocks"][0]["projects"][0]
    assert cascade_project["title"] == "REST API"
    # full project payload is embedded so the UP table can render every column
    assert cascade_project["project"]["title"] == "REST API"
    assert "outcomes_can" in cascade_project["project"]

    plan_page = client.get(f"/up/plans/{plan_id}")
    assert plan_page.status_code == 200
    assert 'id="upProjectsTable"' in plan_page.text

    templates_page = client.get(f"/up/plans/{plan_id}/template-proposals")
    assert templates_page.status_code == 200
    assert 'id="templateStepper"' in templates_page.text

    exported = client.get(f"/curriculum/plans/{plan_id}/export.csv")
    assert exported.status_code == 200
    assert "Название проекта" in exported.text
    assert "REST API" in exported.text

    panel = client.get("/static/curriculum/panel.html")
    assert panel.status_code == 200
    assert 'id="planSelect"' in panel.text
    assert "/static/curriculum/panel.js" in panel.text
    for control_id in (
        'id="projectBlockGoal"',
        'id="projectOutcomesKnow"',
        'id="projectOutcomesSkills"',
        'id="projectSoftware"',
        'id="projectMaterials"',
        'id="projectFormat"',
        'id="projectGroupSize"',
        'id="regenerateTemplateProposals"',
        'id="templateProposalList"',
    ):
        assert control_id in panel.text
    js = client.get("/static/curriculum/panel.js")
    assert js.status_code == 200
    assert "renderProjectsTable" in js.text
    assert "planIdFromLocation" in js.text
    assert "applyTemplateFocus" in js.text and "renderTemplateStepper" in js.text
    for endpoint in (
        "/curriculum/plans/${planId}/template-proposals",
        "/curriculum/plans/${planId}/template-proposals/generate",
        "/curriculum/template-proposals/${proposalId}",
        "/curriculum/template-proposals/${proposalId}/${action}",
    ):
        assert endpoint in js.text


def test_curriculum_template_proposal_lifecycle() -> None:
    client = _client()
    plan = _plan("Template proposal plan", [_project(1, "REST API"), _project(2, "Docker deploy")])
    created = client.post("/curriculum/plans", json={"plan": plan.model_dump(mode="json"), "author_ref": "pytest"})
    assert created.status_code == 201
    plan_id = created.json()["plan_id"]

    generated = client.post(f"/curriculum/plans/{plan_id}/template-proposals/generate")
    assert generated.status_code == 200, generated.text
    proposals = generated.json()
    assert len(proposals) == 1
    proposal_id = proposals[0]["id"]
    assert proposals[0]["status"] == "open"
    assert proposals[0]["scope_names"] == ["Backend"]

    patched = client.patch(
        f"/curriculum/template-proposals/{proposal_id}",
        json={
            "title": "Backend delivery template",
            "artifact_description": "Delivery artifact for Backend projects.",
            "validation_criteria": "Artifact is reproducible and tied to UP outcomes.",
            "confidence": 0.91,
        },
    )
    assert patched.status_code == 200
    assert patched.json()["title"] == "Backend delivery template"
    assert patched.json()["confidence"] == 0.91

    accepted = client.post(f"/curriculum/template-proposals/{proposal_id}/accept")
    assert accepted.status_code == 200, accepted.text
    accepted_payload = accepted.json()
    assert accepted_payload["status"] == "accepted"
    assert accepted_payload["accepted_template_id"]

    listed_templates = client.get("/reference/artifact-templates")
    assert listed_templates.status_code == 200
    assert any(item["title"] == "Backend delivery template" for item in listed_templates.json())

    regenerated = client.post(f"/curriculum/plans/{plan_id}/template-proposals/generate")
    assert regenerated.status_code == 200
    statuses = {item["status"] for item in regenerated.json()}
    assert {"accepted", "open"}.issubset(statuses)
    open_proposal = next(item for item in regenerated.json() if item["status"] == "open")

    rejected = client.post(f"/curriculum/template-proposals/{open_proposal['id']}/reject")
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"


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
    app.dependency_overrides[get_reference_repo] = lambda: repo
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
