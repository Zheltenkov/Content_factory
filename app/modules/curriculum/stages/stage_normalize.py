"""Stage T2.1.3: normalize, deduplicate and keep provenance-rich competencies."""

from __future__ import annotations

import difflib
import re
import unicodedata

from app.core.models import Competency, CompetencyIndicator

DROP_TOKENS = {"навык", "умение", "работа", "основы", "базовый", "тема", "темой"}
ACTION_NORMALIZATION = {"провести": "проведение", "настроить": "настройка", "разработать": "разработка"}


def run(competencies: list[Competency], spec: dict[str, object] | None = None) -> tuple[list[Competency], dict[str, object]]:
    kept: list[Competency] = []
    events: list[dict[str, object]] = []
    for item in competencies:
        if item.atomicity != "atomic":
            kept.append(item)
            continue
        normalized = _canonical_name(item.canonical_name)
        candidate = item.model_copy(update={"canonical_name": normalized, "atomicity": "atomic"})
        anchor = _duplicate_for(candidate, kept)
        if anchor is None:
            kept.append(candidate)
            continue
        _merge(anchor, candidate)
        events.append({"kept": anchor.canonical_name, "absorbed": candidate.canonical_name})

    return kept, {
        "input_count": len(competencies),
        "output_count": len(kept),
        "merged_count": len(events),
        "events": events,
        "artifact_type": (spec or {}).get("artifact_type"),
    }


def _canonical_name(value: str) -> str:
    text = re.sub(r"\s+", " ", value).strip(" .,-:;")
    if not text:
        return "Без названия"
    replacement = ACTION_NORMALIZATION.get(text.casefold())
    if replacement:
        text = replacement
    return text[:1].upper() + text[1:]


def _norm(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold().replace("ё", "е")
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[^0-9a-zа-я+\-/ ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokens(value: str) -> list[str]:
    tokens: list[str] = []
    for token in _norm(value).split():
        token = ACTION_NORMALIZATION.get(token, token)
        if token in DROP_TOKENS:
            continue
        for suffix in ("иями", "ями", "ами", "ого", "его", "ому", "ему", "ция", "ции", "ия", "ие", "ий", "ый", "ой", "ов", "ев"):
            if len(token) > len(suffix) + 3 and token.endswith(suffix):
                token = token[: -len(suffix)]
                break
        if token:
            tokens.append(token)
    return tokens


def _duplicate_for(candidate: Competency, kept: list[Competency]) -> Competency | None:
    left = _tokens(candidate.canonical_name)
    for anchor in kept:
        if anchor.atomicity != "atomic":
            continue
        if candidate.coverage_area and anchor.coverage_area and candidate.coverage_area != anchor.coverage_area:
            continue
        right = _tokens(anchor.canonical_name)
        if not left or not right:
            continue
        jaccard = len(set(left) & set(right)) / len(set(left) | set(right))
        ratio = difflib.SequenceMatcher(None, " ".join(left), " ".join(right)).ratio()
        if _norm(candidate.canonical_name) == _norm(anchor.canonical_name) or jaccard >= 0.86 or ratio >= 0.93:
            return anchor
    return None


def _merge(anchor: Competency, duplicate: Competency) -> None:
    indicators = [*anchor.indicators, *duplicate.indicators]
    seen: set[tuple[str, str]] = set()
    deduped: list[CompetencyIndicator] = []
    for indicator in indicators:
        key = (_norm(indicator.text), indicator.bloom)
        if key not in seen:
            seen.add(key)
            deduped.append(indicator)
    anchor.indicators = deduped
    anchor.tools = list(dict.fromkeys([*anchor.tools, *duplicate.tools]))
    anchor.evidence_ids = list(dict.fromkeys([*anchor.evidence_ids, *duplicate.evidence_ids]))
    anchor.aliases = list(dict.fromkeys([*anchor.aliases, *duplicate.aliases, duplicate.canonical_name]))
    anchor.confidence = max(anchor.confidence, duplicate.confidence)
