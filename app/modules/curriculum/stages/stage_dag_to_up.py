"""Stage T2.2: DAG payload -> spiral-planned core UPSkeleton."""

from __future__ import annotations

from app.core.models import BLOOM_RANK, Competency, CompetencyRef, UPProject, UPSkeleton
from app.modules.curriculum.planner import PlanNode, ProjectBlueprint, SkillOccurrence, build_curriculum_blocks


def run(spec: dict[str, object] | None, competencies: list[Competency], dag_payload: dict[str, object]) -> UPSkeleton:
    ordered_ids = [str(item["id"]) for item in dag_payload.get("order", []) if isinstance(item, dict) and item.get("id")]
    accepted = {
        item.competency_id: item
        for item in competencies
        if item.atomicity == "atomic" and item.status in {"accepted", "candidate"}
    }
    ordered = [accepted[item_id] for item_id in ordered_ids if item_id in accepted]
    if not ordered:
        return UPSkeleton(
            status="deferred",
            title="Черновик учебного плана",
            direction=str((spec or {}).get("domain") or ""),
            metadata={"reason": "no_accepted_competencies", "dag": dag_payload},
        )

    nodes = [_node_from_competency(item) for item in ordered]
    blocks, planner_meta = build_curriculum_blocks(nodes, dag_payload, _artifact_templates(spec))
    if not blocks:
        return UPSkeleton(
            status="deferred",
            title="Черновик учебного плана",
            direction=str((spec or {}).get("domain") or ""),
            metadata={"reason": "planner_empty", "dag": dag_payload, "planner_meta": planner_meta},
        )

    rows: list[UPProject] = []
    by_id = {item.competency_id: item for item in ordered}
    for block in blocks:
        for project in block.projects:
            rows.append(_project_row(project, by_id, spec or {}, len(rows) + 1))
    return UPSkeleton(
        status="built",
        title="Черновик учебного плана",
        direction=str((spec or {}).get("domain") or ""),
        rows=rows,
        metadata={"dag": dag_payload, "source_policy": "accepted_only", "planner_meta": planner_meta},
    )


def _node_from_competency(item: Competency) -> PlanNode:
    know, can, skills = _outcomes_for_competency(item)
    return PlanNode(
        tmp_id=item.competency_id,
        name=item.canonical_name,
        group=item.group or item.coverage_area or "Общее",
        block_key=item.coverage_area or item.group or "Общее",
        bloom=BLOOM_RANK[item.bloom_level],
        outcomes_know=tuple(know),
        outcomes_can=tuple(can),
        outcomes_skills=tuple(skills),
        tools=tuple(item.tools),
    )


def _outcomes_for_competency(item: Competency) -> tuple[list[str], list[str], list[str]]:
    know: list[str] = []
    can: list[str] = []
    skills: list[str] = []
    for indicator in item.indicators:
        target = know if BLOOM_RANK[indicator.bloom] <= 2 else can if BLOOM_RANK[indicator.bloom] <= 4 else skills
        target.append(indicator.text)
    if not (know or can or skills):
        can.append(item.canonical_name)
    return know, can, skills


def _project_row(project: ProjectBlueprint, by_id: dict[str, Competency], spec: dict[str, object], order: int) -> UPProject:
    primary = project.primary_occurrences or project.occurrences
    primary_names = [occurrence.node.name for occurrence in primary]
    know, can, skills = _outcomes_from_occurrences(project.occurrences)
    refs = _competency_refs(project.occurrences, by_id)
    tools = sorted({tool for occurrence in project.occurrences for tool in occurrence.node.tools})
    return UPProject(
        block=project.block_key,
        block_goal=f"Освоить: {', '.join(primary_names)}",
        order=order,
        title=_project_name(project, primary_names),
        description=project.artifact,
        outcomes_know=know,
        outcomes_can=can,
        outcomes_skills=skills,
        competency_refs=refs,
        required_tools=tools,
        materials=project.enrichment.get("materials") or "Сырые материалы и постановка задачи из брифа.",
        storytelling=project.enrichment.get("storytelling")
        or f"Роль: {spec.get('role') or 'участник программы'}; домен: {spec.get('domain') or project.block_key}.",
        format="individual",
        group_size=1,
        hours_astro=_hours([by_id[item.node.tmp_id] for item in project.occurrences if item.node.tmp_id in by_id]),
        metadata=_project_metadata(project),
    )


def _project_name(project: ProjectBlueprint, primary_names: list[str]) -> str:
    """Name a project after the skills it delivers, not a generic "Проект N"."""
    names = _dedupe([name.strip() for name in primary_names if name.strip()])
    if not names:
        return project.title or _compact_title(project.block_key)
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]}, {names[1]}"
    return f"{names[0]}, {names[1]} +{len(names) - 2}"


def _outcomes_from_occurrences(occurrences: list[SkillOccurrence]) -> tuple[list[str], list[str], list[str]]:
    know: list[str] = []
    can: list[str] = []
    skills: list[str] = []
    for occurrence in occurrences:
        know.extend(occurrence.node.outcomes_know)
        if occurrence.bloom_bucket == "skills" and occurrence.is_repeat:
            skills.extend(occurrence.node.outcomes_can or occurrence.node.outcomes_skills)
        else:
            can.extend(occurrence.node.outcomes_can)
            skills.extend(occurrence.node.outcomes_skills)
    return _dedupe(know), _dedupe(can), _dedupe(skills)


def _competency_refs(occurrences: list[SkillOccurrence], by_id: dict[str, Competency]) -> list[CompetencyRef]:
    refs: list[CompetencyRef] = []
    primary_count = max(1, len([item for item in occurrences if item.role == "primary"]))
    for occurrence in occurrences:
        item = by_id.get(occurrence.node.tmp_id)
        weight = round(100 / primary_count, 2) if occurrence.role == "primary" else None
        if item is None:
            refs.append(
                CompetencyRef(
                    competency_id=occurrence.node.tmp_id,
                    canonical_name=occurrence.node.name,
                    role=occurrence.role,
                    weight=weight,
                )
            )
            continue
        refs.append(CompetencyRef.from_competency(item, role=occurrence.role, weight=weight))
    return refs


def _project_metadata(project: ProjectBlueprint) -> dict[str, object]:
    return {
        "node_ids": project.node_ids,
        "primary_node_ids": [item.node.tmp_id for item in project.primary_occurrences],
        "repeat_node_ids": [item.node.tmp_id for item in project.occurrences if item.is_repeat],
        "occurrences": [
            {
                "node_id": item.node.tmp_id,
                "role": item.role,
                "touch_index": item.touch_index,
                "bloom_bucket": item.bloom_bucket,
            }
            for item in project.occurrences
        ],
        "artifact": project.artifact,
        "artifact_key": project.artifact_key,
        "artifact_family": project.artifact_family,
        "artifact_template_code": project.artifact_template_code,
        "project_kind": project.project_kind,
        "validation_criteria": project.enrichment.get("validation_criteria", ""),
    }


def _artifact_templates(spec: dict[str, object] | None) -> list[dict[str, object]]:
    raw = (spec or {}).get("artifact_templates")
    return [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        text = str(item).strip()
        key = text.casefold()
        if text and key not in seen:
            seen.add(key)
            out.append(text)
    return out


def _compact_title(value: str) -> str:
    words = str(value or "").split()
    return " ".join(words[:6]).strip(" .,-:;") or "компетенция"


def _hours(items: list[Competency]) -> int:
    max_bloom = max((BLOOM_RANK[item.bloom_level] for item in items), default=2)
    return min((8, 12, 16, 24, 32), key=lambda band: abs(band - (6 + 3 * len(items) + 2 * max(0, max_bloom - 2))))
