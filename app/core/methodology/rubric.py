"""Rubric serialization shared by generator, checker and gate."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.core.methodology.rules import RuleIssue


def rule_issues_to_rubric(issues: Iterable[RuleIssue]) -> dict[str, Any]:
    """Serialize deterministic skill issues into MethodologyGate rubric_json."""

    items = [issue.model_dump(mode="json") for issue in issues]
    hard = [item for item in items if item.get("severity") == "hard"]
    soft = [item for item in items if item.get("severity") == "soft"]
    return {
        "issues": items,
        "passed": not hard,
        "hard_count": len(hard),
        "soft_count": len(soft),
        "skills": sorted({str(item.get("skill_id")) for item in items if item.get("skill_id")}),
    }
