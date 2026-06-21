"""Program type guard for kids profile regulation 3.1.3."""

from __future__ import annotations

from app.core.methodology.profiles.kids.skills._shared import contains_any, doc_text, issue
from app.core.methodology.rules import GeneratedDoc, RuleIssue

SID = "program_types"


def check(doc: GeneratedDoc, params: dict) -> list[RuleIssue]:
    kind = str(doc.metadata.get("program_type") or params.get("kind") or "")
    expected_model = params["content_models"].get(kind)
    actual_model = doc.metadata.get("content_model") or expected_model
    text = doc_text(doc)
    issues: list[RuleIssue] = []

    if kind not in params["allowed"]:
        issues.append(issue(SID, "unknown", "soft", "Неизвестный вид детской программы.", {"program_type": kind}))
        return issues
    if actual_model != expected_model:
        issues.append(
            issue(
                SID,
                "content_model_mismatch",
                "soft",
                "Вид программы не соответствует выбранной content_model.",
                {"program_type": kind, "expected": expected_model, "actual": actual_model},
            )
        )

    markers = params["master_markers"] if kind == "master_class" else params["course_markers"]
    if not contains_any(text, markers):
        issues.append(
            issue(
                SID,
                "structure_marker_missing",
                "soft",
                "В описании не зафиксирована структура выбранного вида детской программы.",
                {"program_type": kind, "expected_markers": markers},
            )
        )
    return issues
