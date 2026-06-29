"""Reverse-extract project metadata, tasks and audit entities from README."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field

from app.core.llm import StructuredPrompt, complete_typed, load_prompt
from app.core.llm.client import create_llm_client
from app.modules.curriculum.repo import CurriculumCatalogRepo, normalize_catalog_key

EntityType = Literal["link", "image", "version", "date", "technology"]

URL_RE = re.compile(r"https?://[^\s\])>\"']+", re.IGNORECASE)
MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*]\((?P<target>[^)\s]+)(?:\s+\"[^\"]*\")?\)")
VERSION_RE = re.compile(
    r"\b((?:Python|Node\.?js|Docker|PostgreSQL|Redis|FastAPI|React|Vue|Angular|Go|Rust|"
    r"TypeScript|JavaScript|Java|Django|Flask|Spring)\s*(?:version|версии|версия)?\s*[vV]?\d+(?:\.\d+){0,3})\b",
    re.IGNORECASE,
)
DATE_RE = re.compile(r"\b(?:19|20)\d{2}(?:[-./](?:0?[1-9]|1[0-2])(?:[-./](?:0?[1-9]|[12]\d|3[01]))?)?\b")
TECH_RE = re.compile(
    r"\b(Python|Docker|GitLab|GitHub|PostgreSQL|Redis|Django|React|Vue|Angular|FastAPI|"
    r"Flask|Spring|Kotlin|Go|Rust|TypeScript|JavaScript|Java|SQL|OpenAPI|REST|pytest|CI/CD)\b",
    re.IGNORECASE,
)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


class NormalizedReadme(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_text: str
    structure: dict[str, Any] = Field(default_factory=dict)
    chapters: dict[int, str] = Field(default_factory=dict)


class PartialProjectSeed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title_seed: str | None = None
    project_description: str | None = None
    learning_outcomes: list[str] = Field(default_factory=list)
    required_tools: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    tasks_count: int | None = Field(default=None, ge=0)
    theory_parts: list[str] = Field(default_factory=list)
    include_formulas: bool | None = None
    include_tables: bool | None = None
    include_diagrams: bool | None = None
    sjm: str | None = None


class TasksExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tasks_count: int | None = Field(default=None, ge=0)
    task_descriptions: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"


class ExtractedEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str
    entity_type: EntityType
    value: str
    quote: str
    file_path: str = "README.md"
    line_start: int
    line_end: int
    context: str


class ExtractedCompetency(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    aliases: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    competency_id: int | None = None
    match_type: str | None = None


class ReconciliationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason_code: str
    severity: Literal["info", "warning", "error"]
    details: dict[str, Any]
    review_id: int | None = None


class ReverseExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    normalized: NormalizedReadme
    partial_seed: PartialProjectSeed
    tasks: TasksExtractionResult
    competencies: list[ExtractedCompetency] = Field(default_factory=list)
    entities: list[ExtractedEntity] = Field(default_factory=list)
    reconciliation: list[ReconciliationIssue] = Field(default_factory=list)


@dataclass(slots=True)
class ReverseExtractionService:
    """Compact port of legacy reverse extraction agents plus Proverka entity audit."""

    client_factory: Any = create_llm_client

    def extract(
        self,
        markdown: str,
        *,
        client: Any | None = None,
        repo: CurriculumCatalogRepo | None = None,
        source_ref: str = "reverse://readme",
        expected_tasks_count: int | None = None,
        expected_competencies: list[str] | None = None,
        expected_skills: list[str] | None = None,
    ) -> ReverseExtractionResult:
        normalized = normalize_readme(markdown)
        llm = client or self._safe_client()
        partial_seed = self._extract_structure(normalized, llm)
        tasks = self._extract_tasks(normalized, partial_seed.tasks_count, llm)
        if tasks.tasks_count is not None and tasks.confidence in {"high", "medium"}:
            partial_seed.tasks_count = tasks.tasks_count
        result = ReverseExtractionResult(
            normalized=normalized,
            partial_seed=partial_seed,
            tasks=tasks,
            competencies=extract_competency_candidates(partial_seed),
            entities=extract_entities(normalized.raw_text),
        )
        if repo is not None:
            result.reconciliation = self.reconcile_with_catalog(
                result,
                repo,
                source_ref=source_ref,
                expected_tasks_count=expected_tasks_count,
                expected_competencies=expected_competencies or [],
                expected_skills=expected_skills or [],
            )
        return result

    def reconcile_with_catalog(
        self,
        extraction: ReverseExtractionResult,
        repo: CurriculumCatalogRepo,
        *,
        source_ref: str,
        expected_tasks_count: int | None = None,
        expected_competencies: list[str] | None = None,
        expected_skills: list[str] | None = None,
    ) -> list[ReconciliationIssue]:
        issues: list[ReconciliationIssue] = []
        for competency in _merge_competencies(extraction.competencies, expected_competencies or []):
            match = repo.find_competency_match(competency.title, aliases=competency.aliases)
            if match is not None:
                competency.competency_id = match.competency_id
                competency.match_type = match.match_type
            issue = ReconciliationIssue(
                reason_code=f"{'reverse_extracted_competency' if match else 'reverse_missing_competency'}:{normalize_catalog_key(competency.title)[:64]}",
                severity="info" if match else "warning",
                details={
                    "competency": competency.title,
                    "aliases": competency.aliases,
                    "evidence": competency.evidence,
                    "source": source_ref,
                    "match": None
                    if match is None
                    else {
                        "competency_id": match.competency_id,
                        "title": match.title,
                        "status": match.status,
                        "match_type": match.match_type,
                        "matched_name": match.matched_name,
                    },
                },
            )
            issue.review_id = repo.enqueue_review(
                entity_type="competency",
                entity_id=match.competency_id if match else None,
                source_ref=source_ref,
                reason_code=issue.reason_code,
                severity=issue.severity,
                details=issue.details,
            )
            issues.append(issue)

        for skill in _unique_texts([*extraction.partial_seed.skills, *(expected_skills or [])]):
            if _skill_exists(repo, skill):
                continue
            issue = ReconciliationIssue(
                reason_code=f"reverse_missing_skill:{normalize_catalog_key(skill)[:64]}",
                severity="warning",
                details={"skill": skill, "source": source_ref, "title": extraction.partial_seed.title_seed},
            )
            issue.review_id = repo.enqueue_review(
                entity_type="skill",
                entity_id=None,
                source_ref=source_ref,
                reason_code=issue.reason_code,
                severity=issue.severity,
                details=issue.details,
            )
            issues.append(issue)

        if expected_tasks_count is not None and extraction.partial_seed.tasks_count != expected_tasks_count:
            issue = ReconciliationIssue(
                reason_code=f"reverse_task_count_mismatch:{_short_hash(source_ref)}",
                severity="warning",
                details={
                    "expected_tasks_count": expected_tasks_count,
                    "extracted_tasks_count": extraction.partial_seed.tasks_count,
                    "confidence": extraction.tasks.confidence,
                },
            )
            issue.review_id = repo.enqueue_review(
                entity_type="project",
                entity_id=None,
                source_ref=source_ref,
                reason_code=issue.reason_code,
                severity=issue.severity,
                details=issue.details,
            )
            issues.append(issue)
        return issues

    def _extract_structure(self, normalized: NormalizedReadme, client: Any) -> PartialProjectSeed:
        if client is None:
            return fallback_structure_extraction(normalized)
        readme_text = normalized.raw_text
        if len(readme_text) > 20000:
            readme_text = f"{readme_text[:15000]}\n\n[... текст пропущен ...]\n\n{readme_text[-5000:]}"
        prompt = StructuredPrompt(
            system=load_prompt("checker", "reverse_structure_system").text,
            user=load_prompt("checker", "reverse_structure_user").render(readme_text=readme_text),
        )
        try:
            return complete_typed(prompt, PartialProjectSeed, client=client, retries=1, temperature=0.1)
        except Exception:
            return fallback_structure_extraction(normalized)

    def _extract_tasks(self, normalized: NormalizedReadme, initial_count: int | None, client: Any) -> TasksExtractionResult:
        practice_text = get_practice_section(normalized)
        if not practice_text:
            return TasksExtractionResult(tasks_count=initial_count or 0, confidence="low")
        if client is None:
            return fallback_task_count(practice_text, initial_count)
        prompt = StructuredPrompt(
            system=load_prompt("checker", "reverse_tasks_system").text,
            user=load_prompt("checker", "reverse_tasks_user").render(
                practice_text=practice_text[:15000],
                initial_count=initial_count or "не определено",
            ),
        )
        try:
            result = complete_typed(prompt, TasksExtractionResult, client=client, retries=1, temperature=0.1)
            if result.tasks_count is not None and 0 <= result.tasks_count <= 20:
                return result
        except Exception:
            pass
        return fallback_task_count(practice_text, initial_count)

    def _safe_client(self) -> Any | None:
        try:
            return self.client_factory()
        except Exception:
            return None


def normalize_readme(readme_text: str) -> NormalizedReadme:
    text = re.sub(r"<[^>]+>", "", readme_text or "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = "\n".join(line.strip() if line.strip().startswith("#") else line.rstrip() for line in text.splitlines())
    return NormalizedReadme(raw_text=text, structure=extract_structure(text), chapters=extract_chapters(text))


def extract_structure(text: str) -> dict[str, Any]:
    headings = [
        {"level": len(match.group(1)), "title": match.group(2).strip(), "line": _line_for_offset(text, match.start())}
        for match in HEADING_RE.finditer(text)
    ]
    lists = [
        {"line": index, "text": line.strip()}
        for index, line in enumerate(text.splitlines(), 1)
        if re.match(r"^\s*(?:[-*+]|\d+\.)\s+", line)
    ]
    return {"headings": headings, "lists": lists}


def extract_chapters(text: str) -> dict[int, str]:
    matches = list(re.finditer(r"^##\s+(?:Глава|Chapter)?\s*(\d+)[^\n]*", text, re.IGNORECASE | re.MULTILINE))
    chapters: dict[int, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        chapters[int(match.group(1))] = text[match.end() : end].strip()
    return chapters


def fallback_structure_extraction(normalized: NormalizedReadme) -> PartialProjectSeed:
    headings = normalized.structure.get("headings") or []
    title = headings[0]["title"] if headings else None
    first_chapter = normalized.chapters.get(1) or normalized.raw_text
    description = ". ".join([part.strip() for part in re.split(r"[.!?]+", first_chapter) if part.strip()][:3])
    if description:
        description += "."
    text_lower = normalized.raw_text.lower()
    tools = [tool for tool in ("Python", "Docker", "Git", "PostgreSQL", "FastAPI", "React", "pytest", "OpenAPI") if tool.lower() in text_lower]
    skills = [
        skill
        for skill in ("Разработка API", "Тестирование", "Работа с базами данных", "Контейнеризация", "Мониторинг")
        if normalize_catalog_key(skill).split()[0] in normalize_catalog_key(normalized.raw_text)
    ]
    outcomes = re.findall(r"(?:После изучения|В результате|Студент сможет|Студент научится)[:.]?\s*([^.!?]+[.!?])", normalized.raw_text, re.IGNORECASE)
    return PartialProjectSeed(
        title_seed=title,
        project_description=description or None,
        learning_outcomes=[item.strip() for item in outcomes[:5]],
        required_tools=tools,
        skills=skills,
        tasks_count=fallback_task_count(get_practice_section(normalized), None).tasks_count,
        theory_parts=[],
    )


def get_practice_section(normalized: NormalizedReadme) -> str:
    if 3 in normalized.chapters:
        return normalized.chapters[3]
    for pattern in (
        r"##\s+(?:Глава\s+3|Практика|Practice|Задачи|Tasks|Задания)[^\n]*\n(.*?)(?=\n##|\Z)",
        r"###\s+(?:Практика|Practice|Задачи|Tasks)[^\n]*\n(.*?)(?=\n###|\n##|\Z)",
    ):
        match = re.search(pattern, normalized.raw_text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
    return ""


def fallback_task_count(practice_text: str, initial_count: int | None = None) -> TasksExtractionResult:
    found: set[int] = set()
    for pattern in (r"(?:Задача|Task|Задание)\s+(\d+)", r"^\s*(\d+)\.\s+(?:Задача|Task|Задание)"):
        for value in re.findall(pattern, practice_text or "", re.IGNORECASE | re.MULTILINE):
            number = int(value)
            if 1 <= number <= 20:
                found.add(number)
    if found:
        return TasksExtractionResult(tasks_count=max(found), confidence="medium")
    return TasksExtractionResult(tasks_count=initial_count or 0, confidence="low")


def extract_competency_candidates(seed: PartialProjectSeed) -> list[ExtractedCompetency]:
    candidates: list[ExtractedCompetency] = []
    for outcome in _unique_texts(seed.learning_outcomes):
        title = _clean_competency_title(outcome)
        if title:
            candidates.append(
                ExtractedCompetency(
                    title=title,
                    aliases=[],
                    evidence=[outcome],
                )
            )
    return candidates


def extract_entities(text: str, *, unit_id: str = "readme", file_path: str = "README.md") -> list[ExtractedEntity]:
    entities: list[ExtractedEntity] = []
    entities.extend(_extract_by_regex(unit_id, file_path, text, URL_RE, "link", validate_url=True))
    entities.extend(_extract_images(unit_id, file_path, text))
    entities.extend(_extract_by_regex(unit_id, file_path, text, VERSION_RE, "version"))
    entities.extend(_extract_by_regex(unit_id, file_path, text, DATE_RE, "date"))
    entities.extend(_extract_by_regex(unit_id, file_path, text, TECH_RE, "technology"))
    return _deduplicate_entities(entities)


def _extract_by_regex(
    unit_id: str,
    file_path: str,
    text: str,
    pattern: re.Pattern[str],
    entity_type: EntityType,
    *,
    validate_url: bool = False,
) -> list[ExtractedEntity]:
    result: list[ExtractedEntity] = []
    for match in pattern.finditer(text or ""):
        value = match.group(0).rstrip(".,;:*!?")
        if validate_url and not urlparse(value).hostname:
            continue
        result.append(_entity(unit_id, file_path, text, entity_type, value, match.start(), match.end()))
    return result


def _extract_images(unit_id: str, file_path: str, text: str) -> list[ExtractedEntity]:
    return [
        _entity(unit_id, file_path, text, "image", match.group("target").strip(), match.start(), match.end())
        for match in MARKDOWN_IMAGE_RE.finditer(text or "")
    ]


def _entity(
    unit_id: str,
    file_path: str,
    text: str,
    entity_type: EntityType,
    value: str,
    start: int,
    end: int,
) -> ExtractedEntity:
    return ExtractedEntity(
        entity_id=f"ent_{_short_hash(f'{unit_id}|{file_path}|{entity_type}|{value}|{start}')}",
        entity_type=entity_type,
        value=value,
        quote=quote_around(text, start, end),
        file_path=file_path,
        line_start=_line_for_offset(text, start),
        line_end=_line_for_offset(text, end),
        context=context_around(text, start, end),
    )


def _deduplicate_entities(entities: list[ExtractedEntity]) -> list[ExtractedEntity]:
    seen: set[tuple[str, str, str, int]] = set()
    unique: list[ExtractedEntity] = []
    for entity in entities:
        key = (entity.entity_type, entity.value.lower(), entity.file_path, entity.line_start)
        if key not in seen:
            seen.add(key)
            unique.append(entity)
    return unique


def _skill_exists(repo: CurriculumCatalogRepo, skill: str) -> bool:
    normalized = normalize_catalog_key(skill)
    for candidate in repo.list_skills(query=skill, limit=10, include_deprecated=False):
        names = [candidate.canonical_name, *candidate.aliases]
        if any(normalize_catalog_key(name) == normalized for name in names):
            return True
    return False


def _unique_texts(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = normalize_catalog_key(value)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(value.strip())
    return result


def _merge_competencies(existing: list[ExtractedCompetency], expected: list[str]) -> list[ExtractedCompetency]:
    by_normalized: dict[str, ExtractedCompetency] = {}
    for item in [*existing, *(ExtractedCompetency(title=value) for value in expected)]:
        normalized = normalize_catalog_key(item.title)
        if normalized and normalized not in by_normalized:
            by_normalized[normalized] = item
    return list(by_normalized.values())


def _clean_competency_title(value: str) -> str:
    title = re.sub(r"\s+", " ", value or "").strip(" .;:-")
    title = re.sub(r"^(?:студент|участник|выпускник)\s+(?:сможет|научится|умеет|должен)\s+", "", title, flags=re.IGNORECASE)
    return title[:180].strip()


def quote_around(text: str, start: int, end: int, radius: int = 80) -> str:
    return (text[max(0, start - radius) : min(len(text), end + radius)] or "").strip()


def context_around(text: str, start: int, end: int, radius: int = 180) -> str:
    return quote_around(text, start, end, radius)


def _line_for_offset(text: str, offset: int) -> int:
    return (text or "").count("\n", 0, max(0, offset)) + 1


def _short_hash(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]
