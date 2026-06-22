from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.core.llm.client import LLMClient, LLMRequest, LLMResponse
from app.main import create_app
from app.modules.checker.reverse_extraction.service import ReverseExtractionService
from app.modules.curriculum.repo import CurriculumCatalogRepo, create_catalog_schema


class MockTransport:
    def __init__(self, *responses: str) -> None:
        self.responses = list(responses)
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(content=self.responses.pop(0), model=request.model)


def test_reverse_extraction_uses_typed_llm_and_entity_audit() -> None:
    transport = MockTransport(
        """
        {
          "title_seed": "REST API",
          "project_description": "Студент проектирует сервис.",
          "learning_outcomes": ["Проектирует REST API"],
          "required_tools": ["Python", "Docker"],
          "skills": ["Проектирование REST API", "Настройка CI/CD"],
          "tasks_count": 1,
          "theory_parts": ["HTTP"],
          "include_formulas": false,
          "include_tables": false,
          "include_diagrams": true,
          "sjm": "Команда запускает сервис"
        }
        """,
        '{"tasks_count": 2, "task_descriptions": ["API", "Docker"], "confidence": "high"}',
    )
    service = ReverseExtractionService(client_factory=lambda: LLMClient(model="gpt-4o-mini", provider="mock", transport=transport))

    result = service.extract(_readme())

    assert result.partial_seed.title_seed == "REST API"
    assert result.partial_seed.tasks_count == 2
    assert result.tasks.confidence == "high"
    assert {entity.entity_type for entity in result.entities} >= {"link", "image", "technology", "date"}
    assert len(transport.requests) == 2


def test_reverse_reconciliation_writes_missing_skills_to_review_queue() -> None:
    service = ReverseExtractionService(client_factory=lambda: _unused_llm())
    repo = _repo()
    repo.upsert_skill("Проектирование REST API")
    extraction = service.extract(_readme(), client=_unused_llm())
    extraction.partial_seed.skills = ["Проектирование REST API", "Настройка CI/CD"]

    issues = service.reconcile_with_catalog(extraction, repo, source_ref="generator://run/1", expected_tasks_count=3)
    reviews = repo.list_review_queue(status="open")

    assert {issue.reason_code.split(":")[0] for issue in issues} == {
        "reverse_missing_skill",
        "reverse_task_count_mismatch",
    }
    assert len(reviews) == 2
    assert any("Настройка CI/CD" in row["details"] for row in reviews)


def test_reverse_extract_endpoint_without_persist_does_not_require_database() -> None:
    client = TestClient(create_app())

    response = client.post("/checker/reverse-extract", json={"markdown": _readme()})

    assert response.status_code == 200
    assert response.json()["partial_seed"]["title_seed"] == "REST API"


def _readme() -> str:
    return """
# REST API

Проект учит проектировать REST API на Python в 2026 году. См. https://example.com/spec.
![schema](assets/schema.png)

## Глава 1. Введение

После изучения студент сможет описать OpenAPI-контракт.

## Глава 3. Практика

### Задача 1
Разработай API.

### Задача 2
Настрой Docker и CI/CD.
"""


def _repo() -> CurriculumCatalogRepo:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    create_catalog_schema(engine)
    return CurriculumCatalogRepo(engine)


def _unused_llm() -> LLMClient:
    return LLMClient(model="gpt-4o-mini", provider="mock", transport=MockTransport("not-json", "not-json"))
