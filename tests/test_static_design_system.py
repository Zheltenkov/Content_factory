from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"


def test_u1_design_system_exposes_shared_primitives() -> None:
    css = (STATIC / "styles.css").read_text(encoding="utf-8")

    required_selectors = [
        ":root",
        "--cf-accent",
        ".dashboard-shell",
        ".module-grid",
        ".workbench",
        ".tool-grid",
        ".editor-panel",
        ".side-panel",
        ".toolbar",
        ".file-button",
        ".markdown-preview",
        ".tab-list",
        ".metrics-grid",
        ".issue-list",
        ".progress-bar",
        ".s21-run-timeline",
    ]

    for selector in required_selectors:
        assert selector in css
    assert "vendor/mermaid" not in css
    assert "land.png" not in css


def test_d3_reference_and_curriculum_use_unified_s21_skin() -> None:
    css = (STATIC / "styles.css").read_text(encoding="utf-8")
    curriculum = (STATIC / "curriculum" / "panel.html").read_text(encoding="utf-8")
    reference = (STATIC / "reference" / "panel.html").read_text(encoding="utf-8")

    assert "D3 unified S21 panel skin" in css
    assert "Reference Spravochnik parity" in css
    assert "body.s21-product.methodologist-product.page-reference" in css
    assert "body.s21-product.methodologist-product" in css
    assert 'class="s21-product methodologist-product page-curriculum"' in curriculum
    assert 'class="s21-product methodologist-product page-reference"' in reference
    assert "Единый S21-контур" in curriculum
    assert "Единый S21-контур" in reference


def test_module_panels_render_with_shared_layout_classes() -> None:
    client = TestClient(create_app())
    panels = {
        "generator": ("workbench", "tool-grid", "editor-panel"),
        "checker": ("workbench", "tool-grid", "editor-panel"),
        "translator": ("workbench", "tool-grid", "markdown-preview"),
        "curriculum": ("workbench", "curriculum-grid", "file-button"),
        "reference": ("workbench", "reference-grid", "summary-grid"),
    }

    css_response = client.get("/static/styles.css")
    assert css_response.status_code == 200
    assert "--cf-accent" in css_response.text

    for panel, classes in panels.items():
        response = client.get(f"/static/{panel}/panel.html")

        assert response.status_code == 200
        assert '<link rel="stylesheet" href="/static/styles.css" />' in response.text
        for class_name in classes:
            assert class_name in response.text
