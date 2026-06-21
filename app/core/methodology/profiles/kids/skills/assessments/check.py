"""Assessment set guard for kids profile regulation 3.1.3."""

from __future__ import annotations

from app.core.methodology.profiles.kids.skills._shared import contains_any, doc_text, issue, metadata_list
from app.core.methodology.rules import GeneratedDoc, RuleIssue

SID = "assessments"


def check(doc: GeneratedDoc, params: dict) -> list[RuleIssue]:
    required = list(params.get("required") or [])
    if not required:
        return []

    text = doc_text(doc)
    declared = " ".join(str(item).lower() for item in metadata_list(doc, "assessments"))
    issues: list[RuleIssue] = []

    for assessment in required:
        aliases = params["aliases"].get(assessment, [assessment])
        if str(assessment).lower() not in declared and not contains_any(text, aliases):
            issues.append(
                issue(
                    SID,
                    "missing",
                    "hard",
                    "Не хватает обязательной формы контроля для выбранного вида детской программы.",
                    {"assessment": assessment, "aliases": aliases},
                )
            )
    return issues
