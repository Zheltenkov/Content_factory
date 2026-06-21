"""workload_planning — producer for deterministic workload formulas (regulation 3.1.3)."""

from __future__ import annotations

from typing import Any

from app.core.methodology.rules import GeneratedDoc, RuleIssue


def _first(project: Any, fields: list[str]) -> Any:
    if isinstance(project, dict):
        for field in fields:
            value = project.get(field)
            if value is not None:
                return value
    return None


def _project_id(project: Any, params: dict) -> str:
    value = _first(project, params["id_fields"])
    return str(value) if value else str(project)


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: float) -> int:
    return int(round(value))


def _expected(hours: float, params: dict) -> dict[str, int]:
    days = _int(hours * float(params["days_index"])) + int(params["review_days"])
    return {
        "workload_hours": _int(hours),
        "calendar_days": days,
        "xp": _int(hours * float(params["xp_per_hour"])),
        "reviews_required": max(int(params["reviews_per_project"]), int(params["min_reviews"])),
    }


def _p2p_minutes(project: Any, params: dict) -> int:
    raw = _first(project, params["difficulty_fields"])
    value = params["p2p_minutes_by_difficulty"].get(str(raw).lower()) if raw is not None else None
    minutes = int(value or params["p2p_minutes_default"])
    step = int(params["p2p_minutes_step"])
    return max(step, round(minutes / step) * step)


def _actual(project: Any, fields: list[str]) -> int | None:
    value = _number(_first(project, fields))
    return _int(value) if value is not None else None


def _issues(project_id: str, hours: float | None, plan: dict[str, int], project: Any, params: dict) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    low, high = params["hours_band"]
    if hours is None:
        issues.append({"code": "workload_planning.hours_missing", "project_id": project_id})
        return issues
    if hours < low or hours > high:
        issues.append({"code": "workload_planning.hours_out_of_band", "project_id": project_id, "hours": hours, "band": params["hours_band"]})
    checks = {
        "calendar_days": params["calendar_days_fields"],
        "xp": params["xp_fields"],
        "reviews_required": params["reviews_fields"],
    }
    for key, fields in checks.items():
        actual = _actual(project, fields)
        if actual is not None and actual != plan[key]:
            issues.append({"code": f"workload_planning.{key}_mismatch", "project_id": project_id, "actual": actual, "expected": plan[key]})
    return issues


def prepare(ctx: dict, params: dict) -> dict:
    projects = ctx.get("curriculum.projects", [])
    if not projects:
        return {}

    plans, issues = [], []
    for project in projects:
        project_id = _project_id(project, params)
        hours = _number(_first(project, params["hours_fields"]))
        plan = _expected(hours or 0, params)
        plan["project_id"] = project_id
        plan["p2p_minutes"] = _p2p_minutes(project, params)
        plans.append(plan)
        issues.extend(_issues(project_id, hours, plan, project, params))
    return {"curriculum.workload_plan": plans, "curriculum.workload_issues": issues}


def check(doc: GeneratedDoc, params: dict) -> list[RuleIssue]:
    return []
