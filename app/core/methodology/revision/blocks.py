"""Protected markdown blocks used during scoped LLM edits."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ProtectedBlock:
    marker: str
    content: str
    block_type: str


class MarkdownBlockContract:
    """Protect fenced code and markdown display blocks before localized edits."""

    _FENCE_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)

    def protect(
        self,
        markdown: str,
        *,
        protect_code: bool = True,
        protect_mermaid: bool = True,
        protect_tables: bool = True,
    ) -> tuple[str, list[ProtectedBlock]]:
        text = markdown or ""
        blocks: list[ProtectedBlock] = []
        spans: list[tuple[int, int, str]] = []
        if protect_code or protect_mermaid:
            for match in self._FENCE_RE.finditer(text):
                header = match.group(0).splitlines()[0].lower()
                if "mermaid" in header and not protect_mermaid:
                    continue
                if "mermaid" not in header and not protect_code:
                    continue
                spans.append((match.start(), match.end(), "fence"))
        if protect_tables:
            spans.extend(_table_spans(text))
        protected = []
        cursor = 0
        for start, end, block_type in sorted(spans, key=lambda item: item[0]):
            if start < cursor:
                continue
            marker = f"[[[BLOCK_{len(blocks)}]]]"
            protected.append(text[cursor:start])
            protected.append(marker)
            blocks.append(ProtectedBlock(marker=marker, content=text[start:end], block_type=block_type))
            cursor = end
        protected.append(text[cursor:])
        return "".join(protected), blocks

    @staticmethod
    def restore(markdown: str, blocks: list[ProtectedBlock]) -> str:
        restored = markdown or ""
        for block in blocks:
            restored = restored.replace(block.marker, block.content)
        return restored

    @staticmethod
    def protection_instruction(blocks: list[ProtectedBlock], *, allow_display_block_edit: bool = False) -> str:
        if not blocks:
            return ""
        if allow_display_block_edit:
            return "Сохрани маркеры [[[BLOCK_N]]] без изменений; редактируй таблицы/диаграммы только если это прямо требуется."
        return "Сохрани маркеры [[[BLOCK_N]]] без изменений; защищённые таблицы, диаграммы и код редактировать нельзя."

    @staticmethod
    def validate(markdown: str) -> list[str]:
        issues: list[str] = []
        text = markdown or ""
        if re.search(r"\[\[\[BLOCK_\d+\]\]\]", text):
            issues.append("unresolved protected block placeholder")
        if len(re.findall(r"^```", text, flags=re.MULTILINE)) % 2:
            issues.append("unbalanced fenced code blocks")
        if re.search(r"^\s*(?:flowchart|graph)[ \t]+\w+[ \t]+[A-Za-z0-9_]+\[", text, flags=re.I | re.M):
            issues.append("possible flattened mermaid block")
        return issues


def _table_spans(text: str) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    lines = text.splitlines(keepends=True)
    offsets: list[int] = []
    cursor = 0
    for line in lines:
        offsets.append(cursor)
        cursor += len(line)
    index = 0
    while index + 1 < len(lines):
        if "|" not in lines[index] or not re.search(r"\|\s*:?-{3,}:?\s*\|", lines[index + 1]):
            index += 1
            continue
        start = offsets[index]
        end_index = index + 2
        while end_index < len(lines) and "|" in lines[end_index].strip():
            end_index += 1
        spans.append((start, offsets[end_index] if end_index < len(lines) else len(text), "table"))
        index = end_index
    return spans
