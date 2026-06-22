from __future__ import annotations

import pytest
from sqlalchemy import create_engine

from app.core.methodology.gate import MethodologyGateInterrupt
from app.core.methodology.revision import (
    HumanApprovalCheckpointPolicy,
    MethodologistChangeRequest,
    MethodologyAssistantCommandParser,
    MethodologyAssistantParseContext,
    MethodologyRevisionRepo,
    ScopedRevisionExecutor,
    build_checkpoint,
    build_section_target_registry,
    create_revision_schema,
    validate_methodologist_change_request,
)
from app.core.methodology.revision.contracts import ScopedRevisionResult


class MockLLM:
    def __init__(self, *responses: str) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def complete(self, **kwargs: object) -> str:
        self.calls.append(dict(kwargs))
        return self.responses.pop(0)


def test_assistant_parser_builds_scoped_change_request_and_guards_solution_leak() -> None:
    context = _context()
    registry = build_section_target_registry(context).model_dump(mode="json")
    parser = MethodologyAssistantCommandParser()

    command = parser.parse(
        "Упрости задание 1 в главе 3, но не меняй соседние задачи",
        MethodologyAssistantParseContext(checkpoint={"id": "practice", "stage": "practice"}, target_registry=registry),
    )
    request = command.to_change_request()

    assert command.command == "simplify_task"
    assert command.target_stage == "practice"
    assert request.scope == "task_only"
    assert "не добавлять готовые ответы" in request.forbidden_changes

    conflicts = validate_methodologist_change_request(
        MethodologistChangeRequest(
            target_stage="practice",
            target_selector="Глава 3",
            instruction="Добавь готовое решение и answer key в материалы.",
        )
    )
    assert {item.code for item in conflicts} >= {"solution_leak_request", "raw_evidence_contract_violation"}


def test_scoped_revision_edits_only_target_section_and_builds_resume_plan() -> None:
    context = _context()
    action = {
        "action": "changes_requested",
        "timestamp": "1",
        "details": {
            "change_request": MethodologistChangeRequest(
                target_stage="theory",
                target_selector="Глава 2",
                instruction="Добавь объяснение OpenAPI, сохрани кодовый блок.",
            ).model_dump(mode="json")
        },
    }
    context["methodology_review_actions"] = [action]
    executor = ScopedRevisionExecutor(MockLLM("## Глава 2. Теория\nНовая теория про OpenAPI.\n[[[BLOCK_0]]]"))

    results = executor.apply_pending_change_requests(context)
    resume = executor.build_resume_plan(4, ["head", "theory", "practice", "global_quality", "evaluation"], results)

    assert results[0].status == "applied"
    assert results[0].target_kind == "markdown_section"
    assert "Новая теория про OpenAPI" in context["markdown"]
    assert "print('keep')" in context["markdown"]
    assert "Практика" in context["markdown"]
    assert context["theory_parts"] == []
    assert context["practice_tasks"] == []
    assert context["rubric_json"] == {}
    assert resume.moved_back is True
    assert resume.resume_node == "practice"
    assert "global_quality" in resume.invalidated_nodes


def test_material_revision_rejects_non_raw_output_after_llm_edit() -> None:
    context = {
        "dataset_files": [{"path": "materials/task_01_source_notes.md", "data": b"raw notes"}],
        "rubric_json": {"passed": True},
    }
    request = MethodologistChangeRequest(
        target_stage="dataset",
        target_selector="materials/task_01_source_notes.md",
        scope="materials_only",
        instruction="Сделай заметки яснее, не добавляй решения.",
    )
    result = ScopedRevisionExecutor(MockLLM("Готовое решение и заполненная матрица")).apply_change_request(
        context,
        request,
        action_id="material-1",
    )

    assert result.status == "rejected"
    assert result.target_kind == "material_file"
    assert any("raw_evidence_contract_violation" in issue for issue in result.issues)
    assert context["dataset_files"][0]["data"] == b"raw notes"


def test_checkpoint_policy_and_revision_repo_roundtrip_with_rollback() -> None:
    context = _context()
    checkpoint = build_checkpoint("practice", context)
    assert checkpoint is not None
    policy = HumanApprovalCheckpointPolicy({"practice"})

    with pytest.raises(MethodologyGateInterrupt) as error:
        policy.maybe_raise("practice", context)
    assert error.value.context["checkpoint"]["artifact_hash"] == checkpoint.artifact_hash

    engine = create_engine("sqlite:///:memory:")
    create_revision_schema(engine)
    repo = MethodologyRevisionRepo(engine)
    session = repo.create_session(run_id="run-1", artifact_ref="project:1", payload={"source": "test"})
    saved = repo.save_checkpoint(session.id, checkpoint, context_snapshot=context)
    request = MethodologistChangeRequest(target_stage="practice", target_selector="Глава 3", instruction="Упрости задачу 1.")
    change = repo.record_change_request(session.id, request, action_id="action-1", checkpoint_row_id=saved.id)

    pending = repo.pending_change_requests(session.id)
    assert pending[0].action_id == "action-1"
    assert pending[0].request.instruction == "Упрости задачу 1."

    stored = repo.store_revision_result(
        session.id,
        change.action_id,
        ScopedRevisionResult(
            action_id=change.action_id,
            status="applied",
            target_kind="markdown_section",
            target_stage="practice",
            scope="local_section_only",
            changed=True,
        ),
    )
    restored_context = repo.rollback_to_checkpoint(saved.id)

    assert stored is True
    assert repo.pending_change_requests(session.id) == []
    assert restored_context is not None
    assert restored_context["markdown"] == context["markdown"]
    assert repo.load_checkpoint(saved.id).status == "rolled_back"


def _context() -> dict[str, object]:
    return {
        "title": "REST API",
        "annotation": {"text": "Проект про API.", "chars": 15},
        "markdown": (
            "# REST API\n\n"
            "Аннотация проекта.\n\n"
            "## Глава 1. Введение\n\nКонтекст.\n\n"
            "## Глава 2. Теория\n\nСтарая теория.\n\n```python\nprint('keep')\n```\n\n"
            "## Глава 3. Практика\n\n### Задание 1. API\n\nСоберите endpoint.\n"
        ),
        "theory_parts": [{"title": "Old"}],
        "practice_tasks": [{"title": "Task 1"}],
        "dataset_files": [{"path": "materials/task_01_source_notes.md", "data": b"raw notes"}],
        "practice_critic_issues": ["old"],
        "rubric_json": {"passed": True, "issues": []},
    }
