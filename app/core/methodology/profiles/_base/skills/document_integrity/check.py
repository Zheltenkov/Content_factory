"""Cross-document integrity checks for generated learning artifacts."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from app.core.methodology.rules import GeneratedDoc, RuleIssue

SID = "document_integrity"
FENCE_RE = re.compile(r"```(\w*)\n(.*?)```", re.S)


def _issue(code: str, severity: str, message: str, **evidence: Any) -> RuleIssue:
    return RuleIssue(SID, f"{SID}.{code}", severity, message, evidence)


def check(doc: GeneratedDoc, params: dict) -> list[RuleIssue]:
    md = doc.markdown or ""
    issues: list[RuleIssue] = []
    issues.extend(_tables(md, params))
    issues.extend(_template_bleed(md, params))
    issues.extend(_broken_text(md, params))
    issues.extend(_project_id(md, doc, params))
    issues.extend(_diagram_topic(md, params))
    return issues


def _mask_code(md: str) -> str:
    count = [0]

    def repl(_match: re.Match[str]) -> str:
        count[0] += 1
        return f"\n@@CODE{count[0]}@@\n"

    return FENCE_RE.sub(repl, md)


def _cells(line: str) -> int:
    return len(line.strip().strip("|").split("|"))


def _tables(md: str, params: dict) -> list[RuleIssue]:
    if not params.get("check_tables", True):
        return []
    issues: list[RuleIssue] = []
    lines = _mask_code(md).splitlines()
    index = 0
    while index < len(lines):
        has_separator = index + 1 < len(lines) and "|" in lines[index + 1]
        has_separator = has_separator and bool(re.match(r"^\s*\|?\s*:?-{2,}", lines[index + 1]))
        if "|" not in lines[index] or not has_separator:
            index += 1
            continue
        expected = _cells(lines[index])
        if _cells(lines[index + 1]) != expected:
            issues.append(_issue("table_separator", "hard", f"Разделитель таблицы в строке {index + 2} не совпадает с шапкой."))
        row_index = index + 2
        rows = 0
        while row_index < len(lines) and "|" in lines[row_index] and lines[row_index].strip():
            actual = _cells(lines[row_index])
            if actual != expected:
                issues.append(_issue("table_columns", "hard", f"Строка таблицы {row_index + 1}: {actual} колонок вместо {expected}."))
            rows += 1
            row_index += 1
        if rows == 0:
            issues.append(_issue("table_empty", "hard", f"Таблица в строке {index + 1} не содержит строк данных."))
        index = row_index
    return issues[:4]


def _template_bleed(md: str, params: dict) -> list[RuleIssue]:
    issues: list[RuleIssue] = []
    masked = _mask_code(md)
    lower = masked.lower()
    for marker in params.get("placeholder_markers", []):
        marker_text = str(marker)
        if _has_placeholder_marker(masked, lower, marker_text):
            issues.append(_issue("placeholder", "hard", f"В тексте остался шаблонный плейсхолдер: {marker}", marker=marker))
    min_chars = int(params.get("min_block_chars", 120))
    paragraphs = [item.strip() for item in re.split(r"\n\s*\n", masked) if len(item.strip()) >= min_chars]
    seen: dict[str, int] = {}
    duplicate_chars = 0
    for paragraph in paragraphs:
        key = hashlib.md5(re.sub(r"\s+", " ", paragraph.lower()).strip().encode()).hexdigest()
        if key in seen:
            duplicate_chars += len(paragraph)
            if seen[key] == 1:
                issues.append(_issue("repeated_block", "hard", f"Дословно повторяется блок: {paragraph[:80]}..."))
            seen[key] += 1
        else:
            seen[key] = 1
    total = sum(len(paragraph) for paragraph in paragraphs) or 1
    ratio = duplicate_chars / total
    threshold = float(params.get("max_duplicate_block_ratio", 0.08))
    if ratio > threshold:
        issues.append(_issue("duplication_ratio", "hard", f"Доля дословных повторов {ratio:.0%} выше {threshold:.0%}.", ratio=round(ratio, 3)))
    return issues


def _has_placeholder_marker(masked: str, lower: str, marker: str) -> bool:
    if not marker:
        return False
    if not marker.isascii() and marker.upper() == marker:
        return marker in masked
    return marker.lower() in lower


def _broken_text(md: str, params: dict) -> list[RuleIssue]:
    if not params.get("check_broken_text", True):
        return []
    issues: list[RuleIssue] = []
    if md.count("```") % 2 != 0:
        issues.append(_issue("unclosed_fence", "hard", "Незакрытый fenced-блок кода."))
    masked = _mask_code(md)
    if masked.count("«") != masked.count("»"):
        issues.append(_issue("unbalanced_quotes", "soft", "Кавычки «...» не сбалансированы."))
    limit = int(params.get("max_dangling_reported", 3))
    for paragraph in (item.strip() for item in re.split(r"\n\s*\n", masked) if item.strip()):
        last = paragraph.splitlines()[-1].strip()
        if last[:1] in "#|-*>" or "@@CODE" in last:
            continue
        if re.search(r"[,;]$", last) or re.search(r"\b(?:и|или|но|что|как|для|при|чтобы)$", last, re.I):
            issues.append(_issue("dangling_sentence", "soft", f"Возможно оборванное предложение: ...{last[-60:]}"))
            if len([issue for issue in issues if issue.code.endswith("dangling_sentence")]) >= limit:
                break
    return issues


def _project_id(md: str, doc: GeneratedDoc, params: dict) -> list[RuleIssue]:
    if not params.get("require_single_project_id", True):
        return []
    pattern = params.get("project_id_pattern", r"\b[A-Z]{1,4}\d{1,3}_[A-Z][A-Za-z0-9]+(?:_v[\d.]+)?\b")
    found = set(re.findall(pattern, _mask_code(md)))
    if not found:
        return []
    if doc.project_id:
        foreign = sorted(item for item in found if item != doc.project_id)
        return [_issue("foreign_project_id", "hard", f"Найдены чужие project-id: {foreign[:5]}", ids=foreign[:5])] if foreign else []
    if len(found) > 1:
        return [_issue("multiple_project_ids", "hard", f"В документе несколько project-id: {sorted(found)[:5]}", ids=sorted(found)[:5])]
    return []


def _diagram_topic(md: str, params: dict) -> list[RuleIssue]:
    if not params.get("check_diagram_topic", True):
        return []
    issues: list[RuleIssue] = []
    languages = {str(item).lower() for item in params.get("diagram_fences", ["mermaid"])}
    context_lines = int(params.get("diagram_context_lines", 6))
    for match in FENCE_RE.finditer(md):
        if (match.group(1) or "").lower() not in languages:
            continue
        heading = _nearest_heading(md[: match.start()], context_lines)
        if not heading:
            issues.append(_issue("diagram_no_context", "hard", "Диаграмма без ближайшего заголовка или подписи."))
            continue
        diagram_terms = set(re.findall(r"[А-Яа-яA-Za-z]{4,}", match.group(2).lower()))
        heading_terms = set(re.findall(r"[А-Яа-яA-Za-z]{4,}", heading.lower()))
        if diagram_terms and heading_terms and not diagram_terms.intersection(heading_terms):
            issues.append(_issue("diagram_topic_mismatch", "soft", f"Диаграмма не связана словами с разделом '{heading[:40]}'."))
    return issues


def _nearest_heading(prefix: str, context_lines: int) -> str | None:
    for line in reversed(prefix.splitlines()[-context_lines:]):
        stripped = line.strip()
        if re.match(r"^#{1,6}\s+(.+)", stripped):
            return re.sub(r"^#+\s+", "", stripped)
        if re.match(r"^\*{0,2}(?:Рис\.|Схема|Диаграмма|Figure)", stripped):
            return stripped.strip("* ")
    return None
