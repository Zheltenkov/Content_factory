"""Checker orchestration for deterministic structural and content checks."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from difflib import SequenceMatcher, unified_diff
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.methodology.gate import MethodologyGate, StageReviewResult
from app.core.methodology.harness import Harness, resolve_profile
from app.core.methodology.rubric import rule_issues_to_rubric
from app.core.methodology.rules import GeneratedDoc, RuleIssue
from app.modules.checker.structural import StructuralAxisResult, evaluate_document

CONTENT_STAGE = "checker.content_sufficiency"
PROFILES_ROOT = Path(__file__).resolve().parents[2] / "core" / "methodology" / "profiles"
TECH_TERMS = ("Python", "Docker", "Git", "SQL", "PostgreSQL", "API", "REST", "OpenAPI", "pytest", "CI/CD", "Linux")


class ContentSufficiencyResult(BaseModel):
    """Deterministic C4 checks over generated theory/practice metadata."""

    model_config = ConfigDict(extra="forbid")

    stage: str = CONTENT_STAGE
    profile_id: str
    issues: list[RuleIssue] = Field(default_factory=list)
    rubric_json: dict[str, Any] = Field(default_factory=dict)
    gate_review: StageReviewResult

    @property
    def passed(self) -> bool:
        return bool(self.rubric_json.get("passed")) and not self.gate_review.human_review_required


class CheckerDeterministicResult(BaseModel):
    """Combined deterministic checker payload before didactic jury."""

    model_config = ConfigDict(extra="forbid")

    structural: StructuralAxisResult
    content: ContentSufficiencyResult
    rubric_json: dict[str, Any]
    gate_review: StageReviewResult

    @property
    def passed(self) -> bool:
        return self.structural.passed and self.content.passed and not self.gate_review.human_review_required


def evaluate_content_sufficiency(
    doc: GeneratedDoc,
    *,
    profile_id: str = "_base",
    program_type: str | None = None,
    context: dict[str, Any] | None = None,
    gate: MethodologyGate | None = None,
    profile_root: Path = PROFILES_ROOT,
) -> ContentSufficiencyResult:
    """Run C4 theory/practice checks via methodology harness."""

    profile = resolve_profile(profile_id, profile_root, program_type=program_type)
    issues = Harness(profile).validate(CONTENT_STAGE, doc, dict(context or {}))
    rubric = rule_issues_to_rubric(issues)
    review = (gate or MethodologyGate()).review("evaluation", {"generated_doc": doc, "markdown": doc.markdown, "rubric_json": rubric})
    return ContentSufficiencyResult(profile_id=profile_id, issues=issues, rubric_json=rubric, gate_review=review)


def evaluate_deterministic(
    doc: GeneratedDoc,
    *,
    profile_id: str = "_base",
    program_type: str | None = None,
    context: dict[str, Any] | None = None,
    gate: MethodologyGate | None = None,
    profile_root: Path = PROFILES_ROOT,
) -> CheckerDeterministicResult:
    """Run structural C2 and C4 content checks and merge their rubric_json."""

    structural = evaluate_document(
        doc,
        profile_id=profile_id,
        program_type=program_type,
        context=context,
        gate=gate,
        profile_root=profile_root,
    )
    content = evaluate_content_sufficiency(
        doc,
        profile_id=profile_id,
        program_type=program_type,
        context=context,
        gate=gate,
        profile_root=profile_root,
    )
    all_issues = [*structural.issues, *content.issues]
    rubric = rule_issues_to_rubric(all_issues)
    review = (gate or MethodologyGate()).review("evaluation", {"generated_doc": doc, "markdown": doc.markdown, "rubric_json": rubric})
    return CheckerDeterministicResult(structural=structural, content=content, rubric_json=rubric, gate_review=review)


@dataclass
class CheckerImprovementExtract:
    """Stored seed extracted from README before the user edits legacy modal fields."""

    request_id: str
    original_readme: str
    partial_seed: dict[str, Any]
    classification: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CheckerImprovementRun:
    """Completed compact improvement run exposed through legacy-compatible status/diff endpoints."""

    generation_request_id: str
    extract_request_id: str
    original_readme: str
    improved_readme: str
    seed: dict[str, Any]
    rubric: dict[str, Any]
    status: str = "completed"
    phase: str = "completed"
    progress: int = 100

    def result_payload(self) -> dict[str, Any]:
        return {
            "request_id": self.extract_request_id,
            "generation_request_id": self.generation_request_id,
            "markdown": self.improved_readme,
            "rubric": self.rubric,
            "assets": {},
        }


class CheckerImprovementService:
    """Thin compatibility adapter for the legacy README improvement workflow."""

    def __init__(self) -> None:
        self.extracts: dict[str, CheckerImprovementExtract] = {}
        self.runs: dict[str, CheckerImprovementRun] = {}

    def extract(
        self,
        readme_text: str,
        *,
        curriculum_project: dict[str, Any] | None = None,
        curriculum_context: dict[str, Any] | None = None,
    ) -> CheckerImprovementExtract:
        if not readme_text.strip():
            raise ValueError("README пуст")
        partial_seed = _extract_seed(readme_text, curriculum_project or {})
        classification = _classify_readme(readme_text, partial_seed, curriculum_context or {})
        request = CheckerImprovementExtract(
            request_id=str(uuid.uuid4()),
            original_readme=readme_text,
            partial_seed=partial_seed,
            classification=classification,
            metadata={"warnings": _extract_warnings(readme_text), "source": "checker_improvement"},
        )
        self.extracts[request.request_id] = request
        return request

    def generate(self, request_id: str, seed: dict[str, Any]) -> CheckerImprovementRun:
        request = self.extracts.get(request_id)
        if request is None:
            raise KeyError("improvement extract request not found")
        merged_seed = {**request.partial_seed, **{key: value for key, value in (seed or {}).items() if value not in (None, "", [])}}
        improved = _build_improved_readme(request.original_readme, merged_seed)
        evaluation = evaluate_deterministic(GeneratedDoc(markdown=improved, metadata={"source": "checker_improvement"}))
        run = CheckerImprovementRun(
            generation_request_id=str(uuid.uuid4()),
            extract_request_id=request_id,
            original_readme=request.original_readme,
            improved_readme=improved,
            seed=merged_seed,
            rubric=evaluation.rubric_json,
        )
        self.runs[run.generation_request_id] = run
        return run

    def status(self, generation_request_id: str) -> CheckerImprovementRun:
        run = self.runs.get(generation_request_id)
        if run is None:
            raise KeyError("improvement generation request not found")
        return run

    def diff(self, request_or_generation_id: str) -> dict[str, Any]:
        run = self._resolve_run(request_or_generation_id)
        original_lines = run.original_readme.splitlines()
        improved_lines = run.improved_readme.splitlines()
        side_by_side = _side_by_side_diff(original_lines, improved_lines)
        added = sum(1 for row in side_by_side if row["type"] == "insert")
        deleted = sum(1 for row in side_by_side if row["type"] == "delete")
        modified = sum(1 for row in side_by_side if row["type"] == "replace")
        return {
            "request_id": run.extract_request_id,
            "generation_request_id": run.generation_request_id,
            "original_readme": run.original_readme,
            "improved_readme": run.improved_readme,
            "stats": {
                "original_lines": len(original_lines),
                "improved_lines": len(improved_lines),
                "added": added,
                "deleted": deleted,
                "modified": modified,
            },
            "side_by_side": side_by_side,
            "unified": "\n".join(
                unified_diff(original_lines, improved_lines, fromfile="README.original.md", tofile="README.improved.md", lineterm="")
            ),
        }

    def download(self, generation_request_id: str) -> str:
        return self.status(generation_request_id).improved_readme

    def _resolve_run(self, request_or_generation_id: str) -> CheckerImprovementRun:
        if request_or_generation_id in self.runs:
            return self.runs[request_or_generation_id]
        for run in self.runs.values():
            if run.extract_request_id == request_or_generation_id:
                return run
        raise KeyError("improvement run not found")


def _extract_seed(markdown: str, curriculum_project: dict[str, Any]) -> dict[str, Any]:
    title = curriculum_project.get("title") or _first_match(markdown, r"^#\s+(.+)$") or "Улучшенный учебный проект"
    description = curriculum_project.get("description") or _first_paragraph(markdown)
    outcomes = _section_bullets(markdown, ("результат", "learning outcome", "цели обучения"))
    skills = _section_bullets(markdown, ("навык", "skills"))
    tools = sorted({term for term in TECH_TERMS if re.search(rf"\b{re.escape(term)}\b", markdown, re.IGNORECASE)})
    tasks_count = len(re.findall(r"(?im)^(?:#{2,4}\s*)?(?:задание|task|упражнение)\b", markdown))
    return {
        "title_seed": str(title).strip(),
        "project_description": description.strip() or str(title).strip(),
        "learning_outcomes": outcomes[:8],
        "skills": skills[:12],
        "required_tools": tools,
        "tasks_count": tasks_count or None,
    }


def _classify_readme(markdown: str, partial_seed: dict[str, Any], curriculum_context: dict[str, Any]) -> dict[str, Any]:
    lowered = markdown.lower()
    block_name, block_code = _detect_thematic_block(lowered, curriculum_context)
    project_type = "group" if re.search(r"\b(команд|групп|team)\w*", lowered) else "individual"
    return {
        "language": "ru" if re.search(r"[а-яА-ЯёЁ]", markdown) else "en",
        "thematic_block": block_code,
        "thematic_block_name": block_name,
        "thematic_block_suggested": block_code,
        "audience_level": "base",
        "project_type": project_type,
        "group_size": 3 if project_type == "group" else None,
        "title": partial_seed.get("title_seed"),
    }


def _detect_thematic_block(lowered: str, curriculum_context: dict[str, Any]) -> tuple[str, str]:
    if curriculum_context.get("block"):
        return str(curriculum_context["block"]), str(curriculum_context.get("block_code") or "UP")
    mapping = (
        ("DevOps", "DO", ("docker", "ci/cd", "deploy", "kubernetes")),
        ("Тестирование и обеспечение качества", "QA", ("pytest", "тест", "qa", "quality")),
        ("Машинное обучение", "DS", ("ml", "модель", "dataset", "данные")),
        ("Backend", "BE", ("api", "backend", "postgres", "sql", "rest")),
    )
    for name, code, markers in mapping:
        if any(marker in lowered for marker in markers):
            return name, code
    return "Общий учебный проект", "GEN"


def _build_improved_readme(original: str, seed: dict[str, Any]) -> str:
    fixed = _close_unclosed_fence(original.strip())
    title = str(seed.get("title_seed") or _first_match(fixed, r"^#\s+(.+)$") or "Учебный проект").strip()
    if not re.match(r"^#\s+", fixed):
        fixed = f"# {title}\n\n{fixed}"
    fixed = re.sub(r"\bTODO\b|ЗАГЛУШКА", "Требует уточнения методологом", fixed, flags=re.IGNORECASE)
    sections: list[str] = []
    if not _has_section(fixed, "цель проекта"):
        sections.append(f"## Цель проекта\n\n{seed.get('project_description') or 'Собрать учебный результат в формате практического проекта.'}")
    outcomes = seed.get("learning_outcomes") or ["Сформировать применимый результат обучения.", "Связать теорию с практическими заданиями."]
    if not _has_section(fixed, "образовательные результаты"):
        sections.append("## Образовательные результаты\n\n" + "\n".join(f"- {item}" for item in outcomes))
    tools = seed.get("required_tools") or ["Git"]
    if not _has_section(fixed, "инструменты"):
        sections.append("## Инструменты\n\n" + ", ".join(map(str, tools)))
    if not _has_section(fixed, "практика"):
        tasks_count = int(seed.get("tasks_count") or 3)
        tasks = [f"{idx}. Выполнить практический шаг и зафиксировать результат в репозитории." for idx in range(1, max(2, tasks_count) + 1)]
        sections.append("## Практика\n\n" + "\n".join(tasks))
    if not _has_section(fixed, "критерии сдачи"):
        sections.append("## Критерии сдачи\n\n- README содержит цель, теорию, практику и критерии проверки.\n- Все артефакты воспроизводимы по инструкции.\n- Практика проверяет заявленные образовательные результаты.")
    return "\n\n".join([fixed, *sections]).strip() + "\n"


def _side_by_side_diff(original_lines: list[str], improved_lines: list[str]) -> list[dict[str, str | None]]:
    rows: list[dict[str, str | None]] = []
    matcher = SequenceMatcher(a=original_lines, b=improved_lines)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            rows.extend({"type": "equal", "original": line, "improved": line} for line in original_lines[i1:i2])
        elif tag == "delete":
            rows.extend({"type": "delete", "original": line, "improved": None} for line in original_lines[i1:i2])
        elif tag == "insert":
            rows.extend({"type": "insert", "original": None, "improved": line} for line in improved_lines[j1:j2])
        else:
            pairs = max(i2 - i1, j2 - j1)
            for offset in range(pairs):
                rows.append(
                    {
                        "type": "replace",
                        "original": original_lines[i1 + offset] if i1 + offset < i2 else None,
                        "improved": improved_lines[j1 + offset] if j1 + offset < j2 else None,
                    }
                )
    return rows


def _extract_warnings(markdown: str) -> list[str]:
    warnings: list[str] = []
    if "TODO" in markdown.upper():
        warnings.append("README содержит TODO-маркеры.")
    if markdown.count("```") % 2:
        warnings.append("В README есть незакрытый code fence.")
    if not re.match(r"^#\s+", markdown.strip()):
        warnings.append("README начинается не с H1.")
    return warnings


def _first_match(markdown: str, pattern: str) -> str | None:
    match = re.search(pattern, markdown, re.MULTILINE | re.IGNORECASE)
    return match.group(1).strip() if match else None


def _first_paragraph(markdown: str) -> str:
    for block in re.split(r"\n\s*\n", re.sub(r"^#.*$", "", markdown, count=1, flags=re.MULTILINE)):
        text = block.strip(" \n#")
        if text and not text.startswith("```"):
            return re.sub(r"\s+", " ", text)
    return ""


def _section_bullets(markdown: str, markers: tuple[str, ...]) -> list[str]:
    sections = re.split(r"(?m)^#{2,4}\s+", markdown)
    for section in sections:
        header, _, body = section.partition("\n")
        if any(marker in header.lower() for marker in markers):
            bullets = re.findall(r"(?m)^\s*(?:[-*]|\d+[.)])\s+(.+)$", body)
            return [item.strip() for item in bullets if item.strip()]
    return []


def _close_unclosed_fence(markdown: str) -> str:
    return markdown + "\n```" if markdown.count("```") % 2 else markdown


def _has_section(markdown: str, name: str) -> bool:
    return bool(re.search(rf"(?im)^##+\s+.*{re.escape(name)}", markdown))
