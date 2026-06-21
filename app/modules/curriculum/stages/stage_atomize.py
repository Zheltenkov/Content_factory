"""Stage T2.1.2: classify and split composite competency candidates."""

from __future__ import annotations

import re

from app.core.models import Competency, CompetencyIndicator


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
    if "," in name or re.search(r"\s(и|или)\s", lowered) or len(name.split()) >= 8:
        return "composite"
    return "atomic"


def _children(parent: Competency) -> list[Competency]:
    parts = [part.strip(" .,-:;") for part in re.split(r",|\s+и\s+|\s+или\s+", parent.canonical_name) if part.strip(" .,-:;")]
    children: list[Competency] = []
    for index, part in enumerate(parts[:6], 1):
        name = part if re.search(r"\b(анализ|проект|разработ|настрой|тест|работ|управл|создан|выбор)", part, re.I) else f"Работа с темой «{part}»"
        bloom = parent.bloom_level
        children.append(
            Competency(
                competency_id=f"{parent.competency_id}.{index}",
                canonical_name=name,
                source_name=parent.canonical_name,
                group=parent.group,
                coverage_area=parent.coverage_area or parent.canonical_name,
                indicators=[CompetencyIndicator(text=f"Применяет: {name}", bloom=bloom)],
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
