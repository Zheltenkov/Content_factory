"""competency_weights — producer for competency percentages from regulation 3.1.2."""

from __future__ import annotations

from collections.abc import Iterable
from math import floor
from typing import Any

from app.core.methodology.rules import GeneratedDoc, RuleIssue


ID_FIELDS = ("competency_id", "id", "tmp_id", "skill_id", "name", "title")
PROJECT_ID_FIELDS = ("id", "project_id", "title", "name")
COMPETENCY_FIELDS = ("competency_refs", "competencies", "skills", "skill_ids")


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable) and not isinstance(value, dict):
        return list(value)
    return [value]


def _id(item: Any, fields: tuple[str, ...] = ID_FIELDS) -> str | None:
    if isinstance(item, dict):
        for field in fields:
            if item.get(field):
                return str(item[field])
        return None
    text = str(item).strip()
    return text or None


def _project_id(project: Any) -> str:
    return _id(project, PROJECT_ID_FIELDS) or str(project)


def _competency_ids(project: Any) -> list[str]:
    if isinstance(project, dict):
        for field in COMPETENCY_FIELDS:
            values = [_id(item) for item in _as_list(project.get(field))]
            ids = [value for value in values if value]
            if ids:
                return ids
    return [_project_id(project)]


def _project_score(project: Any) -> float:
    if isinstance(project, dict):
        for field in ("workload_hours", "hours", "xp"):
            if project.get(field) is not None:
                try:
                    return max(float(project[field]), 0.0) or 1.0
                except (TypeError, ValueError):
                    return 1.0
    return 1.0


def _reference_ids(ctx: dict) -> set[str]:
    refs = ctx.get("reference.competencies") or ctx.get("competencies") or []
    return {cid for item in _as_list(refs) if (cid := _id(item))}


def _percentages(scores: dict[str, float], total: int) -> dict[str, int]:
    score_total = sum(scores.values())
    if score_total <= 0:
        return {}
    raw = {key: value * total / score_total for key, value in scores.items()}
    weights = {key: floor(value) for key, value in raw.items()}
    remainder = total - sum(weights.values())
    order = sorted(raw, key=lambda key: (raw[key] - weights[key], raw[key]), reverse=True)
    for key in order[:remainder]:
        weights[key] += 1
    return weights


def prepare(ctx: dict, params: dict) -> dict:
    projects = ctx.get("curriculum.projects", [])
    if not projects:
        return {}

    scores: dict[str, float] = {}
    for project in projects:
        ids = _competency_ids(project)
        share = _project_score(project) / len(ids)
        for competency_id in ids:
            scores[competency_id] = scores.get(competency_id, 0.0) + share

    total = int(params["weight_total"])
    weights = _percentages(scores, total)
    references = _reference_ids(ctx)
    missing = sorted(set(weights) - references) if references else []
    issues = [{"code": "competency_weights.reference_missing", "competency_id": cid} for cid in missing]
    return {"curriculum.competency_weights": weights, "curriculum.competency_weight_issues": issues}


def check(doc: GeneratedDoc, params: dict) -> list[RuleIssue]:
    return []
