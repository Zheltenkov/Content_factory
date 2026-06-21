"""Lesson duration and project span guard for kids profile regulation 3.1.3."""

from __future__ import annotations

from app.core.methodology.profiles.kids.skills._shared import as_list, issue
from app.core.methodology.rules import GeneratedDoc, RuleIssue

SID = "lesson_structure"


def _ints(value: object) -> list[int]:
    out: list[int] = []
    for item in as_list(value):
        try:
            out.append(int(item))
        except (TypeError, ValueError):
            continue
    return out


def _in_range(values: list[int], bounds: list[int]) -> bool:
    if not values:
        return False
    lo, hi = min(bounds), max(bounds)
    return all(lo <= value <= hi for value in values)


def check(doc: GeneratedDoc, params: dict) -> list[RuleIssue]:
    issues: list[RuleIssue] = []
    expected_duration = params.get("duration_minutes")

    if expected_duration is not None:
        actual = doc.metadata.get("duration_minutes")
        if int(actual or 0) != int(expected_duration):
            issues.append(
                issue(
                    SID,
                    "duration",
                    "hard",
                    "Мастер-класс должен быть рассчитан на 90 минут.",
                    {"expected": expected_duration, "actual": actual},
                )
            )
        first_result = int(doc.metadata.get("first_result_minutes") or 0)
        if first_result and first_result > int(params["early_progress_minutes"]):
            issues.append(
                issue(
                    SID,
                    "late_first_result",
                    "hard",
                    "В мастер-классе ребёнок должен увидеть первый результат в первые 15-20 минут.",
                    {"max_minutes": params["early_progress_minutes"], "actual": first_result},
                )
            )
        return issues

    lesson_hours = _ints(doc.metadata.get("lesson_hours"))
    if not _in_range(lesson_hours, params["lesson_hours"]):
        issues.append(
            issue(
                SID,
                "lesson_hours",
                "hard",
                "Длительность занятия должна попадать в допустимый диапазон детской программы.",
                {"expected": params["lesson_hours"], "actual": lesson_hours},
            )
        )

    project_span = _ints(doc.metadata.get("project_span"))
    if not _in_range(project_span, params["project_span"]):
        issues.append(
            issue(
                SID,
                "project_span",
                "hard",
                "Проект должен укладываться в допустимое число занятий.",
                {"expected": params["project_span"], "actual": project_span},
            )
        )
    return issues
