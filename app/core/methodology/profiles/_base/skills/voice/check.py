"""Soft style guard for voice requirements from regulation 3.2.4."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from app.core.methodology.rules import GeneratedDoc, RuleIssue

SID = "voice"


def _issue(code: str, message: str, evidence: dict[str, Any]) -> RuleIssue:
    return RuleIssue(SID, f"{SID}.{code}", "soft", message, evidence)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _term_hits(text: str, terms: Iterable[str]) -> list[str]:
    hits: list[str] = []
    for term in terms:
        needle = _normalize(str(term))
        if needle and needle in text:
            hits.append(str(term))
    return hits


def _pattern_hits(text: str, patterns: Iterable[str]) -> list[str]:
    hits: list[str] = []
    for pattern in patterns:
        if re.search(str(pattern), text, flags=re.IGNORECASE):
            hits.append(str(pattern))
    return hits


def check(doc: GeneratedDoc, params: dict) -> list[RuleIssue]:
    text = doc.markdown or ""
    normalized = _normalize(text)
    issues: list[RuleIssue] = []

    bureaucratic = _term_hits(normalized, params.get("bureaucratic_terms", []))
    if len(bureaucratic) > params["max_bureaucratic_hits"]:
        issues.append(
            _issue(
                "bureaucratic",
                "Текст перегружен канцеляритом; перепиши проще и ближе к p2p-тону.",
                {"terms": bureaucratic},
            )
        )

    placeholders = _term_hits(normalized, params.get("placeholder_terms", []))
    placeholders.extend(_pattern_hits(text, params.get("placeholder_patterns", [])))
    if placeholders:
        issues.append(
            _issue(
                "placeholder",
                "В тексте остались шаблонные болванки или незаполненные плейсхолдеры.",
                {"markers": placeholders},
            )
        )

    return issues
