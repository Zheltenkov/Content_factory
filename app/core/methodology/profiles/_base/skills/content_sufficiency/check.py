"""Deterministic theory/practice sufficiency checks."""

from __future__ import annotations

import re
from typing import Any

from app.core.methodology.rules import GeneratedDoc, RuleIssue

SID = "content_sufficiency"


def _issue(code: str, severity: str, message: str, **evidence: Any) -> RuleIssue:
    return RuleIssue(SID, f"{SID}.{code}", severity, message, evidence)


def check(doc: GeneratedDoc, params: dict) -> list[RuleIssue]:
    theory = _items(doc.metadata.get("theory_parts"))
    practice = _items(doc.metadata.get("practice_tasks"))
    if not theory and not practice:
        return []
    return [*_check_theory(theory, params), *_check_practice(practice, params)]


def _check_theory(parts: list[Any], params: dict) -> list[RuleIssue]:
    issues: list[RuleIssue] = []
    lo, hi = params["theory_parts_range"]
    if not lo <= len(parts) <= hi:
        issues.append(_issue("theory_parts_count", "hard", "Количество теоретических разделов вне допустимого диапазона.", count=len(parts), expected=[lo, hi]))
    words_lo, words_hi = params["theory_words_per_part"]
    words_hi = int(words_hi * float(params.get("theory_words_overflow_factor", 1)))
    for index, part in enumerate(parts, 1):
        title = str(_get(part, "title", "") or f"2.{index}")
        body = str(_get(part, "body", "") or "")
        words = int(_get(part, "word_count", 0) or _count_words(body))
        if words < words_lo or words > words_hi:
            issues.append(_issue("theory_part_length", "hard", "Длина теоретического раздела вне диапазона.", part=index, title=title, words=words, expected=[words_lo, words_hi]))
        if len(str(_get(part, "example", "") or "").strip()) < params["min_text_chars"]:
            issues.append(_issue("theory_example_missing", "hard", "В теоретическом разделе нет проверяемого примера.", part=index, title=title))
        if not _items(_get(part, "bridge_questions")):
            issues.append(_issue("theory_bridge_missing", "hard", "В теоретическом разделе нет вопросов к практике.", part=index, title=title))
        if not _items(_get(part, "definitions_found")) and not _has_definition(body):
            issues.append(_issue("theory_definitions_missing", "soft", "В теоретическом разделе не найдены явные определения терминов.", part=index, title=title))
        if not _items(_get(part, "covers_outcomes")):
            issues.append(_issue("theory_outcomes_missing", "soft", "Теоретический раздел не привязан к результатам обучения.", part=index, title=title))
    return issues


def _check_practice(tasks: list[Any], params: dict) -> list[RuleIssue]:
    issues: list[RuleIssue] = []
    lo, hi = params["practice_tasks_range"]
    if not lo <= len(tasks) <= hi:
        issues.append(_issue("practice_tasks_count", "hard", "Количество практических заданий вне допустимого диапазона.", count=len(tasks), expected=[lo, hi]))
    for index, task in enumerate(tasks, 1):
        title = str(_get(task, "title", "") or f"Задание {index}")
        _required_task_fields(task, index, title, issues, params)
        goal = str(_get(task, "goal", "") or "")
        if _banned_goal(goal):
            issues.append(_issue("practice_goal_passive", "hard", "Цель сформулирована как изучение вместо действия с результатом.", task=index, title=title))
        elif goal and not _active_goal(goal):
            issues.append(_issue("practice_goal_weak", "soft", "Цель не выглядит как активное действие с результатом.", task=index, title=title))
        approach = _items(_get(task, "approach_bullets"))
        a_lo, a_hi = params["approach_bullets_range"]
        words = _count_words(" ".join(map(str, approach)))
        if approach and not a_lo <= len(approach) <= a_hi:
            issues.append(_issue("practice_approach_shape", "hard", "В подходе неверное число пунктов.", task=index, title=title, count=len(approach), expected=[a_lo, a_hi]))
        if words > params["approach_words_max"]:
            issues.append(_issue("practice_approach_length", "hard", "Блок подхода слишком длинный.", task=index, title=title, words=words))
        criteria = [str(item).strip() for item in _items(_get(task, "p2p_criteria")) if str(item).strip()]
        if len(criteria) < params["p2p_criteria_min"]:
            issues.append(_issue("practice_p2p_missing", "hard", "Недостаточно критериев P2P-проверки.", task=index, title=title, count=len(criteria)))
        elif sum(_observable(item, params) for item in criteria) < params["p2p_observable_min"]:
            issues.append(_issue("practice_p2p_weak", "soft", "Критерии P2P выглядят слишком общими.", task=index, title=title))
        if not _items(_get(task, "covered_outcomes")):
            issues.append(_issue("practice_outcomes_missing", "soft", "Задание не привязано к результатам обучения.", task=index, title=title))
        if not _items(_get(task, "theory_support")):
            issues.append(_issue("practice_theory_support_missing", "soft", "Задание не ссылается на темы из теории.", task=index, title=title))
    return issues


def _required_task_fields(task: Any, index: int, title: str, issues: list[RuleIssue], params: dict) -> None:
    min_chars = params["min_text_chars"]
    checks = {
        "situation": ("practice_situation_missing", params["min_situation_chars"], "Нет рабочей ситуации с контекстом."),
        "input_data": ("practice_input_missing", min_chars, "Входные данные слишком короткие или неявные."),
        "goal": ("practice_goal_missing", min_chars, "Нет цели задания."),
        "expected_artifact": ("practice_artifact_missing", min_chars, "Ожидаемый результат слишком короткий или неявный."),
    }
    for field, (code, length, message) in checks.items():
        if len(str(_get(task, field, "") or "").strip()) < length:
            issues.append(_issue(code, "hard", message, task=index, title=title))
    artifact = str(_get(task, "expected_artifact", "") or "")
    location = str(_get(task, "artifact_location", "") or "")
    if artifact and not (_looks_like_path(artifact) or _looks_like_path(location)):
        issues.append(_issue("practice_artifact_location_missing", "hard", "Нет явного пути к артефакту.", task=index, title=title))
    if not str(_get(task, "constraints_or_risk", "") or "").strip():
        issues.append(_issue("practice_risk_missing", "soft", "Нет явного ограничения или риска.", task=index, title=title))


def _items(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list | tuple):
        return list(value)
    return [value]


def _get(item: Any, key: str, default: Any = None) -> Any:
    return item.get(key, default) if isinstance(item, dict) else getattr(item, key, default)


def _count_words(text: str) -> int:
    return len(re.findall(r"[A-Za-zА-Яа-яЁё0-9]+", text or ""))


def _has_definition(text: str) -> bool:
    return bool(re.search(r"\*\*[^*]{2,80}\*\*\s+[—-]\s+|\bэто\b|\bназывается\b", text or "", re.I))


def _looks_like_path(text: str) -> bool:
    return bool(re.search(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+\.[A-Za-z0-9]+", text or ""))


def _banned_goal(text: str) -> bool:
    return bool(re.search(r"\b(изучи|изучить|ознакомься|ознакомиться|посмотри|посмотреть|рассмотри|рассмотреть|пойми|понять)\b", text or "", re.I))


def _active_goal(text: str) -> bool:
    return bool(re.search(r"\b(разработ|созда|собер|опиш|спроект|подготов|провед|настро|проверь|сформир|проанализ|заполн|реализ)\w*", text or "", re.I))


def _observable(text: str, params: dict) -> bool:
    normalized = re.sub(r"\s+", " ", str(text).lower())
    return any(marker in normalized for marker in params["observable_markers"]) or bool(re.search(r"\b\d+\b", normalized))
