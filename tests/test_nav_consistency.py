"""Every module shell must reach every module through one unified top nav."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app

MODULE_NAV_LINKS = (
    'href="/app"',
    'href="/app/generate"',
    'href="/app/check"',
    'href="/app/translate"',
    'href="/up"',
    'href="/catalog-admin/groups"',
    'href="/app/instruction"',
)

SHELL_ROUTES = (
    "/",
    "/app/generate",
    "/app/check",
    "/app/translate",
    "/up",
    "/catalog-admin/groups",
)


def test_every_shell_exposes_all_module_nav_links() -> None:
    client = TestClient(create_app())
    for route in SHELL_ROUTES:
        page = client.get(route)
        assert page.status_code == 200, route
        for link in MODULE_NAV_LINKS:
            assert link in page.text, f"{route} missing nav link {link}"


def test_shared_shell_module_nav_lists_all_modules() -> None:
    client = TestClient(create_app())
    shell = client.get("/static/shared/shell.js").text
    for token in ('"/app/generate"', '"/app/check"', '"/app/translate"', '"/up"', '"/catalog-admin/groups"'):
        assert token in shell, token
