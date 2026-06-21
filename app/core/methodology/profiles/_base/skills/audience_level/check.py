"""audience_level — producer for entry frontier from regulation 3.1.1."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.core.methodology.rules import GeneratedDoc, RuleIssue


EMPTY_MARKERS = {"", "none", "null", "empty", "[]", "новичок", "бассейн", "pool"}


def _as_items(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, str):
        return [] if value.strip().lower() in EMPTY_MARKERS else [value]
    if isinstance(value, Iterable) and not isinstance(value, dict):
        return list(value)
    return [value]


def _competency_id(item: Any) -> str | None:
    if isinstance(item, dict):
        for field in ("competency_id", "id", "tmp_id", "skill_id", "name", "title"):
            value = item.get(field)
            if value:
                return str(value)
        return None
    text = str(item).strip()
    return text or None


def _dedupe(items: Iterable[Any]) -> list[str]:
    seen: dict[str, None] = {}
    for item in items:
        if cid := _competency_id(item):
            seen.setdefault(cid, None)
    return list(seen)


def _from_previous_branches(ctx: dict, params: dict) -> list[str]:
    collected: list[Any] = []
    for branch in _as_items(ctx.get("curriculum.previous_branches") or ctx.get("previous_branches")):
        if isinstance(branch, dict):
            for field in params["previous_fields"]:
                collected.extend(_as_items(branch.get(field)))
        else:
            collected.append(branch)
    direct = ctx.get("curriculum.previous_competencies") or ctx.get("previous_competencies")
    collected.extend(_as_items(direct))
    return _dedupe(collected)


def _level_source(ctx: dict, params: dict, assumed_known: list[str]) -> str:
    raw = ctx.get("curriculum.level_source") or ctx.get("level_source") or params["default_source"]
    normalized = str(raw).lower()
    if normalized in {"branch", "branch_of_branch", "next_level", "следующий"}:
        return "branch_of_branch"
    if assumed_known:
        return "branch_of_branch"
    return "pool"


def prepare(ctx: dict, params: dict) -> dict:
    explicit = _dedupe(_as_items(ctx.get("curriculum.assumed_known") or ctx.get("assumed_known") or params["assumed_known"]))
    previous = _from_previous_branches(ctx, params)
    assumed_known = _dedupe([*explicit, *previous])
    source = _level_source(ctx, params, assumed_known)

    return {
        "curriculum.assumed_known": assumed_known if source == "branch_of_branch" else explicit,
        "curriculum.experienced_share": float(params["experienced_share"]),
        "curriculum.level_source": source,
        "curriculum.audience_level": {
            "assumed_known": assumed_known if source == "branch_of_branch" else explicit,
            "experienced_share": float(params["experienced_share"]),
            "level_source": source,
        },
    }


def check(doc: GeneratedDoc, params: dict) -> list[RuleIssue]:
    return []
