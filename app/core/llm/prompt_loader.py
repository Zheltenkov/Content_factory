"""Versioned markdown prompt loader for app/core/llm/prompts/<area>/<name>@v1.md."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

PROMPTS_ROOT = Path(__file__).resolve().parent / "prompts"
_SAFE_PART = re.compile(r"^[A-Za-z0-9_.-]+$")
_CACHE: dict[Path, "PromptTemplate"] = {}


class PromptNotFoundError(FileNotFoundError):
    """Raised when a versioned prompt markdown file is absent."""


@dataclass(frozen=True)
class PromptTemplate:
    area: str
    name: str
    version: str
    path: Path
    text: str
    prompt_hash: str

    def render(self, **values: object) -> str:
        """Render simple {{ key }} placeholders with deterministic values."""
        rendered = self.text
        for key, value in values.items():
            rendered = re.sub(r"\{\{\s*" + re.escape(key) + r"\s*\}\}", str(value), rendered)
        return rendered


def load_prompt(area: str, name: str, version: str = "v1", *, root: Path | None = None) -> PromptTemplate:
    """Load a versioned markdown prompt by area/name/version."""
    for part in (area, name, version):
        if not _SAFE_PART.match(part):
            raise ValueError(f"Unsafe prompt path component: {part!r}")
    prompt_root = root or PROMPTS_ROOT
    path = (prompt_root / area / f"{name}@{version}.md").resolve()
    if path in _CACHE:
        return _CACHE[path]
    if not path.exists():
        raise PromptNotFoundError(f"Prompt not found: {path}")
    text = path.read_text(encoding="utf-8")
    template = PromptTemplate(
        area=area,
        name=name,
        version=version,
        path=path,
        text=text,
        prompt_hash=hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
    )
    _CACHE[path] = template
    return template
