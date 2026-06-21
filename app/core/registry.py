from dataclasses import dataclass, field

from fastapi import APIRouter


@dataclass(frozen=True, slots=True)
class Tile:
    action: str
    subtitle: str


@dataclass(frozen=True, slots=True)
class ModuleManifest:
    id: str
    title: str
    icon: str
    router: APIRouter
    ui_panel: str
    tables: tuple[str, ...] = field(default_factory=tuple)
    dashboard_tile: Tile | None = None


MODULE_REGISTRY: dict[str, ModuleManifest] = {}


def register_module(manifest: ModuleManifest) -> ModuleManifest:
    if manifest.id in MODULE_REGISTRY:
        raise ValueError(f"Module already registered: {manifest.id}")
    MODULE_REGISTRY[manifest.id] = manifest
    return manifest


def reset_registry(manifests: tuple[ModuleManifest, ...]) -> None:
    MODULE_REGISTRY.clear()
    for manifest in manifests:
        register_module(manifest)


def iter_modules() -> tuple[ModuleManifest, ...]:
    return tuple(MODULE_REGISTRY.values())


def module_payloads() -> list[dict[str, object]]:
    payloads: list[dict[str, object]] = []
    for manifest in iter_modules():
        tile = manifest.dashboard_tile
        payloads.append(
            {
                "id": manifest.id,
                "title": manifest.title,
                "icon": manifest.icon,
                "ui_panel": manifest.ui_panel,
                "tables": list(manifest.tables),
                "dashboard_tile": None if tile is None else {"action": tile.action, "subtitle": tile.subtitle},
            }
        )
    return payloads
