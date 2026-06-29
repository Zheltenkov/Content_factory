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
    assert 'request("/generator/runs/from-curriculum/async"' in js
    assert 'request("/generator/runs/recent")' in js
    assert "/generator/runs/${runId}/status" in js
    assert "/generator/runs/${state.currentRunId}/cancel" in js
    assert "/generator/runs/${state.currentRunId}/archive" in js
    assert "/generator/runs/${state.currentRunId}/review/request-changes" in js
    assert "/generator/runs/${state.currentRunId}/review/preview-changes" in js
    assert "/generator/runs/${state.currentRunId}/review/approve-diff" in js
    assert "/generator/runs/${state.currentRunId}/regenerate" in js
    assert "selectedRegenerationScopes" in js
    assert "regenerateCurrentRun" in js
    assert "project_order: Number(state.currentProject.project.order)" in js
    assert "pollGenerationStatus" in js
    assert "setTimeout" in js


def test_generator_panel_keeps_legacy_controls_without_mocking_backend() -> None:
    html = (STATIC / "generator" / "panel.html").read_text(encoding="utf-8")
    js = (STATIC / "generator" / "panel.js").read_text(encoding="utf-8")

    required_controls = [
        'id="curriculumFile"',
        'id="methodologyHumanReview"',
        'id="direction"',
        'id="projectType"',
        'id="groupSize"',
        'id="audienceLevel"',
        'id="titleSeed"',
        'id="storytellingType"',
        'id="storytelling"',
        'id="learningOutcomes"',
        'id="skills"',
        'id="includeDiagrams"',
        'id="includeTables"',
        'id="includeFormulas"',
        'id="generateBonus"',
        'id="regenerationComments"',
        'id="methodologyAssistantChat"',
        'id="assistantChatInput"',
        'data-tab-target="generatorPractice"',
        'data-tab-target="generatorRegen"',
    ]

    for control in required_controls:
        assert control in html
    assert "/curriculum/plans/import-csv" in js
    assert "overrides: collectOverrides()" in js


def test_generator_panel_keeps_legacy_full_width_split_layout() -> None:
    css = (STATIC / "styles.css").read_text(encoding="utf-8")

    assert "body.s21-product.page-generate .generator-workflow-grid" in css
    assert "grid-template-columns: 560px minmax(0, 1fr);" in css
    assert "body.s21-product.page-generate .generator-result-title" in css
    assert "linear-gradient(rgba(15, 20, 25, 0.04) 1px, transparent 1px)" in css
    assert "body.s21-product.page-generate .generator-empty-state .generator-result-checklist" in css
