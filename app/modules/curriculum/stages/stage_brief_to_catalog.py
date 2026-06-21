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
        name = skill_name_from_topic(topic)
        bloom = bloom_for_text(topic)
        competencies.append(
            Competency(
                competency_id=f"C{index:02d}",
                canonical_name=name,
                source_name=topic,
                group=str(spec.get("domain") or "Общее"),
                coverage_area=topic,
                indicators=[CompetencyIndicator(text=f"{indicator_prefix(bloom)}: {name}", bloom=bloom)],
                tools=tools_for_text(topic),
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

