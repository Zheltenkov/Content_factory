"""Small deterministic helpers for kids overlay methodology skills."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from app.core.methodology.rules import GeneratedDoc, RuleIssue


def issue(skill_id: str, code: str, severity: str, message: str, evidence: dict[str, Any] | None = None) -> RuleIssue:
    return RuleIssue(skill_id, f"{skill_id}.{code}", severity, message, evidence or {})


def norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value).lower()).strip()


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple | set):
        return list(value)
    return [value]


def doc_text(doc: GeneratedDoc) -> str:
    chunks: list[str] = [doc.markdown or ""]
    for artifact in doc.artifacts:
        chunks.extend(str(v) for v in artifact.metadata.values() if isinstance(v, str))
        chunks.extend(str(v) for v in (artifact.kind, artifact.path, artifact.target, artifact.uri) if v)
    chunks.extend(str(v) for v in doc.metadata.values() if isinstance(v, str))
    return norm("\n".join(chunks))


def contains_any(text: str, terms: Iterable[Any]) -> bool:
    return any(norm(term) in text for term in terms if norm(term))


def metadata_list(doc: GeneratedDoc, key: str) -> list[Any]:
    value = doc.metadata.get(key)
    if isinstance(value, str):
        return [part.strip() for part in re.split(r"[,;]", value) if part.strip()]
    return as_list(value)
