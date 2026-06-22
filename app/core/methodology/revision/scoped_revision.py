"""Scoped methodologist revisions for paused generation state."""

from __future__ import annotations

import difflib
import hashlib
import re
from typing import Any

from pydantic import BaseModel

from app.core.methodology.revision.blocks import MarkdownBlockContract
from app.core.methodology.revision.contracts import MethodologistChangeRequest, ScopedResumePlan, ScopedRevisionResult
from app.core.methodology.revision.guards import find_non_raw_material_issues, has_hard_conflicts, validate_methodologist_change_request
from app.core.methodology.revision.target_registry import SectionTarget, build_section_target_registry

_DISPLAY_BLOCK_REQUEST_RE = re.compile(r"(?:диаграм|mermaid|схем|таблиц|markdown\s*table|\btable\b)", re.I)


class RevisionRejectedError(RuntimeError):
    """Raised when a hard revision conflict must stop resume."""

    def __init__(self, result: ScopedRevisionResult) -> None:
        super().__init__("Scoped revision rejected")
        self.result = result


class _MarkdownSection(BaseModel):
    start: int
    end: int
    text: str
    heading: str
    target_id: str = ""


class ScopedRevisionExecutor:
    """Apply approved change requests without letting an editor touch adjacent targets."""

    def __init__(self, llm_client: Any, block_contract: MarkdownBlockContract | None = None) -> None:
        self.llm = llm_client
        self.block_contract = block_contract or MarkdownBlockContract()

    def apply_pending_change_requests(self, context: dict[str, Any], *, raise_on_rejected: bool = True) -> list[ScopedRevisionResult]:
        actions = list(context.get("methodology_review_actions") or [])
        processed_ids = set(context.get("processed_methodology_change_ids") or [])
        results = _existing_results(context)
        newly_processed: list[ScopedRevisionResult] = []
        for index, action in enumerate(actions):
            if not isinstance(action, dict) or action.get("action") != "changes_requested":
                continue
            details = action.get("details") if isinstance(action.get("details"), dict) else {}
            payload = details.get("change_request") if isinstance(details, dict) else None
            if not isinstance(payload, dict):
                continue
            request = MethodologistChangeRequest.model_validate(payload)
            action_id = self.action_id_for_action(action, index, request)
            if action_id in processed_ids:
                continue
            result = self.apply_change_request(context, request, action_id=action_id)
            results.append(result)
            newly_processed.append(result)
            processed_ids.add(action_id)
            if result.status == "rejected" and raise_on_rejected:
                _store_results(context, processed_ids, results)
                raise RevisionRejectedError(result)
        _store_results(context, processed_ids, results)
        return newly_processed

    def apply_change_request(self, context: dict[str, Any], request: MethodologistChangeRequest, *, action_id: str) -> ScopedRevisionResult:
        conflicts = validate_methodologist_change_request(request)
        if has_hard_conflicts(conflicts):
            return ScopedRevisionResult(
                action_id=action_id,
                status="rejected",
                target_kind="unsupported",
                target_stage=request.target_stage,
                target_selector=request.target_selector,
                target_id=request.target_selector,
                scope=request.scope,
                issues=[f"{conflict.code}: {conflict.message}" for conflict in conflicts],
            )
        if self._targets_field(context, request):
            return self._apply_field_revision(context, request, action_id)
        if self._targets_material(request):
            return self._apply_material_revision(context, request, action_id)
        if self._targets_markdown(request):
            return self._apply_markdown_revision(context, request, action_id)
        return ScopedRevisionResult(
            action_id=action_id,
            status="skipped",
            target_kind="unsupported",
            target_stage=request.target_stage,
            target_selector=request.target_selector,
            target_id=request.target_selector,
            scope=request.scope,
            issues=[f"Unsupported revision target: {request.target_stage}/{request.scope}"],
        )

    def build_resume_plan(self, current_start_index: int, execution_plan: list[str], results: list[ScopedRevisionResult] | None) -> ScopedResumePlan:
        total_nodes = len(execution_plan)
        original_index = max(0, min(int(current_start_index or 0), total_nodes))
        start_index = original_index
        applied_ids: list[str] = []
        ignored_ids: list[str] = []
        reasons: list[str] = []
        for result in results or []:
            if result.status != "applied" or not result.changed or not result.recommended_resume_node:
                ignored_ids.append(result.action_id)
                reasons.append(f"{result.action_id}: status={result.status}, changed={result.changed}")
                continue
            try:
                node_index = execution_plan.index(result.recommended_resume_node)
            except ValueError:
                ignored_ids.append(result.action_id)
                reasons.append(f"{result.action_id}: unknown node {result.recommended_resume_node}")
                continue
            applied_ids.append(result.action_id)
            start_index = min(start_index, node_index)
        return ScopedResumePlan(
            original_resume_from_index=original_index,
            resume_from_index=start_index,
            original_resume_node=execution_plan[original_index] if original_index < total_nodes else "completed",
            resume_node=execution_plan[start_index] if start_index < total_nodes else "completed",
            moved_back=start_index < original_index,
            invalidated_nodes=execution_plan[start_index:original_index] if start_index < original_index else [],
            applied_action_ids=applied_ids,
            ignored_action_ids=ignored_ids,
            reasons=reasons,
        )

    @staticmethod
    def trim_previous_steps_for_resume(previous_steps: list[Any] | None, resume_from_index: int, execution_plan: list[str]) -> list[Any]:
        if not previous_steps:
            return []
        node_positions = {node_id: index for index, node_id in enumerate(execution_plan)}
        keep_before = max(0, min(int(resume_from_index or 0), len(execution_plan)))
        trimmed: list[Any] = []
        for step in previous_steps:
            node_id = getattr(step, "node_id", None) if not isinstance(step, dict) else step.get("node_id")
            node_index = node_positions.get(str(node_id or ""))
            if node_index is None or node_index < keep_before:
                trimmed.append(step)
        return trimmed

    def _apply_field_revision(self, context: dict[str, Any], request: MethodologistChangeRequest, action_id: str) -> ScopedRevisionResult:
        target = self._resolve_target(context, request, kind="field")
        field_name = str((target.metadata.get("field") if target else "") or request.target_stage).strip()
        if field_name not in {"title", "annotation"}:
            return _skipped(action_id, request, "field", "Target field was not found", target)
        original = self._field_value(context, field_name)
        revised, issues = self._revise_field(original, request, field_name=field_name)
        if issues:
            return _rejected(action_id, request, "field", issues, target, field_name)
        self._set_field_value(context, field_name, revised)
        self._invalidate_downstream_context(context, request)
        return _applied(action_id, request, "field", original, revised, target, field_name, self._recommended_node_for_stage(request.target_stage))

    def _apply_markdown_revision(self, context: dict[str, Any], request: MethodologistChangeRequest, action_id: str) -> ScopedRevisionResult:
        markdown = str(context.get("markdown") or "")
        section = self._resolve_markdown_section(markdown, request)
        if section is None:
            return _skipped(action_id, request, "markdown_section", "Target markdown section was not found")
        revised_section, issues = self._revise_text(section.text, request, target_label=section.heading)
        if issues:
            return _rejected(action_id, request, "markdown_section", issues, target_id=section.target_id, label=section.heading)
        revised_section = self._preserve_markdown_boundaries(original_section=section.text, revised_section=revised_section, suffix=markdown[section.end :])
        revised_markdown = markdown[: section.start] + revised_section + markdown[section.end :]
        if markdown[: section.start] != revised_markdown[: section.start]:
            return _rejected(action_id, request, "markdown_section", ["prefix changed outside target section"])
        suffix_start = section.start + len(revised_section)
        if markdown[section.end :] != revised_markdown[suffix_start:]:
            return _rejected(action_id, request, "markdown_section", ["suffix changed outside target section"])
        context["markdown"] = revised_markdown
        self._invalidate_downstream_context(context, request)
        if request.target_stage in {"annotation", "skeleton"}:
            self._sync_title_annotation_from_markdown(context)
        return _applied(action_id, request, "markdown_section", section.text, revised_section, None, section.heading, self._recommended_node_for_stage(request.target_stage), target_id=section.target_id)

    def _apply_material_revision(self, context: dict[str, Any], request: MethodologistChangeRequest, action_id: str) -> ScopedRevisionResult:
        dataset_files = list(context.get("dataset_files") or [])
        target = self._resolve_target(context, request, kind="material_file")
        target_index = self._find_material_index(dataset_files, request.target_selector, target=target)
        if target_index is None:
            return _skipped(action_id, request, "material_file", "Target material file was not found", target)
        file_item = dict(dataset_files[target_index])
        original_data = file_item.get("data") or b""
        original_text = original_data if isinstance(original_data, str) else bytes(original_data).decode("utf-8", errors="replace")
        revised_text, issues = self._revise_text(original_text, request, target_label=str(file_item.get("path") or "material"))
        if issues:
            return _rejected(action_id, request, "material_file", issues, target, str(file_item.get("path") or ""))
        if material_issues := find_non_raw_material_issues(revised_text):
            return _rejected(action_id, request, "material_file", [f"raw_evidence_contract_violation:{issue}" for issue in material_issues], target, str(file_item.get("path") or ""))
        file_item["data"] = revised_text.encode("utf-8")
        dataset_files[target_index] = file_item
        context["dataset_files"] = dataset_files
        self._invalidate_downstream_context(context, request)
        return _applied(action_id, request, "material_file", original_text, revised_text, target, str(file_item.get("path") or "material"), self._recommended_node_for_stage(request.target_stage))

    def _revise_text(self, text: str, request: MethodologistChangeRequest, *, target_label: str) -> tuple[str, list[str]]:
        original = text or ""
        allow_display_block_edit = self._allows_display_block_edit(request)
        protected, blocks = self.block_contract.protect(original, protect_mermaid=not allow_display_block_edit, protect_tables=not allow_display_block_edit)
        system = "Ты редактор учебного контента. Исправляй только переданный фрагмент или файл. Верни только обновленный markdown/text."
        user = "\n".join(
            [
                f"Target: {target_label}",
                f"Stage: {request.target_stage}",
                f"Scope: {request.scope}",
                f"Selector: {request.target_selector or '-'}",
                f"Instruction: {request.instruction}",
                f"Expected outcome: {request.expected_outcome or '-'}",
                f"Forbidden changes: {', '.join(request.forbidden_changes or []) or '-'}",
                self.block_contract.protection_instruction(blocks, allow_display_block_edit=allow_display_block_edit),
                "",
                "ФРАГМЕНТ ДЛЯ ПРАВКИ:",
                protected,
            ]
        )
        edited = self.llm.complete(system=system, user=user, temperature=0.1, use_cache=False).strip()
        if placeholder_issues := self._validate_protected_placeholders(edited, len(blocks)):
            return original, placeholder_issues
        restored = self.block_contract.restore(edited, blocks)
        if validation_issues := self.block_contract.validate(restored):
            return original, validation_issues
        return restored, []

    def _revise_field(self, text: str, request: MethodologistChangeRequest, *, field_name: str) -> tuple[str, list[str]]:
        label = "название проекта" if field_name == "title" else "аннотация"
        user = "\n".join([f"Поле: {label}", f"Instruction: {request.instruction}", f"Expected outcome: {request.expected_outcome or '-'}", "", "ТЕКУЩЕЕ ЗНАЧЕНИЕ:", text or ""])
        edited = self.llm.complete(system="Исправь только указанное поле. Верни только новое значение.", user=user, temperature=0.1, use_cache=False).strip()
        edited = re.sub(r"^#+\s*", "", edited).strip(" \t\r\n\"'`")
        edited = re.sub(r"\s+", " ", edited).strip()
        if not edited:
            return text or "", ["LLM returned an empty field value"]
        if field_name == "title" and len(edited.split()) > 12:
            return text or "", ["Project title is too long after revision"]
        return edited.splitlines()[0].strip() if field_name == "title" else edited, []

    def _resolve_markdown_section(self, markdown: str, request: MethodologistChangeRequest) -> _MarkdownSection | None:
        target = self._resolve_target({"markdown": markdown}, request, kind="markdown_section")
        if target and target.start is not None and target.end is not None:
            return _MarkdownSection(start=target.start, end=target.end, text=markdown[target.start : target.end], heading=target.label, target_id=target.id)
        selector = (request.target_selector or self._default_selector(request.target_stage)).strip()
        if not selector:
            return None
        selector_norm = self._norm(selector)
        matches = list(re.finditer(r"^(#{1,6})\s+(.+?)\s*$", markdown, flags=re.M))
        for index, match in enumerate(matches):
            heading = match.group(2).strip()
            heading_norm = self._norm(heading)
            if selector_norm not in heading_norm and heading_norm not in selector_norm:
                continue
            end = len(markdown)
            for next_match in matches[index + 1 :]:
                if len(next_match.group(1)) <= len(match.group(1)):
                    end = next_match.start()
                    break
            return _MarkdownSection(start=match.start(), end=end, text=markdown[match.start() : end], heading=heading)
        return None

    @staticmethod
    def _resolve_target(context: dict[str, Any], request: MethodologistChangeRequest, *, kind: str) -> SectionTarget | None:
        registry = build_section_target_registry(context)
        target = registry.find(request.target_selector, kind=kind)  # type: ignore[arg-type]
        if target or kind != "markdown_section":
            return target
        return registry.find(request.target_selector or ScopedRevisionExecutor._default_selector(request.target_stage), kind="markdown_section", stage=request.target_stage if request.target_stage in {"annotation", "skeleton", "theory", "practice", "final"} else None)

    @staticmethod
    def _field_value(context: dict[str, Any], field_name: str) -> str:
        if field_name == "title":
            return str(context.get("title") or "")
        annotation = context.get("annotation")
        return str(annotation.get("text") or "") if isinstance(annotation, dict) else str(getattr(annotation, "text", "") or "")

    @staticmethod
    def _set_field_value(context: dict[str, Any], field_name: str, value: str) -> None:
        if field_name == "title":
            context["title"] = value
            if markdown := str(context.get("markdown") or ""):
                context["markdown"] = re.sub(r"^#\s+.+?$", f"# {value}", markdown, count=1, flags=re.M)
            return
        annotation = context.get("annotation")
        if isinstance(annotation, dict):
            annotation["text"] = value
            annotation["chars"] = len(value)
        else:
            context["annotation"] = {"text": value, "chars": len(value)}

    @staticmethod
    def _default_selector(stage: str) -> str:
        return {"skeleton": "Глава 1", "annotation": "annotation", "theory": "Глава 2", "practice": "Глава 3"}.get(stage, "")

    @staticmethod
    def _find_material_index(dataset_files: list[Any], selector: str, *, target: SectionTarget | None = None) -> int | None:
        if target is not None:
            target_path = str(target.metadata.get("path") or target.selector or "").replace("\\", "/").lower()
            for index, item in enumerate(dataset_files):
                if isinstance(item, dict) and str(item.get("path") or "").replace("\\", "/").lower() == target_path:
                    return index
        selector_norm = selector.replace("\\", "/").lower().strip()
        if not selector_norm and len(dataset_files) == 1:
            return 0
        for index, item in enumerate(dataset_files):
            path = str(item.get("path") or "").replace("\\", "/").lower() if isinstance(item, dict) else ""
            if selector_norm and (selector_norm == path or selector_norm in path or path in selector_norm):
                return index
        return None

    @staticmethod
    def _targets_material(request: MethodologistChangeRequest) -> bool:
        selector = (request.target_selector or "").replace("\\", "/").lower()
        return request.scope == "materials_only" or request.target_stage == "dataset" or selector.startswith("materials/")

    @staticmethod
    def _targets_field(context: dict[str, Any], request: MethodologistChangeRequest) -> bool:
        return request.target_stage == "title" or ScopedRevisionExecutor._resolve_target(context, request, kind="field") is not None

    @staticmethod
    def _targets_markdown(request: MethodologistChangeRequest) -> bool:
        return request.target_stage in {"annotation", "skeleton", "theory", "practice", "final"}

    @staticmethod
    def _recommended_node_for_stage(stage: str) -> str | None:
        return {"title": "skeleton", "annotation": "theory", "skeleton": "theory", "theory": "practice", "practice": "global_quality", "dataset": "global_quality", "final": "evaluation"}.get(stage)

    @staticmethod
    def _invalidate_downstream_context(context: dict[str, Any], request: MethodologistChangeRequest) -> None:
        stage = request.target_stage
        if stage in {"title", "annotation", "skeleton", "theory"}:
            context["practice_tasks"] = []
            context["dataset_files"] = []
            context["practice_critic_issues"] = []
            context["theory_parts"] = []
        if stage in {"practice", "dataset"}:
            context["practice_tasks"] = []
            context["practice_critic_issues"] = []
        if stage in {"title", "annotation", "skeleton", "theory", "practice", "dataset", "final"}:
            context["rubric_json"] = {}
            context.pop("translated_markdown", None)

    @staticmethod
    def _allows_display_block_edit(request: MethodologistChangeRequest) -> bool:
        return bool(_DISPLAY_BLOCK_REQUEST_RE.search(" ".join([request.instruction, request.target_selector, request.expected_outcome, " ".join(request.issue_codes)])))

    @staticmethod
    def _preserve_markdown_boundaries(*, original_section: str, revised_section: str, suffix: str) -> str:
        revised = revised_section or ""
        if original_section.startswith("\n") and not revised.startswith("\n"):
            revised = "\n\n" + revised.lstrip()
        if suffix.startswith("#") and revised.strip() and not revised.endswith("\n"):
            revised = revised.rstrip() + "\n\n"
        return revised

    @staticmethod
    def _validate_protected_placeholders(edited: str, block_count: int) -> list[str]:
        issues: list[str] = []
        for block_id in range(block_count):
            marker = f"[[[BLOCK_{block_id}]]]"
            if (count := edited.count(marker)) != 1:
                issues.append(f"protected block marker {marker} count is {count}, expected 1")
        return issues

    @staticmethod
    def action_id_for_action(action: dict[str, Any], index: int, request: MethodologistChangeRequest) -> str:
        fingerprint = "|".join([str(action.get("timestamp") or index), request.target_stage, request.scope, request.target_selector, request.instruction])
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _sync_title_annotation_from_markdown(context: dict[str, Any]) -> None:
        markdown = str(context.get("markdown") or "")
        if not (title_match := re.search(r"^#\s+(.+?)\s*$", markdown, flags=re.M)):
            return
        title = title_match.group(1).strip()
        next_heading = re.search(r"^##\s+", markdown[title_match.end() :], flags=re.M)
        end = len(markdown) if next_heading is None else title_match.end() + next_heading.start()
        context["title"] = title
        context["annotation"] = {"text": markdown[title_match.end() : end].strip(), "chars": len(markdown[title_match.end() : end].strip())}

    @staticmethod
    def _norm(value: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"[^\wа-яА-ЯёЁ0-9]+", " ", value.lower(), flags=re.I)).strip()


def _existing_results(context: dict[str, Any]) -> list[ScopedRevisionResult]:
    results: list[ScopedRevisionResult] = []
    for item in context.get("methodology_revision_results") or []:
        if isinstance(item, dict):
            try:
                results.append(ScopedRevisionResult.model_validate(item))
            except Exception:
                continue
    return results


def _store_results(context: dict[str, Any], processed_ids: set[str], results: list[ScopedRevisionResult]) -> None:
    context["processed_methodology_change_ids"] = sorted(processed_ids)
    context["methodology_revision_results"] = [item.model_dump(mode="json") for item in results]


def _skipped(action_id: str, request: MethodologistChangeRequest, kind: str, issue: str, target: SectionTarget | None = None) -> ScopedRevisionResult:
    return ScopedRevisionResult(action_id=action_id, status="skipped", target_kind=kind, target_stage=request.target_stage, target_selector=request.target_selector, target_id=target.id if target else request.target_selector, scope=request.scope, issues=[issue])


def _rejected(action_id: str, request: MethodologistChangeRequest, kind: str, issues: list[str], target: SectionTarget | None = None, label: str = "", *, target_id: str = "") -> ScopedRevisionResult:
    return ScopedRevisionResult(action_id=action_id, status="rejected", target_kind=kind, target_stage=request.target_stage, target_selector=request.target_selector, target_id=target.id if target else target_id or request.target_selector, target_label=target.label if target else label, scope=request.scope, issues=issues)


def _applied(action_id: str, request: MethodologistChangeRequest, kind: str, original: str, revised: str, target: SectionTarget | None, label: str, resume_node: str | None, *, target_id: str = "") -> ScopedRevisionResult:
    return ScopedRevisionResult(
        action_id=action_id,
        status="applied",
        target_kind=kind,
        target_stage=request.target_stage,
        target_selector=request.target_selector,
        target_id=target.id if target else target_id or label,
        target_label=target.label if target else label,
        scope=request.scope,
        changed=revised != original,
        changed_chars=len(revised) - len(original),
        recommended_resume_node=resume_node,
        diff_preview=_diff_preview(original, revised, fromfile=target.label if target else label),
        before_hash=_hash_text(original),
        after_hash=_hash_text(revised),
    )


def _diff_preview(original: str, revised: str, *, fromfile: str) -> list[str]:
    if original == revised:
        return []
    diff = list(difflib.unified_diff((original or "").splitlines(), (revised or "").splitlines(), fromfile=f"before:{fromfile}", tofile=f"after:{fromfile}", lineterm="", n=3))
    return diff[:160] + [f"... diff truncated: {len(diff) - 160} more lines"] if len(diff) > 160 else diff


def _hash_text(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()[:16]
