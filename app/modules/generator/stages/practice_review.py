"""G4b practice critic, repair loop and optional bonus tasks."""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.llm.prompt_loader import PromptNotFoundError, load_prompt
from app.core.llm.structured import StructuredPrompt, complete_typed
from app.core.models import CurriculumContext, GeneratedDoc
from app.modules.generator.stages.head import _coerce_context
from app.modules.generator.stages.practice import (
    ArtifactChainPlan,
    PracticeTask,
    _active_goal,
    _artifact_path,
    _content_type,
    _ensure_p2p_criteria,
    _expected_artifact,
    _infer_covered_outcomes,
    _infer_theory_support,
    _normalize_task_input,
    _replace_practice_chapter,
    _render_practice_chapter,
    _sjm_anchors,
    _task_body,
    _theory_summary,
    normalize_sentence,
)

IssueKind = Literal["p2p_check", "theory_alignment", "story_alignment", "sjm_alignment", "raw_input", "goal", "artifact"]
IssueSeverity = Literal["critical", "error", "warning", "info"]


class PracticeIssue(BaseModel):
    """Practice critic finding."""

    model_config = ConfigDict(extra="forbid")

    task_index: int = Field(ge=1, le=20)
    kind: IssueKind
    severity: IssueSeverity
    message: str
    suggestion: str = ""


class PracticeCriticResponse(BaseModel):
    """Optional LLM critic response."""

    model_config = ConfigDict(extra="forbid")

    issues: list[PracticeIssue] = Field(default_factory=list)


class PracticeReviewResult(BaseModel):
    """G4b output."""

    model_config = ConfigDict(extra="forbid")

    tasks: list[PracticeTask]
    bonus_tasks: list[PracticeTask] = Field(default_factory=list)
    issues: list[PracticeIssue] = Field(default_factory=list)
    repaired_issue_count: int = 0
    markdown: str


def run(ctx: dict[str, Any], augment: str = "") -> dict[str, Any]:
    """Engine adapter for ``EngineStage('generator.practice_review', run)``."""
    context = _coerce_context(ctx)
    llm_issues = _llm_critic(context, ctx, ctx.get("llm_client"), augment) if ctx.get("llm_client") else []
    result = review_practice(
        context,
        markdown=str(ctx.get("markdown") or ""),
        engine_context=ctx,
        llm_issues=llm_issues,
        generate_bonus=bool(ctx.get("generate_bonus") or ctx.get("bonus_wish")),
    )
    return {
        "practice_review": result.model_dump(mode="json"),
        "practice_tasks": [task.model_dump(mode="json") for task in result.tasks],
        "bonus_tasks": [task.model_dump(mode="json") for task in result.bonus_tasks],
        "practice_critic_issues": [issue.model_dump(mode="json") for issue in result.issues],
        "practice_repaired_issue_count": result.repaired_issue_count,
        "markdown": result.markdown,
        "generated_doc": GeneratedDoc(
            markdown=result.markdown,
            metadata={
                "artifact_target": "readme_practice_review",
                "practice_issues_count": len(result.issues),
                "practice_repaired_issue_count": result.repaired_issue_count,
                "bonus_tasks_count": len(result.bonus_tasks),
            },
        ),
    }


def review_practice(
    context: CurriculumContext,
    *,
    markdown: str,
    engine_context: dict[str, Any] | None = None,
    llm_issues: list[PracticeIssue] | None = None,
    generate_bonus: bool = False,
    n_bonus: int = 1,
) -> PracticeReviewResult:
    """Review, repair and re-render practice tasks."""
    state = dict(engine_context or {})
    tasks = _coerce_tasks(state.get("practice_tasks"))
    theory = _theory_summary(state, markdown)
    issues = _dedupe_issues([*_deterministic_issues(context, tasks, theory), *(llm_issues or [])])
    repaired = _repair_tasks(context, tasks, issues, theory)
    bonus = _bonus_tasks(context, repaired, theory, n_bonus=n_bonus) if generate_bonus else []
    chapter = _render_practice_chapter(repaired)
    final_markdown = _replace_practice_chapter(markdown, chapter)
    if bonus:
        final_markdown = _upsert_bonus_section(final_markdown, bonus)
    return PracticeReviewResult(
        tasks=repaired,
        bonus_tasks=bonus,
        issues=issues,
        repaired_issue_count=len([issue for issue in issues if issue.severity in {"critical", "error", "warning"}]),
        markdown=final_markdown,
    )


def _llm_critic(context: CurriculumContext, state: dict[str, Any], client: Any, augment: str) -> list[PracticeIssue]:
    try:
        template = load_prompt("generator", "practice_review")
    except PromptNotFoundError:
        return []
    payload = {
        "curriculum_context": context.model_dump(mode="json"),
        "theory_parts": state.get("theory_parts") or [],
        "practice_tasks": state.get("practice_tasks") or [],
        "augment": augment,
    }
    prompt = template.render(context_json=json.dumps(payload, ensure_ascii=False, indent=2))
    try:
        response = complete_typed(
            StructuredPrompt(
                system="Return only valid JSON for PracticeCriticResponse.",
                user=prompt,
                kwargs={"temperature": 0.0, "max_tokens": 3000},
            ),
            PracticeCriticResponse,
            client=client,
            retries=1,
        )
    except Exception:
        return []
    return response.issues[:8]


def _deterministic_issues(context: CurriculumContext, tasks: list[PracticeTask], theory_summary: str) -> list[PracticeIssue]:
    issues: list[PracticeIssue] = []
    anchors = _sjm_anchors(context.sjm_context or "")
    for index, task in enumerate(tasks, 1):
        if not _has_story_context(task):
            issues.append(_issue(index, "story_alignment", "warning", "Task lacks a concrete story/situation context."))
        if anchors and not _has_anchor(task, anchors):
            issues.append(_issue(index, "sjm_alignment", "critical", "Task does not preserve SJM anchors."))
        if len([item for item in task.p2p_criteria if _is_observable(item)]) < 3:
            issues.append(_issue(index, "p2p_check", "error", "Task has weak observable P2P criteria."))
        if not task.artifact_location or task.artifact_location not in task.expected_artifact:
            issues.append(_issue(index, "artifact", "error", "Expected artifact lacks a concrete artifact location."))
        if _has_processed_or_solution_input(task.input_data):
            issues.append(_issue(index, "raw_input", "error", "Task input contains processed or solution-like materials."))
        if not _active_goal_prefix(task.goal):
            issues.append(_issue(index, "goal", "warning", "Task goal is not active and checkable."))
        if theory_summary and not task.theory_support and index <= max(1, len(tasks) - 1):
            issues.append(_issue(index, "theory_alignment", "warning", "Task is weakly grounded in Chapter 2 theory."))
    return _suppress_false_positives(issues, context, tasks, theory_summary)


def _repair_tasks(context: CurriculumContext, tasks: list[PracticeTask], issues: list[PracticeIssue], theory_summary: str) -> list[PracticeTask]:
    repaired = [task.model_copy(deep=True) for task in tasks]
    content_type = _content_type(context)
    by_task: dict[int, list[PracticeIssue]] = {}
    for issue in issues:
        by_task.setdefault(issue.task_index, []).append(issue)

    for index, task in enumerate(repaired, 1):
        task_issues = by_task.get(index, [])
        previous = repaired[index - 2] if index > 1 else None
        if any(issue.kind in {"raw_input", "artifact"} for issue in task_issues):
            task.input_data = _normalize_task_input(task.input_data, index=index, chain=_chain_from_context(context, repaired), previous=previous)
        if any(issue.kind == "goal" for issue in task_issues):
            task.goal = _active_goal(task.goal, content_type)
        if any(issue.kind in {"story_alignment", "sjm_alignment"} for issue in task_issues):
            task.situation = _repair_situation(context, task, index)
        if any(issue.kind == "theory_alignment" for issue in task_issues):
            support = _infer_theory_support(theory_summary, task.title, task.goal, " ".join(task.approach_bullets))
            task.theory_support = support or task.theory_support
            if task.theory_support and not _mentions_support(task.approach_bullets, task.theory_support):
                task.approach_bullets = [
                    *task.approach_bullets[:5],
                    normalize_sentence(f"Свяжи решение с темами из теории: {', '.join(task.theory_support[:2])}"),
                ]
        if any(issue.kind in {"p2p_check", "artifact", "theory_alignment"} for issue in task_issues):
            artifact_location = task.artifact_location or _artifact_path(context, index)
            task.expected_artifact = _expected_artifact(task.expected_artifact, task.title, artifact_location, content_type)
            task.artifact_location = artifact_location
            task.p2p_criteria = _ensure_p2p_criteria(task.p2p_criteria, task.artifact_location, task.expected_artifact, task.theory_support)
        task.covered_outcomes = _infer_covered_outcomes(context, task.title, task.situation, task.goal, " ".join(task.approach_bullets))
        repaired[index - 1] = task
    return repaired


def _bonus_tasks(context: CurriculumContext, tasks: list[PracticeTask], theory_summary: str, *, n_bonus: int) -> list[PracticeTask]:
    count = max(1, min(2, n_bonus))
    support = re.findall(r"^\s*\d+\.\s+(.+?)\s*$", theory_summary or "", flags=re.M)
    bonus: list[PracticeTask] = []
    last_artifact = tasks[-1].artifact_location if tasks else ""
    content_type = _content_type(context)
    for index in range(1, count + 1):
        title = f"Бонус: улучшение {context.current_project_title or 'проекта'}"
        artifact = _bonus_artifact_path(context, index)
        theory_support = support[:2]
        task = PracticeTask(
            title=title,
            situation=normalize_sentence(
                f"После основной цепочки у тебя есть итоговый артефакт `{last_artifact}`. Нужно усилить решение без изменения базовых требований."
            ),
            constraints_or_risk=normalize_sentence("Бонус не должен ломать основной результат и должен быть проверяем отдельно."),
            input_data=normalize_sentence(f"Основной результат проекта — см. файл `{last_artifact}`.") if last_artifact else "Итоговый артефакт основной практики.",
            goal=_active_goal("Улучшить итоговый артефакт и добавить обоснование выбранного улучшения", content_type),
            approach_bullets=[
                "Выбери одно ограничение или риск, который остался после основной практики.",
                "Предложи улучшение и объясни, почему оно не ломает базовый результат.",
                "Оформи отдельный bonus README с решением, проверкой и выводом.",
            ],
            expected_artifact=_expected_artifact("", title, artifact, content_type),
            artifact_location=artifact,
            p2p_criteria=[],
            covered_outcomes=context.current_project_learning_outcomes[:2],
            theory_support=theory_support,
        )
        task.p2p_criteria = _ensure_p2p_criteria([], task.artifact_location, task.expected_artifact, task.theory_support)
        bonus.append(task)
    return bonus


def _upsert_bonus_section(markdown: str, bonus_tasks: list[PracticeTask]) -> str:
    if not bonus_tasks:
        return markdown
    chunks = ["## Бонус"]
    for index, task in enumerate(bonus_tasks, 1):
        chunks.extend(["", f"### Бонусное задание {index}. {task.title}", "", _task_body(task, None)])
    section = "\n".join(chunks).strip()
    bonus_re = re.compile(r"^##\s+Бонус\b[\s\S]*\Z", re.M)
    if bonus_re.search(markdown):
        return bonus_re.sub(section, markdown).strip()
    return f"{markdown.rstrip()}\n\n{section}"


def _coerce_tasks(raw: Any) -> list[PracticeTask]:
    if not raw:
        return []
    return [item if isinstance(item, PracticeTask) else PracticeTask.model_validate(item) for item in raw]


def _suppress_false_positives(
    issues: list[PracticeIssue],
    context: CurriculumContext,
    tasks: list[PracticeTask],
    theory_summary: str,
) -> list[PracticeIssue]:
    filtered: list[PracticeIssue] = []
    for issue in issues:
        task = tasks[issue.task_index - 1] if 0 <= issue.task_index - 1 < len(tasks) else None
        if not task:
            continue
        if issue.kind == "p2p_check" and len([item for item in task.p2p_criteria if _is_observable(item)]) >= 3:
            continue
        if issue.kind == "theory_alignment" and task.theory_support:
            continue
        if issue.kind == "sjm_alignment" and _has_anchor(task, _sjm_anchors(context.sjm_context or "")):
            continue
        if issue.kind == "story_alignment" and _has_story_context(task):
            continue
        if issue.kind == "raw_input" and not _has_processed_or_solution_input(task.input_data):
            continue
        filtered.append(issue)
    return filtered[:12]


def _dedupe_issues(issues: list[PracticeIssue]) -> list[PracticeIssue]:
    seen: set[tuple[int, str]] = set()
    result: list[PracticeIssue] = []
    for issue in issues:
        key = (issue.task_index, issue.kind)
        if key in seen:
            continue
        seen.add(key)
        result.append(issue)
    return result


def _issue(task_index: int, kind: IssueKind, severity: IssueSeverity, message: str) -> PracticeIssue:
    return PracticeIssue(task_index=task_index, kind=kind, severity=severity, message=message)


def _has_story_context(task: PracticeTask) -> bool:
    text = f"{task.situation} {task.constraints_or_risk}".lower()
    actors = ("ты", "команда", "заказчик", "клиент", "проект")
    tension = ("нужно", "риск", "срок", "ошиб", "огранич", "соглас", "проблем", "важно")
    return len(text) >= 60 and any(item in text for item in actors) and any(item in text for item in tension)


def _has_anchor(task: PracticeTask, anchors: list[str]) -> bool:
    if not anchors:
        return True
    text = f"{task.situation} {task.constraints_or_risk} {task.expected_artifact}".lower()
    required = min(2, len(anchors))
    return sum(1 for anchor in anchors if anchor in text) >= required


def _is_observable(text: str) -> bool:
    low = (text or "").lower()
    signals = ("содержит", "есть", "описан", "размещ", "указан", "заполн", "обоснован", "путь", "файл", "раздел", "таблица", "схема")
    return len(low) >= 12 and any(signal in low for signal in signals)


def _has_processed_or_solution_input(text: str) -> bool:
    low = (text or "").lower()
    if re.search(r"\b(готов\w*\s+(?:матриц|план|отч[её]т|решени)|итогов\w+\s+(?:документ|таблиц))\b", low):
        return True
    refs = re.findall(r"`?(materials/[A-Za-z0-9_.-]+\.[A-Za-z0-9]+)`?", text or "", flags=re.I)
    return any(re.search(r"(final|result|solution|answer|итог|решени|матриц)", ref, re.I) for ref in refs)


def _active_goal_prefix(goal: str) -> bool:
    return bool(re.match(r"^(?:сформировать|подготовить|описать|проанализировать|спроектировать|разработать|настроить|проверить|собрать|оформить|сравнить|выбрать|зафиксировать)\b", goal or "", flags=re.I))


def _repair_situation(context: CurriculumContext, task: PracticeTask, index: int) -> str:
    anchors = _sjm_anchors(context.sjm_context or "")
    anchor_text = " Заказчик остаётся главным адресатом результата." if "заказчик" in anchors else ""
    if len(task.situation) >= 40:
        return normalize_sentence(f"{task.situation} {anchor_text}".strip())
    case = context.sjm_context or context.current_project_description or context.current_project_title
    return normalize_sentence(f"Ты работаешь с кейсом проекта: {case}. На шаге {index} нужно принять решение и показать проверяемый результат.{anchor_text}")


def _mentions_support(items: list[str], support: list[str]) -> bool:
    blob = " ".join(items).lower()
    return any(set(re.findall(r"[А-Яа-яЁёA-Za-z0-9]+", topic.lower())) & set(re.findall(r"[А-Яа-яЁёA-Za-z0-9]+", blob)) for topic in support)


def _chain_from_context(context: CurriculumContext, tasks: list[PracticeTask]) -> ArtifactChainPlan:
    from app.modules.generator.stages.practice import ArtifactStep, EvidenceSpec, raw_material_path_for_task

    raw_path = raw_material_path_for_task(1)
    steps = []
    for index, task in enumerate(tasks, 1):
        previous = tasks[index - 2].artifact_location if index > 1 else None
        steps.append(
            ArtifactStep(
                task_index=index,
                input_refs=[raw_path] if index == 1 else ([previous] if previous else []),
                artifact_location=task.artifact_location or _artifact_path(context, index),
                artifact_kind=task.expected_artifact or "проверяемый артефакт",
                depends_on=previous,
            )
        )
    return ArtifactChainPlan(
        raw_input_path=raw_path,
        steps=steps,
        evidence_specs=[EvidenceSpec(path=raw_path, source_task_index=1)],
    )


def _bonus_artifact_path(context: CurriculumContext, index: int) -> str:
    root = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(context.current_project_platform_name or context.current_project_title or "project")).strip("_.-")
    return f"{root or 'project'}/part-03/bonus-{index:02d}/README.md"
