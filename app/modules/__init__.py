from fastapi import APIRouter

from app.core.registry import ModuleManifest, Tile
from app.modules.checker.router import router as checker_router
from app.modules.curriculum.router import router as curriculum_router
from app.modules.generator.router import router as generator_router
from app.modules.reference.router import router as reference_router


def _empty_module(module_id: str, title: str, icon: str, subtitle: str) -> ModuleManifest:
    return ModuleManifest(
        id=module_id,
        title=title,
        icon=icon,
        router=APIRouter(prefix=f"/{module_id}", tags=[module_id]),
        ui_panel=f"{module_id}/panel.html",
        dashboard_tile=Tile(action=f"goTo{module_id.title()}", subtitle=subtitle),
    )


BUILTIN_MODULES = (
    ModuleManifest(
        id="generator",
        title="Генератор",
        icon="wand",
        router=generator_router,
        ui_panel="generator/panel.html",
        dashboard_tile=Tile(action="goToGenerator", subtitle="Генерация учебных материалов"),
    ),
    ModuleManifest(
        id="checker",
        title="Проверка",
        icon="check-circle",
        router=checker_router,
        ui_panel="checker/panel.html",
        dashboard_tile=Tile(action="goToChecker", subtitle="Структурная и дидактическая оценка"),
    ),
    _empty_module("translator", "Переводчик", "languages", "Перевод документов и видео"),
    ModuleManifest(
        id="curriculum",
        title="Учебный план",
        icon="map",
        router=curriculum_router,
        ui_panel="curriculum/panel.html",
        tables=("curriculum_plan", "curriculum_project"),
        dashboard_tile=Tile(action="goToCurriculum", subtitle="Каталог, планирование и редактор УП"),
    ),
    ModuleManifest(
        id="reference",
        title="Справочник",
        icon="book-open",
        router=reference_router,
        ui_panel="reference/panel.html",
        tables=("competency", "skill", "indicator_row", "review_queue"),
        dashboard_tile=Tile(action="goToReference", subtitle="Каталог компетенций, skills и индикаторов"),
    ),
)

__all__ = ["BUILTIN_MODULES"]
