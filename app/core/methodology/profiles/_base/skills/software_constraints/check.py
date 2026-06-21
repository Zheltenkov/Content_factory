"""Software availability and licensing guard from regulation 3.1.2."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from app.core.methodology.rules import GeneratedDoc, RuleIssue

SID = "software_constraints"


def _issue(code: str, severity: str, message: str, evidence: dict[str, Any]) -> RuleIssue:
    return RuleIssue(SID, f"{SID}.{code}", severity, message, evidence)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _term_hits(text: str, terms: Iterable[str]) -> list[str]:
    hits: list[str] = []
    for term in terms:
        needle = str(term).lower()
        if needle and needle in text:
            hits.append(str(term))
    return hits


def _has_version(text: str, patterns: Iterable[str]) -> bool:
    return any(re.search(str(pattern), text, flags=re.IGNORECASE) for pattern in patterns)


def check(doc: GeneratedDoc, params: dict) -> list[RuleIssue]:
    text = doc.markdown or ""
    normalized = _normalize(text)
    issues: list[RuleIssue] = []

    for group, terms in params["hard_patterns"].items():
        hits = _term_hits(normalized, terms)
        if hits:
            issues.append(
                _issue(
                    group,
                    "hard",
                    "Описание ПО нарушает требования доступности, официального распространения или лицензирования.",
                    {"markers": hits},
                )
            )

    software_mentions = _term_hits(normalized, params["software_terms"])
    if software_mentions and not _has_version(text, params["version_patterns"]):
        issues.append(
            _issue(
                "version_missing",
                "soft",
                "Для используемого ПО или библиотек не указаны версии.",
                {"software_terms": software_mentions},
            )
        )

    required = _term_hits(normalized, params["required_markers"])
    if software_mentions and len(required) < len(params["required_markers"]):
        issues.append(
            _issue(
                "requirements_incomplete",
                "soft",
                "Описание зависимостей должно явно фиксировать официальный источник, доступность в России и лицензию.",
                {"found_markers": required},
            )
        )

    return issues
