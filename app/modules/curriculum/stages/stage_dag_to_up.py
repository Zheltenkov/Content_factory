"""Stage T2.1.5: DAG payload -> core UPSkeleton."""

from __future__ import annotations

from app.core.models import BLOOM_RANK, Competency, CompetencyRef, UPProject, UPSkeleton


def run(spec: dict[str, object] | None, competencies: list[Competency], dag_payload: dict[str, object]) -> UPSkeleton:
    ordered_ids = [str(item["id"]) for item in dag_payload.get("order", []) if isinstance(item, dict) and item.get("id")]
    by_id = {item.competency_id: item for item in competencies if item.atomicity == "atomic"}
    ordered = [by_id[item_id] for item_id in ordered_ids if item_id in by_id]
    if not ordered:
        return UPSkeleton(
            status="deferred",
            title="Черновик учебного плана",
            direction=str((spec or {}).get("domain") or ""),
            metadata={"reason": "no_accepted_competencies", "dag": dag_payload},
        )

    rows: list[UPProject] = []
    for order, group in enumerate(_chunks(ordered, size=2), 1):
        primary = group[0]
        block = primary.group or primary.coverage_area or "Общее"
        outcomes_know, outcomes_can, outcomes_skills = _outcomes(group)
        rows.append(
            UPProject(
                block=block,
                block_goal=f"Освоить: {', '.join(item.canonical_name for item in group)}",
                order=order,
                title=f"Проект {order}. {_compact_title(primary.canonical_name)}",
                description=f"Практический проект для закрепления компетенций: {', '.join(item.canonical_name for item in group)}.",
                outcomes_know=outcomes_know,
                outcomes_can=outcomes_can,
                outcomes_skills=outcomes_skills,
                competency_refs=[CompetencyRef.from_competency(item, weight=round(100 / len(group), 2)) for item in group],
                required_tools=sorted({tool for item in group for tool in item.tools}),
                materials="Сырые материалы и постановка задачи из брифа.",
                storytelling=f"Роль: {(spec or {}).get('role') or 'участник программы'}; домен: {(spec or {}).get('domain') or block}.",
                format="individual",
                group_size=1,
                hours_astro=_hours(group),
                metadata={"node_ids": [item.competency_id for item in group]},
            )
        )
    return UPSkeleton(
        status="built",
        title="Черновик учебного плана",
        direction=str((spec or {}).get("domain") or ""),
        rows=rows,
        metadata={"dag": dag_payload, "source_policy": "accepted_only"},
    )


def _chunks(items: list[Competency], *, size: int) -> list[list[Competency]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def _outcomes(items: list[Competency]) -> tuple[list[str], list[str], list[str]]:
    know: list[str] = []
    can: list[str] = []
    skills: list[str] = []
    for item in items:
        target = know if BLOOM_RANK[item.bloom_level] <= 2 else can if BLOOM_RANK[item.bloom_level] <= 3 else skills
        target.extend(indicator.text for indicator in item.indicators)
    return know, can, skills


def _compact_title(value: str) -> str:
    words = value.split()
    return " ".join(words[:6]).strip(" .,-:;") or "компетенция"


def _hours(items: list[Competency]) -> int:
    max_bloom = max((BLOOM_RANK[item.bloom_level] for item in items), default=2)
    return min((8, 12, 16, 24, 32), key=lambda band: abs(band - (6 + 3 * len(items) + 2 * max(0, max_bloom - 2))))
