from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.core.models import Competency
from app.main import create_app
from app.modules.curriculum.repo import CurriculumCatalogRepo, create_catalog_schema
from app.modules.curriculum.router import get_curriculum_repo
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

    profiles = client.get("/reference/profiles?include_service=true")
    assert profiles.status_code == 200
    profile_id = profiles.json()[0]["id"]
    profile = client.get(f"/reference/profiles/{profile_id}")
    assert profile.status_code == 200
    assert profile.json()["competencies"][0]["title"] == "Backend"
    assert profile.json()["competencies"][0]["skills"][0]["indicators"][0]["text"].startswith("Проектирует")

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

    groups = client.get("/reference/groups")
    assert groups.status_code == 200
    group_id = groups.json()[0]["id"]
    group = client.get(f"/reference/groups/{group_id}")
    assert group.status_code == 200
    assert group.json()["skills"][0]["skill_id"] == link.skill_id

    created_skill = client.post(
        f"/reference/groups/{group_id}/skills",
        json={"canonical_name": "Диагностика API", "aliases": ["API troubleshooting"]},
    )
    assert created_skill.status_code == 201
    created_skill_id = created_skill.json()["skill_id"]
    assert created_skill.json()["links"][0]["competency_id"] == group_id

    detail = client.get(f"/reference/skills/{created_skill_id}")
    assert detail.status_code == 200
    assert detail.json()["aliases"] == ["API troubleshooting"]
    assert detail.json()["links"][0]["competency_title"] == "Backend Engineering"

    indicator = client.post(
        f"/reference/skills/{created_skill_id}/indicators",
        json={"dimension_code": "ability", "text": "Диагностирует ошибки REST API по логам"},
    )
    assert indicator.status_code == 201
    indicator_id = indicator.json()["id"]
    assert indicator.json()["dimension_code"] == "ability"

    patched_indicator = client.patch(
        f"/reference/indicators/{indicator_id}",
        json={"dimension_code": "proficiency", "text": "Устраняет ошибки REST API по логам и трассировкам"},
    )
    assert patched_indicator.status_code == 200
    assert patched_indicator.json()["dimension_code"] == "proficiency"
    assert "трассировкам" in patched_indicator.json()["text"]
    assert client.delete(f"/reference/indicators/{indicator_id}").status_code == 204

    reviews = client.get("/reference/reviews")
    assert reviews.status_code == 200
    review_id = reviews.json()[0]["id"]
    resolved = client.patch(f"/reference/reviews/{review_id}", json={"status": "resolved", "note": "confirmed"})
    assert resolved.status_code == 200
    assert client.get("/reference/reviews").json() == []


def test_candidate_competency_actions_cover_legacy_admin_workflow() -> None:
    client, repo = _client()
    source = repo.save_competency(_competency(), source_note="pytest:source")
    target = repo.save_competency(
        Competency(
            competency_id="C2",
            canonical_name="Настройка Docker",
            group="Backend Platform",
            coverage_area="Backend Platform",
            indicators=[{"text": "Настраивает Docker окружение", "bloom": "apply"}],
            confidence=0.91,
            atomicity="atomic",
            resolution="new",
            status="accepted",
        ),
        source_note="pytest:target",
    )
    assert client.post(
        "/reference/candidate-competencies/actions",
        json={"action": "accept", "competency_id": target.competency_id},
    ).status_code == 200

    workspace = client.get("/reference/candidate-competencies")
    assert workspace.status_code == 200
    candidate = next(item for item in workspace.json()["candidates"] if item["competency_id"] == source.competency_id)
    assert candidate["skills"][0]["competency_skill_id"] == source.competency_skill_id
    assert workspace.json()["competency_options"][0]["status"] == "active"

    renamed = client.post(
        "/reference/candidate-competencies/actions",
        json={"action": "rename", "competency_id": source.competency_id, "new_title": "Backend API Engineering"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Backend API Engineering"

    moved = client.post(
        "/reference/candidate-competencies/actions",
        json={
            "action": "move_skill",
            "competency_id": source.competency_id,
            "competency_skill_id": source.competency_skill_id,
            "target_competency_id": target.competency_id,
        },
    )
    assert moved.status_code == 200
    assert moved.json()["status"] in {"moved", "deduplicated"}
    assert client.get(f"/reference/groups/{target.competency_id}").json()["skill_count"] >= 2

    rejected = repo.save_competency(
        Competency(
            competency_id="C3",
            canonical_name="Обработка временных файлов",
            group="Temporary Candidate",
            coverage_area="Temporary Candidate",
            indicators=[{"text": "Удаляет временные файлы", "bloom": "apply"}],
            confidence=0.7,
            atomicity="atomic",
            resolution="new",
            status="accepted",
        ),
        source_note="pytest:reject",
    )
    assert client.post(
        "/reference/candidate-competencies/actions",
        json={"action": "reject", "competency_id": rejected.competency_id, "resolution_note": "out of scope"},
    ).status_code == 200
    assert client.get(f"/reference/groups/{rejected.competency_id}").json()["status"] == "deprecated"

    merged = repo.save_competency(
        Competency(
            competency_id="C4",
            canonical_name="Проверка CI pipeline",
            group="CI Backend",
            coverage_area="CI Backend",
            indicators=[{"text": "Проверяет CI pipeline", "bloom": "analyze"}],
            confidence=0.88,
            atomicity="atomic",
            resolution="new",
            status="accepted",
        ),
        source_note="pytest:merge",
    )
    merge = client.post(
        "/reference/candidate-competencies/actions",
        json={"action": "merge", "competency_id": merged.competency_id, "target_competency_id": target.competency_id},
    )
    assert merge.status_code == 200
    assert merge.json()["moved"] >= 1
    assert client.get(f"/reference/groups/{merged.competency_id}").json()["status"] == "deprecated"


def test_artifact_template_admin_crud_covers_scope_patterns_and_criteria() -> None:
    client, _repo = _client()

    created = client.post(
        "/reference/artifact-templates",
        json={
            "code": "customer-interview-report",
            "title": "Отчет по интервью",
            "artifact_family": "analysis",
            "artifact_description": "Проверяемый отчет по теме {theme}: {skills}",
            "project_name_pattern": "Интервью по теме {theme}",
            "materials_pattern": "Скрипт, таблица инсайтов, skills: {skills}",
            "storytelling_pattern": "Студент действует как исследователь продукта.",
            "validation_criteria": "Есть респонденты, инсайты и следующий шаг.",
            "priority": 80,
            "status": "active",
            "scope_type": "coverage_area",
            "scope_names": ["Customer Discovery", "Проверка гипотез"],
            "scope_weight": 1.5,
        },
    )
    assert created.status_code == 201, created.text
    template = created.json()
    assert template["code"] == "customer-interview-report"
    assert template["scopes"][0]["normalized_scope_name"] == "customer discovery"
    assert template["validation_criteria"].startswith("Есть респонденты")

    listed = client.get("/reference/artifact-templates")
    assert listed.status_code == 200
    assert listed.json()[0]["title"] == "Отчет по интервью"
    assert listed.json()[0]["scope_names"] == ["Customer Discovery", "Проверка гипотез"]

    patched_status = client.patch(f"/reference/artifact-templates/{template['id']}/status", json={"status": "deprecated"})
    assert patched_status.status_code == 200
    assert patched_status.json()["status"] == "deprecated"
    assert client.get("/reference/artifact-templates?active_only=true").json() == []


def test_archive_search_and_restore_covers_groups_skills_and_indicators() -> None:
    client, repo = _client()
    link = repo.save_competency(_competency(), source_note="pytest:archive")
    skill_detail = client.get(f"/reference/skills/{link.skill_id}").json()
    indicator_id = skill_detail["indicators"][0]["id"]

    assert client.patch(f"/reference/groups/{link.competency_id}", json={"status": "deprecated"}).status_code == 200
    assert client.patch(f"/reference/skills/{link.skill_id}", json={"status": "deprecated"}).status_code == 200
    assert client.delete(f"/reference/indicators/{indicator_id}").status_code == 204

    archive = client.get("/reference/archive?scope=all")
    assert archive.status_code == 200
    payload = archive.json()
    assert payload["counts"] == {"groups": 1, "skills": 1, "indicators": 1}
    assert payload["groups"][0]["title"] == "Backend"
    assert payload["skills"][0]["canonical_name"] == "Проектирование REST API"
    assert payload["indicators"][0]["text"].startswith("Проектирует")

    filtered = client.get("/reference/archive?scope=indicators&q=OpenAPI")
    assert filtered.status_code == 200
    assert filtered.json()["counts"]["indicators"] == 1
    assert filtered.json()["groups"] == []

    restored = client.post("/reference/archive/actions", json={"kind": "indicator", "id": indicator_id})
    assert restored.status_code == 200
    assert restored.json()["status"] == "restored"
    assert client.get(f"/reference/groups/{link.competency_id}").json()["status"] == "active"
    assert client.get(f"/reference/skills/{link.skill_id}").json()["status"] == "active"
    assert client.get(f"/reference/skills/{link.skill_id}").json()["indicators"][0]["status"] == "active"
    assert client.get("/reference/archive?scope=all").json()["counts"] == {"groups": 0, "skills": 0, "indicators": 0}


def test_reference_manifest_and_static_panel_are_registered() -> None:
    client, _repo = _client()

    modules = client.get("/api/modules").json()
    reference = next(item for item in modules if item["id"] == "reference")

    assert reference["tables"] == ["competency", "skill", "indicator_row", "review_queue"]
    assert reference["ui_panel"] == "reference/panel.html"
    assert client.get("/static/reference/panel.html").status_code == 200


def test_reference_panel_exposes_parity_controls_and_real_endpoints() -> None:
    client, _repo = _client()

    panel = client.get("/static/reference/panel.html")
    js = client.get("/static/reference/panel.js")

    assert panel.status_code == 200
    assert js.status_code == 200
    for marker in (
        'data-reference-mode="competencies"',
        'data-reference-mode="profiles"',
        'data-reference-mode="skills"',
        'data-reference-mode="reviews"',
        'id="skillForm"',
        'id="skillAliases"',
        'id="groupList"',
        'id="groupDetailSection"',
        'id="skillIndicators"',
        'id="indicatorCreateForm"',
        'id="candidateCompetencySection"',
        'id="candidateCompetencyCards"',
        'id="artifactTemplateSection"',
        'id="artifactTemplateForm"',
        'id="artifactTemplateTable"',
        'id="archiveSection"',
        'id="archiveForm"',
        'id="archivedIndicators"',
    ):
        assert marker in panel.text
    for marker in ('data-review-status="resolved"', 'data-review-status="ignored"'):
        assert marker in js.text
    for endpoint in (
        "/reference/summary",
        "/reference/competencies",
        "/reference/profiles",
        "/reference/skills",
        "/reference/groups",
        "/reference/indicators",
        "/reference/reviews",
        "/reference/candidate-competencies",
        "/reference/artifact-templates",
        "/reference/archive",
        "/intake/jobs",
    ):
        assert endpoint in js.text
    assert "fetch(" in js.text
    assert "sqlite" not in js.text.lower()


def test_intake_legacy_route_exposes_workspace_controls() -> None:
    client, _repo = _client()

    page = client.get("/intake")
    panel = client.get("/static/reference/panel.html")
    js = client.get("/static/reference/panel.js")

    assert page.status_code == 200
    assert panel.status_code == 200
    assert js.status_code == 200
    for marker in (
        'id="intakeWorkspace"',
        'id="briefFileInput"',
        'id="briefText"',
        'id="nextIntakeStep"',
        'id="jobBlockers"',
        'id="jobCreatedItems"',
        'id="jobPipelineResult"',
        "workflow-step",
        "Последние intake-задачи",
    ):
        assert marker in panel.text
    assert 'mode === "workspace"' in js.text
    assert 'request("/intake/jobs"' in js.text
    assert "/intake/jobs/${job.id}" in js.text


def test_intake_job_runs_pipeline_into_reference_and_curriculum() -> None:
    client, _repo = _client()

    created = client.post(
        "/intake/jobs",
        json={"brief_text": "Подготовить junior backend-разработчика: REST API, PostgreSQL, Docker, pytest.", "use_llm": False},
    )

    assert created.status_code == 201, created.text
    job = created.json()
    assert job["status"] == "succeeded"
    assert job["brief_id"]
    assert job["result_payload"]["competency_count"] >= 3
    assert job["result_payload"]["saved_items"]
    card = job["result_payload"]["saved_items"][0]
    assert card["name"]
    # adjudication engine surfaces per-card catalog-match + council metrics
    assert card["resolution"] in {"matched", "alias", "fuzzy", "new", "unresolved"}
    assert 0.0 <= float(card["confidence"]) <= 1.0
    assert card["match_score"] is not None and card["novelty_score"] is not None
    assert card["similarity_hint"]["class"] in {"strong", "medium", "weak", "neutral"}
    assert card["recommended_action"]["code"]
    assert "council" in job["result_payload"]
    dag = job["result_payload"]["dag"]
    assert dag["nodes"] >= 1
    assert isinstance(dag["waves"], list) and dag["waves"]
    assert isinstance(dag["final_edges"], list)
    assert dag["acyclic"] in {True, False}
    assert job["result_payload"]["curriculum_plan"]["plan_id"]
    assert client.get(f"/intake/jobs/{job['id']}/status").json()["status"] == "succeeded"
    detail_page = client.get(f"/intake/jobs/{job['id']}")
    assert detail_page.status_code == 200
    assert "text/html" in detail_page.headers["content-type"]
    assert 'id="intakeWorkspace"' in detail_page.text
    assert 'id="jobSkillCards"' in detail_page.text
    panel_js = client.get("/static/reference/panel.js").text
    assert "/intake/jobs/${currentJobId}/status" in panel_js
    assert "renderSkillCards" in panel_js
    assert "recommended_action" in panel_js
    assert "renderDag" in panel_js and "dag-svg" in panel_js
    assert 'id="jobDagMap"' in detail_page.text
    assert client.get("/reference/summary").json()["skills"] >= 3
    assert client.get("/curriculum/plans").json()[0]["plan_id"] == job["result_payload"]["curriculum_plan"]["plan_id"]


def test_create_group_adds_empty_competency_without_review() -> None:
    client, _repo = _client()

    created = client.post(
        "/reference/groups",
        json={"title": "Платформенная инженерия", "description": "Группа методолога"},
    )
    assert created.status_code == 201, created.text
    group = created.json()
    assert group["title"] == "Платформенная инженерия"
    assert group["status"] == "active"
    assert group["skills"] == []
    group_id = group["id"]

    listed = client.get("/reference/groups")
    assert any(item["id"] == group_id for item in listed.json())
    assert client.get(f"/reference/groups/{group_id}").status_code == 200

    # methodologist-created group must not enqueue a candidate review
    assert client.get("/reference/reviews").json() == []

    duplicate = client.post("/reference/groups", json={"title": "Платформенная инженерия"})
    assert duplicate.status_code == 409


def test_groups_panel_exposes_create_control() -> None:
    client, _repo = _client()
    panel = client.get("/static/reference/panel.html").text
    js = client.get("/static/reference/panel.js").text
    for marker in ('id="groupCreateForm"', 'id="groupCreateTitle"'):
        assert marker in panel
    assert "groupCreateForm" in js


def test_reviews_filter_by_severity_reason_and_entity() -> None:
    client, repo = _client()
    repo.save_competency(_competency(), source_note="pytest:reviewfilter")

    items = client.get("/reference/reviews").json()
    assert len(items) == 1
    item = items[0]
    assert item["severity"] == "warning"
    assert item["reason_code"] == "new_competency_candidate"
    assert item["entity_type"] == "competency"

    assert len(client.get("/reference/reviews?severity=warning").json()) == 1
    assert client.get("/reference/reviews?severity=critical").json() == []
    assert len(client.get("/reference/reviews?entity_type=competency").json()) == 1
    assert client.get("/reference/reviews?entity_type=skill").json() == []
    assert len(client.get("/reference/reviews?reason_code=new_competency_candidate").json()) == 1
    assert client.get("/reference/reviews?reason_code=missing_indicator").json() == []


def test_review_can_be_returned_to_queue() -> None:
    client, repo = _client()
    repo.save_competency(_competency(), source_note="pytest:reopen")
    review_id = client.get("/reference/reviews").json()[0]["id"]

    assert client.patch(f"/reference/reviews/{review_id}", json={"status": "resolved"}).status_code == 200
    assert client.get("/reference/reviews").json() == []

    reopened = client.patch(f"/reference/reviews/{review_id}", json={"status": "open", "note": "повторно"})
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "open"
    assert any(item["id"] == review_id for item in client.get("/reference/reviews").json())


def test_reviews_panel_exposes_return_to_queue_action() -> None:
    client, _repo = _client()
    js = client.get("/static/reference/panel.js").text
    assert 'data-review-status="open"' in js


def test_reviews_panel_exposes_severity_reason_entity_filters() -> None:
    client, _repo = _client()
    panel = client.get("/static/reference/panel.html").text
    js = client.get("/static/reference/panel.js").text
    for marker in ('id="reviewSeverityFilter"', 'id="reviewReasonFilter"', 'id="reviewEntityFilter"'):
        assert marker in panel
    assert "reviewFilterQuery" in js
    for param in ('"severity"', '"reason_code"', '"entity_type"'):
        assert param in js
    for el_id in ("reviewSeverityFilter", "reviewEntityFilter", "reviewReasonFilter"):
        assert el_id in js


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
    app.dependency_overrides[get_curriculum_repo] = lambda: repo
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
