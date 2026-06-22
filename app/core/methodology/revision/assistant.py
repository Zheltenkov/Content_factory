"""Deterministic methodology assistant command parser."""

from __future__ import annotations

import re
from typing import get_args

from pydantic import ValidationError

from app.core.methodology.revision.contracts import (
    AssistantCommandType,
    ChangeScope,
    ChangeTargetStage,
    MethodologyAssistantCommand,
    MethodologyAssistantParseContext,
)
from app.core.methodology.revision.target_registry import SectionTarget, SectionTargetRegistry

_TARGET_STAGES = set(get_args(ChangeTargetStage))
_SCOPES = set(get_args(ChangeScope))
_STAGE_ALIASES = {"structure": "skeleton", "quality": "final", "evaluation": "final", "readme": "final", "README": "final"}
_APPROVE_RE = re.compile(r"^\s*/?(?:approve|continue|go|ok|продолж(?:ить|ай)?|подтверждаю|утверждаю|готово|все\s+ок|всё\s+ок)\b", re.I)
_CHANGE_MARKERS_RE = re.compile(r"(?:но|исправ|измени|правк|упрост|проще|добав|пример|критер|failed|fix|change|simplify|example|диаграм|mermaid|таблиц)", re.I)
_DISPLAY_BLOCK_RE = re.compile(r"(?:диаграм|mermaid|схем|таблиц|markdown\s*table|\btable\b)", re.I)
_SIMPLIFY_RE = re.compile(r"(?:упрост|проще|simplify|make\s+.+?simpler)", re.I)
_ADD_EXAMPLE_RE = re.compile(r"(?:пример|examples?|добавь\s+.{0,80}пример)", re.I)
_FIX_FAILED_RE = re.compile(r"(?:критер|criteria|failed|не\s*пройден|непройден|провален|warning)", re.I)
_REGENERATE_RE = re.compile(r"(?:перегенер|сгенерируй\s+заново|пересобер|regenerate|rerun|rebuild)", re.I)
_TASK_NUMBER_RE = re.compile(r"(?:задач[аеиу]?|задани[еяю]|task)\s*#?\s*(\d+)", re.I)
_STAGE_HINTS: tuple[tuple[str, ChangeTargetStage], ...] = (
    (r"(?:глава\s*3|chapter\s*3|практик|задани|задач|practice)", "practice"),
    (r"(?:глава\s*2|chapter\s*2|теор|theory)", "theory"),
    (r"(?:глава\s*1|chapter\s*1|структур|каркас|skeleton|intro)", "skeleton"),
    (r"(?:план\s+практик|task\s+plan|planning)", "task_planning"),
    (r"(?:датасет|данн|dataset|materials)", "dataset"),
    (r"(?:финал|оценк|критер|quality|evaluation|final)", "final"),
)
_STAGE_TO_WORKFLOW_NODE = {
    "context": "context",
    "task_planning": "task_planning",
    "title": "title_annotation",
    "annotation": "title_annotation",
    "skeleton": "skeleton",
    "theory": "theory",
    "practice": "practice",
    "dataset": "practice",
    "final": "evaluation",
}


class MethodologyAssistantCommandParser:
    """Parse methodologist chat text into command contracts with no network dependency."""

    def parse(self, message: str, context: MethodologyAssistantParseContext | None = None) -> MethodologyAssistantCommand:
        parse_context = context or MethodologyAssistantParseContext()
        text = message.strip()
        if not text:
            raise ValueError("assistant command message is empty")
        command_type = self._detect_command(text)
        target = self._target_for_command(command_type, text, parse_context)
        issue_codes = self._failed_issue_codes(parse_context) if command_type == "fix_failed_criteria" else []
        command = MethodologyAssistantCommand(
            command=command_type,
            raw_text=text,
            target_stage=self._target_stage(target, parse_context),
            target_selector=self._selector_for_target(target, parse_context),
            target_id=target.id if target else "",
            scope=self._target_scope(target, command_type, text),
            instruction=self._instruction_for(command_type, text, issue_codes),
            issue_codes=issue_codes,
            forbidden_changes=self._forbidden_changes(command_type, text),
            expected_outcome=self._expected_outcome(command_type),
            confidence=0.86 if target else 0.58,
        )
        return self._bind_checkpoint(command, parse_context)

    def _detect_command(self, text: str) -> AssistantCommandType:
        lowered = text.lower()
        if _APPROVE_RE.search(lowered) and not _CHANGE_MARKERS_RE.search(lowered):
            return "approve"
        if _SIMPLIFY_RE.search(lowered):
            return "simplify_task"
        if _ADD_EXAMPLE_RE.search(lowered):
            return "add_example"
        if _REGENERATE_RE.search(lowered):
            return "regenerate_section"
        if _FIX_FAILED_RE.search(lowered) and re.search(r"(?:исправ|fix|заполн|подтян|пройден|failed)", lowered):
            return "fix_failed_criteria"
        return "request_changes"

    def _target_for_command(self, command_type: AssistantCommandType, text: str, context: MethodologyAssistantParseContext) -> SectionTarget | None:
        registry = self._registry(context)
        if context.selected_target_id and (selected := registry.find(context.selected_target_id)):
            return selected
        if command_type == "simplify_task":
            return self._practice_target(registry, text) or self._target_by_stage(registry, "practice")
        if command_type == "add_example":
            return self._target_by_stage(registry, self._current_stage(context), allowed={"theory", "practice"}) or self._target_by_stage(registry, "theory")
        if command_type == "fix_failed_criteria":
            return self._target_by_stage(registry, "final") or self._target_by_stage(registry, self._current_stage(context))
        hinted = self._stage_from_text(text) or self._current_stage(context)
        return self._target_by_stage(registry, hinted) or self._target_by_stage(registry, "final")

    @staticmethod
    def _registry(context: MethodologyAssistantParseContext) -> SectionTargetRegistry:
        try:
            return SectionTargetRegistry.model_validate(context.target_registry)
        except ValidationError:
            return SectionTargetRegistry()

    @staticmethod
    def _practice_target(registry: SectionTargetRegistry, text: str) -> SectionTarget | None:
        if not (match := _TASK_NUMBER_RE.search(text)):
            return None
        number = match.group(1)
        for target in registry.targets:
            haystack = " ".join([target.id, target.label, target.selector]).lower()
            if target.stage == "practice" and re.search(rf"(?:задач[аеиу]?|задани[еяю]|task)[^\d]{{0,12}}{re.escape(number)}\b", haystack):
                return target
        return None

    def _target_by_stage(self, registry: SectionTargetRegistry, stage: str, *, allowed: set[str] | None = None) -> SectionTarget | None:
        normalized_stage = self._normalize_stage(stage)
        if allowed and normalized_stage not in allowed:
            normalized_stage = "theory" if "theory" in allowed else sorted(allowed)[0]
        for target in registry.targets:
            if target.stage == normalized_stage:
                return target
        if allowed:
            return next((target for target in registry.targets if target.stage in allowed), None)
        return None

    def _normalize_stage(self, value: str) -> ChangeTargetStage:
        normalized = _STAGE_ALIASES.get(str(value or "").strip(), str(value or "").strip()).lower()
        normalized = _STAGE_ALIASES.get(normalized, normalized)
        return normalized if normalized in _TARGET_STAGES else "final"  # type: ignore[return-value]

    def _current_stage(self, context: MethodologyAssistantParseContext) -> ChangeTargetStage:
        checkpoint = context.checkpoint or {}
        return self._normalize_stage(str(checkpoint.get("stage") or checkpoint.get("resume_from_node") or ""))

    def _target_stage(self, target: SectionTarget | None, context: MethodologyAssistantParseContext) -> ChangeTargetStage:
        return self._normalize_stage(target.stage if target else self._current_stage(context))

    @staticmethod
    def _stage_from_text(text: str) -> ChangeTargetStage | None:
        for pattern, stage in _STAGE_HINTS:
            if re.search(pattern, text, re.I):
                return stage
        return None

    def _selector_for_target(self, target: SectionTarget | None, context: MethodologyAssistantParseContext) -> str:
        if target:
            return (target.selector or target.id)[:300]
        checkpoint = context.checkpoint or {}
        return str(checkpoint.get("node_id") or checkpoint.get("stage") or checkpoint.get("id") or "")[:300]

    @staticmethod
    def _target_scope(target: SectionTarget | None, command_type: AssistantCommandType, text: str = "") -> ChangeScope:
        if _DISPLAY_BLOCK_RE.search(text or ""):
            return "local_section_only"
        if command_type == "simplify_task":
            return "task_only"
        if target and target.scope in _SCOPES:
            return target.scope  # type: ignore[return-value]
        return "local_section_only"

    @staticmethod
    def _instruction_for(command_type: AssistantCommandType, text: str, issue_codes: list[str]) -> str:
        if command_type == "approve":
            return ""
        if command_type == "simplify_task":
            return f"Упрости выбранную практическую задачу: {text}"
        if command_type == "add_example":
            return f"Добавь короткий учебный пример в выбранный блок: {text}"
        if command_type == "fix_failed_criteria":
            suffix = f" ({', '.join(issue_codes)})" if issue_codes else ""
            return f"Исправь непройденные критерии{suffix}: {text}"
        if command_type == "regenerate_section":
            return f"Перегенерируй выбранный раздел с учетом комментария методолога: {text}"
        if _DISPLAY_BLOCK_RE.search(text or ""):
            return f"Исправь только таблицы или Mermaid-диаграммы в выбранном фрагменте. Комментарий: {text}"
        return text

    @staticmethod
    def _forbidden_changes(command_type: AssistantCommandType, text: str = "") -> list[str]:
        if command_type == "approve":
            return []
        rules = ["не менять соседние разделы"]
        if command_type in {"simplify_task", "fix_failed_criteria"} and not _DISPLAY_BLOCK_RE.search(text or ""):
            rules.append("не добавлять готовые ответы")
        if command_type == "regenerate_section":
            rules.append("не менять входные параметры проекта")
        return rules

    @staticmethod
    def _expected_outcome(command_type: AssistantCommandType) -> str:
        return {
            "approve": "",
            "request_changes": "Локальная правка сохранена без изменения соседних блоков.",
            "simplify_task": "Задача стала проще и атомарнее, но учебная цель сохранилась.",
            "add_example": "В блоке появился короткий пример без готового решения практики.",
            "fix_failed_criteria": "Непройденные критерии закрыты точечными правками.",
            "regenerate_section": "Выбранный раздел перегенерирован от ближайшего durable checkpoint.",
        }[command_type]

    @staticmethod
    def _failed_issue_codes(context: MethodologyAssistantParseContext) -> list[str]:
        checkpoint = context.checkpoint or {}
        artifact = checkpoint.get("artifact") if isinstance(checkpoint.get("artifact"), dict) else {}
        matrix = artifact.get("requirements_matrix") if isinstance(artifact, dict) else context.review_state.get("requirements_matrix", [])
        codes: list[str] = []
        for item in matrix if isinstance(matrix, list) else []:
            if isinstance(item, dict) and (item.get("passed") is False or str(item.get("status") or "").lower() in {"fail", "failed", "warning"}):
                if code := item.get("id") or item.get("code") or item.get("criterion"):
                    codes.append(str(code))
        return codes

    def _bind_checkpoint(self, command: MethodologyAssistantCommand, context: MethodologyAssistantParseContext) -> MethodologyAssistantCommand:
        checkpoint = context.checkpoint or {}
        return command.model_copy(
            update={
                "checkpoint_id": str(checkpoint.get("id") or ""),
                "checkpoint_stage": self._normalize_stage(str(checkpoint.get("stage") or "")),
                "node_id": str(checkpoint.get("node_id") or checkpoint.get("resume_from_node") or ""),
                "workflow_node_id": _STAGE_TO_WORKFLOW_NODE.get(command.target_stage, "evaluation"),
            }
        )
