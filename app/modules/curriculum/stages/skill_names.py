"""Declarative skill-name normalization used by curriculum intake stages."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.core.models import BLOOM_RANK, BloomLevel


@dataclass(frozen=True)
class SkillNameRules:
    action_nouns: frozenset[str]
    action_prefixes: tuple[tuple[re.Pattern[str], str], ...]
    fragment_repairs: dict[str, str]
    object_rewrites: dict[str, str]
    tech_terms: tuple[str, ...]
    create_signal: re.Pattern[str]
    analyze_signal: re.Pattern[str]
    apply_signal: re.Pattern[str]
    context_prefix: re.Pattern[str]
    program_schedule: re.Pattern[str]
    program_context: re.Pattern[str]


@lru_cache
def rules() -> SkillNameRules:
    payload = yaml.safe_load(Path(__file__).with_name("skill_name_rules.yaml").read_text(encoding="utf-8")) or {}
    bloom = payload.get("bloom_signals") or {}
    program = payload.get("program_frame") or {}
    return SkillNameRules(
        action_nouns=frozenset(_norm_key(item) for item in payload.get("action_nouns", [])),
        action_prefixes=tuple(
            (re.compile(str(item["pattern"]), re.IGNORECASE), str(item["noun"]))
            for item in payload.get("action_prefixes", [])
        ),
        fragment_repairs={_norm_key(key): str(value) for key, value in (payload.get("fragment_repairs") or {}).items()},
        object_rewrites={_norm_key(key): str(value) for key, value in (payload.get("object_rewrites") or {}).items()},
        tech_terms=tuple(str(item) for item in payload.get("tech_terms", [])),
        create_signal=re.compile(str(bloom.get("create", r"$^")), re.IGNORECASE),
        analyze_signal=re.compile(str(bloom.get("analyze", r"$^")), re.IGNORECASE),
        apply_signal=re.compile(str(bloom.get("apply", r"$^")), re.IGNORECASE),
        context_prefix=re.compile(str(payload.get("context_prefix", r"$^")), re.IGNORECASE),
        program_schedule=re.compile(str(program.get("schedule_pattern", r"$^")), re.IGNORECASE),
        program_context=re.compile(str(program.get("context_pattern", r"$^")), re.IGNORECASE),
    )


def skill_name_from_topic(text: str) -> str:
    canonical = canonicalize_skill_name(text)
    if has_observable_action(canonical):
        return canonical
    return f"Работа с темой «{short_label(canonical)}»"


def skill_name_from_fragment(text: str) -> str:
    canonical = canonicalize_skill_name(text)
    if has_observable_action(canonical):
        return canonical
    return f"Работа с темой «{clean(canonical)}»"


def canonicalize_skill_name(text: str) -> str:
    active = rules()
    cleaned = strip_context(text)
    key = _norm_key(cleaned)
    if key in active.fragment_repairs:
        return active.fragment_repairs[key]
    for pattern, noun in active.action_prefixes:
        match = pattern.match(cleaned)
        if match:
            return clean(f"{noun} {rewrite_object(match.group(1))}")
    first, *rest = cleaned.split()
    if _norm_key(first) in active.action_nouns and rest:
        return clean(f"{first[:1].upper() + first[1:]} {rewrite_object(' '.join(rest))}")
    return cleaned[:1].upper() + cleaned[1:] if cleaned else cleaned


def has_observable_action(text: str) -> bool:
    active = rules()
    cleaned = clean(text)
    if not cleaned:
        return False
    first = _norm_key(cleaned.split(" ", 1)[0])
    explicit_work = bool(re.match(r"работа\s+с\s+(?!темой\b)", cleaned, flags=re.IGNORECASE))
    return (
        first in active.action_nouns
        or explicit_work
        or bool(active.create_signal.search(cleaned) or active.analyze_signal.search(cleaned) or active.apply_signal.search(cleaned))
    )


def bloom_for_text(text: str, fallback: BloomLevel = "understand") -> BloomLevel:
    active = rules()
    if active.create_signal.search(text):
        return "create"
    if active.analyze_signal.search(text):
        return "analyze"
    if active.apply_signal.search(text) or has_observable_action(text):
        return "apply"
    return fallback


def indicator_prefix(bloom: BloomLevel) -> str:
    return "Применяет" if BLOOM_RANK[bloom] <= 3 else "Прорабатывает"


def tools_for_text(text: str) -> list[str]:
    normalized = text.upper()
    return [term for term in rules().tech_terms if term.upper() in normalized]


def is_program_frame(text: str) -> bool:
    active = rules()
    lowered = clean(text).casefold().replace("ё", "е")
    return bool(active.program_schedule.search(lowered) and active.program_context.search(lowered))


def strip_context(text: str) -> str:
    return rules().context_prefix.sub("", clean(text))


def rewrite_object(text: str) -> str:
    cleaned = clean(text)
    return rules().object_rewrites.get(_norm_key(cleaned), cleaned)


def short_label(text: str, *, max_words: int = 8, max_chars: int = 90) -> str:
    words = clean(text).split()
    label = " ".join(words[:max_words]).strip(" .,-:;")
    return label[:max_chars].rstrip(" .,-:;") or "общая тема"


def clean(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "").replace("‑", "-").strip(" \t\r\n.,;:"))


def _norm_key(text: Any) -> str:
    return clean(text).casefold().replace("ё", "е")
