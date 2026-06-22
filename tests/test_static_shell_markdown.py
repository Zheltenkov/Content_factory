from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"


def test_shared_markdown_renderer_sanitizes_and_preserves_mermaid() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is required for static renderer smoke test")

    script = f"""
const fs = require("fs");
const vm = require("vm");

(async () => {{
  const source = fs.readFileSync({json.dumps(str(STATIC / "shared" / "markdown.js"))}, "utf8");
  const context = {{
    console,
    URL,
    document: {{ addEventListener() {{}}, querySelectorAll() {{ return []; }} }},
    window: {{ location: {{ href: "http://localhost/" }} }},
  }};
  context.window.document = context.document;
  vm.createContext(context);
  vm.runInContext(source, context);

  const container = {{ innerHTML: "", querySelectorAll() {{ return []; }} }};
  await context.window.ContentFactoryMarkdown.renderMarkdown(
    container,
    "# Title\\n\\n<script>alert(1)</script>\\n\\n| A | B |\\n| --- | --- |\\n| 1 | 2 |\\n\\n```mermaid\\ngraph TD\\nA-->B\\n```"
  );

  if (container.innerHTML.includes("<script>")) throw new Error("unsafe script tag rendered");
  if (!container.innerHTML.includes("&lt;script&gt;alert(1)&lt;/script&gt;")) throw new Error("script text was not escaped");
  if (!container.innerHTML.includes("table-wrapper")) throw new Error("markdown table was not rendered");
  if (!container.innerHTML.includes('class="mermaid"')) throw new Error("mermaid block was not preserved");
  if (!container.innerHTML.includes("data-mermaid-source")) throw new Error("mermaid source was not retained");
}})().catch((error) => {{
  console.error(error);
  process.exit(1);
}});
"""

    result = subprocess.run([node, "-e", script], cwd=ROOT, text=True, capture_output=True, check=False)

    assert result.returncode == 0, result.stderr


def test_shared_shell_sanitizes_dashboard_navigation_targets() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is required for static shell smoke test")

    script = f"""
const fs = require("fs");
const vm = require("vm");

const source = fs.readFileSync({json.dumps(str(STATIC / "shared" / "shell.js"))}, "utf8");
const context = {{
  console,
  document: {{
    addEventListener() {{}},
    querySelectorAll() {{ return []; }},
  }},
  window: {{ location: {{ href: "" }} }},
}};
context.window.document = context.document;
vm.createContext(context);
vm.runInContext(source, context);

const shell = context.window.ContentFactoryShell;
const locationRef = {{ href: "" }};
if (shell.panelUrl("generator/panel.html") !== "/static/generator/panel.html") throw new Error("valid panel rejected");
if (shell.panelUrl("../secret.html") !== "") throw new Error("path traversal accepted");
if (shell.panelUrl("https://example.com/panel.html") !== "") throw new Error("external URL accepted");
if (!shell.navigateToPanel("checker/panel.html", locationRef)) throw new Error("navigation failed");
if (locationRef.href !== "/static/checker/panel.html") throw new Error("unexpected target " + locationRef.href);
"""

    result = subprocess.run([node, "-e", script], cwd=ROOT, text=True, capture_output=True, check=False)

    assert result.returncode == 0, result.stderr


def test_dashboard_navigation_remains_manifest_driven() -> None:
    client = TestClient(create_app())

    dashboard = client.get("/")
    modules = client.get("/api/modules").json()

    assert dashboard.status_code == 200
    assert '<script src="/static/shared/shell.js"></script>' in dashboard.text
    assert 'document.addEventListener("click"' not in dashboard.text
    for module in modules:
        if module["dashboard_tile"]:
            assert f'data-panel="{module["ui_panel"]}"' in dashboard.text


def test_generator_checker_translator_share_markdown_renderer() -> None:
    client = TestClient(create_app())
    shared_renderer = client.get("/static/shared/markdown.js")

    assert shared_renderer.status_code == 200
    assert "cdn.jsdelivr.net/npm/mermaid" in shared_renderer.text
    assert "vendor/mermaid" not in shared_renderer.text
    assert "mermaid.min.js" in shared_renderer.text

    for panel in ("generator", "checker", "translator"):
        response = client.get(f"/static/{panel}/panel.html")

        assert response.status_code == 200
        assert '<script src="/static/shared/markdown.js"></script>' in response.text
        assert "vendor/mermaid" not in response.text
        assert "mermaid.min.js" not in response.text
