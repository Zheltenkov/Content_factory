"""Deterministic presentation helpers for intake skill-card adjudication.

Ported from Spravochnik ``viewer/app.py`` (``format_catalog_similarity`` /
``build_similarity_hint`` / ``build_candidate_recommended_action``). Pure functions —
they turn a resolved candidate's catalog-match score into the methodologist-facing
similarity, novelty, interpretation hint and recommended action shown on each card.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

Reasons = Iterable[str] | str | None


def format_catalog_similarity(score: float | int | None) -> tuple[str | None, str | None]:
    """Return UI-ready catalog similarity and novelty on a 0..100 scale."""
    if score is None:
        return None, None
    bounded = max(0.0, min(100.0, float(score)))
    return f"{bounded:.2f}", f"{100.0 - bounded:.2f}"


def _reason_set(reasons: Reasons) -> set[str]:
    if reasons is None:
        return set()
    if isinstance(reasons, str):
        parts = {part.strip() for part in re.split(r"[,;]\s*", reasons) if part.strip()}
        lowered = reasons.casefold()
        if "подозрительный match" in lowered or "catalog_match_suspicious" in lowered:
            parts.add("catalog_match_suspicious")
        return parts
    return {str(reason).strip() for reason in reasons if str(reason).strip()}


def _bounded(score: float | int | None) -> float | None:
    try:
        return None if score is None else max(0.0, min(100.0, float(score)))
    except (TypeError, ValueError):
        return None


def build_similarity_hint(
    score: float | int | None,
    resolution: str | None,
    has_nearest: bool,
    reasons: Reasons = None,
) -> dict[str, str]:
    """Explain how a catalog similarity score should be interpreted."""
    reason_set = _reason_set(reasons)
    if "catalog_match_suspicious" in reason_set:
        return {
            "label": "Подозрительный матч",
            "class": "weak",
            "recommendation": "Не используйте canonical skill автоматически. Нужно проверить смысл, группу и индикаторы.",
        }
    bounded = _bounded(score)
    if bounded is None:
        return {
            "label": "Нет данных",
            "class": "neutral",
            "recommendation": "Нет ближайшего совпадения для методологической сверки.",
        }
    normalized_resolution = str(resolution or "").casefold()
    if normalized_resolution in {"matched", "alias"}:
        return {
            "label": "Покрывает",
            "class": "strong",
            "recommendation": "Кандидат уже покрыт существующим skill. Используйте canonical skill в DAG.",
        }
    if normalized_resolution == "fuzzy" or bounded >= 90.0:
        return {
            "label": "Почти эквивалент",
            "class": "strong",
            "recommendation": "Лучше привязать к существующему skill, если индикаторы покрывают смысл брифа.",
        }
    if has_nearest and bounded >= 75.0:
        return {
            "label": "Частично похоже",
            "class": "medium",
            "recommendation": "Проверьте индикаторы ближайшего skill: если они покрывают требование, используйте привязку.",
        }
    if has_nearest:
        return {
            "label": "Слабое совпадение",
            "class": "weak",
            "recommendation": "Не привязывайте автоматически. Обычно это новый skill или кандидат на отклонение.",
        }
    return {
        "label": "Новое",
        "class": "neutral",
        "recommendation": "Похожего skill не найдено. Решение: добавить новый или отклонить как нерелевантный.",
    }


def build_candidate_recommended_action(
    score: float | int | None,
    resolution: str | None,
    has_nearest: bool,
    nearest_name: str | None = None,
    reasons: Reasons = None,
    decision: str | None = None,
) -> dict[str, str]:
    """Return the deterministic methodologist action for a resolved candidate."""
    normalized_decision = str(decision or "").casefold()
    normalized_resolution = str(resolution or "").casefold()
    reason_set = _reason_set(reasons)
    target = str(nearest_name or "").strip()
    bounded = _bounded(score)

    if normalized_decision == "accepted":
        return {"code": "done", "label": "Уже принято", "target": target, "detail": "Кандидат используется в каталоге/DAG."}
    if normalized_decision == "rejected":
        return {"code": "rejected", "label": "Отклонено", "target": "", "detail": "Кандидат не используется для покрытия брифа."}
    if "catalog_match_suspicious" in reason_set:
        return {
            "code": "check",
            "label": "Проверить match",
            "target": target,
            "detail": "Есть риск ложного совпадения: группа, смысл или coverage area конфликтуют.",
        }
    if has_nearest and normalized_resolution in {"matched", "alias", "fuzzy"}:
        return {
            "code": "link",
            "label": "Покрыть существующим",
            "target": target,
            "detail": "Проверьте индикаторы nearest skill и привяжите, если смысл закрыт.",
        }
    if has_nearest and bounded is not None and bounded >= 75.0:
        return {
            "code": "link",
            "label": "Вероятно покрыть существующим",
            "target": target,
            "detail": "Похожесть высокая: сначала проверьте ближайший skill, потом решайте про новый.",
        }
    if normalized_resolution == "new" or not has_nearest:
        return {
            "code": "create",
            "label": "Создать новый skill",
            "target": "",
            "detail": "Похожего покрытия нет или оно слишком слабое.",
        }
    return {"code": "review", "label": "Оставить на review", "target": target, "detail": "Недостаточно данных для безопасного автодействия."}
