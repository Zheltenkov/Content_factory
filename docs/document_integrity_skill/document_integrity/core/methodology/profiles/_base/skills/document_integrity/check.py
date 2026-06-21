"""skills/document_integrity/check.py — кросс-документная целостность (structural_criteria_v2 N.1-N.5).

Детерминированно, без LLM. НЕ зависит от каркаса (content_model) — работает на сырой структуре
markdown: таблицы, fenced-блоки, кавычки, диаграммы, project-id. Поэтому применим к readme_*,
lesson_* и прочим artifact_family.

N.1 целостность таблиц | N.2 template bleed + дословные повторы | N.3 диаграмма<->тема (эвристика)
N.4 оборванные фразы/кавычки | N.5 единый project-id
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter

from core.methodology.rules import GeneratedDoc, RuleIssue

SID = "document_integrity"
_FENCE = re.compile(r"```(\w*)\n(.*?)```", re.S)


def _i(code: str, sev: str, msg: str, **ev) -> RuleIssue:
    return RuleIssue(SID, f"{SID}.{code}", sev, msg, ev)


def _mask_code(md: str) -> str:
    """Заменяет все fenced-блоки на плейсхолдеры — чтобы '|' и кавычки внутри кода не давали ложь."""
    n = [0]

    def repl(_m):
        n[0] += 1
        return f"\n@@CODE{n[0]}@@\n"

    return _FENCE.sub(repl, md)


def _cells(line: str) -> int:
    return len(line.strip().strip("|").split("|"))


def check(doc: GeneratedDoc, params: dict) -> list[RuleIssue]:
    md = doc.markdown
    out: list[RuleIssue] = []
    out += _tables(md, params)
    out += _template_bleed(md, params)
    out += _broken_text(md, params)
    out += _project_id(md, doc, params)
    out += _diagram_topic(md, params)
    return out


# ---------- N.1 ----------
def _tables(md: str, params: dict) -> list[RuleIssue]:
    if not params.get("check_tables", True):
        return []
    out, lines, i = [], _mask_code(md).splitlines(), 0
    while i < len(lines):
        sep = i + 1 < len(lines) and "|" in lines[i + 1] and re.match(r"^\s*\|?\s*:?-{2,}", lines[i + 1])
        if "|" in lines[i] and sep:
            head = _cells(lines[i])
            if _cells(lines[i + 1]) != head:
                out.append(_i("table_separator", "hard", f"Таблица (стр. {i+1}): разделитель ≠ шапке ({head} колонок)"))
            j, rows = i + 2, 0
            while j < len(lines) and "|" in lines[j] and lines[j].strip():
                if _cells(lines[j]) != head:
                    out.append(_i("table_columns", "hard", f"Строка таблицы {j+1}: {_cells(lines[j])} колонок ≠ шапка {head}"))
                rows, j = rows + 1, j + 1
            if rows == 0:
                out.append(_i("table_empty", "hard", f"Таблица (стр. {i+1}): нет строк данных"))
            i = j
        else:
            i += 1
    # ограничим шум: не более 4 табличных issue
    return out[:4]


# ---------- N.2 ----------
def _template_bleed(md: str, params: dict) -> list[RuleIssue]:
    out, masked = [], _mask_code(md)
    low = masked.lower()
    for mark in params.get("placeholder_markers", []):
        if mark.lower() in low:
            out.append(_i("placeholder", "hard", f"Шаблонный плейсхолдер в тексте: «{mark}»", marker=mark))
    min_chars = params.get("min_block_chars", 120)
    paras = [p.strip() for p in re.split(r"\n\s*\n", masked) if len(p.strip()) >= min_chars]
    seen, dup_chars = {}, 0
    for p in paras:
        k = hashlib.md5(re.sub(r"\s+", " ", p.lower()).strip().encode()).hexdigest()
        if k in seen:
            dup_chars += len(p)
            if seen[k] == 1:
                out.append(_i("repeated_block", "hard", f"Дословно повторяющийся блок ({len(p)} симв.): «{p[:60]}…»"))
            seen[k] += 1
        else:
            seen[k] = 1
    total = sum(len(p) for p in paras) or 1
    ratio = dup_chars / total
    thr = params.get("max_duplicate_block_ratio", 0.08)
    if ratio > thr:
        out.append(_i("duplication_ratio", "hard", f"Доля дословных повторов {ratio:.0%} > {thr:.0%}", ratio=round(ratio, 3)))
    return out


# ---------- N.4 ----------
def _broken_text(md: str, params: dict) -> list[RuleIssue]:
    if not params.get("check_broken_text", True):
        return []
    out = []
    if md.count("```") % 2 != 0:
        out.append(_i("unclosed_fence", "hard", "Нечётное число ``` — незакрытый блок кода"))
    masked = _mask_code(md)
    op, cl = masked.count("«"), masked.count("»")
    if op != cl:
        out.append(_i("unbalanced_quotes", "soft", f"Кавычки «…» не сбалансированы: {op} «, {cl} »"))
    dangling, cap = [], params.get("max_dangling_reported", 3)
    for p in (x.strip() for x in re.split(r"\n\s*\n", masked) if x.strip()):
        last = p.splitlines()[-1].strip()
        if last[:1] in "#|-*>" or "@@CODE" in last:
            continue
        if re.search(r"[,;]$", last) or re.search(r"\b(и|или|но|что|как|для|при|чтобы)$", last, re.I):
            dangling.append(last[-50:])
    for d in dangling[:cap]:
        out.append(_i("dangling_sentence", "soft", f"Возможно оборванное предложение: «…{d}»"))
    return out


# ---------- N.5 ----------
def _project_id(md: str, doc: GeneratedDoc, params: dict) -> list[RuleIssue]:
    if not params.get("require_single_project_id", True):
        return []
    pat = params.get("project_id_pattern", r"\b[A-Z]{1,4}\d{1,3}_[A-Z][A-Za-z0-9]+(?:_v[\d.]+)?\b")
    ids = set(re.findall(pat, _mask_code(md)))
    if not ids:
        return []
    if doc.project_id:
        alien = sorted(s for s in ids if s != doc.project_id)
        if alien:
            return [_i("foreign_project_id", "hard", f"Чужие project-id (ожидался {doc.project_id}): {alien[:5]}", ids=alien[:5])]
    elif len(ids) > 1:
        return [_i("multiple_project_ids", "hard", f"Несколько разных project-id: {sorted(ids)[:5]}", ids=sorted(ids)[:5])]
    return []


# ---------- N.3 ----------
def _diagram_topic(md: str, params: dict) -> list[RuleIssue]:
    if not params.get("check_diagram_topic", True):
        return []
    out, langs = [], set(params.get("diagram_fences", ["mermaid"]))
    ctx = params.get("diagram_context_lines", 6)
    for m in _FENCE.finditer(md):
        if (m.group(1) or "").lower() not in langs:
            continue
        window = md[:m.start()].splitlines()[-ctx:]
        heading = None
        for line in reversed(window):
            s = line.strip()
            if re.match(r"^#{1,6}\s+(.+)", s):
                heading = re.sub(r"^#+\s+", "", s)
                break
            if re.match(r"^\*{0,2}(Рис\.|Схема|Диаграмма|Figure)", s):
                heading = s.strip("* ")
                break
        if not heading:
            out.append(_i("diagram_no_context", "hard", f"Диаграмма ({m.group(1)}) без ближайшего заголовка/подписи в {ctx} строках"))
            continue
        d_tok = set(re.findall(r"[А-Яа-яA-Za-z]{4,}", m.group(2).lower()))
        h_tok = set(re.findall(r"[А-Яа-яA-Za-z]{4,}", heading.lower()))
        if d_tok and h_tok and not (d_tok & h_tok):
            out.append(_i("diagram_topic_mismatch", "soft", f"Диаграмма не пересекается по словам с разделом «{heading[:40]}» — проверьте соответствие"))
    return out
