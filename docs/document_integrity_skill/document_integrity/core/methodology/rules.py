"""core/methodology/rules.py — контракт методического слоя (см. SKILLS_ARCHITECTURE.md §3.3, §6.1)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Severity = Literal["hard", "soft"]


@dataclass
class RuleIssue:
    skill_id: str
    code: str
    severity: Severity
    message: str
    evidence: dict = field(default_factory=dict)


@dataclass
class DocImage:
    path: str
    width: int
    height: int
    size_bytes: int
    format: str
    dpi: int | None = None
    is_vector: bool = False


@dataclass
class GeneratedDoc:
    markdown: str
    images: list[DocImage] = field(default_factory=list)
    project_id: str | None = None      # каноничный id проекта; document_integrity сверяет с ним N.5
