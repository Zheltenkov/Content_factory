"""Deterministic safety guards for methodologist revision requests."""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from app.core.methodology.revision.contracts import ChangeRequestConflict, MethodologistChangeRequest

_FIX_INTENT_MARKERS = (
    "убери",
    "убрать",
    "удали",
    "удалить",
    "исключи",
    "исключить",
    "remove",
    "delete",
    "exclude",
    "avoid",
    "do not",
)
_SOLUTION_LEAK_RE = re.compile(
    r"(?:добавь|включи|дай|покажи|include|add|provide|show).{0,80}"
    r"(?:готов\w*\s+(?:ответ|решени|реестр|матриц|таблиц)|правильн\w*\s+ответ|answer key|solution)",
    re.I | re.S,
)
_BROAD_REWRITE_RE = re.compile(r"(?:перепиш\w*|измени|переделай|rewrite|regenerate).{0,80}(?:весь|всю|полностью|all|entire|whole)", re.I | re.S)
_POLICY_OVERRIDE_RE = re.compile(r"(?:игнорируй|отключи|обойди|skip|disable|ignore|bypass).{0,80}(?:валидатор|guard|policy|контракт|провер\w*)", re.I | re.S)
_STATIC_INSTRUCTION_LEAK_RE = re.compile(r"(?:добавь|включи|insert|include|add).{0,80}(?:p2p|peer[-\s]?to[-\s]?peer|gitlab|статическ\w+\s+инструкц)", re.I | re.S)
_MATERIAL_REF_RE = re.compile(r"`?(materials/[A-Za-z0-9_./-]+\.[A-Za-z0-9]+)`?", re.I)
_PROCESSED_MATERIAL_RE = tuple(
    re.compile(pattern, re.I)
    for pattern in (
        r"\bготов\w*\s+(?:список|реестр|матриц\w*|план|рекомендаци\w*|решени\w*|отч[её]т|таблиц\w*)\b",
        r"\bуже\s+(?:заполненн\w*|классифицир\w*|сформированн\w*|подготовленн\w*)\b",
        r"\b(?:план|матриц\w*|реестр|стратеги\w*|отч[её]т|решени\w*)\s+(?:уже\s+)?(?:готов|заполн|сформир|классифиц)",
    )
)
_SOLUTION_STEMS = ("answer", "solution", "final", "result", "output", "deliverable", "register", "registry", "matrix", "analysis", "classification", "plan")
_RAW_HINTS = ("raw", "source", "draft", "notes", "case", "incident", "event", "log", "interview", "requirements", "source_notes")


def validate_methodologist_change_request(request: MethodologistChangeRequest) -> list[ChangeRequestConflict]:
    """Validate a requested edit before it can affect generation state."""

    instruction = request.instruction or ""
    combined = " ".join([request.target_selector, instruction, request.expected_outcome, " ".join(request.forbidden_changes)])
    normalized = combined.lower()
    fix_intent = any(marker in normalized for marker in _FIX_INTENT_MARKERS)
    conflicts: list[ChangeRequestConflict] = []

    material_issues = find_non_raw_material_issues(instruction)
    if material_issues and not fix_intent:
        conflicts.append(
            ChangeRequestConflict(
                code="raw_evidence_contract_violation",
                message="Materials должны оставаться raw evidence без готовых решений.",
                details={"issues": material_issues},
            )
        )
    if _SOLUTION_LEAK_RE.search(instruction) and not fix_intent:
        conflicts.append(
            ChangeRequestConflict(
                code="solution_leak_request",
                message="Запрос ведёт к готовым ответам или полуответам в материалах/практике.",
                details={"scope": request.scope, "target_stage": request.target_stage},
            )
        )
    if request.scope == "local_section_only" and _BROAD_REWRITE_RE.search(instruction) and not fix_intent:
        conflicts.append(ChangeRequestConflict(code="scope_expansion_violation", message="Локальная правка не может переписывать весь результат."))
    if _POLICY_OVERRIDE_RE.search(instruction) and not fix_intent:
        conflicts.append(ChangeRequestConflict(code="policy_override_request", message="Запрос не может отключать validators, guard-правила или hard contracts."))
    if request.target_stage == "theory" and _STATIC_INSTRUCTION_LEAK_RE.search(instruction) and not fix_intent:
        conflicts.append(ChangeRequestConflict(code="static_instruction_leak_request", message="Правка теории не должна подтягивать статическую инструкцию про P2P/GitLab."))
    if request.scope == "local_section_only" and not request.target_selector:
        conflicts.append(ChangeRequestConflict(code="missing_local_selector", message="Для локальной правки желательно указать главу, часть или артефакт.", severity="warning"))
    return conflicts


def has_hard_conflicts(conflicts: list[ChangeRequestConflict]) -> bool:
    return any(conflict.severity == "hard" for conflict in conflicts)


def find_non_raw_material_issues(text: str) -> list[str]:
    """Detect materials refs or phrases that look like solved learner deliverables."""

    normalized = (text or "").strip()
    if not normalized:
        return []
    issues: list[str] = []
    for match in _MATERIAL_REF_RE.finditer(normalized):
        ref = match.group(1)
        if _is_solution_like_material_ref(ref, context=normalized):
            issues.append(f"solution_like_ref:{ref}")
    for pattern in _PROCESSED_MATERIAL_RE:
        if match := pattern.search(normalized):
            issues.append(f"processed_material_phrase:{match.group(0)}")
    result: list[str] = []
    seen: set[str] = set()
    for issue in issues:
        key = issue.lower()
        if key not in seen:
            result.append(issue)
            seen.add(key)
    return result


def _is_solution_like_material_ref(path_or_filename: str, *, context: str = "") -> bool:
    stem = PurePosixPath(path_or_filename.replace("\\", "/")).stem.lower()
    if not stem or any(hint in stem or hint in context.lower() for hint in _RAW_HINTS):
        return False
    return any(re.search(rf"(^|[_-]){re.escape(token)}($|[_-])", stem) for token in _SOLUTION_STEMS)
