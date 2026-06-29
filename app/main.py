from html import escape
from pathlib import Path
from typing import Sequence

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from app.core.registry import ModuleManifest, iter_modules, module_payloads, reset_registry
from app.modules import BUILTIN_MODULES
from app.modules.reference.router import intake_router


STATIC_DIR = Path(__file__).resolve().parent / "static"
DASHBOARD_PATH = STATIC_DIR / "dashboard.html"
GENERATOR_PANEL_PATH = STATIC_DIR / "generator" / "panel.html"
CHECKER_PANEL_PATH = STATIC_DIR / "checker" / "panel.html"
TRANSLATOR_PANEL_PATH = STATIC_DIR / "translator" / "panel.html"
CURRICULUM_PANEL_PATH = STATIC_DIR / "curriculum" / "panel.html"
REFERENCE_PANEL_PATH = STATIC_DIR / "reference" / "panel.html"
INSTRUCTION_PATH = STATIC_DIR / "instruction.html"
TILE_MARKER = "{{ module_tiles }}"
TILE_DETAILS = {
    "generator": {
        "index": "РЕЖИМ / 01",
        "art": "art-generate",
        "bullets": ("УП из общей БД", "README, теория и практика", "Gate и методология"),
    },
    "checker": {
        "index": "РЕЖИМ / 02",
        "art": "art-check",
        "bullets": ("Структурная ось", "Дидактическое жюри", "Reverse-extraction"),
    },
    "translator": {
        "index": "РЕЖИМ / 03",
        "art": "art-translate",
        "bullets": ("Документы", "Видео и субтитры", "Сохранение структуры"),
    },
    "curriculum": {
        "index": "РЕЖИМ / 04",
        "art": "art-curriculum",
        "bullets": ("Импорт CSV", "Редактор УП", "Экспорт из БД"),
    },
    "reference": {
        "index": "РЕЖИМ / 05",
        "art": "art-reference",
        "bullets": ("Компетенции", "Skills и индикаторы", "Review queue"),
    },
}


class NoCacheStaticFiles(StaticFiles):
    """Serve local UI assets without browser caching during active parity work."""

    def file_response(self, full_path: Path, stat_result: object, scope: dict[str, object], status_code: int = 200) -> Response:
        response = super().file_response(full_path, stat_result, scope, status_code)
        response.headers["Cache-Control"] = "no-store"
        return response


def create_app(modules: Sequence[ModuleManifest] | None = None) -> FastAPI:
    """Build the ASGI app and register module manifests for this process."""
    application = FastAPI(title="Content Factory")
    reset_registry(tuple(BUILTIN_MODULES if modules is None else modules))

    application.mount("/static", NoCacheStaticFiles(directory=STATIC_DIR), name="static")
    for manifest in iter_modules():
        application.include_router(manifest.router)
    application.include_router(intake_router)

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

    @application.get("/app")
    def content_generator_dashboard() -> RedirectResponse:
        return RedirectResponse(url="/", status_code=307)

    @application.get("/app/generate")
    def content_generator_generate() -> FileResponse:
        return FileResponse(GENERATOR_PANEL_PATH, headers={"Cache-Control": "no-store"})

    @application.get("/app/check")
    def content_generator_check() -> FileResponse:
        return FileResponse(CHECKER_PANEL_PATH, headers={"Cache-Control": "no-store"})

    @application.get("/app/translate")
    def content_generator_translate() -> FileResponse:
        return FileResponse(TRANSLATOR_PANEL_PATH, headers={"Cache-Control": "no-store"})

    @application.get("/app/instruction")
    def content_generator_instruction() -> FileResponse:
        return FileResponse(INSTRUCTION_PATH, headers={"Cache-Control": "no-store"})

    @application.get("/intake")
    def spravochnik_intake() -> FileResponse:
        return FileResponse(REFERENCE_PANEL_PATH, headers={"Cache-Control": "no-store"})

    @application.get("/intake/jobs/{job_id}")
    def spravochnik_intake_job(job_id: int) -> FileResponse:
        return FileResponse(REFERENCE_PANEL_PATH, headers={"Cache-Control": "no-store"})

    @application.get("/up")
    def spravochnik_curriculum() -> FileResponse:
        return FileResponse(CURRICULUM_PANEL_PATH, headers={"Cache-Control": "no-store"})

    @application.get("/catalog-admin")
    def spravochnik_catalog_admin() -> RedirectResponse:
        return RedirectResponse(url="/catalog-admin/groups", status_code=307)

    @application.get("/catalog-admin/{path:path}")
    def spravochnik_catalog_admin_path(path: str) -> FileResponse:
        return FileResponse(REFERENCE_PANEL_PATH, headers={"Cache-Control": "no-store"})

    @application.get("/competencies")
    def spravochnik_competencies() -> FileResponse:
        return FileResponse(REFERENCE_PANEL_PATH, headers={"Cache-Control": "no-store"})

    @application.get("/competencies/{path:path}")
    def spravochnik_competencies_path(path: str) -> FileResponse:
        return FileResponse(REFERENCE_PANEL_PATH, headers={"Cache-Control": "no-store"})

    @application.get("/profiles")
    def spravochnik_profiles() -> FileResponse:
        return FileResponse(REFERENCE_PANEL_PATH, headers={"Cache-Control": "no-store"})

    @application.get("/profiles/{path:path}")
    def spravochnik_profiles_path(path: str) -> FileResponse:
        return FileResponse(REFERENCE_PANEL_PATH, headers={"Cache-Control": "no-store"})

    @application.get("/reviews")
    def spravochnik_reviews() -> FileResponse:
        return FileResponse(REFERENCE_PANEL_PATH, headers={"Cache-Control": "no-store"})

    return application


def _render_tile(module: dict[str, object]) -> str:
    tile = module["dashboard_tile"]
    assert isinstance(tile, dict)
    module_id = str(module["id"])
    panel_url = _module_url(module_id, str(module["ui_panel"]))
    details = TILE_DETAILS.get(module_id, {})
    bullets = "".join(f"<li>{escape(item)}</li>" for item in details.get("bullets", ()))
    index = str(details.get("index", "МОДУЛЬ"))
    art = _render_tile_art(str(details.get("art", "art-generic")), module_id, index)
    return (
        f'<article class="module-tile dashboard-mode-card" data-action="{escape(str(tile["action"]))}" '
        f'data-panel="{escape(str(module["ui_panel"]))}">'
        f"{art}"
        '<div class="dashboard-card-body">'
        f"<h2>{escape(str(module['title']))}</h2>"
        f"<p>{escape(str(tile['subtitle']))}</p>"
        f"<ul>{bullets}</ul>"
        f'<a class="dashboard-primary-action" href="{panel_url}">Открыть <span>→</span></a>'
        "</div>"
        "</article>"
    )


def _render_tile_art(art_class: str, module_id: str, index: str = "МОДУЛЬ") -> str:
    if module_id == "generator":
        body = '<div class="art-doc light"></div><span class="art-plus">+</span><div class="art-doc dark"><span></span></div>'
    elif module_id == "checker":
        body = (
            '<div class="art-report"><span class="art-line short"></span><span class="art-line wide"></span>'
            '<span class="art-line"></span><div class="art-report-score">87%</div>'
            '<div class="art-report-tags"><span>35 ✓</span><span>4 ×</span></div></div>'
        )
    elif module_id == "translator":
        body = '<div class="art-lang-card light">RU<span></span></div><span class="art-arrow">→</span><div class="art-lang-card dark">EN<span></span></div>'
    elif module_id == "curriculum":
        body = '<div class="art-plan"><span>01</span><span>02</span><span>03</span><strong>УП</strong></div>'
    elif module_id == "reference":
        body = '<div class="art-catalog"><span></span><span></span><span></span><strong>CAT</strong></div>'
    else:
        body = f'<span class="module-icon">{escape(module_id[:2].upper())}</span>'
    return f'<div class="dashboard-card-art {escape(art_class)}"><div class="dashboard-card-index">{escape(index)}</div>{body}</div>'


def _module_url(module_id: str, ui_panel: str) -> str:
    routes = {
        "generator": "/app/generate",
        "checker": "/app/check",
        "translator": "/app/translate",
        "curriculum": "/up",
        "reference": "/catalog-admin/groups",
    }
    return routes.get(module_id, f"/static/{escape(ui_panel)}")


app = create_app()
