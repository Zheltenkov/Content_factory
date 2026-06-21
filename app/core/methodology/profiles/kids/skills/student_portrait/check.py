"""Student portrait and SJM guard for kids profile regulation 3.1.3."""

from __future__ import annotations

from app.core.methodology.profiles.kids.skills._shared import contains_any, doc_text, issue
from app.core.methodology.rules import GeneratedDoc, RuleIssue

SID = "student_portrait"


def _portrait_has(doc: GeneratedDoc, group: str, markers: list[str], text: str) -> bool:
    portrait = doc.metadata.get("student_portrait")
    if isinstance(portrait, dict) and portrait.get(group):
        return True
    return contains_any(text, markers)


def check(doc: GeneratedDoc, params: dict) -> list[RuleIssue]:
    text = doc_text(doc)
    issues: list[RuleIssue] = []

    for group, markers in params["portrait_markers"].items():
        if not _portrait_has(doc, group, markers, text):
            issues.append(
                issue(
                    SID,
                    "portrait_part_missing",
                    "soft",
                    "Портрет ученика на выходе должен покрывать ЗУН и софт-скиллы.",
                    {"part": group, "markers": markers},
                )
            )

    if params.get("require_sjm") and not (doc.metadata.get("sjm") or contains_any(text, params["sjm_markers"])):
        issues.append(
            issue(
                SID,
                "sjm_missing",
                "soft",
                "Для основной программы и интенсива нужна Student Journey Map.",
                {"markers": params["sjm_markers"]},
            )
        )
    return issues
