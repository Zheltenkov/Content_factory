from html import escape
from pathlib import Path
from collections.abc import Sequence

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
        "title": "Генерация README",
        "description": "Полный пайплайн: от паспорта программы до итогового документа с теорией, практикой и критериями.",
        "cta": "Перейти к генератору",
        "art": "art-generate",
        "bullets": (
            "Анализ учебного плана и результатов обучения",
            "План практики, задачи и критерии",
            "Диаграммы, формулы, отчёты",
        ),
    },
    "checker": {
        "index": "РЕЖИМ / 02",
        "title": "Проверка README",
        "description": "Загрузите готовый README.md и получите разбор по 39 критериям с понятными комментариями.",
        "cta": "Перейти к проверке",
        "art": "art-check",
        "bullets": (
            "Все 39 критериев качества",
            "Что улучшить и почему — текстом",
            "Метрики и структура документа",
        ),
    },
    "translator": {
        "index": "РЕЖИМ / 03",
        "title": "Перевод документов и видео",
        "description": "Переведите README или Markdown с сохранением структуры. Также — видео и субтитры.",
        "cta": "Перейти к переводу",
        "art": "art-translate",
        "bullets": (
            "Markdown, формулы и таблицы целые",
            "Поддержка Mermaid-диаграмм",
            "Субтитры VTT/SRT и видео-перевод",
        ),
    },
    "curriculum": {
        "index": "РЕЖИМ / 04",
        "title": "Учебный план",
        "description": "Каталог, планирование и row-edit учебных проектов с привязкой к единой методологической базе.",
        "cta": "Перейти к УП",
        "art": "art-curriculum",
        "bullets": (
            "Иерархия планов и проектов",
            "Редактор строк и результатов обучения",
            "Предложения шаблонов артефактов",
        ),
    },
    "reference": {
        "index": "РЕЖИМ / 05",
        "title": "Справочник",
        "description": "Каталог компетенций, skills, индикаторов и review queue для общей методологической базы.",
        "cta": "Перейти к справочнику",
        "art": "art-reference",
        "bullets": (
            "Компетенции и профили",
            "Skills и индикаторы",
            "Intake, архив и review queue",
        ),
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
    title = str(details.get("title", module["title"]))
    description = str(details.get("description", tile["subtitle"]))
    cta = str(details.get("cta", "Открыть"))
    return (
        f'<article class="module-tile dashboard-mode-card" data-action="{escape(str(tile["action"]))}" '
        f'data-panel="{escape(str(module["ui_panel"]))}">'
        f"{art}"
        '<div class="dashboard-card-body">'
        '<div class="dashboard-card-copy">'
        f"<h2>{escape(title)}</h2>"
        f"<p>{escape(description)}</p>"
        "</div>"
        f"<ul>{bullets}</ul>"
        f'<a class="dashboard-primary-action" href="{panel_url}">{escape(cta)} <span>→</span></a>'
        "</div>"
        "</article>"
    )


def _render_tile_art(art_class: str, module_id: str, index: str = "МОДУЛЬ") -> str:
    if module_id == "generator":
        body = (
            '<svg class="dashboard-card-illust" width="200" height="140" viewBox="0 0 200 140" fill="none" '
            'aria-hidden="true">'
            '<rect x="20" y="20" width="60" height="80" rx="6" fill="#fff" stroke="#0f1419" stroke-width="1.2"/>'
            '<rect x="30" y="32" width="40" height="3" rx="1.5" fill="#0f1419"/>'
            '<rect x="30" y="42" width="32" height="2" rx="1" fill="#0f1419" opacity=".3"/>'
            '<rect x="30" y="48" width="36" height="2" rx="1" fill="#0f1419" opacity=".3"/>'
            '<rect x="30" y="54" width="28" height="2" rx="1" fill="#0f1419" opacity=".3"/>'
            '<rect x="30" y="64" width="40" height="3" rx="1.5" fill="#0f1419"/>'
            '<rect x="30" y="74" width="34" height="2" rx="1" fill="#0f1419" opacity=".3"/>'
            '<rect x="30" y="80" width="38" height="2" rx="1" fill="#0f1419" opacity=".3"/>'
            '<rect x="30" y="86" width="22" height="2" rx="1" fill="#0f1419" opacity=".3"/>'
            '<rect x="100" y="40" width="60" height="80" rx="6" fill="#0f1419"/>'
            '<rect x="110" y="52" width="40" height="3" rx="1.5" fill="#fff"/>'
            '<rect x="110" y="62" width="32" height="2" rx="1" fill="#fff" opacity=".5"/>'
            '<rect x="110" y="68" width="36" height="2" rx="1" fill="#fff" opacity=".5"/>'
            '<rect x="110" y="74" width="28" height="2" rx="1" fill="#fff" opacity=".5"/>'
            '<rect x="110" y="86" width="22" height="22" rx="4" fill="#fff" opacity=".15"/>'
            '<path d="M115 97l5 5 9-9" stroke="#fff" stroke-width="1.6" fill="none" '
            'stroke-linecap="round" stroke-linejoin="round"/>'
            '<path d="M82 60h16M90 56v8" stroke="#0f1419" stroke-width="1.4" '
            'stroke-linecap="round"/>'
            "</svg>"
        )
    elif module_id == "checker":
        body = (
            '<svg class="dashboard-card-illust" width="200" height="140" viewBox="0 0 200 140" fill="none" '
            'aria-hidden="true">'
            '<rect x="40" y="22" width="120" height="100" rx="6" fill="#fff" stroke="#0f1419" stroke-width="1.2"/>'
            '<rect x="50" y="34" width="40" height="3" rx="1.5" fill="#0f1419"/>'
            '<circle cx="142" cy="36" r="14" fill="#0f1419"/>'
            '<text x="142" y="40" font-size="9" font-weight="700" font-family="Inter" fill="#fff" '
            'text-anchor="middle">87%</text>'
            '<rect x="50" y="58" width="100" height="6" rx="2" fill="#eef0ec"/>'
            '<rect x="50" y="58" width="84" height="6" rx="2" fill="#0f1419"/>'
            '<rect x="50" y="74" width="100" height="3" rx="1" fill="#0f1419" opacity=".25"/>'
            '<rect x="50" y="82" width="76" height="3" rx="1" fill="#0f1419" opacity=".25"/>'
            '<rect x="50" y="92" width="42" height="14" rx="3" fill="#eaf4ee"/>'
            '<text x="71" y="102" font-size="8" font-weight="600" font-family="Inter" fill="#2f7a4d" '
            'text-anchor="middle">35 ✓</text>'
            '<rect x="98" y="92" width="42" height="14" rx="3" fill="#f7ebe7"/>'
            '<text x="119" y="102" font-size="8" font-weight="600" font-family="Inter" fill="#b54a3b" '
            'text-anchor="middle">4 ✕</text>'
            "</svg>"
        )
    elif module_id == "translator":
        body = (
            '<svg class="dashboard-card-illust" width="200" height="140" viewBox="0 0 200 140" fill="none" '
            'aria-hidden="true">'
            '<rect x="20" y="30" width="76" height="80" rx="6" fill="#fff" stroke="#0f1419" stroke-width="1.2"/>'
            '<text x="58" y="52" font-size="11" font-weight="600" font-family="Inter" fill="#0f1419" '
            'text-anchor="middle">RU</text>'
            '<rect x="30" y="62" width="56" height="2" rx="1" fill="#0f1419" opacity=".3"/>'
            '<rect x="30" y="68" width="48" height="2" rx="1" fill="#0f1419" opacity=".3"/>'
            '<rect x="30" y="74" width="52" height="2" rx="1" fill="#0f1419" opacity=".3"/>'
            '<rect x="30" y="80" width="40" height="2" rx="1" fill="#0f1419" opacity=".3"/>'
            '<path d="M100 70h12M108 66l4 4-4 4" stroke="#0f1419" stroke-width="1.4" '
            'stroke-linecap="round" stroke-linejoin="round" fill="none"/>'
            '<rect x="116" y="30" width="76" height="80" rx="6" fill="#0f1419"/>'
            '<text x="154" y="52" font-size="11" font-weight="600" font-family="Inter" fill="#fff" '
            'text-anchor="middle">EN</text>'
            '<rect x="126" y="62" width="56" height="2" rx="1" fill="#fff" opacity=".5"/>'
            '<rect x="126" y="68" width="48" height="2" rx="1" fill="#fff" opacity=".5"/>'
            '<rect x="126" y="74" width="52" height="2" rx="1" fill="#fff" opacity=".5"/>'
            '<rect x="126" y="80" width="40" height="2" rx="1" fill="#fff" opacity=".5"/>'
            "</svg>"
        )
    elif module_id == "curriculum":
        body = (
            '<svg class="dashboard-card-illust" width="200" height="140" viewBox="0 0 200 140" fill="none" '
            'aria-hidden="true">'
            '<rect x="26" y="28" width="148" height="86" rx="6" fill="#fff" stroke="#0f1419" stroke-width="1.2"/>'
            '<rect x="38" y="40" width="34" height="24" rx="4" fill="#f4f5f1"/>'
            '<text x="55" y="56" font-size="10" font-weight="700" font-family="Inter" fill="#0f1419" '
            'text-anchor="middle">01</text>'
            '<rect x="82" y="40" width="34" height="24" rx="4" fill="#f4f5f1"/>'
            '<text x="99" y="56" font-size="10" font-weight="700" font-family="Inter" fill="#0f1419" '
            'text-anchor="middle">02</text>'
            '<rect x="126" y="40" width="34" height="24" rx="4" fill="#f4f5f1"/>'
            '<text x="143" y="56" font-size="10" font-weight="700" font-family="Inter" fill="#0f1419" '
            'text-anchor="middle">03</text>'
            '<rect x="38" y="76" width="122" height="26" rx="5" fill="#0f1419"/>'
            '<text x="99" y="93" font-size="11" font-weight="700" font-family="Inter" fill="#2ed18a" '
            'text-anchor="middle">УП</text>'
            '<path d="M55 64v12M99 64v12M143 64v12" stroke="#0f1419" opacity=".25" stroke-width="1.2"/>'
            "</svg>"
        )
    elif module_id == "reference":
        body = (
            '<svg class="dashboard-card-illust" width="200" height="140" viewBox="0 0 200 140" fill="none" '
            'aria-hidden="true">'
            '<rect x="34" y="24" width="118" height="96" rx="6" fill="#fff" stroke="#0f1419" stroke-width="1.2"/>'
            '<rect x="48" y="38" width="42" height="8" rx="2" fill="#0f1419"/>'
            '<rect x="48" y="56" width="90" height="4" rx="2" fill="#0f1419" opacity=".28"/>'
            '<rect x="48" y="68" width="72" height="4" rx="2" fill="#0f1419" opacity=".28"/>'
            '<rect x="48" y="80" width="84" height="4" rx="2" fill="#0f1419" opacity=".28"/>'
            '<rect x="48" y="94" width="44" height="16" rx="4" fill="#eaf4ee"/>'
            '<text x="70" y="105" font-size="8" font-weight="700" font-family="Inter" fill="#2f7a4d" '
            'text-anchor="middle">skill</text>'
            '<rect x="102" y="94" width="36" height="16" rx="4" fill="#f4f5f1"/>'
            '<text x="120" y="105" font-size="8" font-weight="700" font-family="Inter" fill="#0f1419" '
            'text-anchor="middle">CAT</text>'
            '<rect x="132" y="44" width="34" height="34" rx="6" fill="#0f1419"/>'
            '<path d="M141 61h16M149 53v16" stroke="#2ed18a" stroke-width="1.6" stroke-linecap="round"/>'
            "</svg>"
        )
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
