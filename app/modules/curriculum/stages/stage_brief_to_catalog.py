"""Stage T2.1.1: brief text -> normalized core competencies."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.llm.prompt_loader import load_prompt
from app.core.llm.structured import StructuredPrompt, complete_typed
from app.core.models import Competency, CompetencyIndicator, EvidenceSource
from app.modules.curriculum.stages.skill_names import bloom_for_text, indicator_prefix, skill_name_from_topic, tools_for_text

SECTION_LABEL_RE = re.compile(
    r"^(наименование|идея|целевая аудитория|участники|результат|цель|задача|описание|требования|контекст)\s*[:\-]\s*",
    re.IGNORECASE,
)
MUST_INCLUDE_RE = re.compile(
    r"(?:какие\s+темы\s+или\s+компетенции\s+должны\s+быть\s+обязательно\s+включены|"
    r"обязательно\s+должны\s+быть\s+включены\s+следующие\s+темы\s+и\s+компетенции)\s*[:?]?.*",
    re.IGNORECASE,
)
SECTION_STOP_RE = re.compile(
    r"^(?:требования\s+к|sjm\b|портрет\s+участника|портрет\s+эксперта|какие\s+дополнительные|открытые\s+вопросы)\b",
    re.IGNORECASE,
)


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
    areas = [
        str(area).strip()
        for area in spec.get("must_include_areas", [])
        if spec.get("must_include_areas_source") == "explicit" and str(area).strip()
    ]
    topics = areas or _topic_candidates(brief) or [str(spec.get("domain") or "Ключевые задачи программы")]
    competencies: list[Competency] = []
    coverage_rows: list[dict[str, Any]] = []
    for area_index, topic in enumerate(topics[:16], 1):
        names = _area_skill_names(topic) if areas else [skill_name_from_topic(topic)]
        area_names: list[str] = []
        for name_index, name in enumerate(names, 1):
            bloom = bloom_for_text(f"{name} {topic}")
            competencies.append(
                Competency(
                    competency_id=f"C{area_index:02d}.{name_index}" if areas else f"C{area_index:02d}",
                    canonical_name=name,
                    source_name=topic,
                    group=_group_for_area(topic, spec),
                    coverage_area=topic,
                    indicators=_indicators_for(name, topic, bloom),
                    tools=tools_for_text(topic),
                    confidence=0.72,
                    atomicity="atomic" if areas else "unknown",
                    resolution="new",
                    status="accepted",
                    metadata={"source": "brief_offline", "order": area_index, "coverage_order": name_index},
                )
            )
            area_names.append(name)
        coverage_rows.append(
            {
                "area": topic,
                "status": "covered" if area_names else "uncovered",
                "candidate_names": area_names,
                "dropped_candidate_names": [],
                "rationale": "Offline coverage-first extraction from must_include_areas.",
            }
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
        coverage_audit=_coverage_audit(coverage_rows, fallback_areas=topics[:16]),
    )


def _spec_from_brief(brief: str) -> dict[str, Any]:
    is_program = bool(re.search(r"\b(программа|курс|обучени|учебн|ветк|паспорт|тз)\b", brief.casefold().replace("ё", "е")))
    areas = _must_include_areas(brief)
    topics = areas or _topic_candidates(brief)
    return {
        "artifact_type": "program_brief" if is_program else "learner_brief",
        "role": _match_or_default(brief, r"(?:роль|профиль|выпускник|специалист)\s*[:\-]\s*([^.\n;]{3,90})", "Выпускник программы"),
        "seniority": _match_or_default(brief, r"\b(junior\+?|middle|senior|lead|начинающ[а-я]+|базов[а-я]+)\b", "не указан"),
        "domain": topics[0][:120] if topics else "Домен из брифа",
        "must_include_areas": topics[:16],
        "must_include_areas_source": "explicit" if areas else "fallback",
        "sub_queries": [f"Навыки выпускника: {topic}" for topic in topics[:6]],
    }


def _must_include_areas(brief: str) -> list[str]:
    lines = brief.splitlines()
    start: int | None = None
    for index, line in enumerate(lines):
        if MUST_INCLUDE_RE.search(line):
            start = index + 1
            break
    if start is None:
        return []

    raw_items: list[str] = []
    for line in lines[start:]:
        text = line.strip()
        if not text:
            continue
        if SECTION_STOP_RE.search(text):
            break
        for part in text.split(";"):
            item = re.sub(r"^[\-–—•*\d.)\s]+", "", part).strip(" .;:")
            if _is_area_candidate(item):
                raw_items.append(item)
    return list(dict.fromkeys(raw_items))


def _topic_candidates(brief: str) -> list[str]:
    out: list[str] = []
    for chunk in re.split(r"[\n.;•\u2022]+", brief):
        text = SECTION_LABEL_RE.sub("", chunk).strip(" \t:-")
        text = re.sub(r"\s+", " ", text)
        if 12 <= len(text) <= 180 and not re.search(r"\b(email|http|www|телефон)\b", text.casefold()):
            out.append(text)
    return list(dict.fromkeys(out))


def _area_skill_names(area: str) -> list[str]:
    parts = _area_parts(area)
    names: list[str] = []
    for part in parts[:4]:
        name = skill_name_from_topic(part)
        names.append(name)
    return list(dict.fromkeys(names)) or [skill_name_from_topic(area)]


def _area_parts(area: str) -> list[str]:
    text = re.sub(r"\s+", " ", area).strip(" .;:")
    if ":" in text:
        head, tail = text.split(":", 1)
        seeds = [head, *re.split(r",|\s+и\s+", tail)]
    else:
        seeds = re.split(r",|\s+и\s+", text)
    out: list[str] = []
    for seed in seeds:
        item = seed.strip(" .;:")
        if _is_area_candidate(item):
            out.append(item)
    return out


def _is_area_candidate(text: str) -> bool:
    normalized = text.casefold().replace("ё", "е")
    if not (8 <= len(text) <= 220):
        return False
    if re.search(r"\b(email|http|www|телефон)\b", normalized):
        return False
    if re.search(r"^(согласно|обязательно|какие темы|следующие темы)\b", normalized):
        return False
    return True


def _indicators_for(name: str, area: str, bloom: str) -> list[CompetencyIndicator]:
    return [
        CompetencyIndicator(text=f"{indicator_prefix(bloom)}: {name}", bloom=bloom),
        CompetencyIndicator(text=f"Связывает навык с областью «{_short_area(area)}».", bloom="understand"),
    ]


def _group_for_area(area: str, spec: dict[str, Any]) -> str:
    if ":" in area:
        return area.split(":", 1)[0].strip(" .;:")[:80]
    words = area.split()
    return " ".join(words[:4]).strip(" .;:") or str(spec.get("domain") or "Общее")


def _coverage_audit(rows: list[dict[str, Any]], *, fallback_areas: list[str]) -> dict[str, Any]:
    if not rows:
        return {"areas": fallback_areas, "covered": 0, "mode": "offline", "rows": []}
    covered = sum(1 for row in rows if row["status"] == "covered")
    partial = sum(1 for row in rows if row["status"] == "partial")
    uncovered = sum(1 for row in rows if row["status"] == "uncovered")
    return {
        "areas": [str(row["area"]) for row in rows],
        "covered": covered,
        "covered_count": covered,
        "partial_count": partial,
        "uncovered_count": uncovered,
        "mode": "offline",
        "rows": rows,
    }


def _short_area(area: str) -> str:
    text = re.sub(r"\s+", " ", area).strip(" .;:")
    return text[:120].rstrip(" .;:")


def _match_or_default(text: str, pattern: str, default: str) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return " ".join(match.group(1).split()).strip(" .,-") if match else default
