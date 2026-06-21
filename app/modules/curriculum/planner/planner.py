"""Deterministic spiral curriculum planner.

The planner does not call LLMs. It transforms accepted competencies and the
prerequisite DAG into project blueprints with artifact-first packing and
spaced spiral reinforcement.
"""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import dataclass
import re
from typing import Any

from app.modules.curriculum.planner.domain import (
    CurriculumBlock,
    PlanNode,
    PlanQualityMetrics,
    ProjectBlueprint,
    SkillOccurrence,
)


@dataclass(frozen=True)
class PlannerSettings:
    tau_edge_accept: float = 0.80
    max_skills_per_project: int = 4
    max_projects_per_block: int = 4
    spiral_enabled: bool = True
    core_thread_min: int = 4
    core_thread_max: int = 8
    min_thread_occurrences: int = 2
    max_thread_occurrences: int = 3
    spiral_min_gap: int = 2
    spiral_gap_growth: int = 2


SETTINGS = PlannerSettings()
_DANGLING_TAIL_WORDS = {"и", "или", "в", "во", "на", "для", "по", "с", "со", "к", "ко", "о", "об", "от", "до", "из"}
_ARTIFACT_FAMILY_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("analysis", ("анализ", "оцен", "исслед", "выяв", "диагност", "измер", "интерпрет", "сравн", "аудит")),
    ("document", ("документ", "опис", "оформ", "подготов", "состав", "регламент", "чек-лист", "шаблон", "гайд", "отчет", "отчёт")),
    ("configuration", ("настрой", "развер", "внедр", "интегр", "автоматиз", "конфиг", "подключ", "администр")),
    ("design", ("проектир", "модел", "планир", "определ", "формулир", "выбор", "специфиц", "приорит")),
    ("production", ("созда", "собир", "разработ", "реализ", "постро", "изготов", "код", "программ")),
)
_ARTIFACT_FAMILY_LABELS = {
    "analysis": "аналитический вывод",
    "document": "комплект документов",
    "configuration": "рабочая настройка",
    "design": "проектное решение",
    "production": "созданный продуктовый результат",
    "practice": "практический результат",
}


def build_curriculum_blocks(
    nodes: list[PlanNode],
    dag_payload: dict[str, object],
    artifact_templates: list[dict[str, object]] | None = None,
) -> tuple[list[CurriculumBlock], dict[str, object]]:
    """Build project blocks and return planner metadata."""
    if not nodes:
        return [], {"artifact_project_count": 0, "core_thread_ids": [], "repeated_thread_count": 0}

    blocks, artifact_meta = _pack_dynamic_artifact_blocks(nodes, dag_payload, artifact_templates)
    core_threads = _select_core_threads(nodes, dag_payload)
    repeated_threads = _add_spiral_occurrences(blocks, nodes, dag_payload)
    metrics = _quality_metrics(blocks, len(core_threads), len(repeated_threads))
    meta = {
        **artifact_meta,
        "core_thread_ids": [node.tmp_id for node in core_threads],
        "core_thread_names": [node.name for node in core_threads],
        "repeated_thread_ids": sorted(repeated_threads),
        "repeated_thread_count": len(repeated_threads),
        "quality_metrics": metrics.as_dict(),
    }
    return blocks, meta


def _pack_dynamic_artifact_blocks(
    nodes: list[PlanNode],
    dag_payload: dict[str, object],
    artifact_templates: list[dict[str, object]] | None,
) -> tuple[list[CurriculumBlock], dict[str, object]]:
    projects, meta = _pack_dynamic_artifact_projects(nodes, dag_payload, artifact_templates or [])
    projects = _reorder_projects_by_hard_edges(projects, dag_payload)
    return _blocks_from_projects(projects), meta


def _pack_dynamic_artifact_projects(
    nodes: list[PlanNode],
    dag_payload: dict[str, object],
    artifact_templates: list[dict[str, object]],
) -> tuple[list[ProjectBlueprint], dict[str, object]]:
    grouped: dict[str, list[PlanNode]] = {}
    group_order: list[str] = []
    group_meta: dict[str, tuple[str, str, dict[str, object] | None]] = {}
    for node in _ordered_nodes(nodes, dag_payload):
        template = _best_template_for_node(node, artifact_templates)
        dynamic_key = _artifact_key_for(node)
        template_code = str((template or {}).get("code") or "").strip()
        artifact_key = f"{dynamic_key}::template:{template_code}" if template_code else dynamic_key
        if artifact_key not in grouped:
            grouped[artifact_key] = []
            group_order.append(artifact_key)
            group_meta[artifact_key] = (_project_theme_for(node), _artifact_family_for(node), template)
        grouped[artifact_key].append(node)

    projects: list[ProjectBlueprint] = []
    assignment: dict[str, str] = {}
    split_count = 0
    for artifact_key in group_order:
        block_key, artifact_family, template = group_meta[artifact_key]
        chunks = _split_nodes_for_project(grouped[artifact_key], dag_payload, max_skills=SETTINGS.max_skills_per_project)
        split_count += max(0, len(chunks) - 1)
        for chunk_index, chunk in enumerate(chunks, start=1):
            artifact = _template_artifact_for(chunk, block_key, artifact_family, template)
            artifact = artifact or _artifact_for(chunk, block_key, artifact_family)
            title = _template_title_for(chunk, block_key, artifact_family, template)
            projects.append(
                ProjectBlueprint(
                    occurrences=[SkillOccurrence(item, role="primary", touch_index=1) for item in chunk],
                    block_key=block_key,
                    artifact=artifact,
                    artifact_key=artifact_key,
                    artifact_family=artifact_family,
                    artifact_template_code=str((template or {}).get("code") or "").strip(),
                    enrichment=_template_enrichment_for(chunk, block_key, artifact_family, artifact, template),
                    title=title or _project_title_for(block_key, chunk_index, len(chunks)),
                    project_kind="dynamic_artifact",
                )
            )
            for node in chunk:
                assignment[node.tmp_id] = artifact_key

    meta = {
        "artifact_first": True,
        "artifact_project_count": len(projects),
        "artifact_split_count": split_count,
        "dynamic_group_count": len(group_order),
        "artifact_family_counts": dict(Counter(family for _theme, family, _template in group_meta.values())),
        "db_template_count": len(artifact_templates),
        "db_template_project_count": len([project for project in projects if project.artifact_template_code]),
        "unassigned_node_count": 0,
        "assignment": assignment,
    }
    return projects, meta


def _split_nodes_for_project(nodes: list[PlanNode], dag_payload: dict[str, object], *, max_skills: int) -> list[list[PlanNode]]:
    hard_edges = _direct_edge_pairs(dag_payload, hard_only=True)
    chunks: list[list[PlanNode]] = []
    current: list[PlanNode] = []
    for node in nodes:
        can_append = current and len(current) < max_skills and not _has_direct_edge(node, current, hard_edges)
        if can_append:
            current.append(node)
            continue
        if current:
            chunks.append(current)
        current = [node]
    if current:
        chunks.append(current)
    return chunks


def _reorder_projects_by_hard_edges(projects: list[ProjectBlueprint], dag_payload: dict[str, object]) -> list[ProjectBlueprint]:
    if len(projects) <= 1:
        return projects
    project_by_node = _primary_project_index(projects)
    outgoing: dict[int, set[int]] = defaultdict(set)
    incoming = {index: 0 for index in range(len(projects))}
    for src_id, dst_id in _direct_edge_pairs(dag_payload, hard_only=True):
        src_project = project_by_node.get(src_id)
        dst_project = project_by_node.get(dst_id)
        if src_project is None or dst_project is None or src_project == dst_project or dst_project in outgoing[src_project]:
            continue
        outgoing[src_project].add(dst_project)
        incoming[dst_project] += 1

    queue = deque(index for index, count in incoming.items() if count == 0)
    ordered_indexes: list[int] = []
    while queue:
        project_index = min(queue)
        queue.remove(project_index)
        ordered_indexes.append(project_index)
        for target in sorted(outgoing[project_index]):
            incoming[target] -= 1
            if incoming[target] == 0:
                queue.append(target)
    if len(ordered_indexes) != len(projects):
        return projects
    return [projects[index] for index in ordered_indexes]


def _blocks_from_projects(projects: list[ProjectBlueprint]) -> list[CurriculumBlock]:
    blocks: list[CurriculumBlock] = []
    chunk_size = max(1, SETTINGS.max_projects_per_block)
    for offset in range(0, len(projects), chunk_size):
        chunk = projects[offset : offset + chunk_size]
        blocks.append(CurriculumBlock(block_keys=_ordered_block_keys(chunk), projects=chunk))
    return blocks


def _add_spiral_occurrences(blocks: list[CurriculumBlock], nodes: list[PlanNode], dag_payload: dict[str, object]) -> set[str]:
    projects = _flatten_projects(blocks)
    if len(projects) < 3 or not SETTINGS.spiral_enabled:
        return set()
    hard_edges = _direct_edge_pairs(dag_payload, hard_only=True)
    primary_index = _primary_project_index(projects)
    repeated_threads: set[str] = set()
    for node in _select_core_threads(nodes, dag_payload):
        first_index = primary_index.get(node.tmp_id)
        if first_index is None:
            continue
        desired = min(max(1, SETTINGS.max_thread_occurrences), max(1, len(projects) // 3 + 1))
        desired = min(max(SETTINGS.min_thread_occurrences, desired), len(projects))
        targets = _target_repeat_indexes(first_index, len(projects), desired)
        total_occurrences = 1 + len(targets)
        for touch_index, target_index in enumerate(targets, start=2):
            project = projects[target_index]
            existing_nodes = project.unique_nodes
            if node.tmp_id in {item.tmp_id for item in existing_nodes}:
                continue
            if len(existing_nodes) >= SETTINGS.max_skills_per_project:
                continue
            if _has_direct_edge(node, existing_nodes, hard_edges):
                continue
            project.occurrences.append(
                SkillOccurrence(
                    node=node,
                    role="assessment" if touch_index == total_occurrences else "reinforcement",
                    touch_index=touch_index,
                    bloom_bucket=_bucket_for_repeat(touch_index, total_occurrences),
                )
            )
            repeated_threads.add(node.tmp_id)
    return repeated_threads


def _select_core_threads(nodes: list[PlanNode], dag_payload: dict[str, object]) -> list[PlanNode]:
    if not SETTINGS.spiral_enabled:
        return []
    scores = _centrality_scores(nodes, dag_payload)
    candidates = [node for node in nodes if scores.get(node.tmp_id, 0.0) > 0.0]
    if len(nodes) >= SETTINGS.core_thread_min and len(candidates) < SETTINGS.core_thread_min:
        candidates = nodes[: SETTINGS.core_thread_min]
    ordered = sorted(candidates, key=lambda node: (-scores.get(node.tmp_id, 0.0), node.bloom, node.name))
    return ordered[: max(0, SETTINGS.core_thread_max)]


def _centrality_scores(nodes: list[PlanNode], dag_payload: dict[str, object]) -> dict[str, float]:
    by_id = {node.tmp_id: node for node in nodes}
    degree: Counter[str] = Counter()
    reliable_degree: Counter[str] = Counter()
    for edge in dag_payload.get("final_edges", []):
        if not isinstance(edge, dict):
            continue
        src_id, dst_id = _edge_node_ids(edge)
        if src_id in by_id and dst_id in by_id:
            degree[src_id] += 1
            degree[dst_id] += 1
            if _is_reliable_theme_edge(edge):
                reliable_degree[src_id] += 1
                reliable_degree[dst_id] += 1
    block_frequency = Counter(node.block_key for node in nodes)
    return {
        node.tmp_id: float(reliable_degree[node.tmp_id] * 2 + degree[node.tmp_id] + min(block_frequency[node.block_key], 3) * 0.25)
        for node in nodes
    }


def _quality_metrics(blocks: list[CurriculumBlock], core_threads: int, repeated_threads: int) -> PlanQualityMetrics:
    projects = _flatten_projects(blocks)
    if not projects:
        return PlanQualityMetrics(0.0, 0.0, 0, 0, core_threads, repeated_threads, SETTINGS.spiral_enabled)
    skill_counts = [len(project.unique_nodes) for project in projects]
    outcome_counts = [
        sum(len(node.outcomes_know) + len(node.outcomes_can) + len(node.outcomes_skills) for node in project.unique_nodes)
        for project in projects
    ]
    return PlanQualityMetrics(
        avg_skills_per_project=round(sum(skill_counts) / len(skill_counts), 2),
        avg_outcomes_per_project=round(sum(outcome_counts) / len(outcome_counts), 2),
        single_skill_project_count=sum(1 for count in skill_counts if count == 1),
        overloaded_project_count=sum(1 for count in skill_counts if count > SETTINGS.max_skills_per_project),
        core_thread_count=core_threads,
        repeated_thread_count=repeated_threads,
        spiral_enabled=SETTINGS.spiral_enabled,
    )


def _ordered_nodes(nodes: list[PlanNode], dag_payload: dict[str, object]) -> list[PlanNode]:
    position = _dag_position(dag_payload)
    return sorted(nodes, key=lambda item: (position.get(item.tmp_id, 10**9), item.bloom, item.name))


def _dag_position(dag_payload: dict[str, object]) -> dict[str, int]:
    return {
        str(item.get("id")): index
        for index, item in enumerate(dag_payload.get("order", []))
        if isinstance(item, dict) and item.get("id") is not None
    }


def _direct_edge_pairs(dag_payload: dict[str, object], *, hard_only: bool = False) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for edge in dag_payload.get("final_edges", []):
        if not isinstance(edge, dict):
            continue
        if hard_only and str(edge.get("relation_type") or "").casefold() != "hard":
            continue
        src_id, dst_id = _edge_node_ids(edge)
        if src_id and dst_id:
            pairs.add((src_id, dst_id))
    return pairs


def _edge_node_ids(edge: dict[str, object]) -> tuple[str, str]:
    src_id = str(edge.get("src_id") or edge.get("source_id") or edge.get("src") or "").strip()
    dst_id = str(edge.get("dst_id") or edge.get("target_id") or edge.get("dst") or "").strip()
    return src_id, dst_id


def _is_reliable_theme_edge(edge: dict[str, object]) -> bool:
    if str(edge.get("relation_type") or "").casefold() == "hard":
        return True
    try:
        confidence = float(edge.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    return confidence >= SETTINGS.tau_edge_accept


def _has_direct_edge(node: PlanNode, project_nodes: list[PlanNode], direct_edges: set[tuple[str, str]]) -> bool:
    return any(
        (node.tmp_id, existing.tmp_id) in direct_edges or (existing.tmp_id, node.tmp_id) in direct_edges
        for existing in project_nodes
    )


def _primary_project_index(projects: list[ProjectBlueprint]) -> dict[str, int]:
    index: dict[str, int] = {}
    for project_index, project in enumerate(projects):
        for occurrence in project.primary_occurrences:
            index.setdefault(occurrence.node.tmp_id, project_index)
    return index


def _target_repeat_indexes(first_index: int, project_count: int, occurrence_count: int) -> list[int]:
    if project_count <= 2 or occurrence_count <= 1:
        return []
    targets: list[int] = []
    gap = max(2, SETTINGS.spiral_min_gap)
    cursor = first_index
    for _touch in range(2, occurrence_count + 1):
        cursor = min(cursor + gap, project_count - 1)
        if cursor > first_index and cursor not in targets:
            targets.append(cursor)
        gap += max(1, SETTINGS.spiral_gap_growth)
    return targets


def _bucket_for_repeat(touch_index: int, total_occurrences: int) -> str:
    if touch_index <= 1:
        return "can"
    return "skills" if touch_index >= total_occurrences else "can"


def _flatten_projects(blocks: list[CurriculumBlock]) -> list[ProjectBlueprint]:
    return [project for block in blocks for project in block.projects]


def _ordered_block_keys(projects: list[ProjectBlueprint]) -> tuple[str, ...]:
    keys: list[str] = []
    for project in projects:
        if project.block_key and project.block_key not in keys:
            keys.append(project.block_key)
    return tuple(keys) or ("Общее",)


def _artifact_family_for(node: PlanNode) -> str:
    text = _norm_text(" ".join([node.name, node.group, node.block_key, *node.outcomes_know, *node.outcomes_can, *node.outcomes_skills, *node.tools]))
    for family, hints in _ARTIFACT_FAMILY_PATTERNS:
        if any(hint in text for hint in hints):
            return family
    if node.bloom >= 5:
        return "production"
    if node.bloom >= 4:
        return "design"
    return "practice"


def _artifact_key_for(node: PlanNode) -> str:
    return f"{_project_theme_for(node)}::{_artifact_family_for(node)}"


def _artifact_for(nodes: list[PlanNode], block_key: str, artifact_family: str) -> str:
    theme = _compact_text(block_key, max_words=6, max_chars=72)
    family_label = _ARTIFACT_FAMILY_LABELS.get(artifact_family, _ARTIFACT_FAMILY_LABELS["practice"])
    if len(nodes) == 1:
        label = _compact_text(nodes[0].name, max_words=8, max_chars=90)
        return f"Проверяемый артефакт ({family_label}) по навыку «{label}»"
    labels = [_compact_text(node.name, max_words=5, max_chars=56) for node in nodes[:3]]
    suffix = f" и ещё {len(nodes) - 3}" if len(nodes) > 3 else ""
    return f"Интегративный артефакт ({family_label}) по теме «{theme}»: {', '.join(labels)}{suffix}"


def _project_title_for(block_key: str, chunk_index: int, chunk_count: int) -> str:
    suffix = f" {chunk_index}" if chunk_count > 1 else ""
    return f"{_compact_text(block_key, max_words=4, max_chars=44)}{suffix}"


def _project_theme_for(node: PlanNode) -> str:
    return _compact_text(node.block_key or node.group or "Общее", max_words=6, max_chars=72)


def _best_template_for_node(node: PlanNode, artifact_templates: list[dict[str, object]]) -> dict[str, object] | None:
    scored = [(template, _template_scope_score(node, template)) for template in artifact_templates if isinstance(template, dict)]
    scored = [(template, score) for template, score in scored if score >= 0.5]
    if not scored:
        return None
    return max(scored, key=lambda item: (item[1], -int(item[0].get("priority", 100) or 100)))[0]


def _template_scope_score(node: PlanNode, template: dict[str, object]) -> float:
    family = str(template.get("artifact_family") or "").strip()
    if family and family != _artifact_family_for(node):
        return 0.0
    scopes = template.get("scopes")
    if not isinstance(scopes, list) or not scopes:
        return 0.1
    node_text = _norm_text(" ".join([node.name, node.group, node.block_key]))
    node_tokens = set(node_text.split())
    best = 0.0
    for scope in scopes:
        if not isinstance(scope, dict):
            continue
        if str(scope.get("scope_type") or "").strip() == "any":
            best = max(best, 0.6 * float(scope.get("weight", 1.0) or 1.0))
            continue
        scope_name = str(scope.get("normalized_scope_name") or scope.get("scope_name") or "").strip()
        normalized_scope = _norm_text(scope_name)
        if not normalized_scope:
            continue
        scope_tokens = set(normalized_scope.split())
        overlap = len(scope_tokens & node_tokens) / max(len(scope_tokens), 1)
        if normalized_scope in node_text:
            overlap = max(overlap, 1.0)
        best = max(best, overlap * float(scope.get("weight", 1.0) or 1.0))
    return best


def _template_artifact_for(nodes: list[PlanNode], block_key: str, artifact_family: str, template: dict[str, object] | None) -> str:
    return _render_pattern((template or {}).get("artifact_description"), nodes=nodes, block_key=block_key, artifact_family=artifact_family)


def _template_title_for(nodes: list[PlanNode], block_key: str, artifact_family: str, template: dict[str, object] | None) -> str:
    pattern = str((template or {}).get("project_name_pattern") or "").strip()
    rendered = _render_pattern(pattern, nodes=nodes, block_key=block_key, artifact_family=artifact_family)
    if rendered and ("{" not in pattern or len(rendered) <= 72):
        return rendered
    return _render_pattern((template or {}).get("title"), nodes=nodes, block_key=block_key, artifact_family=artifact_family) or rendered


def _template_enrichment_for(
    nodes: list[PlanNode],
    block_key: str,
    artifact_family: str,
    artifact: str,
    template: dict[str, object] | None,
) -> dict[str, str]:
    if not template:
        return {}
    return {
        "materials": _render_pattern(template.get("materials_pattern"), nodes=nodes, block_key=block_key, artifact_family=artifact_family, artifact=artifact),
        "storytelling": _render_pattern(template.get("storytelling_pattern"), nodes=nodes, block_key=block_key, artifact_family=artifact_family, artifact=artifact),
        "validation_criteria": _render_pattern(template.get("validation_criteria"), nodes=nodes, block_key=block_key, artifact_family=artifact_family, artifact=artifact),
    }


def _render_pattern(pattern: object, *, nodes: list[PlanNode], block_key: str, artifact_family: str, artifact: str = "") -> str:
    text = str(pattern or "").strip()
    if not text:
        return ""
    try:
        return text.format(
            theme=block_key,
            skills=", ".join(node.name for node in nodes),
            first_skill=nodes[0].name if nodes else "",
            artifact=artifact,
            artifact_family=_ARTIFACT_FAMILY_LABELS.get(artifact_family, artifact_family),
        )
    except (KeyError, IndexError, ValueError):
        return text


def _compact_text(value: str, *, max_words: int = 6, max_chars: int = 72) -> str:
    text = " ".join(str(value or "").replace("—", "-").split()).strip(" .,-")
    if not text:
        return "Общее"
    text = _drop_latin_parenthetical_notes(text.split(":", 1)[0].strip())
    words = text.split()
    shortened = len(words) > max_words
    if shortened:
        text = " ".join(words[:max_words])
    text = _strip_dangling_tail(text)
    if len(text) > max_chars:
        text = _limit_on_word_boundary(text, max_chars=max_chars)
    elif shortened and text:
        text = f"{text}..."
    return text or "Общее"


def _strip_dangling_tail(text: str) -> str:
    cleaned = re.sub(r"\([^)]*$", "", text).strip(" .,-:;(")
    words = cleaned.split()
    while words and words[-1].casefold().strip(" .,-:;()") in _DANGLING_TAIL_WORDS:
        words.pop()
    return " ".join(words).strip(" .,-:;")


def _drop_latin_parenthetical_notes(text: str) -> str:
    return re.sub(r"\s*\([^)]*[A-Za-z][^)]*\)", "", text).strip()


def _limit_on_word_boundary(text: str, *, max_chars: int) -> str:
    if len(text) <= max_chars:
        return _strip_dangling_tail(text) or text.strip(" .,-")
    candidate = text[: max(12, max_chars - 1)].rstrip()
    boundary = candidate.rfind(" ")
    if boundary >= max(12, len(candidate) // 2):
        candidate = candidate[:boundary]
    candidate = _strip_dangling_tail(candidate)
    return f"{candidate}..." if candidate else "..."


def _norm_text(value: Any) -> str:
    text = str(value or "").casefold().replace("ё", "е")
    text = re.sub(r"[^0-9a-zа-я+ ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()
