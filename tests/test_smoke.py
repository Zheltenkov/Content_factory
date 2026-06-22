from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.core.registry import ModuleManifest, Tile
from app.main import create_app


def test_dashboard_renders_registered_builtin_tiles() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "Content Factory" in response.text
    assert "Генератор" in response.text
    assert "Учебный план" in response.text
    assert 'data-panel="reference/panel.html"' in response.text


def test_builtin_module_panels_render() -> None:
    client = TestClient(create_app())

    for path in (
        "/static/generator/panel.html",
        "/static/checker/panel.html",
        "/static/translator/panel.html",
        "/static/curriculum/panel.html",
        "/static/reference/panel.html",
    ):
        response = client.get(path)
        assert response.status_code == 200


def test_registered_module_has_tile_in_api_modules() -> None:
    manifest = ModuleManifest(
        id="demo",
        title="Demo",
        icon="box",
        router=APIRouter(prefix="/demo"),
        ui_panel="demo/panel.html",
        dashboard_tile=Tile(action="goToDemo", subtitle="Demo module"),
    )
    client = TestClient(create_app(modules=[manifest]))

    response = client.get("/api/modules")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["id"] == "demo"
    assert payload[0]["dashboard_tile"] == {"action": "goToDemo", "subtitle": "Demo module"}
