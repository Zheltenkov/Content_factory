from __future__ import annotations

import json
from pathlib import Path

import yaml

from app.core.models import Competency
from app.modules.curriculum.stages import stage_atomize, stage_normalize
from app.modules.curriculum.stages.pipeline import run_catalog_pipeline
from app.modules.curriculum.stages.skill_names import skill_name_from_topic
from app.modules.curriculum.stages.stage_brief_to_catalog import BriefCatalogResult, run as brief_to_catalog

ROOT = Path(__file__).resolve().parents[2]


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


def test_offline_intake_preserves_dense_backend_brief_semantics() -> None:
    result = run_catalog_pipeline(
        """
        Программа для junior backend-разработчика на 12 недель, 8 часов в неделю.
        Выпускник должен проектировать REST API, моделировать SQL-схему, писать SQL-запросы,
        настраивать Docker окружение, CI/CD pipeline, автотесты pytest, логирование и мониторинг.
        Нужно уметь работать с Git flow, code review, OpenAPI, PostgreSQL, очередями сообщений,
        безопасной обработкой токенов, деплоем сервиса и диагностикой инцидентов.
        Финальный проект: backend-сервис с REST API, БД, тестами, контейнеризацией и pipeline.
        """
    )

    accepted = [item for item in result.competencies if item.atomicity == "atomic" and item.status == "accepted"]
    accepted_names = {item.canonical_name for item in accepted}
    bloom_levels = {item.bloom_level for item in accepted}

    assert result.spec["must_include_areas_source"] == "topic_candidates"
    assert result.reports["atomize"]["non_skill_count"] >= 1
    assert result.reports["atomize"]["split_count"] >= 15
    assert result.dag_payload["acyclic"] is True
    assert result.dag_payload["nodes"] >= 18
    assert result.up.status == "built"
    assert len(result.up.rows) >= 18
    assert {"apply", "analyze", "create"} <= bloom_levels
    joined_names = " ".join(accepted_names).casefold()
    for semantic_marker in ("rest api", "sql", "docker", "ci/cd", "pytest", "инцидент"):
        assert semantic_marker in joined_names
    assert not any("8 часов" in name for name in accepted_names)


def test_offline_program_brief_uses_explicit_must_include_areas_first() -> None:
    result = run_catalog_pipeline(
        """
        Наименование продукта: Ветка основного обучения.
        Целевая аудитория: Участники, которые хотят запустить собственный бизнес.
        Продолжительность программы: 5-6 месяцев при нагрузке 20 часов в неделю.

        Какие темы или компетенции должны быть обязательно включены в программу?
        Обязательно должны быть включены следующие темы и компетенции:

        выявление проблемы и понимание клиента;
        исследование продукта и проверка гипотез;
        базовая инженерная дисциплина: репозиторий, непрерывная интеграция, тесты, выпуск версий;
        контроль качества результатов искусственного интеллекта, оценка данных, безопасность.

        Требования к участникам, пререквизиты: программа доступна для освоения с нуля.
        """
    )

    coverage = result.reports["coverage"]
    accepted = [item for item in result.competencies if item.atomicity == "atomic" and item.status == "accepted"]
    names = " ".join(item.canonical_name for item in accepted).casefold()

    assert result.spec["must_include_areas_source"] == "explicit"
    assert coverage["covered_count"] == 4
    assert len(coverage["rows"]) == 4
    assert "продолжительность программы" not in " ".join(coverage["areas"]).casefold()
    assert len(accepted) >= 8
    for marker in ("выявление проблемы", "проверка гипотез", "репозиторий", "качества"):
        assert marker in names


def test_skill_name_rules_do_not_embed_backend_spotcheck_repairs() -> None:
    rules_path = ROOT / "app/modules/curriculum/stages/skill_name_rules.yaml"
    payload = yaml.safe_load(rules_path.read_text(encoding="utf-8"))

    assert "fragment_repairs" not in payload
    assert "object_rewrites" not in payload
    assert "tech_terms" not in payload
    project_rule = next(item for item in payload["action_prefixes"] if item["pattern"].startswith("^проектировать"))
    assert project_rule["noun"] == "Проектирование"
    assert skill_name_from_topic("проектировать OpenAPI") == "Проектирование OpenAPI"


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
