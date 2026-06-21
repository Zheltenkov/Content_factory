"""branch_structure — producer for curriculum project ordering (regulation 3.2.1)."""

from __future__ import annotations

from typing import Any

from app.core.methodology.rules import GeneratedDoc, RuleIssue


def _project_id(project: Any, params: dict) -> str:
    if isinstance(project, dict):
        for field in params["id_fields"]:
            value = project.get(field)
            if value:
                return str(value)
    return str(project)


def _rank(project: Any, params: dict, fallback: int) -> int:
    if not isinstance(project, dict):
        return fallback
    order = {str(name).lower(): idx for idx, name in enumerate(params["difficulty_order"])}
    for field in params["difficulty_fields"]:
        raw = project.get(field)
        if raw is not None:
            return order.get(str(raw).lower(), fallback)
    return fallback


def _diagnostics(records: list[dict[str, Any]], params: dict) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for prev, current in zip(records, records[1:], strict=False):
        if current["rank"] < prev["rank"]:
            issues.append(
                {
                    "code": "branch_structure.rank_drop",
                    "message": "Проекты идут не от простого к сложному.",
                    "from": prev["project_id"],
                    "to": current["project_id"],
                }
            )
        if current["rank"] - prev["rank"] > params["max_rank_jump"]:
            issues.append(
                {
                    "code": "branch_structure.rank_jump",
                    "message": "Между соседними проектами есть резкий скачок сложности.",
                    "from": prev["project_id"],
                    "to": current["project_id"],
                }
            )
    return issues


def prepare(ctx: dict, params: dict) -> dict:
    projects = ctx.get("curriculum.projects", [])
    if not projects:
        return {}

    records = [
        {
            "project_id": _project_id(project, params),
            "rank": _rank(project, params, index),
            "original_index": index,
            "project": project,
        }
        for index, project in enumerate(projects)
    ]
    ordered = sorted(records, key=lambda item: (item["rank"], item["original_index"]))
    issues = _diagnostics(records, params)

    return {
        "curriculum.branch_order": [item["project_id"] for item in ordered],
        "curriculum.branch_structure": {
            "ordered": [item["project_id"] for item in ordered],
            "original": [item["project_id"] for item in records],
            "issues": issues,
        },
    }


def check(doc: GeneratedDoc, params: dict) -> list[RuleIssue]:
    return []
