from __future__ import annotations

import io
import zipfile

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.core.models import UPProject, UPSkeleton
from app.main import create_app
from app.modules.curriculum.repo import CurriculumCatalogRepo, create_catalog_schema
from app.modules.curriculum.router import get_curriculum_repo
from app.modules.generator.router import get_generator_repo


def test_generator_e2e_uses_curriculum_plan_from_db() -> None:
    repo = _repo()
    plan = UPSkeleton(
        status="built",
        title="Backend curriculum",
        direction="Backend",
        rows=[
            _project(1, "HTTP intro", block="API"),
            _project(2, "REST API", block="API", platform_name="BE02_REST"),
            _project(3, "Docker deploy", block="Deploy"),
        ],
    )
    app = create_app()
    app.dependency_overrides[get_curriculum_repo] = lambda: repo
    app.dependency_overrides[get_generator_repo] = lambda: repo
    client = TestClient(app)

    created = client.post("/curriculum/plans", json={"plan": plan.model_dump(mode="json"), "author_ref": "generator-e2e"})
    assert created.status_code == 201, created.text
    plan_id = created.json()["plan_id"]

    response = client.post(
        "/generator/runs/from-curriculum",
        json={"plan_id": plan_id, "project_order": 2},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["context"]["plan_id"] == plan_id
    assert payload["context"]["current_project_title"] == "REST API"
    assert payload["context"]["previous_projects"][0]["title"] == "HTTP intro"
    assert payload["context"]["next_block_projects"][0]["title"] == "Docker deploy"
    assert payload["document"]["project_id"] == "BE02_REST"
    assert payload["document"]["metadata"]["source"] == "curriculum_db"
    assert "REST API" in payload["document"]["markdown"]
    assert "## Содержание" in payload["document"]["markdown"]
    assert "## Глава 1. Введение и инструкция" in payload["document"]["markdown"]
    assert "## Глава 2. Теория" in payload["document"]["markdown"]
    assert "### 2.1." in payload["document"]["markdown"]
    assert "## Глава 3. Практика" in payload["document"]["markdown"]
    assert "### Задание 1." in payload["document"]["markdown"]
    assert "check-list.yml" in payload["document"]["markdown"]
    assert payload["document"]["metadata"]["theory_parts"]
    assert payload["document"]["metadata"]["practice_tasks"]
    assert payload["document"]["metadata"]["practice_tasks"][0]["artifact_location"].endswith("/task-01/README.md")
    assert "practice_critic_issues" in payload["document"]["metadata"]
    assert "practice_repaired_issue_count" in payload["document"]["metadata"]
    assert payload["document"]["metadata"]["generated_assets"]["formulas"]
    assert payload["document"]["metadata"]["formula_assets"]["tables"]
    assert payload["document"]["metadata"]["dataset_files"]
    assert payload["document"]["metadata"]["code_examples"]
    assert payload["document"]["metadata"]["refine_report"]
    assert payload["document"]["metadata"]["quality_gate"]
    assert payload["document"]["artifacts"]
    assert payload["rubric_json"]["passed"] is True
    assert payload["gate_review"]["human_review_required"] is False


def test_generator_async_run_polling_review_and_archive() -> None:
    repo = _repo()
    plan = UPSkeleton(
        status="built",
        title="Backend curriculum",
        direction="Backend",
        rows=[_project(1, "REST API", block="API", platform_name="BE01_REST")],
    )
    app = create_app()
    app.dependency_overrides[get_curriculum_repo] = lambda: repo
    app.dependency_overrides[get_generator_repo] = lambda: repo
    client = TestClient(app)

    created = client.post("/curriculum/plans", json={"plan": plan.model_dump(mode="json"), "author_ref": "generator-async"})
    assert created.status_code == 201, created.text
    plan_id = created.json()["plan_id"]

    started = client.post(
        "/generator/runs/from-curriculum/async",
        json={"plan_id": plan_id, "project_order": 1, "overrides": {"methodology_human_review": True}},
    )
    assert started.status_code == 200, started.text
    run_id = started.json()["run_id"]

    status_payload = client.get(f"/generator/runs/{run_id}/status").json()
    assert status_payload["status"] in {"completed", "needs_review"}
    assert status_payload["result"]["document"]["metadata"]["source"] == "curriculum_db"
    assert status_payload["workflow"]["run_id"] == run_id

    recent = client.get("/generator/runs/recent")
    assert recent.status_code == 200
    assert recent.json()["items"][0]["run_id"] == run_id

    change = client.post(
        f"/generator/runs/{run_id}/review/request-changes",
        json={"target_stage": "final", "instruction": "Добавь явное предупреждение о проверке окружения."},
    )
    assert change.status_code == 200, change.text
    assert change.json()["methodology"]["pending_change_ids"]

    preview = client.post(f"/generator/runs/{run_id}/review/preview-changes", json={})
    assert preview.status_code == 200, preview.text
    assert "Методологические правки" in preview.json()["methodology"]["preview_markdown"]

    approved = client.post(f"/generator/runs/{run_id}/review/approve-diff", json={"comment": "ok"})
    assert approved.status_code == 200, approved.text
    assert "Методологические правки" in approved.json()["result"]["document"]["markdown"]

    regenerated = client.post(
        f"/generator/runs/{run_id}/regenerate",
        json={
            "instruction": "замени «REST API» на «REST API v2»",
            "scopes": [{"title": "REST API", "start_line": 1, "end_line": 20}],
        },
    )
    assert regenerated.status_code == 200, regenerated.text
    regenerated_payload = regenerated.json()
    assert "REST API v2" in regenerated_payload["result"]["document"]["markdown"]
    assert regenerated_payload["result"]["document"]["metadata"]["regeneration_report"]["changed"] is True
    assert regenerated_payload["result"]["document"]["metadata"]["regeneration_history"][-1]["scopes"][0]["title"] == "REST API"

    archive = client.get(f"/generator/runs/{run_id}/archive")
    assert archive.status_code == 200, archive.text
    with zipfile.ZipFile(io.BytesIO(archive.content)) as bundle:
        assert {"README.md", "rubric.json", "report.json"}.issubset(set(bundle.namelist()))
        assert "REST API v2" in bundle.read("README.md").decode("utf-8")


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
