"""G5 refine stage: editing, enhancement gate and scoped regeneration."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.core.config import get_thresholds
from app.core.llm.prompt_loader import PromptNotFoundError, load_prompt
from app.core.llm.structured import StructuredPrompt, complete_typed
from app.core.methodology.gate import MethodologyGate, StageReviewResult
from app.core.methodology.harness import Harness, resolve_profile
from app.core.methodology.rubric import rule_issues_to_rubric
from app.core.methodology.rules import GeneratedDoc, RuleIssue
from app.core.models import ArtifactRef, CurriculumContext
from app.modules.generator.stages.head import _coerce_context

Importance = Literal["must", "nice_to_have", "no"]
ChangeIntent = Literal["local_section_edit", "structural_document_edit"]
ApplyMode = Literal["typed_patch", "scoped_rewrite_fallback", "deterministic_fallback", "none"]

PROFILES_ROOT = Path(__file__).resolve().parents[2] / "core" / "methodology" / "profiles"
CHAPTER_RE = re.compile(r"^(##\s+Глава\s+(\d+)[^\n]*)(?:\n|$)", re.M)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.M)
PATCH_JSON_RE = re.compile(r'\{[\s\S]*"changes"[\s\S]*\}')
PROTECTED_BLOCK_RE = re.compile(r"```[\s\S]*?```|\$\$[\s\S]*?\$\$|<!--\s*PROTECTED_BLOCK[\s\S]*?-->", re.M)
PLACEHOLDER_RE = re.compile(r"\b(?:todo|tbd|lorem ipsum|здесь будет|вставьте|заполнить)\b|\{\{[^}]+}}", re.I)
INSTRUCTION_LEAK_RE = re.compile(r"(?im)^.*(?:PROTECTED_BLOCK|КРИТИЧЕСКИ ВАЖНО|JSON Schema ответа|Верни только).*$")


class PartEnhancementPlan(BaseModel):
    """Per-theory-part enhancement targets used by the refine gate."""

    model_config = ConfigDict(extra="forbid")

    part_index: int = Field(ge=1)
    topic: str
    formulas: Importance = "no"
    tables: Importance = "no"
    diagrams: Importance = "no"
    code_examples: Importance = "no"
    reasoning: str = ""
    anchor_hints: dict[str, str] = Field(default_factory=dict)


class EnhancementPlan(BaseModel):
    """Global plan used by the refine quality gate."""

    model_config = ConfigDict(extra="forbid")

    content_type: Literal["hard_code", "low_code", "no_code"]
    global_targets: dict[str, int]
    budget: dict[str, dict[str, int]]
    per_part: list[PartEnhancementPlan] = Field(default_factory=list)
    reasoning: str = ""
    fallback_used: bool = False


class QualityGateReport(BaseModel):
    """Enhancement compliance plus reused methodology review."""

    model_config = ConfigDict(extra="forbid")

    passed: bool
    grade: float = Field(ge=0.0, le=1.0)
    violations: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    methodology_issues: list[dict[str, Any]] = Field(default_factory=list)
    methodology_review: dict[str, Any] = Field(default_factory=dict)


class RegenerationPatch(BaseModel):
    """One exact text replacement."""

    model_config = ConfigDict(extra="forbid")

    location_hint: str = ""
    old_text: str = Field(min_length=1)
    new_text: str = ""


class RegenerationPatchSet(BaseModel):
    """Typed schema expected from optional LLM regeneration."""

    model_config = ConfigDict(extra="forbid")

    changes: list[RegenerationPatch] = Field(default_factory=list)


class RegenerationIssue(BaseModel):
    """Regeneration validation issue."""

    model_config = ConfigDict(extra="forbid")

    severity: Literal["info", "warning", "error"]
    code: str
    message: str
    section_title: str | None = None
    patch_location: str | None = None


class RegenerationScope(BaseModel):
    """Line-bounded section that may be edited."""

    model_config = ConfigDict(extra="forbid")

    title: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    change: str = ""
    keep: str = ""
    source: str = "inferred"
    is_history: bool = False

    @model_validator(mode="after")
    def range_is_valid(self) -> "RegenerationScope":
        if self.end_line < self.start_line:
            raise ValueError("end_line must be >= start_line")
        return self

    def as_line_range(self) -> tuple[int, int, str]:
        return (self.start_line, self.end_line, self.title)


class RegenerationReport(BaseModel):
    """Schema-first report for patch parse/apply/fallback."""

    model_config = ConfigDict(extra="forbid")

    change_intent: ChangeIntent = "local_section_edit"
    scoped: bool = False
    selected_sections: list[RegenerationScope] = Field(default_factory=list)
    requested_patch_count: int = 0
    applied_patch_count: int = 0
    failed_patch_count: int = 0
    apply_mode: ApplyMode = "none"
    changed: bool = False
    changes: list[str] = Field(default_factory=list)
    issues: list[RegenerationIssue] = Field(default_factory=list)
    failure_memory: list[dict[str, Any]] = Field(default_factory=list)
    regenerated_markdown: str = ""

    def add_issue(
        self,
        severity: Literal["info", "warning", "error"],
        code: str,
        message: str,
        *,
        section_title: str | None = None,
        patch_location: str | None = None,
    ) -> None:
        self.issues.append(
            RegenerationIssue(
                severity=severity,
                code=code,
                message=message,
                section_title=section_title,
                patch_location=patch_location,
            )
        )


class RefineDraft(BaseModel):
    """Optional LLM output: enhancement plan and regeneration patches only."""

    model_config = ConfigDict(extra="forbid")

    plan: list[PartEnhancementPlan] = Field(default_factory=list)
    patches: list[RegenerationPatch] = Field(default_factory=list)
    reasoning: str = ""


class RefineResult(BaseModel):
    """Full G5 output."""

    model_config = ConfigDict(extra="forbid")

    markdown: str
    enhancement_plan: EnhancementPlan
    quality_gate: QualityGateReport
    regeneration_report: RegenerationReport
    edit_actions: list[str] = Field(default_factory=list)


def run(ctx: dict[str, Any], augment: str = "") -> dict[str, Any]:
    """Engine adapter for ``EngineStage('generator.refine', run)``."""
    context = _coerce_context(ctx)
    markdown = str(ctx.get("markdown") or "")
    draft = _llm_draft(context, markdown, ctx, ctx.get("llm_client"), augment) if ctx.get("llm_client") else None
    result = refine_document(
        context,
        markdown=markdown,
        engine_context=ctx,
        draft=draft,
        comments=str(ctx.get("regeneration_comments") or ""),
        failure_memory=_failure_memory(ctx),
        profile_id=str(ctx.get("profile_id") or "_base"),
        program_type=ctx.get("program_type"),
    )
    artifacts = _artifact_refs(ctx.get("artifacts"))
    return {
        "markdown": result.markdown,
        "refine_report": result.model_dump(mode="json"),
        "enhancement_plan": result.enhancement_plan.model_dump(mode="json"),
        "quality_gate": result.quality_gate.model_dump(mode="json"),
        "regeneration_report": result.regeneration_report.model_dump(mode="json"),
        "edit_actions": result.edit_actions,
        "generated_doc": GeneratedDoc(
            markdown=result.markdown,
            artifacts=artifacts,
            metadata={
                "artifact_target": "readme_refined",
                "refine_changed": result.markdown.strip() != markdown.strip(),
                "quality_gate": result.quality_gate.model_dump(mode="json"),
                "regeneration_report": result.regeneration_report.model_dump(mode="json"),
            },
        ),
    }


def refine_document(
    context: CurriculumContext,
    *,
    markdown: str,
    engine_context: dict[str, Any] | None = None,
    draft: RefineDraft | None = None,
    comments: str = "",
    failure_memory: list[dict[str, Any]] | None = None,
    profile_id: str = "_base",
    program_type: str | None = None,
) -> RefineResult:
    """Apply editor cleanup, enhancement checks and optional regeneration."""
    state = dict(engine_context or {})
    source_markdown = markdown or f"# {context.current_project_title}\n\n## Глава 1. Введение и инструкция\n\n## Глава 2. Теория\n\n## Глава 3. Практика"
    theory_parts = _coerce_theory_parts(state.get("theory_parts"), source_markdown)
    plan = _enhancement_plan(context, theory_parts, state, draft)
    edited, edit_actions = _edit_markdown(source_markdown, context)
    first_gate = _quality_gate(edited, context, plan, state, profile_id=profile_id, program_type=program_type)

    regeneration = RegenerationReport(failure_memory=list(failure_memory or []))
    should_regenerate = bool(comments.strip()) or _has_blocking_quality(first_gate) or _failure_memory_requests_retry(regeneration.failure_memory)
    final_markdown = edited
    final_gate = first_gate
    if should_regenerate:
        regeneration = regenerate_markdown(
            edited,
            comments or _comments_from_quality(first_gate),
            context=context,
            client=state.get("llm_client"),
            draft=draft,
            failure_memory=regeneration.failure_memory,
        )
        if regeneration.changed:
            final_markdown = regeneration.regenerated_markdown or edited
            final_gate = _quality_gate(final_markdown, context, plan, state, profile_id=profile_id, program_type=program_type)

    return RefineResult(
        markdown=final_markdown,
        enhancement_plan=plan,
        quality_gate=final_gate,
        regeneration_report=regeneration,
        edit_actions=edit_actions,
    )


def regenerate_markdown(
    markdown: str,
    comments: str,
    *,
    context: CurriculumContext | None = None,
    client: Any | None = None,
    draft: RefineDraft | None = None,
    failure_memory: list[dict[str, Any]] | None = None,
) -> RegenerationReport:
    """Regenerate by typed patches first, then deterministic scoped fallback."""
    report = RegenerationReport(failure_memory=list(failure_memory or []))
    scopes = _parse_scopes(comments, markdown)
    report.selected_sections = scopes
    report.scoped = bool(scopes)
    report.change_intent = _change_intent(comments, scopes)
    patch_set = RegenerationPatchSet(changes=list(draft.patches)) if draft and draft.patches else None

    if patch_set is None and client is not None:
        patch_set = _llm_patch_set(markdown, comments, scopes, client)
    if patch_set is None:
        patch_set = _patches_from_comments(comments, markdown)

    if patch_set is not None:
        patched = _apply_patches(markdown, patch_set.changes, scopes if report.scoped else [])
        report.apply_mode = "typed_patch"
        report.requested_patch_count = len(patch_set.changes)
        report.applied_patch_count = len(patched["applied"])
        report.failed_patch_count = len(patched["failed"])
        report.changes.extend(patched["messages"])
        for message in patched["errors"]:
            report.add_issue("warning", "patch_not_applied", message)
        if patched["result"].strip() != markdown.strip():
            report.changed = True
            report_markdown_store(report, _postprocess_regenerated(markdown, patched["result"]))
            return report
        if patch_set.changes:
            report.add_issue("warning", "patches_no_effect", "Typed patches did not change the README.")

    fallback = _deterministic_fallback(markdown, comments, scopes, context, report)
    report.apply_mode = "scoped_rewrite_fallback" if scopes else "deterministic_fallback"
    if fallback.strip() != markdown.strip():
        report.changed = True
        report.changes.append("Перегенерация применена через deterministic fallback.")
        report_markdown_store(report, _postprocess_regenerated(markdown, fallback))
    else:
        report.changed = False
        report.add_issue("error", "regeneration_not_applied", "Regeneration could not apply patches or fallback.")
        report_markdown_store(report, markdown)
    return report


def _llm_draft(context: CurriculumContext, markdown: str, state: dict[str, Any], client: Any, augment: str) -> RefineDraft | None:
    try:
        template = load_prompt("generator", "refine")
    except PromptNotFoundError:
        return None
    payload = {
        "curriculum_context": context.model_dump(mode="json"),
        "theory_parts": state.get("theory_parts") or [],
        "formula_assets": state.get("formula_assets") or {},
        "dataset_files": state.get("dataset_files") or [],
        "code_examples": state.get("code_examples") or [],
        "regeneration_comments": state.get("regeneration_comments") or "",
        "failure_memory": _failure_memory(state),
        "markdown": markdown[:10000],
        "augment": augment,
    }
    prompt = template.render(context_json=json.dumps(payload, ensure_ascii=False, indent=2))
    try:
        return complete_typed(
            StructuredPrompt(
                system="Return only valid JSON for RefineDraft.",
                user=prompt,
                kwargs={"temperature": 0.15, "max_tokens": 6000},
            ),
            RefineDraft,
            client=client,
            retries=1,
        )
    except Exception:
        return None


def _enhancement_plan(context: CurriculumContext, parts: list[dict[str, Any]], state: dict[str, Any], draft: RefineDraft | None) -> EnhancementPlan:
    content_type = _content_type(context)
    thresholds = get_thresholds().get(f"enhancement.{content_type}") or get_thresholds().get("enhancement.default") or {}
    targets = {key: int(value.get("min", 0)) for key, value in thresholds.items() if isinstance(value, dict)}
    budget = {
        key: {"min": int(value.get("min", 0)), "max": int(value.get("max", value.get("min", 0)))}
        for key, value in thresholds.items()
        if isinstance(value, dict)
    }
    drafted = {item.part_index: item for item in (draft.plan if draft else [])}
    per_part: list[PartEnhancementPlan] = []
    for index, part in enumerate(parts or [{"index": 1, "title": context.current_project_title, "body": ""}], 1):
        part_index = int(part.get("index") or index)
        if part_index in drafted:
            per_part.append(drafted[part_index])
            continue
        per_part.append(_fallback_part_plan(part_index, str(part.get("title") or f"Часть {part_index}"), content_type, targets))
    return EnhancementPlan(
        content_type=content_type,
        global_targets=targets,
        budget=budget,
        per_part=per_part,
        reasoning="Policy-based fallback plan; optional LLM plan merged when present.",
        fallback_used=not bool(draft and draft.plan),
    )


def _fallback_part_plan(part_index: int, topic: str, content_type: str, targets: dict[str, int]) -> PartEnhancementPlan:
    return PartEnhancementPlan(
        part_index=part_index,
        topic=topic,
        formulas="must" if targets.get("formulas", 0) > 0 and part_index == 1 and content_type == "hard_code" else "no",
        tables="must" if targets.get("tables", 0) > 0 and part_index == 1 else "no",
        diagrams="must" if targets.get("diagrams", 0) > 0 and part_index == 1 else "no",
        code_examples="must" if targets.get("code_examples", 0) > 0 and part_index <= max(1, targets.get("code_examples", 0)) else "no",
        reasoning="Deterministic allocation from enhancement thresholds.",
    )


def _quality_gate(
    markdown: str,
    context: CurriculumContext,
    plan: EnhancementPlan,
    state: dict[str, Any],
    *,
    profile_id: str,
    program_type: str | None,
) -> QualityGateReport:
    counts = _asset_counts(markdown, state)
    violations: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for element, expected in plan.global_targets.items():
        actual = counts.get(element, 0)
        if actual < expected:
            violations.append({"type": "hard_guarantee", "element": element, "expected": expected, "actual": actual})
    for element, limits in plan.budget.items():
        actual = counts.get(element, 0)
        if actual > limits.get("max", actual):
            warnings.append({"type": "budget_exceeded", "element": element, "expected": f"<= {limits['max']}", "actual": actual})
    doc = GeneratedDoc(markdown=markdown, metadata={"curriculum_context": context.model_dump(mode="json")})
    methodology_issues = _methodology_issues(doc, state, profile_id=profile_id, program_type=program_type)
    rubric = rule_issues_to_rubric(methodology_issues)
    review = MethodologyGate().review(
        "evaluation",
        {**state, "markdown": markdown, "generated_doc": doc, "rubric_json": rubric, "curriculum_context": context.model_dump(mode="json")},
    )
    hard_methodology = [issue for issue in methodology_issues if issue.severity == "hard"]
    grade = max(0.0, min(1.0, 1.0 - len(violations) * 0.2 - len(warnings) * 0.05 - len(hard_methodology) * 0.2))
    return QualityGateReport(
        passed=not violations and not hard_methodology and not review.human_review_required,
        grade=grade,
        violations=violations,
        warnings=warnings,
        methodology_issues=[issue.model_dump(mode="json") for issue in methodology_issues],
        methodology_review=review.model_dump(mode="json"),
    )


def _methodology_issues(doc: GeneratedDoc, state: dict[str, Any], *, profile_id: str, program_type: str | None) -> list[RuleIssue]:
    profile = resolve_profile(profile_id, PROFILES_ROOT, program_type=program_type)
    harness = Harness(profile)
    issues = harness.validate("generator.style_guard", doc, state)
    issues.extend(harness.validate("generator.evaluation", doc, state))
    return issues


def _edit_markdown(markdown: str, context: CurriculumContext) -> tuple[str, list[str]]:
    actions: list[str] = []
    edited = markdown
    next_md = _strip_instruction_leaks(edited)
    if next_md != edited:
        actions.append("instruction_leaks_removed")
        edited = next_md
    next_md = _remove_duplicate_chapter_headers(edited)
    if next_md != edited:
        actions.append("duplicate_chapter_headers_removed")
        edited = next_md
    next_md = _remove_adjacent_duplicate_paragraphs(edited)
    if next_md != edited:
        actions.append("adjacent_duplicate_paragraphs_removed")
        edited = next_md
    next_md = _fix_code_blocks(edited)
    if next_md != edited:
        actions.append("code_blocks_fixed")
        edited = next_md
    next_md = _remove_empty_html_blocks(edited)
    if next_md != edited:
        actions.append("empty_html_blocks_removed")
        edited = next_md
    next_md = _ensure_chapter_bridges(edited, context)
    if next_md != edited:
        actions.append("chapter_bridges_added")
        edited = next_md
    return _normalize_markdown(edited), actions


def _parse_scopes(comments: str, markdown: str) -> list[RegenerationScope]:
    explicit = _explicit_scopes(comments, markdown)
    if explicit:
        return explicit
    text = comments.lower()
    ranges = _heading_ranges(markdown)
    result: list[RegenerationScope] = []
    title_scope = "назван" in text and "проект" in text
    for start, end, level, title in ranges:
        low_title = title.lower()
        if title_scope and level == 1:
            result.append(RegenerationScope(title="Название проекта", start_line=start, end_line=start, change=comments, source="inferred"))
        for ref in re.findall(r"(?<!\d)(\d+(?:\.\d+)*)(?!\d)", text):
            if low_title.startswith(ref) or f" {ref}" in low_title:
                result.append(RegenerationScope(title=title, start_line=start, end_line=end, change=comments, source="inferred"))
        if ("глава 2" in text or "теори" in text) and "глава 2" in low_title:
            result.append(RegenerationScope(title=title, start_line=start, end_line=end, change=comments, source="inferred"))
        if ("глава 3" in text or "практик" in text) and "глава 3" in low_title:
            result.append(RegenerationScope(title=title, start_line=start, end_line=end, change=comments, source="inferred"))
    return _dedupe_scopes(result)


def _explicit_scopes(comments: str, markdown: str) -> list[RegenerationScope]:
    header_re = re.compile(r"(?m)^(?P<prefix>Сохран[её]нная правка|Правка)\s+\d+:\s*(?P<title>.+?)\s*$")
    range_re = re.compile(r"Диапазон строк:\s*(?P<start>\d+)\s*[-–—]\s*(?P<end>\d+)", re.I)
    matches = list(header_re.finditer(comments or ""))
    scopes: list[RegenerationScope] = []
    line_count = max(1, len((markdown or "").splitlines()))
    for idx, match in enumerate(matches):
        is_history = match.group("prefix").lower().startswith("сохран")
        if is_history:
            continue
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(comments or "")
        block = comments[match.end() : end]
        range_match = range_re.search(block)
        if not range_match:
            continue
        start_line = max(1, min(int(range_match.group("start")), line_count))
        end_line = max(start_line, min(int(range_match.group("end")), line_count))
        scopes.append(
            RegenerationScope(
                title=match.group("title").strip(),
                start_line=start_line,
                end_line=end_line,
                change=_extract_field(block, "Что исправить") or comments.strip(),
                keep=_extract_field(block, "Что оставить"),
                source="explicit",
            )
        )
    return _dedupe_scopes(scopes)


def _patches_from_comments(comments: str, markdown: str) -> RegenerationPatchSet | None:
    pairs = re.findall(r"(?:замени|заменить)\s+[«\"](.+?)[»\"]\s+(?:на|->)\s+[«\"](.+?)[»\"]", comments or "", flags=re.I | re.S)
    changes = [RegenerationPatch(location_hint="comment replace", old_text=old.strip(), new_text=new.strip()) for old, new in pairs if old.strip()]
    if changes:
        return RegenerationPatchSet(changes=changes)
    if PLACEHOLDER_RE.search(markdown):
        target = PLACEHOLDER_RE.search(markdown)
        if target:
            replacement = _placeholder_replacement(comments)
            return RegenerationPatchSet(changes=[RegenerationPatch(location_hint="placeholder cleanup", old_text=target.group(0), new_text=replacement)])
    return None


def _llm_patch_set(markdown: str, comments: str, scopes: list[RegenerationScope], client: Any) -> RegenerationPatchSet | None:
    try:
        template = load_prompt("generator", "refine")
    except PromptNotFoundError:
        return None
    payload = {
        "markdown": markdown[:12000],
        "comments": comments,
        "allowed_ranges": [scope.model_dump(mode="json") for scope in scopes],
        "schema": RegenerationPatchSet.model_json_schema(),
    }
    try:
        draft = complete_typed(
            StructuredPrompt(
                system="Return only valid JSON matching RefineDraft. Use patches for regeneration comments.",
                user=template.render(context_json=json.dumps(payload, ensure_ascii=False, indent=2)),
                kwargs={"temperature": 0.1, "max_tokens": 6000},
            ),
            RefineDraft,
            client=client,
            retries=1,
        )
    except Exception:
        return None
    return RegenerationPatchSet(changes=draft.patches) if draft.patches else None


def _apply_patches(markdown: str, patches: list[RegenerationPatch], scopes: list[RegenerationScope]) -> dict[str, Any]:
    result = markdown
    applied: list[RegenerationPatch] = []
    failed: list[RegenerationPatch] = []
    errors: list[str] = []
    messages: list[str] = []
    for patch in patches:
        valid, error = _validate_patch(patch)
        if not valid:
            failed.append(patch)
            errors.append(f"{patch.location_hint}: {error}")
            continue
        target_text = result
        offset = 0
        scope_label = ""
        if scopes:
            found = _find_in_scopes(result, patch.old_text, scopes)
            if not found:
                failed.append(patch)
                errors.append(f"{patch.location_hint}: old_text not found in allowed scopes")
                continue
            start, end, scope_label = found
        else:
            match = _find_text(result, patch.old_text)
            if not match:
                failed.append(patch)
                errors.append(f"{patch.location_hint}: old_text not found")
                continue
            start, end = match
        result = result[:start] + patch.new_text + result[end:]
        applied.append(patch)
        messages.append(f"{patch.location_hint or scope_label}: {patch.old_text[:40]} -> {patch.new_text[:40]}")
    return {"result": result, "applied": applied, "failed": failed, "errors": errors, "messages": messages}


def _deterministic_fallback(
    markdown: str,
    comments: str,
    scopes: list[RegenerationScope],
    context: CurriculumContext | None,
    report: RegenerationReport,
) -> str:
    result = markdown
    if scopes:
        for scope in sorted(scopes, key=lambda item: item.start_line, reverse=True):
            block = _slice_scope(result, scope)
            repaired = _repair_block(block, comments, context)
            if repaired != block:
                result = _replace_scope(result, scope, repaired)
                report.changes.append(f"Переписана выбранная часть: {scope.title}")
        return result
    return _repair_block(result, comments, context)


def _repair_block(block: str, comments: str, context: CurriculumContext | None) -> str:
    repaired = PLACEHOLDER_RE.sub(_placeholder_replacement(comments, context), block)
    repaired = _remove_adjacent_duplicate_paragraphs(repaired)
    if "глава 2" in comments.lower() and "## Глава 2" not in repaired:
        repaired += "\n\n## Глава 2. Теория\n\nКлючевые понятия проекта связаны с проверяемыми решениями и практическими артефактами."
    if "глава 3" in comments.lower() and "## Глава 3" not in repaired:
        repaired += "\n\n## Глава 3. Практика\n\nВыполни задания, сохраняя доказательства работы в репозитории."
    return _normalize_markdown(repaired)


def _edit_chapter_body(markdown: str, chapter_number: str, transform: Any) -> str:
    pattern = re.compile(rf"^(##\s+Глава\s+{chapter_number}[^\n]*\n)([\s\S]*?)(?=^##\s+Глава\s+\d+|\Z)", re.M)
    match = pattern.search(markdown)
    if not match:
        return markdown
    return markdown[: match.start()] + match.group(1) + transform(match.group(2)).lstrip() + markdown[match.end() :]


def _ensure_chapter_bridges(markdown: str, context: CurriculumContext) -> str:
    if "## Глава 2" not in markdown or "## Глава 3" not in markdown:
        return markdown
    title = context.current_project_title or "проект"

    def bridge2(body: str) -> str:
        if body.lstrip().startswith(("В этой главе", "Теперь")):
            return body
        return f"Теперь свяжем контекст проекта «{title}» с понятиями, которые понадобятся в практической части.\n\n{body.lstrip()}"

    def bridge3(body: str) -> str:
        if body.lstrip().startswith(("Практика", "Теперь")):
            return body
        return f"Практика переводит теорию в проверяемые действия: каждый результат должен быть виден в артефактах проекта.\n\n{body.lstrip()}"

    return _edit_chapter_body(_edit_chapter_body(markdown, "2", bridge2), "3", bridge3)


def _asset_counts(markdown: str, state: dict[str, Any]) -> dict[str, int]:
    formula_assets = state.get("formula_assets") if isinstance(state.get("formula_assets"), dict) else {}
    return {
        "formulas": len(formula_assets.get("formulas") or []) or len(re.findall(r"\$\$[\s\S]*?\$\$", markdown)),
        "tables": len(formula_assets.get("tables") or []) or len(re.findall(r"^\|.+\|\s*$", markdown, re.M)) // 2,
        "diagrams": len(formula_assets.get("visuals") or []) or markdown.count("```mermaid"),
        "code_examples": len(state.get("code_examples") or []) or len(re.findall(r"```(?!mermaid)[a-zA-Z0-9_-]*\n", markdown)),
    }


def _coerce_theory_parts(raw: Any, markdown: str) -> list[dict[str, Any]]:
    if isinstance(raw, list) and raw:
        parts = []
        for index, item in enumerate(raw, 1):
            if isinstance(item, BaseModel):
                item = item.model_dump(mode="json")
            if isinstance(item, dict):
                parts.append({"index": int(item.get("index") or index), "title": str(item.get("title") or ""), "body": str(item.get("body") or "")})
        if parts:
            return parts
    return [{"index": int(match.group(1)), "title": match.group(2), "body": ""} for match in re.finditer(r"^###\s+2\.(\d+)\.\s*(.+)$", markdown, re.M)]


def _content_type(context: CurriculumContext) -> Literal["hard_code", "low_code", "no_code"]:
    text = f"{context.direction} {context.current_project_title} {' '.join(context.current_project_skills)}".lower()
    if any(token in text for token in ("pjm", "product", "design", "маркет", "презентац", "документ", "ux")):
        return "no_code"
    if any(token in text for token in ("sql", "api", "backend", "python", "javascript", "java", "devops", "код")):
        return "hard_code"
    return "low_code"


def _has_blocking_quality(report: QualityGateReport) -> bool:
    return bool(report.violations or any(issue.get("severity") == "hard" for issue in report.methodology_issues))


def _comments_from_quality(report: QualityGateReport) -> str:
    parts = [item.get("reason") or f"{item.get('element')} expected {item.get('expected')} actual {item.get('actual')}" for item in report.violations]
    parts.extend(issue.get("message", "") for issue in report.methodology_issues if issue.get("severity") == "hard")
    return "\n".join(part for part in parts if part)


def _failure_memory(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    raw = ctx.get("regeneration_failure_memory") or ctx.get("failure_memory") or []
    return [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []


def _failure_memory_requests_retry(memory: list[dict[str, Any]]) -> bool:
    return any(str(item.get("code") or "").startswith(("patch_", "regeneration_")) for item in memory)


def _change_intent(comments: str, scopes: list[RegenerationScope]) -> ChangeIntent:
    text = comments.lower()
    structural = re.search(r"(?:добав|удал|переимен|обнов|перестро).{0,48}(?:глав|оглавлен|содержан|структур)", text)
    return "structural_document_edit" if structural else "local_section_edit"


def _validate_patch(patch: RegenerationPatch) -> tuple[bool, str | None]:
    if not patch.old_text.strip():
        return False, "old_text is empty"
    if "[[[BLOCK_" in patch.old_text or "```" in patch.old_text or "$$" in patch.old_text:
        return False, "old_text touches protected block"
    if len(patch.old_text.strip()) < 3:
        return False, "old_text too short"
    return True, None


def _find_text(text: str, pattern: str) -> tuple[int, int] | None:
    if pattern in text:
        start = text.find(pattern)
        return start, start + len(pattern)
    normalized = re.escape(pattern.strip())
    normalized = re.sub(r"\\\s+", r"\\s+", normalized)
    match = re.search(normalized, text, re.S)
    return (match.start(), match.end()) if match else None


def _find_in_scopes(text: str, pattern: str, scopes: list[RegenerationScope]) -> tuple[int, int, str] | None:
    for scope in scopes:
        block, offset = _scope_with_offset(text, scope)
        match = _find_text(block, pattern)
        if match:
            return offset + match[0], offset + match[1], scope.title
    return None


def _heading_ranges(markdown: str) -> list[tuple[int, int, int, str]]:
    lines = markdown.splitlines()
    headings: list[tuple[int, int, str]] = []
    for line_number, line in enumerate(lines, 1):
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match:
            headings.append((line_number, len(match.group(1)), match.group(2).strip()))
    ranges = []
    for idx, (start, level, title) in enumerate(headings):
        end = len(lines)
        for next_start, next_level, _ in headings[idx + 1 :]:
            if next_level <= level:
                end = next_start - 1
                break
        ranges.append((start, end, level, title))
    return ranges


def _scope_with_offset(markdown: str, scope: RegenerationScope) -> tuple[str, int]:
    starts = [0]
    for match in re.finditer(r"\n", markdown):
        starts.append(match.end())
    start = starts[min(scope.start_line - 1, len(starts) - 1)]
    end = starts[scope.end_line] if scope.end_line < len(starts) else len(markdown)
    return markdown[start:end], start


def _slice_scope(markdown: str, scope: RegenerationScope) -> str:
    return _scope_with_offset(markdown, scope)[0].rstrip("\n")


def _replace_scope(markdown: str, scope: RegenerationScope, replacement: str) -> str:
    block, offset = _scope_with_offset(markdown, scope)
    return markdown[:offset] + replacement.strip("\n") + ("\n" if block.endswith("\n") else "") + markdown[offset + len(block) :]


def _dedupe_scopes(scopes: list[RegenerationScope]) -> list[RegenerationScope]:
    result = []
    seen = set()
    for scope in scopes:
        key = (scope.start_line, scope.end_line, scope.title.lower())
        if key not in seen:
            result.append(scope)
            seen.add(key)
    return result


def _extract_field(block: str, label: str) -> str:
    pattern = re.compile(rf"{re.escape(label)}:\s*(.*?)(?=\n(?:Что исправить|Что оставить|Диапазон строк):|\Z)", re.I | re.S)
    match = pattern.search(block or "")
    return re.sub(r"\s+", " ", match.group(1)).strip() if match else ""


def _placeholder_replacement(comments: str, context: CurriculumContext | None = None) -> str:
    if comments and not PLACEHOLDER_RE.fullmatch(comments.strip()):
        return re.sub(r"\s+", " ", comments.strip())[:240]
    title = context.current_project_title if context else "проекта"
    return f"Сформулируй проверяемый результат для проекта «{title}»."


def _strip_instruction_leaks(markdown: str) -> str:
    return INSTRUCTION_LEAK_RE.sub("", markdown)


def _remove_duplicate_chapter_headers(markdown: str) -> str:
    lines = markdown.splitlines()
    result: list[str] = []
    previous = ""
    for line in lines:
        current = line.strip().lower()
        if line.startswith("## ") and current == previous:
            continue
        if line.startswith("### ") and current.replace("###", "##", 1) == previous:
            continue
        result.append(line)
        previous = current if line.startswith("#") else ""
    return "\n".join(result)


def _remove_adjacent_duplicate_paragraphs(markdown: str) -> str:
    blocks = re.split(r"\n{2,}", markdown)
    result: list[str] = []
    seen_long: set[str] = set()
    for block in blocks:
        normalized = re.sub(r"\s+", " ", block).strip().lower()
        if normalized and result and normalized == re.sub(r"\s+", " ", result[-1]).strip().lower():
            continue
        if len(normalized) >= 120 and normalized in seen_long:
            continue
        if len(normalized) >= 120:
            seen_long.add(normalized)
        result.append(block)
    return "\n\n".join(result)


def _fix_code_blocks(markdown: str) -> str:
    return markdown + ("\n```" if markdown.count("```") % 2 else "")


def _remove_empty_html_blocks(markdown: str) -> str:
    return re.sub(r"<div[^>]*>\s*</div>", "", markdown, flags=re.I | re.S)


def _postprocess_regenerated(original: str, regenerated: str) -> str:
    return _normalize_markdown(_remove_adjacent_duplicate_paragraphs(_strip_instruction_leaks(regenerated or original)))


def report_markdown_store(report: RegenerationReport, markdown: str) -> None:
    report.regenerated_markdown = markdown


def _artifact_refs(raw: Any) -> list[ArtifactRef]:
    if not isinstance(raw, list):
        return []
    refs = []
    for item in raw:
        try:
            refs.append(item if isinstance(item, ArtifactRef) else ArtifactRef.model_validate(item))
        except Exception:
            continue
    return refs


def _normalize_markdown(markdown: str) -> str:
    text = re.sub(r"[ \t]+\n", "\n", markdown or "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"
