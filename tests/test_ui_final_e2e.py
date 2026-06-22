from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.core.llm.client import LLMClient, LLMRequest, LLMResponse
from app.core.models import Competency, UPProject, UPSkeleton
from app.main import create_app
from app.modules.curriculum.repo import CurriculumCatalogRepo, create_catalog_schema
from app.modules.curriculum.router import get_curriculum_repo
from app.modules.generator.router import get_generator_repo
from app.modules.reference.router import get_reference_repo
from app.modules.translator.router import get_translator_service
from app.modules.translator.service import TranslatorService


class MockTransport:
    def __init__(self, *responses: str) -> None:
        self.responses = list(responses)
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(content=self.responses.pop(0), model=request.model)


def test_w6_u7_dashboard_tiles_drive_live_module_workflows() -> None:
    repo = _repo()
    translator_transport = MockTransport("# REST API\n\nTranslated body for learners.")
    translator_llm = LLMClient(model="gpt-4o-mini", provider="mock", transport=translator_transport)
    translator_service = TranslatorService(client_factory=lambda **_kwargs: translator_llm)
    app = create_app()
    app.dependency_overrides[get_curriculum_repo] = lambda: repo
    app.dependency_overrides[get_generator_repo] = lambda: repo
    app.dependency_overrides[get_reference_repo] = lambda: repo
    app.dependency_overrides[get_translator_service] = lambda: translator_service
    client = TestClient(app)

    modules = client.get("/api/modules")
    dashboard = client.get("/")

    assert modules.status_code == 200
    assert dashboard.status_code == 200
    payload = modules.json()
    by_id = {item["id"]: item for item in payload}
    assert set(by_id) == {"generator", "checker", "translator", "curriculum", "reference"}
    for module in payload:
        panel = module["ui_panel"]
        assert f'data-panel="{panel}"' in dashboard.text
        panel_response = client.get(f"/static/{panel}")
        assert panel_response.status_code == 200
        assert "Content Factory" in panel_response.text

    _assert_panels_hit_real_endpoints(client)
    plan_id = _exercise_curriculum_editor(client)
    generated_markdown = _exercise_generator_from_db_plan(client, plan_id)
    _exercise_checker(client, generated_markdown)
    _exercise_reference_editor(client, repo)
    _exercise_translator(client, translator_transport)


def _assert_panels_hit_real_endpoints(client: TestClient) -> None:
    expected = {
        "curriculum": ("/curriculum/plans", "/curriculum/projects", "/curriculum/plans/import-csv"),
        "generator": ("/curriculum/plans", "/generator/runs/from-curriculum"),
        "checker": ("/checker/evaluate",),
        "translator": ("/translator/translate/readme", "/translator/translate/document", "/translator/translate/video"),
        "reference": ("/reference/summary", "/reference/competencies", "/reference/profiles", "/reference/reviews"),
    }
    for module_id, endpoints in expected.items():
        js = client.get(f"/static/{module_id}/panel.js")
        assert js.status_code == 200
        assert "fetch(" in js.text or "request(" in js.text
        for endpoint in endpoints:
            assert endpoint in js.text


def _exercise_curriculum_editor(client: TestClient) -> int:
    plan = _plan("UI final curriculum", [_project(1, "REST API"), _project(2, "Docker deploy")])
    created = client.post("/curriculum/plans", json={"plan": plan.model_dump(mode="json"), "author_ref": "u7-e2e"})
    assert created.status_code == 201, created.text
    plan_id = created.json()["plan_id"]

    cascade = client.get(f"/curriculum/plans/{plan_id}/cascade")
    assert cascade.status_code == 200
    project_id = cascade.json()["blocks"][0]["projects"][0]["project_id"]

    patched = client.patch(f"/curriculum/projects/{project_id}", json={"title": "REST API panel edit"})
    assert patched.status_code == 200
    assert patched.json()["project"]["title"] == "REST API panel edit"

    exported = client.get(f"/curriculum/plans/{plan_id}/export.csv")
    assert exported.status_code == 200
    assert "REST API panel edit" in exported.text
    return plan_id


def _exercise_generator_from_db_plan(client: TestClient, plan_id: int) -> str:
    generated = client.post("/generator/runs/from-curriculum", json={"plan_id": plan_id, "project_order": 1})
    assert generated.status_code == 200, generated.text
    payload = generated.json()
    markdown = payload["document"]["markdown"]
    assert payload["document"]["metadata"]["source"] == "curriculum_db"
    assert "REST API panel edit" in markdown
    assert "## Глава 2. Теория" in markdown
    assert "## Глава 3. Практика" in markdown
    assert payload["rubric_json"]["passed"] is True
    return markdown


def _exercise_checker(client: TestClient, generated_markdown: str) -> None:
    ok = client.post("/checker/evaluate", json={"markdown": generated_markdown})
    assert ok.status_code == 200
    assert "structural" in ok.json()

    broken = client.post("/checker/evaluate", json={"markdown": "Без H1\n\nTODO\n\n```python\nprint('broken')"})
    assert broken.status_code == 200
    payload = broken.json()
    codes = {issue["code"] for issue in payload["rubric_json"]["issues"]}
    assert payload["gate_review"]["human_review_required"] is True
    assert "readme_structure.h1_first" in codes
    assert "document_integrity.unclosed_fence" in codes


def _exercise_reference_editor(client: TestClient, repo: CurriculumCatalogRepo) -> None:
    link = repo.save_competency(_competency(), source_note="u7-reference")
    listed = client.get("/reference/competencies")
    assert listed.status_code == 200
    competency_id = listed.json()[0]["id"]

    patched = client.patch(
        f"/reference/competencies/{competency_id}",
        json={"title": "Backend API", "description": "Отредактировано через reference UI", "status": "active"},
    )
    assert patched.status_code == 200
    assert patched.json()["title"] == "Backend API"

    skill = client.patch(f"/reference/skills/{link.skill_id}", json={"aliases": ["API design"]})
    assert skill.status_code == 200
    assert skill.json()["aliases"] == ["API design"]

    profiles = client.get("/reference/profiles?include_service=true")
    assert profiles.status_code == 200
    profile = client.get(f"/reference/profiles/{profiles.json()[0]['id']}")
    assert profile.status_code == 200
    assert profile.json()["competencies"][0]["skills"][0]["indicators"]

    reviews = client.get("/reference/reviews")
    assert reviews.status_code == 200
    resolved = client.patch(f"/reference/reviews/{reviews.json()[0]['id']}", json={"status": "resolved", "note": "u7"})
    assert resolved.status_code == 200


def _exercise_translator(client: TestClient, transport: MockTransport) -> None:
    started = client.post(
        "/translator/translate/readme",
        json={
            "markdown": "# REST API\n\nОписание проекта для студентов.",
            "target_language": "en",
            "translation_mode": "literal",
        },
    )
    assert started.status_code == 200
    status = client.get(f"/translator/translate/status/{started.json()['request_id']}")
    assert status.status_code == 200
    payload = status.json()
    assert payload["status"] == "completed"
    assert "Translated body" in payload["translated_markdown"]
    assert transport.requests


def _repo() -> CurriculumCatalogRepo:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    create_catalog_schema(engine)
    return CurriculumCatalogRepo(engine)


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
        required_software=["OpenAPI"],
        materials="Материалы из УП",
        storytelling="Командный сервис.",
        format="individual",
        group_size=1,
        hours_astro=8,
        metadata={"platform_name": f"S21-BE-{order:02d}"},
    )


def _competency() -> Competency:
    return Competency(
        competency_id="C-U7",
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
