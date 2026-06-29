"""G3 theory stage: structured theory parts, definitions, length and readability guards."""

from __future__ import annotations

import json
import math
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import get_thresholds
from app.core.llm.prompt_loader import PromptNotFoundError, load_prompt
from app.core.llm.structured import StructuredPrompt, complete_typed
from app.core.models import CurriculumContext, GeneratedDoc
from app.modules.generator.stages.head import _coerce_context

ContentType = Literal["hard_code", "low_code", "no_code"]

PART_HEADING_RE = re.compile(r"^###\s+2\.(\d+)\.\s*(.+?)\s*$", re.M)
EXAMPLE_RE = re.compile(r"\*\*Пример:\*\*\s*(.+?)(?=\n\*\*Вопросы к практике:\*\*|\Z)", re.S)
QUESTIONS_RE = re.compile(r"\*\*Вопросы к практике:\*\*\s*(.+)$", re.S)
DEFINITION_RE = re.compile(
    r"\*\*([^*\n]{2,90})\*\*\s*[—-]\s*(?:это|представляет собой|является|понимается|подразумевается)?",
    re.I,
)
STATIC_LEAK_RE = re.compile(
    r"\b(P2P|peer[- ]?to[- ]?peer|освоил репозиторий|сдать проект|ревьюер|проверяющий|чек-?лист)\b",
    re.I,
)
CODE_FENCE_RE = re.compile(r"```[\s\S]*?```", re.M)
FORMULA_RE = re.compile(r"\$\$[\s\S]*?\$\$|\$[^$\n]+\$", re.M)
MERMAID_STYLE_RE = re.compile(r"%%\{init[\s\S]*?\}%%|^\s*(?:classDef|class|style|linkStyle)\b.*$", re.I | re.M)
WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9_/-]*")


class TheoryDraftPart(BaseModel):
    """One optional LLM-drafted theory part."""

    model_config = ConfigDict(extra="forbid")

    title: str = ""
    body: str = ""
    example: str = ""
    bridge_questions: list[str] = Field(default_factory=list)


class TheoryDraft(BaseModel):
    """Optional typed model output. Deterministic guards remain authoritative."""

    model_config = ConfigDict(extra="forbid")

    parts: list[TheoryDraftPart] = Field(default_factory=list)


class TheoryPart(BaseModel):
    """Structured public theory part consumed by later stages and gate."""

    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=1)
    title: str
    body: str
    example: str
    bridge_questions: list[str] = Field(default_factory=list)
    covers_outcomes: list[str] = Field(default_factory=list)
    definitions_found: list[str] = Field(default_factory=list)
    word_count: int = Field(ge=0)
    readability_score: float = Field(ge=0, le=100)
    content_type: ContentType

    @field_validator("bridge_questions")
    @classmethod
    def bridge_questions_are_compact(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item and item.strip()][:2]


class TheoryResult(BaseModel):
    """Full G3 stage output."""

    model_config = ConfigDict(extra="forbid")

    parts: list[TheoryPart]
    markdown: str
    warnings: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)


def run(ctx: dict[str, Any], augment: str = "") -> dict[str, Any]:
    """Engine adapter for ``EngineStage('generator.theory', run)``."""
    context = _coerce_context(ctx)
    draft = _llm_draft(context, str(ctx.get("markdown") or ""), ctx.get("llm_client"), augment) if ctx.get("llm_client") else None
    result = generate_theory(context, markdown=str(ctx.get("markdown") or ""), draft=draft)
    return {
        "theory": result.model_dump(mode="json"),
        "theory_parts": [part.model_dump(mode="json") for part in result.parts],
        "theory_warnings": result.warnings,
        "theory_issues": result.issues,
        "markdown": result.markdown,
        "generated_doc": GeneratedDoc(
            markdown=result.markdown,
            metadata={
                "artifact_target": "readme_theory",
                "theory_parts_count": len(result.parts),
                "theory_warnings": result.warnings,
            },
        ),
    }


def generate_theory(context: CurriculumContext, *, markdown: str = "", draft: TheoryDraft | None = None) -> TheoryResult:
    """Generate Chapter 2 and replace the theory placeholder in the current markdown."""
    content_type = _content_type(context)
    desired_parts = _desired_parts(context, draft)
    anchors = _anchor_terms(context)
    warnings: list[str] = []
    issues: list[str] = []
    raw_parts = _raw_parts(context, desired_parts=desired_parts, draft=draft)
    parts: list[TheoryPart] = []

    for index, raw in enumerate(raw_parts, 1):
        part = _materialize_part(index, raw, context, content_type, anchors)
        parts.append(part)

    _apply_completeness(parts, context, anchors, warnings)
    chapter = _render_theory_chapter(parts)
    final_markdown = _replace_theory_chapter(markdown or _minimal_markdown(context), chapter)
    if not parts:
        issues.append("theory.parts_empty")
    return TheoryResult(parts=parts, markdown=final_markdown, warnings=warnings, issues=issues)


def _llm_draft(context: CurriculumContext, markdown: str, client: Any, augment: str) -> TheoryDraft | None:
    try:
        template = load_prompt("generator", "theory")
    except PromptNotFoundError:
        return None
    payload = {
        "curriculum_context": context.model_dump(mode="json"),
        "head_markdown": markdown[:6000],
        "thresholds": {
            "parts": get_thresholds().get("structural.theory_parts"),
            "words_per_part": get_thresholds().get("structural.theory_words_per_part"),
            "readability_band": get_thresholds().get("structural.readability_band"),
        },
        "augment": augment,
    }
    prompt = template.render(context_json=json.dumps(payload, ensure_ascii=False, indent=2))
    try:
        return complete_typed(
            StructuredPrompt(
                system="Return only valid JSON for TheoryDraft.",
                user=prompt,
                kwargs={"temperature": 0.2, "max_tokens": 6000},
            ),
            TheoryDraft,
            client=client,
            retries=1,
        )
    except Exception:
        return None


def _desired_parts(context: CurriculumContext, draft: TheoryDraft | None) -> int:
    lo, hi = get_thresholds().require_range("structural.theory_parts")
    draft_count = len(draft.parts) if draft and draft.parts else 0
    if draft_count:
        return _clamp(draft_count, int(lo), int(hi))
    signal_count = len(context.current_project_learning_outcomes) + len(context.current_project_skills)
    workload_bonus = 1 if context.current_project_workload_hours >= 12 else 0
    return _clamp(max(int(lo), math.ceil(signal_count / 2) + workload_bonus), int(lo), int(hi))


def _raw_parts(context: CurriculumContext, *, desired_parts: int, draft: TheoryDraft | None) -> list[TheoryDraftPart]:
    result: list[TheoryDraftPart] = []
    for part in (draft.parts if draft else [])[:desired_parts]:
        result.append(part)
    titles = _part_titles(context, desired_parts)
    while len(result) < desired_parts:
        title = titles[len(result)] if len(result) < len(titles) else f"Тема {len(result) + 1}"
        result.append(TheoryDraftPart(title=title))
    return result[:desired_parts]


def _part_titles(context: CurriculumContext, count: int) -> list[str]:
    candidates: list[str] = [
        *_topic_titles(context.current_project_learning_outcomes),
        *_topic_titles(context.current_project_skills),
        *_topic_titles(context.current_project_required_tools),
        *_topic_titles(context.current_project_required_software),
        _topic_title(context.current_project_title),
    ]
    seen: dict[str, None] = {}
    titles = [seen.setdefault(item, None) or item for item in candidates if item and item not in seen]
    if len(titles) < count:
        fallbacks = ["Контекст проекта", "Ключевые решения", "Критерии выбора", "Ограничения и риски"]
        for item in fallbacks:
            if item not in seen:
                titles.append(item)
                seen[item] = None
    return titles[:count]


def _topic_titles(items: list[str]) -> list[str]:
    return [_topic_title(item) for item in items if item and item.strip()]


def _topic_title(text: str) -> str:
    cleaned = re.sub(r"^\s*(?:проектирует|описывает|разрабатывает|выполняет|применяет|знает|умеет)\s+", "", text, flags=re.I)
    cleaned = re.sub(r"[:.;]+$", "", cleaned.strip())
    words = [word.strip(" ,.;:") for word in cleaned.split() if word.strip(" ,.;:")]
    title = " ".join(words[:5]) or "Ключевая тема"
    return title[:1].upper() + title[1:]


def _no_code_title(title: str) -> str:
    cleaned = re.sub(r"\b(?:код|псевдокод|скрипт|деплой)\w*\b", "процесс", title, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,:;")
    return cleaned[:1].upper() + cleaned[1:] if cleaned else "Рабочий процесс"


def _materialize_part(
    index: int,
    raw: TheoryDraftPart,
    context: CurriculumContext,
    content_type: ContentType,
    anchors: list[str],
) -> TheoryPart:
    title = _topic_title(raw.title or _part_titles(context, index)[-1])
    if content_type == "no_code":
        title = _no_code_title(title)
    body = raw.body.strip() or _default_body(title, context, index)
    body = _strip_theory_heading(body)
    body = _sanitize_body(body, title, context, anchors, content_type)
    body = _ensure_definition(body, title, context)
    body = _ensure_length(body, title, context, anchors)
    body = _ensure_readability(body, context)
    body = _sanitize_body(body, title, context, anchors, content_type)
    example = _sanitize_example(raw.example or _default_example(title, context), content_type)
    questions = _valid_questions(raw.bridge_questions, context, anchors)
    if not questions:
        questions = _default_questions(title, context, anchors)
    covers = _covered_outcomes(body, context.current_project_learning_outcomes)
    definitions = _definitions(body)
    return TheoryPart(
        index=index,
        title=title,
        body=body,
        example=example,
        bridge_questions=questions,
        covers_outcomes=covers,
        definitions_found=definitions,
        word_count=_word_count(body),
        readability_score=_readability_score(body),
        content_type=content_type,
    )


def _default_body(title: str, context: CurriculumContext, index: int) -> str:
    outcome = _pick(context.current_project_learning_outcomes, index - 1) or "связать решение с результатом проекта"
    skill = _pick(context.current_project_skills, index - 1) or title
    tool = _pick([*context.current_project_required_tools, *context.current_project_required_software], index - 1) or "доступные инструменты"
    description = context.current_project_description or "проект требует осознанного выбора подхода и проверки результата"
    block_goal = _pick(context.block_goals, 0) or "собрать понятный учебный артефакт"
    return (
        f"{title} помогает понять, как перейти от цели блока к рабочему результату проекта. "
        f"В этом проекте контекст такой: {description}. "
        f"Сначала разберись, какую роль играет {skill}, затем свяжи это с инструментами: {tool}. "
        f"Главная проверка здесь не в пересказе термина, а в том, можешь ли ты объяснить выбор и показать его влияние на артефакт. "
        f"Это поддерживает результат обучения: {outcome}. "
        f"Держи в фокусе цель блока: {block_goal}."
    )


def _sanitize_body(body: str, title: str, context: CurriculumContext, anchors: list[str], content_type: ContentType) -> str:
    text = _normalize_markdown(body)
    text = _strip_static_leaks(text, _topic_text(context))
    if content_type == "no_code":
        text = CODE_FENCE_RE.sub("", text)
        text = FORMULA_RE.sub("", text)
    text = MERMAID_STYLE_RE.sub("", text)
    text = _normalize_definition_bold(text)
    text = _compact_generic_prose(text, title, context, anchors)
    return _normalize_markdown(text)


def _strip_static_leaks(text: str, topic_text: str) -> str:
    kept: list[str] = []
    topic_low = topic_text.lower()
    for sentence in _split_sentences(text):
        if STATIC_LEAK_RE.search(sentence) and not any(token in topic_low for token in ("p2p", "peer", "репозитор")):
            continue
        kept.append(sentence)
    return _join_sentences(kept) if kept else re.sub(STATIC_LEAK_RE, "", text)


def _compact_generic_prose(text: str, title: str, context: CurriculumContext, anchors: list[str]) -> str:
    protected, blocks = _protect_blocks(text)
    chunks = re.split(r"(@@THEORY_BLOCK_\d+@@)", protected)
    output: list[str] = []
    for chunk in chunks:
        if not chunk:
            continue
        if chunk in blocks:
            output.append(chunk)
            continue
        sentences = []
        for sentence in _split_sentences(chunk):
            low = sentence.lower()
            if re.search(r"\b(в современном мире|крайне важно|значительно расширит|в различных сферах)\b", low):
                continue
            sentences.append(sentence)
        output.append(_join_sentences(sentences) or chunk.strip())
    restored = "\n\n".join(item for item in output if item.strip())
    for key, block in blocks.items():
        restored = restored.replace(key, block)
    if anchors and not any(anchor in restored.lower() for anchor in anchors[:8]):
        restored = (
            restored.rstrip()
            + f" Для этого проекта свяжи {title.lower()} с текущим кейсом: {context.current_project_title}."
        )
    return restored


def _ensure_definition(body: str, title: str, context: CurriculumContext) -> str:
    if _definitions(body):
        return body
    term = _definition_term(title, context)
    definition = (
        f"**{term}** — это понятие, которое помогает объяснить решение проекта простыми словами "
        "и связать его с ожидаемым учебным результатом."
    )
    return f"{definition}\n\n{body}".strip()


def _ensure_length(body: str, title: str, context: CurriculumContext, anchors: list[str]) -> str:
    lo, hi = get_thresholds().require_range("structural.theory_words_per_part")
    text = body.strip()
    while _word_count(text) < int(lo):
        text = f"{text}\n\n{_padding_sentence(title, context, anchors, _word_count(text))}".strip()
        if _word_count(text) > int(hi):
            break
    if _word_count(text) <= int(hi):
        return text
    return _truncate_preserving_definitions(text, int(hi))


def _ensure_readability(body: str, context: CurriculumContext) -> str:
    lo, hi = get_thresholds().require_range("structural.readability_band")
    text = body.strip()
    score = _readability_score(text)
    if lo <= score <= hi:
        return text
    if score < lo:
        text = re.sub(r"\s+(?:который|которая|которые|поскольку|однако|поэтому)\s+", ". ", text, flags=re.I)
        text = re.sub(r";\s+", ". ", text)
    if _readability_score(text) > hi:
        text = f"{text} На практике это решение проверяется через ограничения, артефакты и последствия выбора."
    return _normalize_markdown(text)


def _apply_completeness(parts: list[TheoryPart], context: CurriculumContext, anchors: list[str], warnings: list[str]) -> None:
    full_text = " ".join(part.body for part in parts).lower()
    missing = [anchor for anchor in anchors[:12] if anchor not in full_text]
    if not missing or not parts:
        return
    target = parts[-1]
    addition = (
        "Дополнительно проверь, как эти элементы связаны с проектом: "
        f"{', '.join(missing[:5])}. Это закрывает пробелы между учебным планом и теорией."
    )
    updated = _ensure_length(f"{target.body}\n\n{addition}", target.title, context, anchors)
    parts[-1] = target.model_copy(
        update={
            "body": updated,
            "word_count": _word_count(updated),
            "readability_score": _readability_score(updated),
            "covers_outcomes": _covered_outcomes(updated, context.current_project_learning_outcomes),
            "definitions_found": _definitions(updated),
        }
    )
    warnings.append(f"theory.completeness_added: {', '.join(missing[:5])}")


def _render_theory_chapter(parts: list[TheoryPart]) -> str:
    chunks = ["## Глава 2. Теория"]
    for part in parts:
        chunks.extend(
            [
                "",
                f"### 2.{part.index}. {part.title}",
                "",
                part.body.strip(),
                "",
                f"**Пример:** {part.example.strip()}",
                "",
                "**Вопросы к практике:**",
                *[f"- {question}" for question in part.bridge_questions],
            ]
        )
    return _normalize_markdown("\n".join(chunks))


def _replace_theory_chapter(markdown: str, theory_chapter: str) -> str:
    base = markdown.strip()
    if not base:
        return theory_chapter
    chapter_re = re.compile(r"^##\s+Глава\s+2[^\n]*\n[\s\S]*?(?=^##\s+Глава\s+3|\Z)", re.M)
    if chapter_re.search(base):
        return _normalize_markdown(chapter_re.sub(theory_chapter + "\n\n", base, count=1))
    chapter3 = re.search(r"^##\s+Глава\s+3", base, flags=re.M)
    if chapter3:
        return _normalize_markdown(base[: chapter3.start()].rstrip() + "\n\n" + theory_chapter + "\n\n" + base[chapter3.start() :])
    return _normalize_markdown(f"{base}\n\n{theory_chapter}")


def _minimal_markdown(context: CurriculumContext) -> str:
    return f"# {context.current_project_title or 'Учебный проект'}\n\n## Глава 2. Теория\n\n## Глава 3. Практика"


def _default_example(title: str, context: CurriculumContext) -> str:
    case = context.sjm_context or context.current_project_description or context.current_project_title
    return (
        f"Например, в кейсе «{case[:140]}» ты используешь тему «{title}», чтобы выбрать подход, "
        "объяснить ограничение и показать проверяемый результат."
    )


def _default_questions(title: str, context: CurriculumContext, anchors: list[str]) -> list[str]:
    anchor = anchors[0] if anchors else title.lower()
    artifact = context.current_project_platform_name or context.current_project_title or "артефакт"
    return [
        f"Как применишь {anchor} при подготовке артефакта «{artifact}»?",
        f"По какому признаку поймёшь, что решение по теме «{title}» подходит текущему проекту?",
    ]


def _valid_questions(questions: list[str], context: CurriculumContext, anchors: list[str]) -> list[str]:
    valid: list[str] = []
    project_terms = [context.current_project_title.lower(), context.current_project_platform_name or ""]
    for question in questions:
        clean = re.sub(r"\s+", " ", question.strip("- •\t "))
        low = clean.lower()
        if not (25 <= len(clean) <= 180):
            continue
        if low.startswith(("что такое", "перечисли", "объясни", "расскажи", "определи")):
            continue
        if anchors and not any(anchor in low for anchor in anchors[:12]) and not any(term and term.lower() in low for term in project_terms):
            continue
        valid.append(clean)
    return valid[:2]


def _sanitize_example(example: str, content_type: ContentType) -> str:
    text = _normalize_markdown(example)
    if content_type == "no_code":
        text = CODE_FENCE_RE.sub("", FORMULA_RE.sub("", text))
    sentences = _split_sentences(text)
    return _join_sentences(sentences[:3]) or "Короткий пример показывает, как теория влияет на решение в текущем проекте."


def _definitions(text: str) -> list[str]:
    return [match.group(1).strip() for match in DEFINITION_RE.finditer(text or "")]


def _normalize_definition_bold(text: str) -> str:
    term_expr = r"[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё0-9]*(?:[ /-][A-Za-zА-Яа-яЁё0-9]+){0,7}"
    patterns = [
        re.compile(rf"(?P<prefix>(?:^|[.!?\n]\s*))(?!\*\*)(?P<term>{term_expr})(?P<glue>\s*[—-]\s*это\b)", re.I),
        re.compile(rf"(?P<prefix>(?:^|[.!?\n]\s*))(?!\*\*)(?P<term>{term_expr})(?P<glue>\s+(?:представляет собой|является)\b)", re.I),
    ]
    normalized = text
    for pattern in patterns:
        normalized = pattern.sub(lambda m: f"{m.group('prefix')}**{m.group('term').strip()}**{m.group('glue')}", normalized)
    return normalized


def _definition_term(title: str, context: CurriculumContext) -> str:
    if title and title.lower() not in {"контекст проекта", "ключевые решения"}:
        return title[:80]
    return _pick(context.current_project_skills, 0) or _pick(context.current_project_required_tools, 0) or "Ключевая тема"


def _covered_outcomes(body: str, outcomes: list[str]) -> list[str]:
    body_low = body.lower()
    covered: list[str] = []
    for outcome in outcomes:
        tokens = [token for token in re.findall(r"\w+", outcome.lower()) if len(token) >= 4]
        if tokens and any(token in body_low for token in tokens):
            covered.append(outcome)
    return covered[:4]


def _anchor_terms(context: CurriculumContext) -> list[str]:
    terms: dict[str, None] = {}
    for item in [
        *context.current_project_required_tools,
        *context.current_project_required_software,
        *context.current_project_skills,
        *context.current_project_learning_outcomes,
        context.current_project_description,
        context.current_project_title,
    ]:
        for token in re.findall(r"[A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9_/-]*", str(item).lower()):
            if len(token) >= 4:
                terms.setdefault(token, None)
    return list(terms)


def _topic_text(context: CurriculumContext) -> str:
    return " ".join(
        [
            context.current_project_title,
            context.current_project_description,
            " ".join(context.current_project_learning_outcomes),
            " ".join(context.current_project_skills),
        ]
    )


def _content_type(context: CurriculumContext) -> ContentType:
    direction = (context.direction or context.block_name or "").upper()
    if direction in {"PJM", "UX", "CB", "KB", "BSA", "BA", "PM", "PRODUCT", "DESIGN", "MANAGEMENT", "ANALYST"}:
        return "no_code"
    if direction in {"C", "CPP", "C++", "JAVA", "GO", "RUST", "BACKEND", "MOBILE", "WEB", "FRONTEND", "FULLSTACK"}:
        return "hard_code"
    return "low_code"


def _strip_theory_heading(text: str) -> str:
    return re.sub(r"^#{2,3}\s+(?:Глава\s+2|2\.\d+)[^\n]*\n+", "", text.strip(), flags=re.I | re.M).strip()


def _protect_blocks(text: str) -> tuple[str, dict[str, str]]:
    blocks: dict[str, str] = {}

    def repl(match: re.Match[str]) -> str:
        key = f"@@THEORY_BLOCK_{len(blocks)}@@"
        blocks[key] = match.group(0).strip()
        return f"\n\n{key}\n\n"

    protected = CODE_FENCE_RE.sub(repl, text or "")
    protected = re.sub(r"(^\|[^\n]+\|\s*\n\|[-:\s|]+\|\s*\n(?:\|[^\n]+\|\s*(?:\n|$))+)", repl, protected, flags=re.M)
    return protected, blocks


def _padding_sentence(title: str, context: CurriculumContext, anchors: list[str], current_words: int) -> str:
    outcome = _pick(context.current_project_learning_outcomes, current_words % max(1, len(context.current_project_learning_outcomes)))
    anchor = _pick(anchors, current_words % max(1, len(anchors)))
    if outcome:
        return f"Это помогает закрыть результат обучения: {outcome}, потому что теория сразу связывается с действием в проекте."
    if anchor:
        return f"Отдельно проверь, как {anchor} влияет на выбор подхода, последовательность работы и критерии готовности."
    return f"Тема «{title}» должна быть объяснена через действие, ограничение и проверяемый результат проекта."


def _truncate_preserving_definitions(text: str, max_words: int) -> str:
    sentences = _split_sentences(text)
    definitions = [sentence for sentence in sentences if _definitions(sentence)]
    kept: list[str] = []
    for sentence in [*definitions, *[item for item in sentences if item not in definitions]]:
        candidate = _join_sentences([*kept, sentence])
        if kept and _word_count(candidate) > max_words:
            break
        kept.append(sentence)
    return _join_sentences(kept) or text


def _split_sentences(text: str) -> list[str]:
    raw = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", (text or "").strip()))
    return [chunk.strip() for chunk in raw if chunk and chunk.strip()]


def _join_sentences(sentences: list[str]) -> str:
    return " ".join(sentence.strip() for sentence in sentences if sentence.strip()).strip()


def _normalize_markdown(text: str) -> str:
    normalized = re.sub(r"[ \t]+", " ", (text or "").strip())
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    normalized = re.sub(r" +\n", "\n", normalized)
    return normalized.strip()


def _word_count(text: str) -> int:
    return len(WORD_RE.findall(re.sub(r"`[^`]+`", " ", text or "")))


def _readability_score(text: str) -> float:
    words = WORD_RE.findall(text or "")
    if not words:
        return 0.0
    sentences = max(1, len(_split_sentences(text)))
    avg_sentence = len(words) / sentences
    avg_word_len = sum(len(word) for word in words) / len(words)
    score = 100.0 - avg_sentence * 1.8 - avg_word_len * 4.0
    return round(max(0.0, min(100.0, score)), 2)


def _pick(items: list[str], index: int) -> str:
    if not items:
        return ""
    return str(items[index % len(items)]).strip()


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))
