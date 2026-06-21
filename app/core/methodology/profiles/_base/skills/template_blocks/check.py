"""Verbatim template block guard from regulation 3.2.3."""

from __future__ import annotations

import re
from typing import Any

from app.core.methodology.rules import GeneratedDoc, RuleIssue

SID = "template_blocks"


def _issue(code: str, message: str, evidence: dict[str, Any]) -> RuleIssue:
    return RuleIssue(SID, f"{SID}.{code}", "hard", message, evidence)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _active(doc: GeneratedDoc, params: dict) -> bool:
    if doc.metadata.get(params["require_metadata_flag"]):
        return True
    return doc.metadata.get("artifact_target") in params["required_artifact_targets"]


def _title_present(markdown: str, title: str) -> bool:
    pattern = rf"^\s*#+\s*{re.escape(title)}\s*$"
    return bool(re.search(pattern, markdown, flags=re.IGNORECASE | re.MULTILINE))


def check(doc: GeneratedDoc, params: dict) -> list[RuleIssue]:
    if not _active(doc, params):
        return []

    markdown = doc.markdown or ""
    normalized = _norm(markdown)
    issues: list[RuleIssue] = []

    for block_id, block in params["blocks"].items():
        expected = str(block["text"]).strip()
        if _norm(expected) in normalized:
            continue
        title = str(block["title"])
        code = "changed" if _title_present(markdown, title) else "missing"
        message = "Шаблонный блок изменён." if code == "changed" else "Шаблонный блок отсутствует."
        issues.append(_issue(code, message, {"block_id": block_id, "title": title}))

    return issues
