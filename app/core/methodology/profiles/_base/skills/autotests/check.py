"""autotests — producer for automated testing policy from regulation 3.7."""

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


def _project_id(project: Any, params: dict) -> str:
    if isinstance(project, dict):
        for field in params["id_fields"]:
            if project.get(field):
                return str(project[field])
    return str(project)


def _first(project: dict, fields: list[str]) -> Any:
    for field in fields:
        value = project.get(field)
        if value:
            return value
    return None


def _tokens(value: Any) -> set[str]:
    return {str(item).lower().replace(" ", "") for item in _as_list(value) if str(item).strip()}


def _kind(project: Any, params: dict) -> str:
    if not isinstance(project, dict):
        return "technical"
    explicit = _tokens(_first(project, params["type_fields"]))
    tags = _tokens(project.get("tags"))
    tokens = explicit | tags
    if tokens & set(params["theoretical_types"]):
        return "theoretical"
    if tokens & set(params["technical_types"]):
        return "technical"
    return "technical" if _tokens(_first(project, params["language_fields"])) else "theoretical"


def _languages(project: Any, params: dict) -> list[str]:
    if not isinstance(project, dict):
        return []
    raw = _first(project, params["language_fields"])
    return [str(item).lower().replace(" ", "") for item in _as_list(raw) if str(item).strip()]


def _policy(project: Any, params: dict) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    project_id = _project_id(project, params)
    kind = _kind(project, params)
    languages = _languages(project, params)
    issues: list[dict[str, Any]] = []

    if kind == "theoretical":
        return (
            {
                "project_id": project_id,
                "required": False,
                "verification": "checklist",
                "checklist": params["checklist_mode"],
            },
            issues,
        )

    images = params["docker_images"]
    supported = [lang for lang in languages if lang in images]
    unsupported = [lang for lang in languages if lang not in images]
    if unsupported:
        issues.append({"code": "autotests.unsupported_language", "project_id": project_id, "languages": unsupported})
    image = images[supported[0]] if supported else params["default_docker_image"]
    return (
        {
            "project_id": project_id,
            "required": True,
            "verification": "autotests",
            "docker_image": image,
            "languages": languages,
            "hidden_artifacts": ["tests/", "ci-scripts/", "check-list.yml"],
        },
        issues,
    )


def prepare(ctx: dict, params: dict) -> dict:
    projects = ctx.get("curriculum.projects", [])
    if not projects:
        return {}
    policies, issues = [], []
    for project in projects:
        policy, project_issues = _policy(project, params)
        policies.append(policy)
        issues.extend(project_issues)
    return {"curriculum.autotest_policy": policies, "curriculum.autotest_issues": issues}


def check(doc: GeneratedDoc, params: dict) -> list[RuleIssue]:
    return []
