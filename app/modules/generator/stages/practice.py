"""G4a practice core stage: task contracts, artifact chain and Chapter 3 rendering."""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import get_thresholds
from app.core.llm.prompt_loader import PromptNotFoundError, load_prompt
from app.core.llm.structured import StructuredPrompt, complete_typed
from app.core.models import CurriculumContext, GeneratedDoc
from app.modules.generator.stages.head import _coerce_context

ContentType = Literal["hard_code", "low_code", "no_code"]
ProjectRole = Literal["single", "lead", "executor", "reviewer"]

MATERIAL_REF_RE = re.compile(r"`?(materials/[A-Za-z0-9_.-]+\.[A-Za-z0-9]+)`?", re.I)
ARTIFACT_PATH_RE = re.compile(r"([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+\.[A-Za-z0-9]+)")
CODE_FENCE_RE = re.compile(r"```[\s\S]*?```", re.M)
FORMULA_RE = re.compile(r"\$\$[\s\S]*?\$\$|\$[^$\n]+\$", re.M)
WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9_/-]*")
SOLUTION_STEM_RE = re.compile(
    r"(^|[_-])(answer|solution|final|result|output|deliverable|matrix|analysis|plan|report|"
    r"итог|решени[ея]|матриц[аы]|рекомендаци[яи])($|[_-])",
    re.I,
)
PROCESSED_MATERIAL_RE = re.compile(
    r"\b(готов\w*\s+(?:список|реестр|матриц\w*|план|отч[её]т)|"
    r"заполненн\w+\s+(?:таблиц\w*|матриц\w*)|"
    r"итогов\w+\s+(?:таблиц\w*|документ\w*|отч[её]т))\b",
    re.I,
)
ACTIVE_GOAL_RE = re.compile(
    r"^(?:сформировать|подготовить|описать|проанализировать|спроектировать|разработать|настроить|"
    r"проверить|собрать|оформить|сравнить|выбрать|зафиксировать)\b",
    re.I,
)


class PracticeDraftTask(BaseModel):
    """One optional LLM-drafted practice task."""

    model_config = ConfigDict(extra="forbid")

    title: str = ""
    situation: str = ""
    constraints_or_risk: str = ""
    input_data: str = ""
    goal: str = ""
    approach_bullets: list[str] = Field(default_factory=list)
    expected_artifact: str = ""
    p2p_criteria: list[str] = Field(default_factory=list)


class PracticeDraft(BaseModel):
    """Optional typed LLM output. Deterministic contracts still own final shape."""

    model_config = ConfigDict(extra="forbid")

    tasks: list[PracticeDraftTask] = Field(default_factory=list)


class EvidenceSpec(BaseModel):
    """Raw evidence file contract used by later dataset generation."""

    model_config = ConfigDict(extra="forbid")

    path: str
    evidence_type: str = "raw_case_evidence"
    contains: list[str] = Field(default_factory=list)
    excludes: list[str] = Field(default_factory=list)
    student_must_derive: list[str] = Field(default_factory=list)
    source_task_index: int | None = None


class ArtifactStep(BaseModel):
    """One transition in the practice artifact chain."""

    model_config = ConfigDict(extra="forbid")

    task_index: int = Field(ge=1)
    input_refs: list[str] = Field(default_factory=list)
    artifact_location: str
    artifact_kind: str
    depends_on: str | None = None


class ArtifactChainPlan(BaseModel):
    """Practice-wide raw-input -> task artifacts contract."""

    model_config = ConfigDict(extra="forbid")

    raw_input_path: str
    steps: list[ArtifactStep] = Field(default_factory=list)
    evidence_specs: list[EvidenceSpec] = Field(default_factory=list)


class PracticeTask(BaseModel):
    """Structured practice task consumed by gate/checker and rendered into Chapter 3."""

    model_config = ConfigDict(extra="forbid")

    title: str
    situation: str
    constraints_or_risk: str
    input_data: str
    goal: str
    approach_bullets: list[str] = Field(default_factory=list)
    expected_artifact: str
    artifact_location: str
    p2p_checkable: bool = True
    p2p_criteria: list[str] = Field(default_factory=list)
    covered_outcomes: list[str] = Field(default_factory=list)
    theory_support: list[str] = Field(default_factory=list)
    group_roles: list[ProjectRole] | None = None

    @field_validator("approach_bullets", "p2p_criteria")
    @classmethod
    def compact_non_empty_list(cls, value: list[str]) -> list[str]:
        return [normalize_sentence(item) for item in value if item and str(item).strip()]


class PracticeResult(BaseModel):
    """Full G4a stage output."""

    model_config = ConfigDict(extra="forbid")

    tasks: list[PracticeTask]
    artifact_chain_plan: ArtifactChainPlan
    evidence_specs: list[EvidenceSpec] = Field(default_factory=list)
    markdown: str
    warnings: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)


def run(ctx: dict[str, Any], augment: str = "") -> dict[str, Any]:
    """Engine adapter for ``EngineStage('generator.practice', run)``."""
    context = _coerce_context(ctx)
    markdown = str(ctx.get("markdown") or "")
    draft = _llm_draft(context, markdown, ctx, ctx.get("llm_client"), augment) if ctx.get("llm_client") else None
    result = generate_practice(context, markdown=markdown, engine_context=ctx, draft=draft)
    return {
        "practice": result.model_dump(mode="json"),
        "practice_tasks": [task.model_dump(mode="json") for task in result.tasks],
        "artifact_chain_plan": result.artifact_chain_plan.model_dump(mode="json"),
        "evidence_specs": [spec.model_dump(mode="json") for spec in result.evidence_specs],
        "dataset_files": [],
        "practice_warnings": result.warnings,
        "practice_issues": result.issues,
        "markdown": result.markdown,
        "generated_doc": GeneratedDoc(
            markdown=result.markdown,
            metadata={
                "artifact_target": "readme_practice",
                "practice_tasks_count": len(result.tasks),
                "evidence_specs_count": len(result.evidence_specs),
            },
        ),
    }


def generate_practice(
    context: CurriculumContext,
    *,
    markdown: str = "",
    engine_context: dict[str, Any] | None = None,
    draft: PracticeDraft | None = None,
) -> PracticeResult:
    """Generate Chapter 3 tasks and enforce artifact/input contracts."""
    state = dict(engine_context or {})
    count = _task_count(state)
    content_type = _content_type(context)
    theory_summary = _theory_summary(state, markdown)
    chain = _build_artifact_chain(context, count, theory_summary)
    raw_tasks = _raw_tasks(context, count=count, draft=draft)
    tasks: list[PracticeTask] = []
    for index, raw in enumerate(raw_tasks, 1):
        previous = tasks[-1] if tasks else None
        tasks.append(_materialize_task(index, raw, context, theory_summary, chain, previous, content_type))
    chain = _refresh_artifact_chain(chain, tasks, context)
    tasks = _ensure_sjm_anchors(tasks, context)
    chapter = _render_practice_chapter(tasks)
    return PracticeResult(
        tasks=tasks,
        artifact_chain_plan=chain,
        evidence_specs=chain.evidence_specs,
        markdown=_replace_practice_chapter(markdown or _minimal_markdown(context), chapter),
        warnings=[],
        issues=[] if tasks else ["practice.tasks_empty"],
    )


def _llm_draft(context: CurriculumContext, markdown: str, state: dict[str, Any], client: Any, augment: str) -> PracticeDraft | None:
    try:
        template = load_prompt("generator", "practice")
    except PromptNotFoundError:
        return None
    payload = {
        "curriculum_context": context.model_dump(mode="json"),
        "task_plan": state.get("task_plan") or {},
        "theory_parts": state.get("theory_parts") or [],
        "markdown": markdown[:8000],
        "thresholds": get_thresholds().get("methodology.practice_tasks_range"),
        "augment": augment,
    }
    prompt = template.render(context_json=json.dumps(payload, ensure_ascii=False, indent=2))
    try:
        return complete_typed(
            StructuredPrompt(
                system="Return only valid JSON for PracticeDraft.",
                user=prompt,
                kwargs={"temperature": 0.2, "max_tokens": 7000},
            ),
            PracticeDraft,
            client=client,
            retries=1,
        )
    except Exception:
        return None


def _task_count(state: dict[str, Any]) -> int:
    min_tasks, max_tasks = get_thresholds().require_range("methodology.practice_tasks_range")
    plan = state.get("task_plan") if isinstance(state.get("task_plan"), dict) else {}
    if plan.get("tasks_count") is not None:
        return max(int(min_tasks), min(int(max_tasks), int(plan["tasks_count"])))
    recommend = get_thresholds().get("methodology.practice_tasks_recommend", [2, 5])
    return max(int(min_tasks), min(int(max_tasks), int(recommend[0])))


def _raw_tasks(context: CurriculumContext, *, count: int, draft: PracticeDraft | None) -> list[PracticeDraftTask]:
    result = list((draft.tasks if draft else [])[:count])
    titles = _task_titles(context, count)
    while len(result) < count:
        result.append(PracticeDraftTask(title=titles[len(result)]))
    return result[:count]


def _task_titles(context: CurriculumContext, count: int) -> list[str]:
    verbs = ["Разбор", "Проектирование", "Подготовка", "Проверка", "Документирование", "Защита", "Улучшение", "Итог"]
    topics = [
        *context.current_project_skills,
        *context.current_project_required_tools,
        *context.current_project_required_software,
        *context.current_project_learning_outcomes,
        context.current_project_title,
    ]
    clean_topics = [_short_topic(topic) for topic in topics if _short_topic(topic)]
    titles: list[str] = []
    for index in range(count):
        topic = clean_topics[index % len(clean_topics)] if clean_topics else context.current_project_title
        titles.append(f"{verbs[index % len(verbs)]} {topic}".strip())
    return titles


def _materialize_task(
    index: int,
    raw: PracticeDraftTask,
    context: CurriculumContext,
    theory_summary: str,
    chain: ArtifactChainPlan,
    previous: PracticeTask | None,
    content_type: ContentType,
) -> PracticeTask:
    step = chain.steps[index - 1]
    title = _sanitize_title(raw.title or f"Задача {index}", content_type)
    input_data = _normalize_task_input(raw.input_data, index=index, chain=chain, previous=previous)
    goal = _active_goal(raw.goal or _default_goal(title, context, index), content_type)
    situation = _sentence(raw.situation or _default_situation(context, index, goal))
    risk = _sentence(raw.constraints_or_risk or _default_risk(context, goal))
    artifact_location = _artifact_path(context, index)
    expected = _expected_artifact(raw.expected_artifact, title, artifact_location, content_type)
    approach = _approach_bullets(raw.approach_bullets, title, goal, input_data, context, theory_summary, content_type)
    support = _infer_theory_support(theory_summary, title, situation, risk, goal, input_data, " ".join(approach))
    if support and not _has_theory_anchor(approach, support):
        approach = [*approach[:5], f"Проверь, что решение использует темы из теории: {', '.join(support[:2])}."]
    outcomes = _infer_covered_outcomes(context, title, situation, risk, goal, input_data, " ".join(approach))
    criteria = _ensure_p2p_criteria(raw.p2p_criteria, artifact_location, expected, support)
    group_roles = _group_roles(context)
    return PracticeTask(
        title=title,
        situation=situation,
        constraints_or_risk=risk,
        input_data=input_data,
        goal=goal,
        approach_bullets=approach[:6],
        expected_artifact=expected,
        artifact_location=artifact_location or step.artifact_location,
        p2p_criteria=criteria,
        covered_outcomes=outcomes,
        theory_support=support,
        group_roles=group_roles,
    )


def _build_artifact_chain(context: CurriculumContext, task_count: int, theory_summary: str) -> ArtifactChainPlan:
    raw_path = raw_material_path_for_task(1)
    steps: list[ArtifactStep] = []
    previous: str | None = None
    for index in range(1, task_count + 1):
        artifact = _artifact_path(context, index)
        input_refs = [raw_path] if index == 1 else []
        if previous:
            input_refs.append(previous)
        steps.append(
            ArtifactStep(
                task_index=index,
                input_refs=input_refs,
                artifact_location=artifact,
                artifact_kind=_artifact_kind(context, index, task_count, theory_summary),
                depends_on=previous,
            )
        )
        previous = artifact
    return ArtifactChainPlan(
        raw_input_path=raw_path,
        steps=steps,
        evidence_specs=[_evidence_spec(raw_path, context, 1)],
    )


def _refresh_artifact_chain(chain: ArtifactChainPlan, tasks: list[PracticeTask], context: CurriculumContext) -> ArtifactChainPlan:
    specs: dict[str, EvidenceSpec] = {spec.path.lower(): spec for spec in chain.evidence_specs}
    steps: list[ArtifactStep] = []
    for index, task in enumerate(tasks, 1):
        previous = tasks[index - 2].artifact_location if index > 1 else None
        refs = extract_material_refs(task.input_data)
        if previous and previous not in refs:
            refs.append(previous)
        for ref in refs:
            if ref.startswith("materials/") and ref.lower() not in specs:
                specs[ref.lower()] = _evidence_spec(ref, context, index)
        steps.append(
            ArtifactStep(
                task_index=index,
                input_refs=refs,
                artifact_location=task.artifact_location,
                artifact_kind=_artifact_kind_from_task(task),
                depends_on=previous,
            )
        )
    return ArtifactChainPlan(raw_input_path=chain.raw_input_path, steps=steps, evidence_specs=sorted(specs.values(), key=lambda item: item.path))


def _evidence_spec(path: str, context: CurriculumContext, task_index: int) -> EvidenceSpec:
    topic = context.current_project_title or context.block_name
    return EvidenceSpec(
        path=path,
        contains=[
            f"сырые наблюдения, факты и ограничения по теме «{topic}»",
            "неоднородные записи, которые требуют анализа",
            "контекст, достаточный для выполнения задачи без внешних данных",
        ],
        excludes=[
            "готовый итоговый ответ",
            "заполненный артефакт студента",
            "классифицированную таблицу или матрицу",
            "готовый план, отчет, рекомендации или стратегию",
        ],
        student_must_derive=[
            "выводы, классификацию и решение по задаче",
            "структуру и содержание итогового артефакта",
        ],
        source_task_index=task_index,
    )


def _render_practice_chapter(tasks: list[PracticeTask]) -> str:
    chunks = ["## Глава 3. Практика"]
    for index, task in enumerate(tasks, 1):
        next_task = tasks[index] if index < len(tasks) else None
        chunks.extend(["", f"### Задание {index}. {task.title}", "", _task_body(task, next_task)])
    return _normalize_markdown("\n".join(chunks))


def _task_body(task: PracticeTask, next_task: PracticeTask | None) -> str:
    action_lines = [
        "**Что нужно сделать**",
        "",
        f"Ситуация: {task.situation}",
        f"Исходные данные: {task.input_data}",
        f"Цель: {task.goal}",
        "Подход:",
        *[f"- {item}" for item in task.approach_bullets],
        "",
        "**Что должно получиться**",
        "",
        *[f"- [ ] {item}" for item in _observable_results(task)],
        "",
        "**Ограничения и условия**",
        "",
        task.constraints_or_risk,
    ]
    if task.group_roles:
        action_lines.extend(["", f"Роли для группы: {', '.join(task.group_roles)}."])
    action_lines.extend(
        [
            "",
            "**Формат сдачи**",
            "",
            f"На p2p-ревью покажи артефакт по пути `{task.artifact_location}` и сверь его с блоком «Что должно получиться».",
            "",
            "**Переход к следующему заданию**",
            "",
            _transition(task, next_task),
        ]
    )
    return "\n".join(action_lines).strip()


def _replace_practice_chapter(markdown: str, practice_chapter: str) -> str:
    base = markdown.strip()
    if not base:
        return practice_chapter
    chapter_re = re.compile(r"^##\s+Глава\s+3[^\n]*\n[\s\S]*?(?=^##\s+Глава\s+4|\Z)", re.M)
    if chapter_re.search(base):
        return _normalize_markdown(chapter_re.sub(practice_chapter, base, count=1))
    return _normalize_markdown(f"{base}\n\n{practice_chapter}")


def _minimal_markdown(context: CurriculumContext) -> str:
    return f"# {context.current_project_title or 'Учебный проект'}\n\n## Глава 3. Практика"


def _normalize_task_input(input_data: str, *, index: int, chain: ArtifactChainPlan, previous: PracticeTask | None) -> str:
    normalized = _sentence(input_data)
    if _looks_processed_material(normalized):
        normalized = ""
    if index == 1:
        raw = chain.raw_input_path
        if raw.lower() not in normalized.lower():
            suffix = f"Сырые исходные материалы рабочего кейса — см. файл `{raw}`."
            normalized = f"{normalized} {suffix}".strip() if normalized else suffix
    elif previous and previous.artifact_location.lower() not in normalized.lower():
        suffix = f"Результат предыдущей задачи — см. файл `{previous.artifact_location}`."
        normalized = f"{normalized} {suffix}".strip() if normalized else suffix
    return normalized


def _looks_processed_material(text: str) -> bool:
    if PROCESSED_MATERIAL_RE.search(text or ""):
        return True
    return any(is_solution_like_material_ref(ref, context=text) for ref in extract_material_refs(text))


def _expected_artifact(value: str, title: str, artifact_location: str, content_type: ContentType) -> str:
    text = _sanitize_no_code(_sentence(value), content_type)
    if not text or _is_generic_expected_artifact(text):
        kind = _artifact_subject(title, content_type)
        text = f"Документ README.md с {kind}: исходные допущения, решение, обоснование выбора и итоговый вывод."
    if artifact_location.lower() not in text.lower():
        text = f"{text.rstrip('.')} Артефакт размещён по пути `{artifact_location}`."
    return text


def _approach_bullets(
    bullets: list[str],
    title: str,
    goal: str,
    input_data: str,
    context: CurriculumContext,
    theory_summary: str,
    content_type: ContentType,
) -> list[str]:
    cleaned = [normalize_sentence(_sanitize_no_code(item, content_type)) for item in bullets if item and item.strip()]
    if not cleaned:
        cleaned = [
            f"Разбери входные данные и выпиши ограничения, которые влияют на задачу «{title}».",
            f"Сформулируй решение, которое прямо закрывает цель: {goal}.",
            "Проверь решение на согласованность с контекстом проекта и учебными результатами.",
            "Оформи результат в README так, чтобы другой участник мог проверить ход рассуждений.",
        ]
    if input_data and not any("входн" in item.lower() or "материал" in item.lower() for item in cleaned):
        cleaned.insert(0, "Начни с входных материалов и отдели факты от предположений.")
    support = _infer_theory_support(theory_summary, *cleaned)
    if support and not _has_theory_anchor(cleaned, support):
        cleaned.append(f"Свяжи решение с теорией: {', '.join(support[:2])}.")
    return list(dict.fromkeys(cleaned))[:6]


def _ensure_p2p_criteria(criteria: list[str], artifact_location: str, expected_artifact: str, theory_support: list[str]) -> list[str]:
    normalized: list[str] = []
    for criterion in criteria:
        item = normalize_sentence(criterion)
        if _is_observable(item):
            normalized.append(item)
    if artifact_location and not any(artifact_location.lower() in item.lower() or "по указанному пути" in item.lower() for item in normalized):
        normalized.append(f"Артефакт размещён по указанному пути `{artifact_location}`.")
    normalized.append("В документе есть отдельные разделы с решением, аргументацией и итоговым выводом.")
    if theory_support:
        normalized.append(f"Документ явно использует понятия из теории: {', '.join(theory_support[:2])}.")
    normalized.append("Формулировки конкретны и позволяют проверить результат без устных пояснений автора.")
    return list(dict.fromkeys(normalized))[:5]


def _observable_results(task: PracticeTask) -> list[str]:
    results = [task.expected_artifact]
    for criterion in task.p2p_criteria:
        if criterion not in results:
            results.append(criterion)
        if len(results) >= 5:
            break
    return results[:5]


def _transition(task: PracticeTask, next_task: PracticeTask | None) -> str:
    if next_task is not None:
        return f"В следующем задании используй этот результат как входные данные для шага «{next_task.title}»."
    return "На этом шаге практическая цепочка завершается: итог должен быть проверяемым без устных пояснений автора."


def _theory_summary(state: dict[str, Any], markdown: str) -> str:
    parts = list(state.get("theory_parts") or [])
    titles: list[str] = []
    terms: list[str] = []
    for part in parts:
        title = str(_get(part, "title", "") or "").strip()
        if title:
            titles.append(title)
        terms.extend(str(term) for term in (_get(part, "definitions_found", []) or []) if str(term).strip())
    if not titles:
        chapter = _extract_chapter(markdown, "2", "3")
        titles = re.findall(r"^###\s+2\.\d+\.\s+(.+?)\s*$", chapter, flags=re.M)
        terms = re.findall(r"\*\*([^*\n]{2,80})\*\*\s*[—-]\s*(?:это|представляет собой|является)?", chapter, flags=re.I)
    if not titles:
        return "Глава 2 ещё не сгенерирована. Ориентируйся на описание проекта и LO."
    lines = ["КЛЮЧЕВЫЕ ТЕМЫ ИЗ ТЕОРИИ (Глава 2):"]
    lines.extend(f"{index}. {title}" for index, title in enumerate(titles, 1))
    if terms:
        lines.extend(["", "КЛЮЧЕВЫЕ ПОНЯТИЯ (используй в заданиях):"])
        lines.extend(f"  - {term}" for term in list(dict.fromkeys(terms))[:7])
    return "\n".join(lines)


def _extract_chapter(markdown: str, current: str, next_chapter: str | None) -> str:
    end = rf"(?=^##\s+Глава\s+{next_chapter}\b|\Z)" if next_chapter else r"\Z"
    match = re.search(rf"^##\s+Глава\s+{current}[^\n]*\n([\s\S]*?){end}", markdown or "", flags=re.M)
    return match.group(1).strip() if match else ""


def _infer_theory_support(theory_summary: str, *texts: str) -> list[str]:
    topics = re.findall(r"^\s*\d+\.\s+(.+?)\s*$", theory_summary or "", flags=re.M)
    blob = set().union(*[_token_set(text) for text in texts]) if texts else set()
    scored = [(len(blob & _token_set(topic)), topic) for topic in topics]
    return [topic for score, topic in sorted(scored, reverse=True) if score > 0][:2]


def _infer_covered_outcomes(context: CurriculumContext, *texts: str) -> list[str]:
    blob = set().union(*[_token_set(text) for text in texts]) if texts else set()
    scored = [(len(blob & _token_set(outcome)), outcome) for outcome in context.current_project_learning_outcomes]
    return [outcome for score, outcome in sorted(scored, reverse=True) if score > 0][:2]


def _ensure_sjm_anchors(tasks: list[PracticeTask], context: CurriculumContext) -> list[PracticeTask]:
    anchors = _sjm_anchors(context.sjm_context or "")
    if not anchors:
        return tasks
    target = "заказчик" if "заказчик" in anchors else anchors[0]
    for index, task in enumerate(tasks[:2]):
        blob = f"{task.situation} {task.expected_artifact}".lower()
        if target not in blob:
            task.situation = normalize_sentence(
                f"{task.situation} Заказчик остаётся главным адресатом результата."
                if target == "заказчик"
                else f"{task.situation} Сохрани якорь кейса: {target}."
            )
            task.expected_artifact = normalize_sentence(f"{task.expected_artifact} Артефакт показывает решение для {target}.")
            tasks[index] = task
    return tasks


def _sjm_anchors(text: str) -> list[str]:
    low = (text or "").lower()
    anchors: list[str] = []
    if "заказчик" in low:
        anchors.append("заказчик")
    role = re.search(r"ты\s+[—-]\s+([^.!?\n]+)", low)
    if role:
        anchors.append(role.group(1).strip(" ,"))
    for pattern in (r"\b\d+\s*(?:час(?:а|ов)?|дн(?:я|ей)?|недел[ьяи]?)\b", r"бюджет", r"релиз", r"срок"):
        match = re.search(pattern, low)
        if match:
            anchors.append(match.group(0))
    return list(dict.fromkeys(anchor for anchor in anchors if anchor))[:5]


def _active_goal(goal: str, content_type: ContentType) -> str:
    text = _sanitize_no_code(_sentence(goal), content_type)
    replacements = {
        r"\bизуч(ить|и|ать|ение)\b": "проанализировать",
        r"\bознаком(иться|ься|ление)\b": "описать",
        r"\bпоня(ть|тие|имать)\b": "объяснить",
        r"\bрассмотр(еть|и|ение)\b": "проанализировать",
    }
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text, flags=re.I)
    if not ACTIVE_GOAL_RE.search(text):
        text = f"Сформировать {text[0].lower() + text[1:] if text else 'проверяемый артефакт'}"
    return _sentence(text)


def _default_goal(title: str, context: CurriculumContext, index: int) -> str:
    outcome = _pick(context.current_project_learning_outcomes, index - 1) or f"подготовить результат по теме «{title}»"
    return f"Сформировать артефакт, который показывает: {outcome}"


def _default_situation(context: CurriculumContext, index: int, goal: str) -> str:
    base = context.sjm_context or context.current_project_description or context.current_project_title
    return f"Ты работаешь с кейсом проекта: {base}. На шаге {index} нужно принять решение и сделать его проверяемым. Фокус: {goal}."


def _default_risk(context: CurriculumContext, goal: str) -> str:
    if context.current_project_workload_hours and context.current_project_workload_hours <= 4:
        return "Есть ограничение по времени: результат должен быть компактным и проверяемым без лишних итераций."
    return f"Главный риск — оформить решение по цели «{goal}» слишком общо, без критериев и связи с ограничениями проекта."


def _sanitize_title(title: str, content_type: ContentType) -> str:
    clean = re.sub(r"\s+", " ", (title or "Практическая задача").strip(" .,:;"))
    if content_type == "no_code":
        clean = re.sub(r"\b(?:код|скрипт|деплой|pipeline)\w*\b", "артефакт", clean, flags=re.I)
    return clean[:1].upper() + clean[1:]


def _sanitize_no_code(text: str, content_type: ContentType) -> str:
    clean = text or ""
    if content_type == "no_code":
        clean = CODE_FENCE_RE.sub("", clean)
        clean = FORMULA_RE.sub("", clean)
        clean = re.sub(r"\b(?:код|скрипт|деплой|pipeline)\w*\b", "артефакт", clean, flags=re.I)
    return _sentence(clean)


def _artifact_path(context: CurriculumContext, task_index: int) -> str:
    root = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(context.current_project_platform_name or context.current_project_title or "project")).strip("_.-")
    return f"{root or 'project'}/part-03/task-{task_index:02d}/README.md"


def raw_material_path_for_task(task_index: int) -> str:
    return f"materials/task_{task_index:02d}_source_notes.md"


def extract_material_refs(text: str) -> list[str]:
    refs: list[str] = []
    for match in MATERIAL_REF_RE.finditer(text or ""):
        ref = match.group(1)
        if ref.lower() not in {item.lower() for item in refs}:
            refs.append(ref)
    return refs


def is_solution_like_material_ref(path: str, *, context: str = "") -> bool:
    stem = re.sub(r"\.[A-Za-z0-9]+$", "", (path or "").replace("\\", "/").split("/")[-1]).lower()
    if any(marker in f"{stem} {context}".lower() for marker in ("raw", "source", "draft", "notes", "case", "context", "сырые", "исходн", "кейс")):
        return False
    return bool(SOLUTION_STEM_RE.search(stem))


def _is_generic_expected_artifact(text: str) -> bool:
    stripped = ARTIFACT_PATH_RE.sub("", re.sub(r"`[^`]*`", "", text or "")).strip(" .").lower()
    if not stripped:
        return True
    return len(WORD_RE.findall(stripped)) <= 8 and ("размещ" in stripped or "файл" in stripped or "артефакт" in stripped)


def _artifact_subject(title: str, content_type: ContentType) -> str:
    text = title.lower()
    if content_type == "no_code":
        if any(marker in text for marker in ("таблиц", "матриц", "сравнен")):
            return "таблицей решений и обоснованием выбора"
        if any(marker in text for marker in ("схем", "процесс")):
            return "схемой процесса и пояснением ключевых связей"
    if any(marker in text for marker in ("api", "openapi", "контракт")):
        return "описанием API-контракта и проверкой сценариев взаимодействия"
    return "решением по задаче"


def _artifact_kind(context: CurriculumContext, index: int, count: int, theory_summary: str) -> str:
    topics = re.findall(r"^\s*\d+\.\s+(.+?)\s*$", theory_summary or "", flags=re.M)
    if index == 1:
        return "первичный рабочий артефакт на основе raw evidence"
    if index == count:
        return "итоговый артефакт проекта"
    if index - 1 < len(topics):
        return f"промежуточный артефакт по теме «{topics[index - 1]}»"
    return f"промежуточный артефакт проекта «{context.current_project_title}»"


def _artifact_kind_from_task(task: PracticeTask) -> str:
    text = re.sub(r"`[^`]+`", "", task.expected_artifact or "")
    return re.sub(r"\s+", " ", text).strip(" .")[:160] or "проверяемый артефакт задачи"


def _content_type(context: CurriculumContext) -> ContentType:
    direction = (context.direction or context.block_name or "").upper()
    if direction in {"PJM", "UX", "CB", "KB", "BSA", "BA", "PM", "PRODUCT", "DESIGN", "MANAGEMENT", "ANALYST"}:
        return "no_code"
    if direction in {"C", "CPP", "C++", "JAVA", "GO", "RUST", "BACKEND", "MOBILE", "WEB", "FRONTEND", "FULLSTACK"}:
        return "hard_code"
    return "low_code"


def _group_roles(context: CurriculumContext) -> list[ProjectRole] | None:
    if context.current_project_format != "group" or context.current_project_group_size <= 1:
        return None
    if context.current_project_group_size == 2:
        return ["lead", "executor"]
    return ["lead", "executor", "reviewer"][: context.current_project_group_size]


def _is_observable(text: str) -> bool:
    low = (text or "").lower()
    signals = ("содержит", "есть", "описан", "размещ", "указан", "заполн", "обоснован", "путь", "файл", "раздел", "таблица", "схема")
    return len(low) >= 12 and any(signal in low for signal in signals)


def _has_theory_anchor(items: list[str], support: list[str]) -> bool:
    blob = " ".join(items).lower()
    return any(_token_set(topic) & _token_set(blob) for topic in support)


def _token_set(text: str) -> set[str]:
    stop = {"это", "для", "как", "что", "или", "при", "про", "без", "проект", "задача", "нужно", "важно", "будет"}
    return {token for token in re.findall(r"[А-Яа-яЁёA-Za-z0-9]+", (text or "").lower()) if len(token) > 3 and token not in stop}


def _short_topic(text: str) -> str:
    clean = re.sub(r"^\s*(?:проектирует|описывает|разрабатывает|выполняет|применяет|знает|умеет)\s+", "", str(text), flags=re.I)
    return re.sub(r"\s+", " ", clean).strip(" .,:;")[:48]


def _pick(items: list[str], index: int) -> str:
    return str(items[index % len(items)]).strip() if items else ""


def normalize_sentence(text: str) -> str:
    value = re.sub(r"\s+", " ", str(text or "").strip()).strip(" -")
    if not value:
        return ""
    if value[0].islower():
        value = value[0].upper() + value[1:]
    if value[-1] not in ".!?":
        value += "."
    return value


def _sentence(text: str) -> str:
    return normalize_sentence(text)


def _normalize_markdown(text: str) -> str:
    clean = re.sub(r"[ \t]+", " ", (text or "").strip())
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    clean = re.sub(r" +\n", "\n", clean)
    return clean


def _get(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)
