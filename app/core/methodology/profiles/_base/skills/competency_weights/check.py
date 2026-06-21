"""competency_weights — producer. prepare() на curriculum.planner пишет веса в контекст;
check() — инвариант суммы. Генератор веса ЧИТАЕТ из контекста, скилл повторно не запускает."""
from __future__ import annotations
from app.core.methodology.rules import GeneratedDoc, RuleIssue
def prepare(ctx: dict, params: dict) -> dict:
    projects = ctx.get("curriculum.projects", [])
    if not projects:
        return {}
    per = round(params["weight_total"] / len(projects))
    return {"curriculum.competency_weights": {p: per for p in projects}}
def check(doc: GeneratedDoc, params: dict) -> list[RuleIssue]:
    return []
