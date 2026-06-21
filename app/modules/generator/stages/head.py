"""G2 head stage: title, annotation, intro, task planning and README scaffold."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import get_thresholds
from app.core.llm.prompt_loader import PromptNotFoundError, load_prompt
from app.core.llm.structured import StructuredPrompt, complete_typed
from app.core.models import CurriculumContext, GeneratedDoc, ProjectSummary

Complexity = Literal["easy", "medium", "hard"]

GENERIC_TITLE_KEYS = {
    "анализ",
    "план",
    "практика",
    "проект",
    "работа",
    "учебный проект",
    "рабочий артефакт",
}
STOP_WORDS = {
    "для",
    "или",
    "при",
    "над",
    "под",
    "про",
    "без",
    "это",
    "проект",
    "проекта",
    "проектом",
    "учебный",
}


class HeadAnnotation(BaseModel):
    """Validated project annotation."""

    model_config = ConfigDict(extra="forbid")

    text: str
    chars: int


class HeadIntro(BaseModel):
    """Chapter 1 intro and static instruction blocks."""

    model_config = ConfigDict(extra="forbid")

    intro_text: str
    instruction_text: str


class HeadTaskPlan(BaseModel):
    """Task planning contract that G4 practice consumes later."""

    model_config = ConfigDict(extra="forbid")

    tasks_count: int = Field(ge=2, le=8)
    complexity: Complexity
    level_index: int = Field(ge=0, le=2)
    level_source: str
    rationale: str
    explanation: str
    curriculum_context: dict[str, Any] = Field(default_factory=dict)


class ContextAnalysis(BaseModel):
    """Compact curriculum-aware context analysis."""

    model_config = ConfigDict(extra="forbid")

    is_first_project: bool
    context_summary: str
    narrative_anchor: str = ""
    similar_projects: list[dict[str, Any]] = Field(default_factory=list)
    relevant_chunks: list[str] = Field(default_factory=list)
    skills_alignment: dict[str, Any] = Field(default_factory=dict)
    learning_outcomes_alignment: dict[str, Any] = Field(default_factory=dict)
    tools_alignment: dict[str, Any] = Field(default_factory=dict)
    audience_level_match: bool = True
    metrics: dict[str, Any] = Field(default_factory=dict)


class HeadDraft(BaseModel):
    """Optional LLM draft. Deterministic guards still normalize it."""

    model_config = ConfigDict(extra="forbid")

    title: str = ""
    annotation: str = ""
    intro_text: str = ""
    instruction_text: str = ""


class HeadResult(BaseModel):
    """Full G2 output consumed by downstream generator stages."""

    model_config = ConfigDict(extra="forbid")

    title: str
    annotation: HeadAnnotation
    intro: HeadIntro
    task_plan: HeadTaskPlan
    context_analysis: ContextAnalysis
    toc: list[str]
    markdown: str

    @field_validator("title")
    @classmethod
    def title_is_short(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("title must not be empty")
        if len(value.split()) > 3:
            raise ValueError("title must contain 1-3 words")
        return value


def run(ctx: dict[str, Any], augment: str = "") -> dict[str, Any]:
    """Engine adapter for ``EngineStage('generator.head', run)``."""
    context = _coerce_context(ctx)
    draft = _llm_draft(context, ctx.get("llm_client"), augment) if ctx.get("llm_client") else None
    result = generate_head(context, draft=draft)
    return {
        "head": result.model_dump(mode="json"),
        "title": result.title,
        "annotation": result.annotation.model_dump(mode="json"),
        "intro_section": result.intro.model_dump(mode="json"),
        "task_plan": result.task_plan.model_dump(mode="json"),
        "context_analysis": result.context_analysis.model_dump(mode="json"),
        "markdown": result.markdown,
        "generated_doc": GeneratedDoc(markdown=result.markdown, metadata={"artifact_target": "readme_head"}),
    }


def generate_head(context: CurriculumContext, *, draft: HeadDraft | None = None) -> HeadResult:
    """Generate and validate the deterministic head scaffold."""
    analysis = _context_analysis(context)
    task_plan = _task_plan(context, analysis)
    title = _normalize_title((draft.title if draft else "") or _derive_title(context), context)
    annotation = _annotation((draft.annotation if draft else ""), title, context)
    intro = _intro((draft.intro_text if draft else ""), (draft.instruction_text if draft else ""), annotation.text, context)
    toc = ["Глава 1. Введение и инструкция", "Глава 2. Теория", "Глава 3. Практика"]
    markdown = _markdown(title, annotation.text, toc, intro, task_plan)
    return HeadResult(
        title=title,
        annotation=annotation,
        intro=intro,
        task_plan=task_plan,
        context_analysis=analysis,
        toc=toc,
        markdown=markdown,
    )


def _coerce_context(ctx: dict[str, Any]) -> CurriculumContext:
    raw = ctx.get("curriculum_context") or {}
    if isinstance(raw, CurriculumContext):
        return raw
    if isinstance(raw, dict) and raw:
        return CurriculumContext.model_validate(raw)
    project = ctx.get("current_project") if isinstance(ctx.get("current_project"), dict) else {}
    return CurriculumContext(
        plan_title=str(ctx.get("plan_title") or ""),
        direction=str(ctx.get("direction") or ""),
        block_name=str(project.get("block_name") or "Проектный блок"),
        current_project_order=int(project.get("order") or 1),
        current_project_title=str(project.get("title") or "Учебный проект"),
        current_project_description=str(project.get("description") or ""),
        current_project_learning_outcomes=list(project.get("learning_outcomes") or []),
        current_project_skills=list(project.get("skills") or []),
        current_project_required_tools=list(project.get("required_tools") or []),
        current_project_required_software=list(project.get("required_software") or []),
        current_project_workload_hours=float(project.get("workload_hours") or 0),
    )


def _llm_draft(context: CurriculumContext, client: Any, augment: str) -> HeadDraft | None:
    try:
        template = load_prompt("generator", "head", "v1")
    except PromptNotFoundError:
        return None
    prompt = template.render(
        project=context.current_project_title,
        description=context.current_project_description,
        outcomes="; ".join(context.current_project_learning_outcomes),
        skills="; ".join(context.current_project_skills),
        tools=", ".join([*context.current_project_required_tools, *context.current_project_required_software]),
        previous=", ".join(project.title for project in context.previous_projects),
        next=", ".join(project.title for project in context.next_projects),
        augment=augment,
    )
    return complete_typed(StructuredPrompt(user=prompt), HeadDraft, client=client, temperature=0.2)


def _context_analysis(context: CurriculumContext) -> ContextAnalysis:
    previous = context.previous_projects
    next_projects = context.next_projects or context.next_block_projects
    skills = context.current_project_skills
    outcomes = context.current_project_learning_outcomes
    tools = [*context.current_project_required_tools, *context.current_project_required_software]
    previous_skills = _summary_terms(previous, "competency_refs")
    previous_outcomes = _summary_terms(previous, "learning_outcomes")
    context_summary = (
        f"Проект «{context.current_project_title}» находится в блоке «{context.block_name}». "
        f"Он формирует результаты: {'; '.join(outcomes[:3]) or 'результаты не заданы'}."
    )
    narrative_anchor = (
        f"Проект продолжает предыдущие работы: {', '.join(project.title for project in previous[-3:])}."
        if previous
        else "Это первый проект в текущем блоке; введение должно явно задать рабочий контекст."
    )
    return ContextAnalysis(
        is_first_project=not previous,
        context_summary=context_summary,
        narrative_anchor=narrative_anchor,
        similar_projects=[item.model_dump(mode="json") for item in [*previous[-3:], *next_projects[:3]]],
        relevant_chunks=[item for item in [context.sjm_context, context.additional_materials] if item],
        skills_alignment={"intersection": sorted(set(skills) & previous_skills), "new": sorted(set(skills) - previous_skills)},
        learning_outcomes_alignment={
            "intersection": sorted(set(outcomes) & previous_outcomes),
            "new": sorted(set(outcomes) - previous_outcomes),
        },
        tools_alignment={"current": tools, "new": tools},
        metrics={"previous_projects_count": len(previous), "next_projects_count": len(next_projects)},
    )


def _summary_terms(projects: list[ProjectSummary], field: str) -> set[str]:
    values: set[str] = set()
    for project in projects:
        raw_items = getattr(project, field, []) or []
        for item in raw_items:
            values.add(str(getattr(item, "canonical_name", item)).strip())
    return {item for item in values if item}


def _task_plan(context: CurriculumContext, analysis: ContextAnalysis) -> HeadTaskPlan:
    level = _audience_level(context.current_project_audience_level)
    if not analysis.is_first_project:
        previous_count = int(analysis.metrics.get("previous_projects_count") or 0)
        level = max(level, 2 if previous_count >= 6 else 1 if previous_count >= 3 else 0)
        source = "context+audience"
    else:
        source = "audience_only"
    level = max(0, min(level, 2))
    defaults = {
        0: (6, "easy"),
        1: (5, "medium"),
        2: (3, "hard"),
    }
    tasks, complexity = defaults[level]
    min_tasks, max_tasks = get_thresholds().require_range("methodology.practice_tasks_range")
    tasks = max(int(min_tasks), min(int(max_tasks), tasks))
    rationale = (
        f"Уровень аудитории={context.current_project_audience_level or 'не указан'}, "
        f"предыдущих проектов={analysis.metrics.get('previous_projects_count', 0)}, итоговый уровень={level}."
    )
    explanation = (
        f"Запланировано {tasks} практических задач уровня {complexity}. "
        f"План учитывает блок «{context.block_name}», заявленные результаты и соседние проекты."
    )
    return HeadTaskPlan(
        tasks_count=tasks,
        complexity=complexity,  # type: ignore[arg-type]
        level_index=level,
        level_source=source,
        rationale=rationale,
        explanation=explanation,
        curriculum_context=analysis.model_dump(mode="json"),
    )


def _audience_level(value: str | None) -> int:
    text = (value or "").casefold()
    if any(marker in text for marker in ("beginner", "basic", "base", "junior", "нач", "баз", "нович")):
        return 0
    if any(marker in text for marker in ("advanced", "senior", "expert", "продвин", "проф")):
        return 2
    return 1


def _normalize_title(value: str, context: CurriculumContext) -> str:
    title = re.sub(r"^#+\s*", "", _clean(value)).strip(" .:;")
    title = re.sub(r"\b(проект|учебный проект)\b", "", title, flags=re.I).strip(" .:;") or title
    if _is_generic_title(title) or len(title.split()) > 3:
        title = _derive_title(context)
    words = title.split()
    return " ".join(words[:3]).strip(" .:;") or "Рабочий артефакт"


def _derive_title(context: CurriculumContext) -> str:
    source = " ".join(
        [
            context.current_project_title,
            context.current_project_description,
            " ".join(context.current_project_learning_outcomes),
            " ".join(context.current_project_skills),
        ]
    )
    low = source.casefold()
    candidates = (
        ("REST API", ("rest api", "openapi")),
        ("SQL-схема", ("sql", "бд", "database")),
        ("Docker deploy", ("docker", "контейнер")),
        ("Карта требований", ("требован", "requirement")),
        ("Карта рисков", ("риск", "risk")),
        ("Дорожная карта", ("дорожн", "roadmap")),
        ("План спринта", ("спринт", "sprint")),
        ("Рабочая коммуникация", ("коммуникац", "заказчик", "клиент")),
    )
    for title, markers in candidates:
        if any(marker in low for marker in markers):
            return title
    return _short_label(context.current_project_title or context.block_name, max_words=3)


def _is_generic_title(title: str) -> bool:
    key = re.sub(r"[^\w\sА-Яа-яЁё-]+", " ", title or "").casefold()
    key = re.sub(r"\s+", " ", key).strip()
    if not key or key in GENERIC_TITLE_KEYS:
        return True
    tokens = key.split()
    return len(tokens) <= 2 and all(token in {"анализ", "план", "работа", "работы", "проект"} for token in tokens)


def _annotation(draft: str, title: str, context: CurriculumContext) -> HeadAnnotation:
    lo, hi = get_thresholds().require_range("structural.annotation_chars")
    sentences = _sentences(draft)
    if len(sentences) < 2:
        outcomes = "; ".join(context.current_project_learning_outcomes[:2]) or "проверяемые результаты проекта"
        skills = ", ".join(context.current_project_skills[:3]) or "ключевые действия проекта"
        tools = ", ".join([*context.current_project_required_tools, *context.current_project_required_software][:3])
        tool_sentence = f"Внутри есть работа с инструментами: {tools}." if tools else "Внутри есть разбор ситуации, выбор решения и оформление результата."
        sentences = [
            f"{title} помогает понять, зачем проект нужен в реальной рабочей задаче и какую проблему он решает.",
            f"{tool_sentence}",
            f"В результате участник подготовит артефакт и подтвердит результаты обучения: {outcomes}; навыки: {skills}.",
        ]
    text = " ".join(sentences[:4]).strip()
    while len(text) < int(lo):
        text += " Проект связывает контекст, самостоятельный анализ и проверяемый итог без подмены решения готовыми выводами."
    if len(text) > int(hi):
        text = _clamp_sentences(text, int(hi))
    return HeadAnnotation(text=text, chars=len(text))


def _intro(draft_intro: str, draft_instruction: str, annotation: str, context: CurriculumContext) -> HeadIntro:
    intro = _clean_intro(draft_intro) or _default_intro(annotation, context)
    instruction = _clean_instruction(draft_instruction) or _default_instruction(context)
    intro = _ensure_words(_ensure_context_markers(_remove_overlap(intro, annotation)), "structural.intro_words")
    if _content_type(context) == "no_code":
        instruction = _sanitize_no_code_instruction(instruction)
    instruction = _ensure_words(_ensure_instruction_keywords(instruction), "structural.instruction_words")
    if _content_type(context) == "no_code":
        instruction = _sanitize_no_code_instruction(instruction)
    return HeadIntro(intro_text=intro, instruction_text=instruction)


def _default_intro(annotation: str, context: CurriculumContext) -> str:
    outcomes = "; ".join(context.current_project_learning_outcomes[:3]) or "основные результаты обучения проекта"
    story = context.sjm_context or context.current_project_description or annotation
    return (
        f"В реальной задаче участник работает с ситуацией: {story}. "
        f"Основная идея проекта — перейти от контекста и ограничений к проверяемому артефакту, который можно оценить без устных пояснений. "
        f"Проект используется для тренировки результатов обучения: {outcomes}. "
        "Важно не переносить готовые ответы, а объяснять решения через факты, материалы и выбранные инструменты."
    )


def _default_instruction(context: CurriculumContext) -> str:
    tools = ", ".join([*context.current_project_required_tools, *context.current_project_required_software]) or "инструменты проекта"
    materials = context.additional_materials or "материалы проекта и файлы из репозитория"
    return (
        "**Контекст и ограничения проекта**\n\n"
        f"Обязательно используй {tools}; допускается вести локальные черновики, но итоговый результат должен быть воспроизводимым. "
        f"Работай только с источниками: {materials}. Запрещено подменять анализ готовыми выводами, менять служебные материалы вне задания "
        "или сдавать результат, который нельзя проверить по артефактам.\n\n"
        "**Как работать с проектом**\n\n"
        "Сначала выдели ограничения и ожидаемый результат, затем выполни практические шаги и зафиксируй решение в каноническом месте. "
        "Перед проверкой убедись, что итог связан с результатами обучения, содержит ссылки на использованные материалы и не требует устного пояснения автора."
    )


def _markdown(title: str, annotation: str, toc: list[str], intro: HeadIntro, task_plan: HeadTaskPlan) -> str:
    toc_md = "\n".join(f"- [{item}](#{_anchor(item)})" for item in toc)
    return "\n\n".join(
        [
            f"# {title}",
            annotation,
            "## Содержание\n\n" + toc_md,
            "## Глава 1. Введение и инструкция\n\n"
            f"### Введение\n\n{intro.intro_text}\n\n### Инструкция\n\n{intro.instruction_text}",
            "## Глава 2. Теория\n\n"
            "Теоретическая часть раскрывает понятия и критерии, которые нужны для выполнения практики. "
            "Она должна использовать контекст проекта и подготовить участника к самостоятельному решению.",
            "## Глава 3. Практика\n\n"
            f"Практическая часть планируется как {task_plan.tasks_count} задач уровня {task_plan.complexity}. "
            "Каждая задача должна вести к проверяемому артефакту и сохранять связь с результатами обучения.",
        ]
    )


def _clean(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "").replace("‑", "-")).strip()


def _short_label(text: str, *, max_words: int) -> str:
    words = [word.strip(" .,:;") for word in _clean(text).split() if word.casefold() not in STOP_WORDS]
    return " ".join(words[:max_words]) or "Рабочий артефакт"


def _sentences(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"(?<=[.!?])\s+", _clean(text)) if item.strip()]


def _clamp_sentences(text: str, limit: int) -> str:
    acc: list[str] = []
    for sentence in _sentences(text):
        candidate = " ".join([*acc, sentence])
        if acc and len(candidate) > limit:
            break
        acc.append(sentence)
    return " ".join(acc).strip() or text[:limit].rstrip(" ,.;:") + "."


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\wА-Яа-яЁё-]+\b", text or ""))


def _ensure_words(text: str, threshold_path: str) -> str:
    lo, hi = get_thresholds().require_range(threshold_path)
    fixed = _clean_multiline(text)
    while _word_count(fixed) < int(lo):
        fixed += " Этот блок удерживает контекст проекта, критерии проверки и ожидаемый результат работы."
    if _word_count(fixed) > int(hi):
        parts = _sentences(fixed)
        kept: list[str] = []
        for sentence in parts:
            candidate = " ".join([*kept, sentence])
            if kept and _word_count(candidate) > int(hi):
                break
            kept.append(sentence)
        fixed = " ".join(kept).strip() or fixed
    return fixed


def _clean_multiline(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", str(text or "").strip())


def _clean_intro(text: str) -> str:
    cleaned = re.sub(r"^\s*#{1,6}\s+.+?(?:\n+|$)", "", str(text or ""), count=1, flags=re.M)
    return _clean_multiline(cleaned)


def _clean_instruction(text: str) -> str:
    return _clean_multiline(text)


def _remove_overlap(intro: str, annotation: str) -> str:
    annotation_tokens = set(re.findall(r"[А-Яа-яЁёA-Za-z0-9]+", annotation.casefold()))
    kept: list[str] = []
    for sentence in _sentences(intro):
        tokens = set(re.findall(r"[А-Яа-яЁёA-Za-z0-9]+", sentence.casefold()))
        overlap = len(tokens & annotation_tokens) / max(1, len(tokens))
        if overlap < 0.7:
            kept.append(sentence)
    return " ".join(kept).strip() or intro


def _ensure_context_markers(text: str) -> str:
    markers = ("используется для", "в реальной задаче", "применяется", "основная идея", "зачем")
    if any(marker in text.casefold() for marker in markers):
        return text
    return text.rstrip() + " В реальной задаче это используется для получения проверяемого результата и объясняет, зачем нужен проект."


def _ensure_instruction_keywords(text: str) -> str:
    low = text.casefold()
    if all(keyword in low for keyword in ("обязательно", "допускается", "запрещено")):
        return text
    prefix = (
        "Обязательно используй материалы проекта; допускается вести черновики в удобном формате; "
        "запрещено подменять анализ готовыми выводами.\n\n"
    )
    return prefix + text.strip()


def _content_type(context: CurriculumContext) -> str:
    direction = (context.direction or context.block_name or "").upper()
    if direction in {"PJM", "UX", "CB", "KB", "BSA", "BA", "PM", "PRODUCT", "DESIGN", "MANAGEMENT", "ANALYST"}:
        return "no_code"
    if direction in {"C", "CPP", "C++", "JAVA", "GO", "RUST", "BACKEND", "MOBILE", "WEB", "FRONTEND", "FULLSTACK"}:
        return "hard_code"
    return "low_code"


def _sanitize_no_code_instruction(text: str) -> str:
    replacements = [
        (r"\bкод[а-я]*\b", "артефакты"),
        (r"\bавтотест[а-я]*\b", "проверка результата"),
        (r"\bдепло[йя][а-я]*\b", "подготовка результата к сдаче"),
    ]
    cleaned = text
    for pattern, repl in replacements:
        cleaned = re.sub(pattern, repl, cleaned, flags=re.I)
    return cleaned


def _anchor(text: str) -> str:
    cleaned = re.sub(r"[^\w\sА-Яа-яЁё-]+", "", text.casefold())
    return re.sub(r"\s+", "-", cleaned).strip("-")
