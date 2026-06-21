"""Stage T2.1.2: classify and split composite competency candidates."""

from __future__ import annotations

import re

from app.core.models import BLOOM_RANK, BloomLevel, Competency, CompetencyIndicator

CREATE_ACTION_RE = re.compile(r"\b(созда|разработ(к|а|ыва|ать|ает|ают|ал|али|ан)|спроект|постро|собир|контейнериз)", re.IGNORECASE)
ANALYZE_ACTION_RE = re.compile(r"\b(анализ|оцени|сравнив|выбира|проектир|моделир|диагност)", re.IGNORECASE)
APPLY_ACTION_RE = re.compile(
    r"\b(примен|использ|настро|настра|тестир|писа|обработ|депло|разверт|развёрт|логирован|мониторинг|интегрир)",
    re.IGNORECASE,
)
ACTION_NOUNS = {
    "анализ",
    "деплой",
    "диагностика",
    "логирование",
    "моделирование",
    "мониторинг",
    "написание",
    "настройка",
    "обработка",
    "проведение",
    "проектирование",
    "разработка",
    "тестирование",
}
ACTION_PREFIXES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^проектировать\s+(.+)$", re.IGNORECASE), "Проектирование"),
    (re.compile(r"^моделировать\s+(.+)$", re.IGNORECASE), "Моделирование"),
    (re.compile(r"^писать\s+(.+)$", re.IGNORECASE), "Написание"),
    (re.compile(r"^настраивать\s+(.+)$", re.IGNORECASE), "Настройка"),
    (re.compile(r"^тестировать\s+(.+)$", re.IGNORECASE), "Тестирование"),
    (re.compile(r"^работать\s+с\s+(.+)$", re.IGNORECASE), "Работа с"),
)
FRAGMENT_REPAIRS = {
    "автотесты pytest": "Разработка автотестов pytest",
    "безопасной обработкой токенов": "Обработка токенов",
    "ci/cd pipeline": "Настройка CI/CD pipeline",
    "очередями сообщений": "Работа с очередями сообщений",
    "бд": "Работа с БД",
    "деплоем сервиса": "Деплой сервиса",
    "диагностикой инцидентов": "Диагностика инцидентов",
    "code review": "Проведение code review",
    "финальный проект: backend-сервис с rest api": "Разработка backend-сервиса с REST API",
    "тестами": "Разработка тестов сервиса",
    "контейнеризацией": "Контейнеризация сервиса",
    "pipeline": "Настройка pipeline",
    "openapi": "Проектирование OpenAPI-контракта",
    "postgresql": "Работа с PostgreSQL",
}
OBJECT_REWRITES = {
    "docker окружение": "Docker-окружения",
    "sql-запросы": "SQL-запросов",
    "sql-схему": "SQL-схемы",
}


def run(competencies: list[Competency]) -> tuple[list[Competency], dict[str, object]]:
    out: list[Competency] = []
    split_count = 0
    non_skill_count = 0
    for item in competencies:
        if item.atomicity == "atomic":
            out.append(item)
            continue
        verdict = _verdict(item.canonical_name)
        if verdict == "non_skill":
            out.append(item.model_copy(update={"atomicity": "non_skill", "status": "needs_review"}))
            non_skill_count += 1
            continue
        if verdict == "composite":
            out.append(item.model_copy(update={"atomicity": "composite", "status": "superseded"}))
            children = _children(item)
            out.extend(children)
            split_count += len(children)
            continue
        out.append(item.model_copy(update={"atomicity": "atomic"}))
    return out, {"input_count": len(competencies), "output_count": len(out), "split_count": split_count, "non_skill_count": non_skill_count}


def _verdict(name: str) -> str:
    lowered = name.casefold()
    if re.search(r"^(основы|обзор|введение в)\b", lowered):
        return "non_skill"
    if _is_program_frame(lowered):
        return "non_skill"
    if "," in name or re.search(r"\s(и|или)\s", lowered) or len(name.split()) >= 8:
        return "composite"
    return "atomic"


def _children(parent: Competency) -> list[Competency]:
    parts = [part.strip(" .,-:;") for part in re.split(r",|\s+и\s+|\s+или\s+", parent.canonical_name) if part.strip(" .,-:;")]
    children: list[Competency] = []
    for index, part in enumerate(parts[:6], 1):
        name = _canonical_child_name(part)
        bloom = _bloom_for_text(f"{name} {part}", parent.bloom_level)
        children.append(
            Competency(
                competency_id=f"{parent.competency_id}.{index}",
                canonical_name=name,
                source_name=parent.canonical_name,
                group=parent.group,
                coverage_area=parent.coverage_area or parent.canonical_name,
                indicators=[CompetencyIndicator(text=f"{_indicator_prefix(bloom)}: {name}", bloom=bloom)],
                tools=parent.tools,
                evidence_ids=parent.evidence_ids,
                confidence=parent.confidence,
                atomicity="atomic",
                resolution=parent.resolution,
                status="accepted",
                metadata={**parent.metadata, "parent_competency_id": parent.competency_id},
            )
        )
    return children


def _canonical_child_name(part: str) -> str:
    cleaned = _strip_context(part)
    key = cleaned.casefold().replace("ё", "е")
    if key in FRAGMENT_REPAIRS:
        return FRAGMENT_REPAIRS[key]
    for pattern, noun in ACTION_PREFIXES:
        match = pattern.match(cleaned)
        if match:
            return _clean(f"{noun} {_rewrite_object(match.group(1))}")
    first, *rest = cleaned.split()
    if first.casefold().replace("ё", "е") in ACTION_NOUNS and rest:
        return _clean(f"{first[:1].upper() + first[1:]} {_rewrite_object(' '.join(rest))}")
    if _has_observable_action(cleaned):
        return cleaned[:1].upper() + cleaned[1:]
    return f"Работа с темой «{cleaned}»"


def _bloom_for_text(text: str, fallback: BloomLevel) -> BloomLevel:
    if CREATE_ACTION_RE.search(text):
        return "create"
    if ANALYZE_ACTION_RE.search(text):
        return "analyze"
    if APPLY_ACTION_RE.search(text) or _has_observable_action(text):
        return "apply"
    return fallback


def _indicator_prefix(bloom: BloomLevel) -> str:
    return "Применяет" if BLOOM_RANK[bloom] <= 3 else "Прорабатывает"


def _strip_context(text: str) -> str:
    cleaned = _clean(text)
    return re.sub(
        r"^(?:выпускник\s+должен|участник\s+должен|нужно\s+уметь|студент\s+должен)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )


def _rewrite_object(value: str) -> str:
    cleaned = _clean(value)
    return OBJECT_REWRITES.get(cleaned.casefold().replace("ё", "е"), cleaned)


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("‑", "-").strip(" \t\r\n.,;:"))


def _has_observable_action(text: str) -> bool:
    cleaned = _clean(text)
    if not cleaned:
        return False
    first = cleaned.split(" ", 1)[0].casefold().replace("ё", "е")
    explicit_work = bool(re.match(r"работа\s+с\s+(?!темой\b)", cleaned, flags=re.IGNORECASE))
    return first in ACTION_NOUNS or explicit_work or bool(CREATE_ACTION_RE.search(cleaned) or ANALYZE_ACTION_RE.search(cleaned) or APPLY_ACTION_RE.search(cleaned))


def _is_program_frame(lowered_name: str) -> bool:
    text = lowered_name.replace("ё", "е")
    has_schedule = bool(re.search(r"\b(недель|часов?\s+(?:в|/)\s+недел)\b", text))
    return has_schedule and bool(re.search(r"\b(программа|курс|обучени|учебн|работа\s+с\s+темой)\b", text))
