"""Stage T2.1.4: accepted competencies -> prerequisite DAG payload."""

from __future__ import annotations

from collections import defaultdict, deque

from app.core.models import BLOOM_RANK, Competency, CompetencyEdge


def run(competencies: list[Competency]) -> tuple[list[CompetencyEdge], dict[str, object]]:
    nodes = [item for item in competencies if item.atomicity == "atomic" and item.status in {"accepted", "candidate"}]
    nodes = sorted(nodes, key=lambda item: (str(item.metadata.get("order", "")), BLOOM_RANK[item.bloom_level], item.canonical_name))
    edges = _propose_edges(nodes)
    acyclic_edges, removed = _remove_cycles(nodes, edges)
    waves, order = _topological(nodes, acyclic_edges)
    payload = {
        "nodes": len(nodes),
        "edges": len(acyclic_edges),
        "acyclic": len(removed) == 0,
        "removed_cycle": len(removed),
        "order": [_node_payload(node) for node in order],
        "waves": [[_node_payload(node) for node in wave] for wave in waves],
        "final_edges": [edge.model_dump(mode="json") for edge in acyclic_edges],
        "used_candidate_ids": [node.competency_id for node in nodes],
    }
    return acyclic_edges, payload


def _propose_edges(nodes: list[Competency]) -> list[CompetencyEdge]:
    edges: list[CompetencyEdge] = []
    for left, right in zip(nodes, nodes[1:], strict=False):
        relation = "hard" if left.group == right.group and BLOOM_RANK[left.bloom_level] <= BLOOM_RANK[right.bloom_level] else "soft"
        edges.append(
            CompetencyEdge(
                source_id=left.competency_id,
                target_id=right.competency_id,
                relation_type=relation,
                confidence=0.75 if relation == "soft" else 0.9,
                rationale="Стабильная последовательность из брифа и Bloom-level.",
            )
        )
    return edges


def _remove_cycles(nodes: list[Competency], edges: list[CompetencyEdge]) -> tuple[list[CompetencyEdge], list[CompetencyEdge]]:
    accepted: list[CompetencyEdge] = []
    removed: list[CompetencyEdge] = []
    node_ids = {node.competency_id for node in nodes}
    for edge in edges:
        if edge.source_id not in node_ids or edge.target_id not in node_ids or edge.source_id == edge.target_id:
            removed.append(edge)
            continue
        probe = [*accepted, edge]
        if _has_cycle(node_ids, probe):
            removed.append(edge)
        else:
            accepted.append(edge)
    return accepted, removed


def _has_cycle(node_ids: set[str], edges: list[CompetencyEdge]) -> bool:
    incoming = {node_id: 0 for node_id in node_ids}
    outgoing: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        outgoing[edge.source_id].append(edge.target_id)
        incoming[edge.target_id] += 1
    queue = deque([node_id for node_id, count in incoming.items() if count == 0])
    visited = 0
    while queue:
        current = queue.popleft()
        visited += 1
        for target in outgoing[current]:
            incoming[target] -= 1
            if incoming[target] == 0:
                queue.append(target)
    return visited != len(node_ids)


def _topological(nodes: list[Competency], edges: list[CompetencyEdge]) -> tuple[list[list[Competency]], list[Competency]]:
    by_id = {node.competency_id: node for node in nodes}
    incoming = {node.competency_id: 0 for node in nodes}
    outgoing: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        outgoing[edge.source_id].append(edge.target_id)
        incoming[edge.target_id] += 1

    waves: list[list[Competency]] = []
    order: list[Competency] = []
    current = [node_id for node_id, count in incoming.items() if count == 0]
    while current:
        wave = [by_id[node_id] for node_id in current]
        waves.append(wave)
        order.extend(wave)
        next_wave: list[str] = []
        for node_id in current:
            for target in outgoing[node_id]:
                incoming[target] -= 1
                if incoming[target] == 0:
                    next_wave.append(target)
        current = next_wave
    return waves, order


def _node_payload(node: Competency) -> dict[str, object]:
    return {
        "id": node.competency_id,
        "name": node.canonical_name,
        "group": node.group,
        "bloom": BLOOM_RANK[node.bloom_level],
    }
