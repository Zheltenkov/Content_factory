from __future__ import annotations

import json

from app.core.models import Competency
from app.modules.curriculum.stages import stage_atomize, stage_normalize
from app.modules.curriculum.stages.pipeline import run_catalog_pipeline
from app.modules.curriculum.stages.stage_brief_to_catalog import BriefCatalogResult, run as brief_to_catalog


class FakeStructuredClient:
    model = "mock-model"

    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[dict] = []

    def complete(self, **kwargs):
        self.calls.append(kwargs)
        return json.dumps(self.payload, ensure_ascii=False)


def test_regression_pipeline_builds_catalog_dag_and_up_offline() -> None:
    result = run_catalog_pipeline(
        """
        Программа для junior backend-разработчика.
        Нужно обучить проектированию REST API, работе с SQL, тестированию сервисов и настройке CI/CD.
        Выпускник должен применять Git и Docker в командной разработке.
        """
    )

    assert len(result.competencies) >= 3
    assert all(isinstance(item, Competency) for item in result.competencies)
    assert result.dag_payload["acyclic"] is True
    assert result.dag_payload["nodes"] >= 3
    assert result.up.status == "built"
    assert result.up.rows
    assert result.up.rows[0].competency_refs
    assert result.profile_package().competencies == result.competencies


def test_brief_to_catalog_uses_core_structured_llm_client() -> None:
    payload = {
        "spec": {"role": "Data analyst", "domain": "Аналитика", "artifact_type": "program_brief"},
        "evidence_sources": [
            {
                "evidence_id": "E1",
                "claim": "Нужна SQL-аналитика",
                "source_type": "other",
                "snippet": "SQL и BI",
            }
        ],
        "competencies": [
            {
                "competency_id": "C1",
                "canonical_name": "Анализ данных с SQL",
                "group": "Аналитика",
                "coverage_area": "SQL",
                "indicators": [{"text": "Пишет SQL-запросы для анализа", "bloom": "apply"}],
                "tools": ["SQL"],
                "confidence": 0.9,
                "atomicity": "atomic",
                "resolution": "new",
                "status": "accepted",
            }
        ],
        "coverage_audit": {"mode": "llm"},
    }
    client = FakeStructuredClient(payload)

    result = brief_to_catalog("brief", client=client)

    assert isinstance(result, BriefCatalogResult)
    assert client.calls
    assert result.competencies[0].canonical_name == "Анализ данных с SQL"
    assert result.evidence_sources[0].evidence_id == "E1"


def test_atomize_and_normalize_keep_children_and_merge_duplicates() -> None:
    first = Competency(
        competency_id="C1",
        canonical_name="Анализ клиентов и настройка SQL",
        group="Продукт",
        coverage_area="analytics",
        indicators=[{"text": "Анализирует клиентов", "bloom": "analyze"}],
        atomicity="unknown",
        resolution="new",
        status="accepted",
    )
    duplicate = Competency(
        competency_id="C2",
        canonical_name="Настройка SQL",
        group="Продукт",
        coverage_area="analytics",
        indicators=[{"text": "Настраивает SQL", "bloom": "apply"}],
        atomicity="atomic",
        resolution="new",
        status="accepted",
    )

    atomized, atomize_report = stage_atomize.run([first, duplicate])
    normalized, normalize_report = stage_normalize.run(atomized, {"artifact_type": "program_brief"})

    assert atomize_report["split_count"] >= 2
    assert any(item.metadata.get("parent_competency_id") == "C1" for item in atomized)
    assert normalize_report["merged_count"] >= 1
    assert any(item.canonical_name == "Настройка SQL" for item in normalized)
