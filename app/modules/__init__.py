from fastapi import APIRouter

from app.core.registry import ModuleManifest, Tile


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
    _empty_module("generator", "Генератор", "wand", "Генерация учебных материалов"),
    _empty_module("checker", "Проверка", "check-circle", "Структурная и дидактическая оценка"),
    _empty_module("translator", "Переводчик", "languages", "Перевод документов и видео"),
    _empty_module("curriculum", "Учебный план", "map", "Каталог, планирование и редактор УП"),
    _empty_module("reference", "Справочник", "book-open", "Каталог компетенций и профилей"),
)

__all__ = ["BUILTIN_MODULES"]
