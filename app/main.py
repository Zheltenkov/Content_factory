from html import escape
from pathlib import Path
from typing import Sequence

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.core.registry import ModuleManifest, iter_modules, module_payloads, reset_registry
from app.modules import BUILTIN_MODULES


STATIC_DIR = Path(__file__).resolve().parent / "static"
DASHBOARD_PATH = STATIC_DIR / "dashboard.html"
TILE_MARKER = "{{ module_tiles }}"


def create_app(modules: Sequence[ModuleManifest] | None = None) -> FastAPI:
    """Build the ASGI app and register module manifests for this process."""
    application = FastAPI(title="Content Factory")
    reset_registry(tuple(BUILTIN_MODULES if modules is None else modules))

    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    for manifest in iter_modules():
        application.include_router(manifest.router)

    @application.get("/api/modules")
    def modules_index() -> list[dict[str, object]]:
        return module_payloads()

    @application.get("/", response_class=HTMLResponse)
    def dashboard() -> str:
        tiles = "\n".join(_render_tile(module) for module in module_payloads() if module["dashboard_tile"])
        return DASHBOARD_PATH.read_text(encoding="utf-8").replace(
            TILE_MARKER,
            tiles or '<div class="empty-state">Модули еще не зарегистрированы.</div>',
        )

    return application


def _render_tile(module: dict[str, object]) -> str:
    tile = module["dashboard_tile"]
    assert isinstance(tile, dict)
    return (
        f'<article class="module-tile" data-action="{escape(str(tile["action"]))}" data-panel="{escape(str(module["ui_panel"]))}">'
        f'<span class="module-icon">{escape(str(module["icon"]))}</span>'
        f"<h2>{escape(str(module['title']))}</h2>"
        f"<p>{escape(str(tile['subtitle']))}</p>"
        "</article>"
    )


app = create_app()
