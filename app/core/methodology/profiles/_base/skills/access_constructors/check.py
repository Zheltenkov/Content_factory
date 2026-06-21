"""access_constructors — producer for project unlock policy from regulation 3.1.2."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.core.methodology.rules import GeneratedDoc, RuleIssue


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable) and not isinstance(value, dict):
        return list(value)
    return [value]


def _first(project: dict, fields: list[str]) -> Any:
    for field in fields:
        value = project.get(field)
        if value not in (None, "", []):
            return value
    return None


def _project_id(project: Any, params: dict) -> str:
    if isinstance(project, dict):
        value = _first(project, params["id_fields"])
        if value:
            return str(value)
    return str(project)


def _dependencies(project: Any, params: dict) -> list[str]:
    if not isinstance(project, dict):
        return []
    out: list[str] = []
    for field in params["dependency_fields"]:
        out.extend(str(item) for item in _as_list(project.get(field)) if str(item).strip())
    return list(dict.fromkeys(out))


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "да", "required", "обязателен"}
    return bool(value)


def _small_group(project: Any, ctx: dict, params: dict) -> bool:
    values = []
    if isinstance(project, dict):
        values.extend(project.get(field) for field in params["group_size_fields"])
    values.extend(ctx.get(field) for field in params["group_size_fields"])
    values.extend(ctx.get(f"curriculum.{field}") for field in params["group_size_fields"])
    for value in values:
        try:
            return int(value) <= int(params["small_group_max"])
        except (TypeError, ValueError):
            continue
    return False


def _relaxed(project: Any, ctx: dict, params: dict) -> bool:
    values = []
    if isinstance(project, dict):
        values.extend(project.get(field) for field in params["customer_preference_fields"])
    values.extend(ctx.get(field) for field in params["customer_preference_fields"])
    values.extend(ctx.get(f"curriculum.{field}") for field in params["customer_preference_fields"])
    text = " ".join(str(value).lower() for value in values if value)
    return any(marker.lower() in text for marker in params["relaxed_markers"])


def _has_exam(project: Any, params: dict) -> bool:
    if not isinstance(project, dict):
        return False
    return any(_truthy(project.get(field)) for field in params["exam_fields"])


def _policy(project: Any, ctx: dict, params: dict, known: set[str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    project_id = _project_id(project, params)
    deps = _dependencies(project, params)
    issues = [
        {"code": "access_constructors.unknown_dependency", "project_id": project_id, "dependency": dep}
        for dep in deps
        if dep not in known
    ]
    if _has_exam(project, params):
        mode = params["modes"]["after_exam"]
        reason = "exam_gate"
    elif deps:
        mode = params["modes"]["sequential"]
        reason = "project_dependencies"
    elif _relaxed(project, ctx, params):
        mode = params["modes"]["parallel"]
        reason = "customer_preference"
    elif _small_group(project, ctx, params):
        mode = params["modes"]["after_review"]
        reason = "small_group"
    else:
        mode = params["modes"]["parallel"]
        reason = "no_blocking_dependencies"
    return {"project_id": project_id, "mode": mode, "depends_on": deps, "reason": reason}, issues


def prepare(ctx: dict, params: dict) -> dict:
    projects = ctx.get("curriculum.projects", [])
    if not projects:
        return {}
    known = {_project_id(project, params) for project in projects}
    policies, issues = [], []
    for project in projects:
        policy, project_issues = _policy(project, ctx, params, known)
        policies.append(policy)
        issues.extend(project_issues)
    return {"curriculum.access_policy": policies, "curriculum.access_issues": issues}


def check(doc: GeneratedDoc, params: dict) -> list[RuleIssue]:
    return []
