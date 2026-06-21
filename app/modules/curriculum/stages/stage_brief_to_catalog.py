"""Stage T2.1.1: brief text -> normalized core competencies."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.llm.prompt_loader import load_prompt
from app.core.llm.structured import StructuredPrompt, complete_typed
from app.core.models import BLOOM_RANK, BloomLevel, Competency, CompetencyIndicator, EvidenceSource

SECTION_LABEL_RE = re.compile(
    r"^(наименование|идея|целевая аудитория|участники|результат|цель|задача|описание|требования|контекст)\s*[:\-]\s*",
    re.IGNORECASE,
)
ACTION_RE = re.compile(
    r"\b(анализ|проектир|моделир|разработ(к|а|ыва|ать|ает|ают|ал|али|ан)|настро|настра|тестир|провед|проведение|формулир|управл|оцен|созда|выбор|интеграц|писа|обработ|депло|диагност|логирован|мониторинг|контейнериз)",
    re.IGNORECASE,
)
CREATE_ACTION_RE = re.compile(r"\b(созда|разработ(к|а|ыва|ать|ает|ают|ал|али|ан)|спроект|постро|собир|контейнериз)", re.IGNORECASE)
ANALYZE_ACTION_RE = re.compile(r"\b(анализ|оцени|сравнив|выбира|проектир|моделир|диагност)", re.IGNORECASE)
APPLY_ACTION_RE = re.compile(
    r"\b(примен|использ|настро|настра|тестир|писа|обработ|депло|разверт|развёрт|логирован|мониторинг|интегрир)",
    re.IGNORECASE,
)
ACTION_NOUNS = {
    "анализ",
    "выбор",
    "диагностика",
    "логирование",
    "моделирование",
    "мониторинг",
    "написание",
    "настройка",
    "обработка",
    "проектирование",
    "разработка",
    "тестирование",
}
ACTION_PREFIXES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^проектировать\s+(.+)$", re.IGNORECASE), "Проектирование"),
    (re.compile(r"^моделировать\s+(.+)$", re.IGNORECASE), "Моделирование"),
    (re.compile(r"^писать\s+(.+)$", re.IGNORECASE), "Написание"),
    (re.compile(r"^настраивать\s+(.+)$", re.IGNORECASE), "Настройка"),
    (re.compile(r"^разработать\s+(.+)$", re.IGNORECASE), "Разработка"),
    (re.compile(r"^разрабатывать\s+(.+)$", re.IGNORECASE), "Разработка"),
    (re.compile(r"^тестировать\s+(.+)$", re.IGNORECASE), "Тестирование"),
    (re.compile(r"^работать\s+с\s+(.+)$", re.IGNORECASE), "Работа с"),
    (re.compile(r"^обрабатывать\s+(.+)$", re.IGNORECASE), "Обработка"),
    (re.compile(r"^диагностировать\s+(.+)$", re.IGNORECASE), "Диагностика"),
)
OBJECT_REWRITES = {
    "docker окружение": "Docker-окружения",
    "sql-запросы": "SQL-запросов",
    "sql-схему": "SQL-схемы",
}
TECH_TERMS = ("SQL", "PostgreSQL", "API", "REST", "OpenAPI", "CI/CD", "Git", "Docker", "pytest", "LLM", "MVP")


class BriefCatalogResult(BaseModel):
    """Typed output of the brief-to-catalog stage."""

    model_config = ConfigDict(extra="forbid")

    spec: dict[str, Any] = Field(default_factory=dict)
    evidence_sources: list[EvidenceSource] = Field(default_factory=list)
    competencies: list[Competency] = Field(default_factory=list)
    coverage_audit: dict[str, Any] = Field(default_factory=dict)


def run(brief: str, *, client: Any | None = None, use_llm: bool | None = None) -> BriefCatalogResult:
    """Extract a compact competency portrait from a text brief.

    The production path uses core.llm.structured. Offline mode keeps the legacy Spravochnik behavior of producing
    a deterministic draft from the brief itself, so tests and local runs do not depend on a provider.
    """
    should_call_llm = bool(client) if use_llm is None else use_llm
    if should_call_llm:
        prompt_text = load_prompt("curriculum", "brief_to_catalog", "v1").render(brief=brief)
        return complete_typed(
            StructuredPrompt(user=prompt_text),
            BriefCatalogResult,
            client=client,
            temperature=0,
        )
    return _offline_result(brief)


def _offline_result(brief: str) -> BriefCatalogResult:
    spec = _spec_from_brief(brief)
    topics = _topic_candidates(brief) or [str(spec.get("domain") or "Ключевые задачи программы")]
    competencies: list[Competency] = []
    for index, topic in enumerate(topics[:12], 1):
        name = _skill_name(topic)
        bloom = _bloom_for_text(topic)
        competencies.append(
            Competency(
                competency_id=f"C{index:02d}",
                canonical_name=name,
                source_name=topic,
                group=str(spec.get("domain") or "Общее"),
                coverage_area=topic,
                indicators=[CompetencyIndicator(text=_indicator_text(name, bloom), bloom=bloom)],
                tools=_tools(topic),
                confidence=0.72,
                atomicity="unknown",
                resolution="new",
                status="accepted",
                metadata={"source": "brief_offline", "order": index},
            )
        )
    return BriefCatalogResult(
        spec=spec,
        evidence_sources=[
            EvidenceSource(
                evidence_id="brief:source",
                claim="Компетенции извлечены из текста брифа.",
                source_type="other",
                snippet=brief[:500],
            )
        ],
        competencies=competencies,
        coverage_audit={"areas": topics[:12], "covered": len(competencies), "mode": "offline"},
    )


def _spec_from_brief(brief: str) -> dict[str, Any]:
    is_program = bool(re.search(r"\b(программа|курс|обучени|учебн|ветк|паспорт|тз)\b", brief.casefold().replace("ё", "е")))
    topics = _topic_candidates(brief)
    return {
        "artifact_type": "program_brief" if is_program else "learner_brief",
        "role": _match_or_default(brief, r"(?:роль|профиль|выпускник|специалист)\s*[:\-]\s*([^.\n;]{3,90})", "Выпускник программы"),
        "seniority": _match_or_default(brief, r"\b(junior\+?|middle|senior|lead|начинающ[а-я]+|базов[а-я]+)\b", "не указан"),
        "domain": topics[0][:120] if topics else "Домен из брифа",
        "must_include_areas": topics[:12],
        "sub_queries": [f"Навыки выпускника: {topic}" for topic in topics[:6]],
    }


def _topic_candidates(brief: str) -> list[str]:
    out: list[str] = []
    for chunk in re.split(r"[\n.;•\u2022]+", brief):
        text = SECTION_LABEL_RE.sub("", chunk).strip(" \t:-")
        text = re.sub(r"\s+", " ", text)
        if 12 <= len(text) <= 180 and not re.search(r"\b(email|http|www|телефон)\b", text.casefold()):
            out.append(text)
    return list(dict.fromkeys(out))


def _match_or_default(text: str, pattern: str, default: str) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return " ".join(match.group(1).split()).strip(" .,-") if match else default


def _skill_name(topic: str) -> str:
    text = SECTION_LABEL_RE.sub("", topic).strip(" .,-:;")
    canonical = _canonicalize_skill_name(text)
    if _has_observable_action(canonical):
        return canonical
    return f"Работа с темой «{_short_label(canonical)}»"


def _short_label(text: str) -> str:
    words = re.sub(r"\s+", " ", text).split()
    label = " ".join(words[:8]).strip(" .,-:;")
    return label[:90].rstrip(" .,-:;") or "общая тема"


def _bloom_for_text(text: str) -> BloomLevel:
    if CREATE_ACTION_RE.search(text):
        return "create"
    if ANALYZE_ACTION_RE.search(text):
        return "analyze"
    if APPLY_ACTION_RE.search(text):
        return "apply"
    return "understand"


def _indicator_text(name: str, bloom: BloomLevel) -> str:
    prefix = "Объясняет" if BLOOM_RANK[bloom] <= 2 else "Применяет" if BLOOM_RANK[bloom] <= 3 else "Прорабатывает"
    return f"{prefix}: {name}"


def _tools(text: str) -> list[str]:
    normalized = text.upper()
    return [term for term in TECH_TERMS if term.upper() in normalized]


def _canonicalize_skill_name(text: str) -> str:
    cleaned = _strip_context(text)
    for pattern, noun in ACTION_PREFIXES:
        match = pattern.match(cleaned)
        if match:
            return _clean(f"{noun} {_rewrite_object(match.group(1))}")
    return cleaned[:1].upper() + cleaned[1:] if cleaned else cleaned


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
    first = cleaned.split(" ", 1)[0].casefold().replace("ё", "е") if cleaned else ""
    explicit_work = bool(re.match(r"работа\s+с\s+(?!темой\b)", cleaned, flags=re.IGNORECASE))
    return first in ACTION_NOUNS or explicit_work or bool(ACTION_RE.search(cleaned))
