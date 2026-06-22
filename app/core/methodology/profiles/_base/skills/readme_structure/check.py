"""README structural preflight skill."""

from __future__ import annotations

import re
from typing import Any

from app.core.methodology.rules import GeneratedDoc, RuleIssue

SID = "readme_structure"
H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.M)


def _issue(code: str, message: str, **evidence: Any) -> RuleIssue:
    return RuleIssue(SID, f"{SID}.{code}", "hard", message, evidence)


def check(doc: GeneratedDoc, params: dict) -> list[RuleIssue]:
    md = doc.markdown or ""
    required_flag = params.get("require_metadata_flag")
    if required_flag and not doc.metadata.get(str(required_flag)):
        return []

    issues: list[RuleIssue] = []

    if not md.lstrip().startswith("# "):
        issues.append(_issue("h1_first", "README должен начинаться с H1-заголовка."))

    annotation = _annotation_after_h1(md)
    if not annotation or re.search(r"^##", annotation, re.M) or re.search(r"^\s*[-*+]", annotation, re.M):
        issues.append(
            _issue(
                "annotation_missing",
                "После H1 должен идти связный блок аннотации без заголовков и списков.",
                annotation_chars=len(annotation),
            )
        )

    toc_lines = _toc_lines(md)
    toc_min = int(params.get("toc_min_lines", 3))
    if toc_lines < toc_min:
        issues.append(
            _issue(
                "toc_missing",
                f"Оглавление должно содержать минимум {toc_min} непустые строки.",
                toc_lines=toc_lines,
            )
        )

    min_chars = int(params.get("chapter_min_chars", 50))
    for number, label, code in (
        (1, "Глава 1 / введение", "chapter1_missing"),
        (2, "Глава 2 / теория", "chapter2_missing"),
        (3, "Глава 3 / практика", "chapter3_missing"),
    ):
        chars = len(_chapter_text(md, number))
        if chars < min_chars:
            issues.append(
                _issue(
                    code,
                    f"{label} отсутствует или короче {min_chars} символов.",
                    chars=chars,
                    min_chars=min_chars,
                )
            )
    return issues


def _annotation_after_h1(md: str) -> str:
    match = re.search(r"^#\s+.+$", md, re.M)
    if not match:
        return ""
    return md[match.end() :].split("\n## ", 1)[0].strip()


def _toc_lines(md: str) -> int:
    match = re.search(r"^##\s+(?:Содержание|Оглавление)\s*$", md, re.M | re.I)
    if not match:
        return 0
    block = md[match.end() :].split("\n## ", 1)[0]
    return len([line for line in block.splitlines() if line.strip()])


def _chapter_text(md: str, number: int) -> str:
    headings = list(H2_RE.finditer(md))
    for index, match in enumerate(headings):
        if _is_chapter(match.group(1), number):
            end = headings[index + 1].start() if index + 1 < len(headings) else len(md)
            return md[match.end() : end].strip()
    return ""


def _is_chapter(title: str, number: int) -> bool:
    clean = title.lower().replace("ё", "е")
    if re.search(rf"\b(?:глава\s*)?{number}(?:[\s.:\-—]|$)", clean):
        return True
    aliases = {
        1: ("введение", "обзор"),
        2: ("теория", "теорет"),
        3: ("практика", "задани"),
    }
    return any(alias in clean for alias in aliases[number])
