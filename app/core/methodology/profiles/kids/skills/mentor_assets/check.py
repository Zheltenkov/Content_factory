"""Mentor asset completeness guard for kids profile regulation 3.1.3."""

from __future__ import annotations

from app.core.methodology.profiles.kids.skills._shared import contains_any, doc_text, issue
from app.core.methodology.rules import GeneratedDoc, RuleIssue

SID = "mentor_assets"


def check(doc: GeneratedDoc, params: dict) -> list[RuleIssue]:
    text = doc_text(doc)
    issues: list[RuleIssue] = []

    for asset_id, terms in params["required_assets"].items():
        if not contains_any(text, terms):
            issues.append(
                issue(
                    SID,
                    "missing_asset",
                    "soft",
                    "Для детской программы не хватает обязательного материала наставника.",
                    {"asset": asset_id, "terms": terms},
                )
            )

    if params.get("require_mentor_portrait") and not (
        doc.metadata.get("mentor_portrait") or contains_any(text, ["портрет наставника", "роль наставника"])
    ):
        issues.append(
            issue(
                SID,
                "mentor_portrait_missing",
                "soft",
                "Не зафиксирован портрет наставника для детской программы.",
                {},
            )
        )
    return issues
