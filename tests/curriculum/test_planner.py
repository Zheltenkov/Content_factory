from __future__ import annotations

from app.core.models import Competency
from app.modules.curriculum.planner import PlanNode, build_curriculum_blocks
from app.modules.curriculum.stages import stage_catalog_to_dag, stage_dag_to_up


def test_planner_preserves_hard_dag_project_order() -> None:
    nodes = [_node("C1", "SQL база", "SQL"), _node("C2", "SQL агрегации", "SQL"), _node("C3", "API контракт", "API")]
    dag_payload = {
        "order": [{"id": "C1"}, {"id": "C2"}, {"id": "C3"}],
        "final_edges": [
            {"source_id": "C1", "target_id": "C2", "relation_type": "hard", "confidence": 0.95},
            {"source_id": "C2", "target_id": "C3", "relation_type": "hard", "confidence": 0.95},
        ],
    }

    blocks, meta = build_curriculum_blocks(nodes, dag_payload)

    projects = [project for block in blocks for project in block.projects]
    first_indexes = {project.primary_occurrences[0].node.tmp_id: index for index, project in enumerate(projects)}
    assert first_indexes["C1"] < first_indexes["C2"] < first_indexes["C3"]
    assert meta["artifact_project_count"] == len(projects)


def test_planner_adds_spiral_reinforcement_occurrences() -> None:
    nodes = [_node(f"C{index}", f"Компетенция {index}", f"Тема {index}") for index in range(1, 7)]
    dag_payload = {
        "order": [{"id": node.tmp_id} for node in nodes],
        "final_edges": [
            {"source_id": "C1", "target_id": "C2", "relation_type": "hard", "confidence": 0.95},
            {"source_id": "C2", "target_id": "C3", "relation_type": "hard", "confidence": 0.95},
            {"source_id": "C3", "target_id": "C4", "relation_type": "hard", "confidence": 0.95},
            {"source_id": "C4", "target_id": "C5", "relation_type": "hard", "confidence": 0.95},
        ],
    }

    blocks, meta = build_curriculum_blocks(nodes, dag_payload)

    occurrences = [occurrence for block in blocks for project in block.projects for occurrence in project.occurrences]
    assert meta["repeated_thread_count"] >= 1
    assert any(occurrence.is_repeat for occurrence in occurrences)


def test_stage_dag_to_up_uses_planner_metadata() -> None:
    competencies = [
        _competency("C1", "Проектирует REST API", "REST API", "apply", ["OpenAPI"]),
        _competency("C2", "Реализует SQL-запросы", "SQL", "apply", ["SQL"]),
        _competency("C3", "Пишет автотесты сервиса", "Тестирование", "analyze", ["pytest"]),
        _competency("C4", "Настраивает Docker окружение", "DevOps", "evaluate", ["Docker"]),
        _competency("C5", "Настраивает CI/CD пайплайн", "DevOps", "create", ["GitHub Actions"]),
    ]
    _edges, dag_payload = stage_catalog_to_dag.run(competencies)

    up = stage_dag_to_up.run({"role": "backend developer", "domain": "Backend"}, competencies, dag_payload)

    assert up.status == "built"
    assert up.rows
    assert up.metadata["planner_meta"]["artifact_project_count"] == len(up.rows)
    assert up.metadata["planner_meta"]["repeated_thread_count"] >= 1
    assert up.rows[0].metadata["artifact_family"]
    assert any(ref.role in {"reinforcement", "assessment"} for row in up.rows for ref in row.competency_refs)


def _node(tmp_id: str, name: str, block_key: str) -> PlanNode:
    return PlanNode(
        tmp_id=tmp_id,
        name=name,
        group="Backend",
        block_key=block_key,
        bloom=3,
        outcomes_know=(),
        outcomes_can=(f"Выполняет {name}",),
        outcomes_skills=(),
        tools=(),
    )


def _competency(tmp_id: str, name: str, coverage_area: str, bloom: str, tools: list[str]) -> Competency:
    return Competency(
        competency_id=tmp_id,
        canonical_name=name,
        group="Backend",
        coverage_area=coverage_area,
        indicators=[{"text": f"Демонстрирует: {name}", "bloom": bloom}],
        tools=tools,
        confidence=0.9,
        atomicity="atomic",
        resolution="new",
        status="accepted",
    )
