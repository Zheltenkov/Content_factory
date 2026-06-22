"""Human approval checkpoints and rollback-friendly artifact snapshots."""

from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any

from app.core.methodology.gate.decision import MethodologyGateInterrupt
from app.core.methodology.revision.contracts import HumanApprovalCheckpoint


class HumanApprovalCheckpointPolicy:
    """Deterministic policy that pauses workflow nodes for methodologist approval."""

    DEFAULT_CHECKPOINTS = {"task_planning", "title", "structure", "theory", "practice", "quality", "evaluation", "translation"}
    CHECKPOINT_NODE_MAP = {
        "context": "context",
        "task_planning": "task_planning",
        "title_annotation": "title",
        "skeleton": "structure",
        "theory": "theory",
        "practice": "practice",
        "global_quality": "quality",
        "evaluation": "evaluation",
        "translate": "translation",
        "finalize": "finalize",
    }

    def __init__(self, checkpoints: set[str] | None = None) -> None:
        self.checkpoints = checkpoints or set()

    @classmethod
    def from_env(cls, *, enabled_by_default: bool = False) -> "HumanApprovalCheckpointPolicy":
        raw = os.getenv("METHODOLOGY_HUMAN_CHECKPOINTS")
        if raw is None:
            raw = "all" if enabled_by_default else ""
        normalized = raw.strip().lower()
        if normalized in {"", "0", "false", "off", "none", "disabled"}:
            return cls(set())
        if normalized in {"1", "true", "on", "enabled", "all"}:
            return cls(set(cls.DEFAULT_CHECKPOINTS))
        checkpoints = {part.strip() for part in normalized.split(",") if part.strip()}
        if "all" in checkpoints:
            checkpoints.remove("all")
            checkpoints.update(cls.DEFAULT_CHECKPOINTS)
        if "annotation" in checkpoints:
            checkpoints.remove("annotation")
            checkpoints.add("title")
        return cls(checkpoints)

    def maybe_raise(self, node_id: str, context: dict[str, Any]) -> None:
        checkpoint_id = self.CHECKPOINT_NODE_MAP.get(node_id)
        if not checkpoint_id or checkpoint_id not in self.checkpoints:
            return
        checkpoint = build_checkpoint(checkpoint_id, context)
        if checkpoint is None:
            return
        checkpoint_payload = checkpoint.model_dump(mode="json")
        if _checkpoint_already_approved(context, checkpoint_payload):
            context["last_skipped_human_approval_checkpoint"] = checkpoint_payload
            return
        context["human_approval_checkpoint"] = checkpoint_payload
        context.setdefault("human_approval_checkpoints", []).append(checkpoint_payload)
        raise MethodologyGateInterrupt(
            checkpoint.summary,
            context={"phase": checkpoint.stage, "error_type": "HumanApprovalCheckpoint", "checkpoint": checkpoint_payload},
        )


def build_checkpoint(checkpoint_id: str, context: dict[str, Any]) -> HumanApprovalCheckpoint | None:
    builders = {
        "context": _context_checkpoint,
        "task_planning": _task_planning_checkpoint,
        "title": _title_checkpoint,
        "structure": _structure_checkpoint,
        "theory": _theory_checkpoint,
        "practice": _practice_checkpoint,
        "quality": _quality_checkpoint,
        "evaluation": _evaluation_checkpoint,
        "translation": _translation_checkpoint,
        "finalize": _finalize_checkpoint,
    }
    if builder := builders.get(checkpoint_id):
        checkpoint = builder(context)
        checkpoint.artifact_hash = checkpoint_artifact_hash(checkpoint)
        return checkpoint
    return None


def build_requirement_matrix(context: dict[str, Any], markdown: str | None = None) -> list[dict[str, Any]]:
    """Build compact deterministic pass/fail rows for review UI and assistant targeting."""

    text = str(markdown if markdown is not None else context.get("markdown") or "")
    chapter_2 = _markdown_section(text, "глава 2")
    chapter_3 = _markdown_section(text, "глава 3")
    rubric = context.get("rubric_json") if isinstance(context.get("rubric_json"), dict) else {}
    issues = rubric.get("issues") if isinstance(rubric, dict) else []
    return [
        _matrix_item("readme.h1", "README имеет H1", bool(re.search(r"^#\s+.+$", text, flags=re.M)), _first_heading(text)),
        _matrix_item("readme.theory", "Глава 2 присутствует", bool(chapter_2.strip()), _truncate_text(chapter_2, 180)),
        _matrix_item("readme.practice", "Глава 3 присутствует", bool(chapter_3.strip()), _truncate_text(chapter_3, 180)),
        _matrix_item("review.issues", "Методологические issues отсутствуют", not issues, f"issues: {len(issues or [])}"),
    ]


def checkpoint_artifact_hash(checkpoint: HumanApprovalCheckpoint) -> str:
    payload = {
        "id": checkpoint.id,
        "stage": checkpoint.stage,
        "node_id": checkpoint.node_id,
        "resume_from_node": checkpoint.resume_from_node,
        "artifact": checkpoint.artifact,
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]


def _context_checkpoint(context: dict[str, Any]) -> HumanApprovalCheckpoint:
    artifact = {
        "title": str(context.get("title") or _seed_title(context)),
        "summary": "Контекст проекта готов и будет использован downstream.",
        "learning_outcomes": _compact_list(_get_value(context.get("seed"), "learning_outcomes"), limit=10),
        "skills": _compact_list(_get_value(context.get("seed"), "skills"), limit=10),
        "warnings_count": len(context.get("warnings") or []),
    }
    return HumanApprovalCheckpoint(id="context", stage="context", node_id="context", title="Проверка контекста", summary="Подтвердите входные данные перед планированием.", resume_from_node="task_planning", allowed_targets=["context", "seed", "curriculum_context"], artifact=artifact)


def _task_planning_checkpoint(context: dict[str, Any]) -> HumanApprovalCheckpoint:
    artifact = {
        "title": _seed_title(context),
        "practice_plan": _compact_value(context.get("practice_plan") or context.get("task_plan")),
        "storytelling": _compact_value(context.get("storytelling") or context.get("story_map_contract")),
    }
    return HumanApprovalCheckpoint(id="task_planning", stage="task_planning", node_id="task_planning", title="Проверка замысла и плана", summary="Подтвердите план задач перед генерацией README.", resume_from_node="title_annotation", allowed_targets=["task_planning", "practice_plan", "storytelling"], artifact=artifact)


def _title_checkpoint(context: dict[str, Any]) -> HumanApprovalCheckpoint:
    artifact = {"title": str(context.get("title") or ""), "annotation": _annotation_text(context.get("annotation"))}
    return HumanApprovalCheckpoint(id="title", stage="title", node_id="title_annotation", title="Проверка названия проекта", summary="Подтвердите название и аннотацию.", resume_from_node="skeleton", allowed_targets=["title", "annotation"], artifact=artifact)


def _structure_checkpoint(context: dict[str, Any]) -> HumanApprovalCheckpoint:
    markdown = str(context.get("markdown") or "")
    artifact = {"title": str(context.get("title") or ""), "structure_outline": markdown_outline(markdown), "requirements_matrix": build_requirement_matrix(context, markdown), "markdown_excerpt": markdown, "markdown_sections": markdown_subsections(markdown, min_level=2)}
    return HumanApprovalCheckpoint(id="structure", stage="skeleton", node_id="skeleton", title="Проверка структуры README", summary="Подтвердите структуру перед генерацией теории.", resume_from_node="theory", allowed_targets=["title", "annotation", "chapter_1", "chapter_2", "chapter_3", "skeleton"], artifact=artifact)


def _theory_checkpoint(context: dict[str, Any]) -> HumanApprovalCheckpoint:
    markdown = _markdown_section(str(context.get("markdown") or ""), "глава 2")
    artifact = {"title": str(context.get("title") or ""), "summary": f"Сгенерировано частей теории: {len(context.get('theory_parts') or [])}", "theory_parts": _compact_list(context.get("theory_parts"), limit=12), "requirements_matrix": build_requirement_matrix(context), "markdown_excerpt": markdown, "markdown_sections": markdown_subsections(markdown)}
    return HumanApprovalCheckpoint(id="theory", stage="theory", node_id="theory", title="Проверка теории", summary="Глава 2 готова. Подтвердите перед практикой.", resume_from_node="practice", allowed_targets=["chapter_2", "theory"], artifact=artifact)


def _practice_checkpoint(context: dict[str, Any]) -> HumanApprovalCheckpoint:
    markdown = _markdown_section(str(context.get("markdown") or ""), "глава 3")
    dataset_files = [{"path": str(item.get("path") or ""), "bytes": _data_size(item.get("data"))} for item in context.get("dataset_files") or [] if isinstance(item, dict)]
    artifact = {"title": str(context.get("title") or ""), "summary": f"Сгенерировано задач: {len(context.get('practice_tasks') or [])}, materials-файлов: {len(dataset_files)}", "practice_tasks": _compact_list(context.get("practice_tasks"), limit=12), "dataset_files": dataset_files, "requirements_matrix": build_requirement_matrix(context), "markdown_excerpt": markdown, "markdown_sections": markdown_subsections(markdown)}
    return HumanApprovalCheckpoint(id="practice", stage="practice", node_id="practice", title="Проверка практики и материалов", summary="Глава 3 и materials готовы. Подтвердите перед редактурой.", resume_from_node="global_quality", allowed_targets=["chapter_3", "practice", "dataset", "materials"], artifact=artifact)


def _quality_checkpoint(context: dict[str, Any]) -> HumanApprovalCheckpoint:
    markdown = str(context.get("markdown") or "")
    artifact = {"title": str(context.get("title") or ""), "markdown_chars": len(markdown), "warnings_count": len(context.get("warnings") or []), "requirements_matrix": build_requirement_matrix(context, markdown), "markdown_excerpt": markdown, "markdown_sections": markdown_subsections(markdown, min_level=2)}
    return HumanApprovalCheckpoint(id="quality", stage="final", node_id="global_quality", title="Проверка редакторской сборки", summary="Подтвердите README перед финальной оценкой.", resume_from_node="evaluation", allowed_targets=["annotation", "chapter_1", "chapter_2", "chapter_3", "final"], artifact=artifact)


def _evaluation_checkpoint(context: dict[str, Any]) -> HumanApprovalCheckpoint:
    rubric = context.get("rubric_json") if isinstance(context.get("rubric_json"), dict) else {}
    artifact = {"title": str(context.get("title") or ""), "summary": "Финальная оценка завершена.", "rubric": rubric, "issues_count": len(rubric.get("issues") or [])}
    return HumanApprovalCheckpoint(id="evaluation", stage="final", node_id="evaluation", title="Проверка финальной оценки", summary="Методолог может подтвердить export или запросить точечные правки.", resume_from_node="finalize", allowed_targets=["annotation", "chapter_1", "chapter_2", "chapter_3", "final"], artifact=artifact)


def _translation_checkpoint(context: dict[str, Any]) -> HumanApprovalCheckpoint:
    markdown = str(context.get("translated_markdown") or context.get("markdown") or "")
    artifact = {"title": str(context.get("title") or _seed_title(context)), "target_language": str(context.get("target_language") or ""), "markdown_chars": len(markdown), "requirements_matrix": build_requirement_matrix(context, markdown), "markdown_excerpt": markdown, "markdown_sections": markdown_subsections(markdown, min_level=2)}
    return HumanApprovalCheckpoint(id="translation", stage="translation", node_id="translate", title="Проверка перевода README", summary="Подтвердите перевод перед финальной сборкой.", resume_from_node="finalize", allowed_targets=["translation", "annotation", "chapter_1", "chapter_2", "chapter_3", "final"], artifact=artifact)


def _finalize_checkpoint(context: dict[str, Any]) -> HumanApprovalCheckpoint:
    markdown = str(context.get("translated_markdown") or context.get("markdown") or "")
    artifact = {"title": str(context.get("title") or _seed_title(context)), "markdown_chars": len(markdown), "requirements_matrix": build_requirement_matrix(context, markdown), "markdown_excerpt": markdown, "markdown_sections": markdown_subsections(markdown, min_level=2)}
    return HumanApprovalCheckpoint(id="finalize", stage="final", node_id="finalize", title="Проверка финального результата", summary="Подтвердите завершение генерации.", resume_from_node="completed", allowed_targets=["final", "export", "materials"], artifact=artifact)


def markdown_outline(markdown: str) -> list[dict[str, Any]]:
    return [{"level": len(match.group(1)), "title": match.group(2).strip()} for match in re.finditer(r"^(#{1,6})\s+(.+?)\s*$", markdown or "", flags=re.M)]


def markdown_subsections(section_markdown: str, *, min_level: int = 3) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    matches = list(re.finditer(r"^(#{1,6})\s+(.+?)\s*$", section_markdown or "", flags=re.M))
    for index, match in enumerate(matches):
        level = len(match.group(1))
        if level < min_level:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(section_markdown)
        result.append({"title": match.group(2).strip(), "markdown": section_markdown[match.start() : end].strip()})
    return result


def _markdown_section(markdown: str, heading_marker: str, limit: int = 2200) -> str:
    pattern = re.compile(rf"^(#{{1,6}})\s+.*{re.escape(heading_marker)}.*$", flags=re.I | re.M)
    if not (match := pattern.search(markdown or "")):
        return ""
    level = len(match.group(1))
    end = len(markdown)
    for next_match in re.finditer(r"^(#{1,6})\s+.+$", markdown[match.end() :], flags=re.M):
        if len(next_match.group(1)) <= level:
            end = match.end() + next_match.start()
            break
    return _truncate_text(markdown[match.start() : end].strip(), limit)


def _checkpoint_already_approved(context: dict[str, Any], checkpoint: dict[str, Any]) -> bool:
    approved = context.get("approved_human_approval_checkpoints") or []
    return any(isinstance(item, dict) and item.get("artifact_hash") == checkpoint.get("artifact_hash") for item in approved)


def _matrix_item(item_id: str, title: str, passed: bool, evidence: str) -> dict[str, Any]:
    return {"id": item_id, "title": title, "status": "pass" if passed else "fail", "passed": passed, "evidence": evidence or "-"}


def _first_heading(markdown: str) -> str:
    return match.group(1).strip() if (match := re.search(r"^#\s+(.+?)\s*$", markdown or "", flags=re.M)) else "-"


def _annotation_text(annotation: Any) -> str:
    return str(annotation.get("text") or "") if isinstance(annotation, dict) else str(getattr(annotation, "text", "") or "")


def _seed_title(context: dict[str, Any]) -> str:
    return str(context.get("title") or _get_value(context.get("seed"), "title") or _get_value(context.get("curriculum_context"), "current_project_title") or "")


def _compact_list(value: Any, *, limit: int = 8) -> list[Any]:
    return [_compact_value(item) for item in list(value or [])[:limit]] if isinstance(value, list | tuple) else []


def _compact_value(value: Any, *, text_limit: int = 260) -> Any:
    if isinstance(value, dict):
        return {key: _compact_value(item, text_limit=text_limit) for key, item in list(value.items())[:10]}
    if isinstance(value, list | tuple):
        return [_compact_value(item, text_limit=text_limit) for item in list(value)[:8]]
    if isinstance(value, str):
        return _truncate_text(value, text_limit)
    return value


def _get_value(value: Any, field: str) -> Any:
    if isinstance(value, dict):
        return value.get(field)
    return getattr(value, field, None)


def _data_size(data: Any) -> int:
    return len(data) if isinstance(data, bytes) else len(str(data or "").encode("utf-8"))


def _truncate_text(text: str, limit: int) -> str:
    value = (text or "").strip()
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"
