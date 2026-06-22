from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "app" / "static"


def test_generator_panel_uses_db_backed_controls_and_result_tabs() -> None:
    client = TestClient(create_app())

    response = client.get("/static/generator/panel.html")

    assert response.status_code == 200
    assert 'id="planSelect"' in response.text
    assert 'id="blockSelect"' in response.text
    assert 'id="projectSelect"' in response.text
    assert 'data-tab-target="generatorReadme"' in response.text
    assert 'data-tab-target="generatorMetadata"' in response.text
    assert 'data-tab-target="generatorIssues"' in response.text
    assert 'data-tab-target="generatorArtifacts"' in response.text
    assert '<script src="/static/shared/shell.js"></script>' in response.text
    assert '<script src="/static/shared/markdown.js"></script>' in response.text


def test_generator_panel_js_hits_real_curriculum_and_generator_endpoints() -> None:
    js = (STATIC / "generator" / "panel.js").read_text(encoding="utf-8")

    assert 'request("/curriculum/plans")' in js
    assert "request(`/curriculum/plans/${planId}/cascade`)" in js
    assert "request(`/curriculum/projects/${projectId}`)" in js
    assert 'request("/generator/runs/from-curriculum"' in js
    assert "project_order: Number(state.currentProject.project.order)" in js
    assert "pollGenerationStatus" not in js
    assert "setInterval" not in js
