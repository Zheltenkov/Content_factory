"""Runtime state, polling payloads and review actions for generator runs."""

from __future__ import annotations

import difflib
import hashlib
import io
import json
import zipfile
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from threading import RLock
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ValidationError

from app.core.methodology.revision import (
    MethodologistChangeRequest,
    MethodologyAssistantCommandParser,
    MethodologyAssistantParseContext,
    build_section_target_registry,
)
from app.modules.generator.service import GeneratorRun

GeneratorRunStatus = Literal["created", "running", "completed", "failed", "needs_review", "cancelled"]


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass(slots=True)
class StoredGeneratorRun:
    """Process-local durable view of one generator request for UI polling."""

    run_id: str
    request: dict[str, Any]
    status: GeneratorRunStatus = "created"
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)
    result: GeneratorRun | None = None
    error: str | None = None
    review_actions: list[dict[str, Any]] = field(default_factory=list)
    preview_markdown: str = ""
    preview_action_ids: list[str] = field(default_factory=list)
    approved_action_ids: list[str] = field(default_factory=list)


class GeneratorRunStore:
    """Small run registry used by polling, recent-run dashboard and review actions."""

    def __init__(self) -> None:
        self._runs: dict[str, StoredGeneratorRun] = {}
        self._lock = RLock()

    def create(self, request: dict[str, Any]) -> StoredGeneratorRun:
        run = StoredGeneratorRun(run_id=str(uuid4()), request=dict(request), status="running")
        with self._lock:
            self._runs[run.run_id] = run
        return run

    def get(self, run_id: str) -> StoredGeneratorRun | None:
        with self._lock:
            return self._runs.get(run_id)

    def complete(self, run_id: str, result: GeneratorRun) -> StoredGeneratorRun | None:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None or run.status == "cancelled":
                return run
            needs_review = bool(
                result.engine_result.gate_review
                and result.engine_result.gate_review.human_review_required
            )
            if result.engine_result.workflow and result.engine_result.workflow.status == "needs_review":
                needs_review = True
            run.result = result
            run.status = "needs_review" if needs_review else "completed"
            run.error = None
            run.updated_at = _now()
            return run

    def fail(self, run_id: str, error: str) -> StoredGeneratorRun | None:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None or run.status == "cancelled":
                return run
            run.status = "failed"
            run.error = error
            run.updated_at = _now()
            return run

    def cancel(self, run_id: str, comment: str | None = None) -> StoredGeneratorRun | None:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return None
            if run.status in {"created", "running", "needs_review"}:
                run.status = "cancelled"
                run.error = comment or "Генерация остановлена пользователем"
            run.review_actions.append(_action("cancelled", {"comment": comment or ""}))
            run.updated_at = _now()
            return run

    def recent(self, limit: int = 8) -> list[StoredGeneratorRun]:
        with self._lock:
            rows = sorted(self._runs.values(), key=lambda item: item.updated_at, reverse=True)
            return rows[: max(1, min(int(limit or 8), 50))]

    def record_review_action(self, run_id: str, action: str, payload: dict[str, Any] | None = None) -> StoredGeneratorRun | None:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return None
            payload = dict(payload or {})
            action_id = f"review-{len(run.review_actions) + 1}"
            if action == "request_changes":
                payload["change_request"] = _change_request(payload)
            if action == "preview_changes":
                _preview_changes(run)
            elif action in {"approve", "continue"}:
                run.status = "completed" if run.result is not None else run.status
                run.approved_action_ids.extend(_pending_change_ids(run))
            elif action == "approve_diff":
                _approve_preview(run)
                run.status = "completed" if run.result is not None else run.status
            elif action == "reject":
                run.status = "cancelled"
                run.error = payload.get("comment") or "Остановлено методологом"
            run.review_actions.append(_action(action, payload, action_id=action_id))
            run.updated_at = _now()
            return run

    def parse_assistant_command(self, run_id: str, message: str, selected_target_id: str = "") -> dict[str, Any] | None:
        run = self.get(run_id)
        if run is None:
            return None
        context = _revision_context(run)
        parser_context = MethodologyAssistantParseContext(
            checkpoint=_checkpoint(run),
            target_registry=build_section_target_registry(context).model_dump(mode="json"),
            review_state=review_state(run),
            selected_target_id=selected_target_id,
        )
        command = MethodologyAssistantCommandParser().parse(message, parser_context)
        if command.command == "approve":
            self.record_review_action(run_id, "approve", {"comment": message, "assistant_command": command.model_dump(mode="json")})
        else:
            request = command.to_change_request()
            self.record_review_action(
                run_id,
                "request_changes",
                {"change_request": request.model_dump(mode="json"), "assistant_command": command.model_dump(mode="json")},
            )
        return command.model_dump(mode="json")


GENERATOR_RUNS = GeneratorRunStore()


def run_result_payload(run_id: str, result: GeneratorRun) -> dict[str, Any]:
    """Serialize the generator result with legacy-compatible request id."""
    return {
        "run_id": run_id,
        "request_id": run_id,
        "context": result.context.model_dump(mode="json"),
        "document": result.document.model_dump(mode="json"),
        "rule_issues": [item.model_dump(mode="json") for item in result.engine_result.rule_issues],
        "rubric_json": _jsonable(result.engine_result.rubric_json),
        "gate_review": _jsonable(result.engine_result.gate_review),
    }


def status_payload(run: StoredGeneratorRun) -> dict[str, Any]:
    """Return the polling contract used by the generator UI."""
    workflow = _workflow_payload(run)
    result_payload = run_result_payload(run.run_id, run.result) if run.result is not None else None
    status = run.status
    return {
        "run_id": run.run_id,
        "request_id": run.run_id,
        "status": status,
        "created_at": run.created_at.isoformat(),
        "updated_at": run.updated_at.isoformat(),
        "progress": _progress(workflow, status),
        "current_stage": workflow.get("current_node") if workflow else None,
        "error": run.error,
        "workflow": workflow,
        "stage_results": _stage_results(run),
        "stage_reviews": _stage_reviews(run),
        "methodology": review_state(run),
        "review_actions": list(run.review_actions),
        "result": result_payload,
    }


def recent_payload(run: StoredGeneratorRun) -> dict[str, Any]:
    project = run.result.context.current_project_title if run.result else run.request.get("overrides", {}).get("title")
    return {
        "run_id": run.run_id,
        "request_id": run.run_id,
        "title": project or "README project",
        "status": run.status,
        "created_at": run.created_at.isoformat(),
        "updated_at": run.updated_at.isoformat(),
        "plan_id": run.request.get("plan_id"),
        "project_order": run.request.get("project_order"),
        "profile_id": run.request.get("profile_id"),
        "download_url": f"/generator/runs/{run.run_id}/archive" if run.result is not None else None,
    }


def review_state(run: StoredGeneratorRun) -> dict[str, Any]:
    """Build the review state expected by legacy methodology UI widgets."""
    context = _revision_context(run)
    registry = build_section_target_registry(context)
    pending_ids = _pending_change_ids(run)
    return {
        "request_id": run.run_id,
        "review_state": run.status,
        "checkpoint": _checkpoint(run),
        "target_registry": registry.model_dump(mode="json"),
        "review_actions": list(run.review_actions),
        "pending_change_ids": pending_ids,
        "preview_action_ids": list(run.preview_action_ids),
        "approved_action_ids": list(run.approved_action_ids),
        "diff_approvable_action_ids": list(run.preview_action_ids),
        "requires_diff_approval": bool(run.preview_action_ids),
        "preview_hash": _hash(run.preview_markdown) if run.preview_markdown else "",
        "preview_markdown": run.preview_markdown,
        "revision_results": _preview_results(run),
        "preview_has_rejections": False,
    }


def build_archive(run: StoredGeneratorRun) -> bytes:
    """Build a ZIP archive equivalent to the legacy generator download."""
    if run.result is None:
        raise ValueError("README ещё не готов")
    document = run.result.document
    report = {
        "run_id": run.run_id,
        "status": run.status,
        "context": run.result.context.model_dump(mode="json"),
        "workflow": _workflow_payload(run),
        "stage_results": _stage_results(run),
        "stage_reviews": _stage_reviews(run),
        "review_actions": run.review_actions,
        "metadata": document.metadata,
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.md", document.markdown)
        archive.writestr("rubric.json", json.dumps(run.result.engine_result.rubric_json, ensure_ascii=False, indent=2, default=str))
        archive.writestr("report.json", json.dumps(report, ensure_ascii=False, indent=2, default=str))
        artifact_refs = [item.model_dump(mode="json") for item in document.artifacts]
        if artifact_refs:
            archive.writestr("artifacts.json", json.dumps(artifact_refs, ensure_ascii=False, indent=2, default=str))
    return buffer.getvalue()


def _preview_changes(run: StoredGeneratorRun) -> None:
    if run.result is None:
        return
    markdown = run.preview_markdown or run.result.document.markdown
    action_ids: list[str] = []
    for index, action in enumerate(run.review_actions, 1):
        if action.get("action") != "request_changes":
            continue
        action_id = str(action.get("id") or f"review-{index}")
        if action_id in run.approved_action_ids:
            continue
        details = action.get("details") if isinstance(action.get("details"), dict) else {}
        request_payload = details.get("change_request") if isinstance(details, dict) else None
        if not isinstance(request_payload, dict):
            continue
        request = MethodologistChangeRequest.model_validate(request_payload)
        markdown = _apply_preview_note(markdown, request)
        action_ids.append(action_id)
    run.preview_markdown = markdown
    run.preview_action_ids = action_ids


def _preview_results(run: StoredGeneratorRun) -> list[dict[str, Any]]:
    if not run.result or not run.preview_markdown:
        return []
    diff = list(
        difflib.unified_diff(
            run.result.document.markdown.splitlines(),
            run.preview_markdown.splitlines(),
            fromfile="README.md",
            tofile="README.preview.md",
            lineterm="",
        )
    )[:120]
    return [
        {
            "action_id": action_id,
            "status": "applied",
            "target_kind": "markdown_section",
            "scope": "local_section_only",
            "changed": bool(diff),
            "diff_preview": diff,
        }
        for action_id in run.preview_action_ids
    ]


def _approve_preview(run: StoredGeneratorRun) -> None:
    if run.result is None or not run.preview_markdown:
        return
    document = run.result.document.model_copy(update={"markdown": run.preview_markdown})
    run.result.engine_result.documents["generator.evaluation"] = document
    run.result.engine_result.context["markdown"] = run.preview_markdown
    run.result = replace(run.result, document=document)
    run.approved_action_ids = list(dict.fromkeys([*run.approved_action_ids, *run.preview_action_ids]))
    run.preview_action_ids = []


def _apply_preview_note(markdown: str, request: MethodologistChangeRequest) -> str:
    note = "\n\n> Методологическая правка: " + request.instruction.strip()
    context = {"markdown": markdown}
    target = build_section_target_registry(context).find(request.target_selector, kind="markdown_section", stage=request.target_stage)
    if target and target.end is not None:
        return markdown[: target.end].rstrip() + note + "\n\n" + markdown[target.end:].lstrip()
    return markdown.rstrip() + "\n\n## Методологические правки\n" + f"- {request.instruction.strip()}\n"


def _change_request(payload: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("change_request") if isinstance(payload.get("change_request"), dict) else payload
    try:
        request = MethodologistChangeRequest.model_validate(raw)
    except ValidationError:
        request = MethodologistChangeRequest(
            target_stage=_stage(raw.get("target_stage")),
            target_selector=str(raw.get("target_selector") or ""),
            scope=_scope(raw.get("scope")),
            instruction=str(raw.get("instruction") or raw.get("comment") or "Уточнить README по замечанию методолога."),
            issue_codes=_string_list(raw.get("issue_codes")),
            forbidden_changes=_string_list(raw.get("forbidden_changes")),
            expected_outcome=str(raw.get("expected_outcome") or ""),
        )
    return request.model_dump(mode="json")


def _stage(value: Any) -> Any:
    allowed = {"context", "task_planning", "title", "annotation", "skeleton", "theory", "practice", "dataset", "final"}
    text = str(value or "final")
    return text if text in allowed else "final"


def _scope(value: Any) -> Any:
    allowed = {"local_section_only", "task_only", "materials_only"}
    text = str(value or "local_section_only")
    return text if text in allowed else "local_section_only"


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        raw = value
    else:
        raw = str(value or "").split(",")
    return [str(item).strip() for item in raw if str(item).strip()]


def _revision_context(run: StoredGeneratorRun) -> dict[str, Any]:
    if run.result is None:
        return {}
    metadata = run.result.document.metadata or {}
    context = dict(run.result.engine_result.context or {})
    context["markdown"] = run.preview_markdown or run.result.document.markdown
    context["dataset_files"] = metadata.get("dataset_files") or context.get("dataset_files") or []
    return context


def _checkpoint(run: StoredGeneratorRun) -> dict[str, Any]:
    stages = _stage_results(run)
    last = stages[-1] if stages else {}
    return {
        "id": last.get("node_id") or "final",
        "stage": last.get("node_id") or "final",
        "node_id": last.get("node_id") or "final",
        "title": last.get("stage_name") or "Итоговый README",
        "resume_from_node": last.get("node_id") or "evaluation",
        "artifact": {"requirements_matrix": _rubric_issues(run)},
    }


def _pending_change_ids(run: StoredGeneratorRun) -> list[str]:
    return [str(action.get("id")) for action in run.review_actions if action.get("action") == "request_changes" and action.get("id")]


def _rubric_issues(run: StoredGeneratorRun) -> list[dict[str, Any]]:
    if run.result is None:
        return []
    issues = run.result.engine_result.rubric_json.get("issues")
    return issues if isinstance(issues, list) else []


def _workflow_payload(run: StoredGeneratorRun) -> dict[str, Any]:
    if run.result and run.result.engine_result.workflow:
        return run.result.engine_result.workflow.model_dump(mode="json")
    return {
        "run_id": run.run_id,
        "status": run.status,
        "current_node": "generator",
        "progress_current": 1 if run.status == "running" else 0,
        "progress_total": 8,
        "metadata": {"profile_id": run.request.get("profile_id")},
    }


def _stage_results(run: StoredGeneratorRun) -> list[dict[str, Any]]:
    if not run.result:
        return []
    return [item.model_dump(mode="json") for item in run.result.engine_result.stage_results]


def _stage_reviews(run: StoredGeneratorRun) -> dict[str, Any]:
    if not run.result:
        return {}
    return {key: value.model_dump(mode="json") for key, value in run.result.engine_result.stage_reviews.items()}


def _progress(workflow: dict[str, Any], status: str) -> int:
    if status == "completed":
        return 100
    total = int(workflow.get("progress_total") or 0)
    current = int(workflow.get("progress_current") or 0)
    return max(1, min(99, round(current * 100 / total))) if total else (8 if status == "running" else 0)


def _action(action: str, details: dict[str, Any], *, action_id: str | None = None) -> dict[str, Any]:
    return {"id": action_id or str(uuid4()), "action": action, "details": details, "created_at": _now().isoformat()}


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
