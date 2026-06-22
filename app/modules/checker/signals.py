"""Shared deterministic checker signals for structural and didactic axes."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

FENCE_RE = re.compile(r"```([A-Za-z0-9_-]*)\s*\n(.*?)```", re.S)
TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9_/-]*")
SENTENCE_RE = re.compile(r"(?<=[.!?。！？])\s+|\n{2,}")
HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$")

STOPWORDS_RU = {
    "без",
    "более",
    "будет",
    "были",
    "быть",
    "вам",
    "вас",
    "все",
    "для",
    "его",
    "если",
    "есть",
    "еще",
    "или",
    "как",
    "над",
    "она",
    "они",
    "оно",
    "при",
    "так",
    "это",
    "этот",
    "эта",
    "эти",
    "что",
    "чтобы",
}

STOPWORDS_EN = {
    "about",
    "after",
    "and",
    "are",
    "for",
    "from",
    "have",
    "into",
    "that",
    "the",
    "this",
    "with",
    "your",
}

DIRECTIVE_RE = re.compile(r"\b(сделай|нажми|введите|скопируй|выполни\s+шаг|do\s+this|click|copy)\b", re.I)
EXAMPLE_RE = re.compile(r"(\*\*Пример\b|\bПример\s+\d+|\bExample\s+\d+)", re.I)


class SimilaritySignal(BaseModel):
    """A normalized similarity value with method metadata."""

    model_config = ConfigDict(extra="forbid")

    score: float
    method: str
    left_tokens: int = 0
    right_tokens: int = 0


class NearDuplicateSignal(BaseModel):
    """A pair of sentences or paragraphs that look almost the same."""

    model_config = ConfigDict(extra="forbid")

    left: str
    right: str
    score: float


class TableSignal(BaseModel):
    """A structural signal for a markdown table, not a RuleIssue."""

    model_config = ConfigDict(extra="forbid")

    line: int
    code: str
    expected: int
    actual: int | None = None
    preview: str = ""


class DiagramSignal(BaseModel):
    """A topicality signal for a fenced diagram and nearby heading/caption."""

    model_config = ConfigDict(extra="forbid")

    line: int
    language: str
    heading: str | None = None
    score: float = 0.0
    has_context: bool = False


class DocumentShapeSignal(BaseModel):
    """Lightweight document-shape features consumed as context only."""

    model_config = ConfigDict(extra="forbid")

    has_h1: bool = False
    annotation_chars: int = 0
    toc_lines: int = 0
    chapter_count: int = 0
    h2_count: int = 0


class CheckerSignals(BaseModel):
    """Unified signal payload shared by structural and didactic checker axes."""

    model_config = ConfigDict(extra="forbid")

    markdown_chars: int = 0
    token_count: int = 0
    repetition_ratio: float = 0.0
    near_dup: int = 0
    near_dup_examples: list[tuple[str, str]] = Field(default_factory=list)
    near_duplicates: list[NearDuplicateSignal] = Field(default_factory=list)
    broken_tables: int = 0
    table_issues: list[TableSignal] = Field(default_factory=list)
    diagram_match_avg: float = 1.0
    diagram_signals: list[DiagramSignal] = Field(default_factory=list)
    example_count: int = 0
    directive_hits: int = 0
    shape: DocumentShapeSignal = Field(default_factory=DocumentShapeSignal)


EmbeddingFunction = Callable[[Sequence[str]], Sequence[Sequence[float]]]


def collect_signals(markdown: Any, metadata: Mapping[str, Any] | None = None) -> CheckerSignals:
    """Collect deterministic checker signals from markdown or a GeneratedDoc-like object."""

    text = _coerce_markdown(markdown)
    duplicate_signals = near_duplicate_pairs(text)
    table_issues = table_signals(text)
    diagrams = diagram_signals(text)
    diagram_score = round(sum(item.score for item in diagrams) / len(diagrams), 3) if diagrams else 1.0
    return CheckerSignals(
        markdown_chars=len(text),
        token_count=len(tokens(text)),
        repetition_ratio=round(repetition_ratio(text), 3),
        near_dup=len(duplicate_signals),
        near_dup_examples=[(item.left, item.right) for item in duplicate_signals[:2]],
        near_duplicates=duplicate_signals,
        broken_tables=len(table_issues),
        table_issues=table_issues,
        diagram_match_avg=diagram_score,
        diagram_signals=diagrams,
        example_count=_example_count(text, metadata),
        directive_hits=len(DIRECTIVE_RE.findall(_mask_code(text))),
        shape=document_shape(text),
    )


def extract_signals(markdown: Any, metadata: Mapping[str, Any] | None = None) -> CheckerSignals:
    """Alias used by checker wiring."""

    return collect_signals(markdown, metadata)


def analyze(markdown: Any, metadata: Mapping[str, Any] | None = None) -> CheckerSignals:
    """Alias used by checker wiring."""

    return collect_signals(markdown, metadata)


def scan(markdown: Any, metadata: Mapping[str, Any] | None = None) -> CheckerSignals:
    """Alias used by checker wiring."""

    return collect_signals(markdown, metadata)


def tokens(text: str, *, drop_stopwords: bool = True) -> list[str]:
    """Return normalized lexical tokens for deterministic similarity features."""

    normalized = text.replace("ё", "е").lower()
    found = [item.strip("_-/") for item in TOKEN_RE.findall(normalized)]
    if not drop_stopwords:
        return [item for item in found if item]
    stopwords = STOPWORDS_RU | STOPWORDS_EN
    return [item for item in found if len(item) > 2 and item not in stopwords]


def bag_of_words(items: Iterable[str]) -> dict[str, int]:
    """Build a sparse token-count vector."""

    return dict(Counter(item for item in items if item))


def cosine(left: Mapping[str, int | float], right: Mapping[str, int | float]) -> float:
    """Cosine similarity for sparse vectors."""

    if not left or not right:
        return 0.0
    dot = sum(float(left[key]) * float(right.get(key, 0.0)) for key in left)
    left_norm = math.sqrt(sum(float(value) ** 2 for value in left.values()))
    right_norm = math.sqrt(sum(float(value) ** 2 for value in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    return max(0.0, min(1.0, dot / (left_norm * right_norm)))


def text_similarity(
    left: str,
    right: str,
    *,
    embedding_function: EmbeddingFunction | None = None,
) -> SimilaritySignal:
    """Compare two texts, using embeddings when injected and bag-of-words otherwise."""

    left_tokens = tokens(left)
    right_tokens = tokens(right)
    if embedding_function is not None and left.strip() and right.strip():
        try:
            vectors = list(embedding_function([left, right]))
            if len(vectors) == 2:
                score = _cosine_dense(vectors[0], vectors[1])
                return SimilaritySignal(score=round(score, 4), method="embedding", left_tokens=len(left_tokens), right_tokens=len(right_tokens))
        except Exception:
            pass
    score = cosine(bag_of_words(left_tokens), bag_of_words(right_tokens))
    return SimilaritySignal(score=round(score, 4), method="bag_of_words", left_tokens=len(left_tokens), right_tokens=len(right_tokens))


def moss_similarity(left: str, right: str, *, n: int = 5) -> SimilaritySignal:
    """Approximate MOSS-style overlap with token shingles."""

    left_shingles = _shingles(tokens(left, drop_stopwords=False), n)
    right_shingles = _shingles(tokens(right, drop_stopwords=False), n)
    score = _jaccard(left_shingles, right_shingles)
    return SimilaritySignal(score=round(score, 4), method=f"shingle_jaccard_{n}", left_tokens=len(left_shingles), right_tokens=len(right_shingles))


def pairwise_similarities(reference: str, candidates: Sequence[str]) -> list[SimilaritySignal]:
    """Compare one reference text with several candidates."""

    return [text_similarity(reference, candidate) for candidate in candidates]


def sequential_similarities(texts: Sequence[str]) -> list[SimilaritySignal]:
    """Compare adjacent items, useful for detecting repetitive sequences."""

    return [text_similarity(left, right) for left, right in zip(texts, texts[1:], strict=False)]


def split_sentences(text: str, *, min_chars: int = 25) -> list[str]:
    """Split prose into candidate sentences while ignoring fenced code."""

    masked = re.sub(r"<[^>]+>", " ", _mask_code(text))
    return [item.strip() for item in SENTENCE_RE.split(masked) if len(item.strip()) >= min_chars]


def repetition_ratio(text: str, *, n: int = 8) -> float:
    """Return the share of repeated token n-grams in the document."""

    items = tokens(_mask_code(text), drop_stopwords=False)
    if len(items) < n:
        return 0.0
    grams = [" ".join(items[index : index + n]) for index in range(len(items) - n + 1)]
    counts = Counter(grams)
    return sum(value for value in counts.values() if value > 1) / len(grams)


def near_duplicate_pairs(text: str, *, threshold: float = 0.7, cap: int = 40) -> list[NearDuplicateSignal]:
    """Find near-duplicate sentence pairs with token Jaccard similarity."""

    sentences = split_sentences(text)
    bags = [set(tokens(sentence, drop_stopwords=False)) for sentence in sentences]
    pairs: list[NearDuplicateSignal] = []
    for left in range(len(bags)):
        for right in range(left + 1, len(bags)):
            score = _jaccard(bags[left], bags[right])
            if score >= threshold:
                pairs.append(
                    NearDuplicateSignal(
                        left=_preview(sentences[left]),
                        right=_preview(sentences[right]),
                        score=round(score, 3),
                    )
                )
                if len(pairs) >= cap:
                    return pairs
    return pairs


def table_signals(markdown: str) -> list[TableSignal]:
    """Detect malformed markdown tables without turning them into rule issues."""

    lines = _mask_code(markdown).splitlines()
    signals: list[TableSignal] = []
    index = 0
    while index < len(lines) - 1:
        if "|" not in lines[index] or not _looks_like_separator(lines[index + 1]):
            index += 1
            continue
        expected = _cell_count(lines[index])
        separator_count = _cell_count(lines[index + 1])
        if separator_count != expected:
            signals.append(_table_signal(index + 2, "table_separator", expected, separator_count, lines[index + 1]))
        row_index = index + 2
        rows = 0
        while row_index < len(lines) and "|" in lines[row_index] and lines[row_index].strip():
            actual = _cell_count(lines[row_index])
            if actual != expected:
                signals.append(_table_signal(row_index + 1, "table_columns", expected, actual, lines[row_index]))
            rows += 1
            row_index += 1
        if rows == 0:
            signals.append(_table_signal(index + 1, "table_empty", expected, 0, lines[index]))
        index = max(row_index, index + 1)
    return signals[:8]


def diagram_signals(
    markdown: str,
    *,
    languages: set[str] | None = None,
    context_lines: int = 6,
) -> list[DiagramSignal]:
    """Measure topical overlap between fenced diagrams and nearby headings/captions."""

    allowed = {item.lower() for item in (languages or {"mermaid", "plantuml", "dot", "graphviz"})}
    lines_before = _line_starts(markdown)
    signals: list[DiagramSignal] = []
    for match in FENCE_RE.finditer(markdown):
        language = (match.group(1) or "").lower()
        if language not in allowed:
            continue
        heading = _nearest_heading(markdown[: match.start()], context_lines)
        score = _topic_overlap(match.group(2), heading or "")
        signals.append(
            DiagramSignal(
                line=_line_number(lines_before, match.start()),
                language=language,
                heading=heading,
                score=round(score, 3),
                has_context=bool(heading),
            )
        )
    return signals


def document_shape(markdown: str) -> DocumentShapeSignal:
    """Extract shape features from H1, annotation, TOC and H2 chapters."""

    h1 = re.search(r"^#\s+.+$", markdown, re.M)
    headings = list(re.finditer(r"^##\s+(.+)$", markdown, re.M))
    annotation = ""
    if h1:
        annotation = markdown[h1.end() : headings[0].start() if headings else len(markdown)].strip()
    return DocumentShapeSignal(
        has_h1=bool(h1),
        annotation_chars=len(annotation),
        toc_lines=_toc_lines(markdown),
        chapter_count=sum(1 for item in headings if _looks_like_chapter(item.group(1))),
        h2_count=len(headings),
    )


def _coerce_markdown(markdown: Any) -> str:
    if isinstance(markdown, str):
        return markdown
    return str(getattr(markdown, "markdown", "") or "")


def _mask_code(markdown: str) -> str:
    return FENCE_RE.sub(lambda match: "\n" + "\n".join("@@CODE@@" for _ in match.group(0).splitlines()) + "\n", markdown)


def _cosine_dense(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(float(a) * float(b) for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(float(item) ** 2 for item in left))
    right_norm = math.sqrt(sum(float(item) ** 2 for item in right))
    return 0.0 if not left_norm or not right_norm else max(0.0, min(1.0, dot / (left_norm * right_norm)))


def _shingles(items: Sequence[str], n: int) -> set[tuple[str, ...]]:
    if not items:
        return set()
    width = max(1, min(n, len(items)))
    return {tuple(items[index : index + width]) for index in range(len(items) - width + 1)}


def _jaccard(left: set[Any], right: set[Any]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _cell_count(line: str) -> int:
    return len([cell for cell in line.strip().strip("|").split("|")])


def _looks_like_separator(line: str) -> bool:
    if "|" not in line:
        return False
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    return bool(cells) and all(re.fullmatch(r":?-{2,}:?", cell or "") for cell in cells)


def _table_signal(line: int, code: str, expected: int, actual: int | None, preview: str) -> TableSignal:
    return TableSignal(line=line, code=code, expected=expected, actual=actual, preview=_preview(preview, limit=96))


def _nearest_heading(prefix: str, context_lines: int) -> str | None:
    for line in reversed(prefix.splitlines()[-context_lines:]):
        stripped = line.strip()
        heading = HEADING_RE.match(stripped)
        if heading:
            return heading.group(1).strip()
        if re.match(r"^\*{0,2}(?:Рис\.|Схема|Диаграмма|Figure)", stripped, re.I):
            return stripped.strip("* ")
    return None


def _topic_overlap(diagram_body: str, heading: str) -> float:
    diagram_terms = set(tokens(diagram_body))
    heading_terms = set(tokens(heading))
    if not heading_terms:
        return 0.0
    if not diagram_terms:
        return 0.0
    return _jaccard(diagram_terms, heading_terms)


def _line_starts(text: str) -> list[int]:
    starts = [0]
    for match in re.finditer(r"\n", text):
        starts.append(match.end())
    return starts


def _line_number(starts: Sequence[int], offset: int) -> int:
    line = 1
    for start in starts:
        if start > offset:
            break
        line += 1
    return max(1, line - 1)


def _toc_lines(markdown: str) -> int:
    match = re.search(r"^##\s+(?:Содержание|Оглавление)\s*$", markdown, re.M | re.I)
    if not match:
        return 0
    block = markdown[match.end() :].split("\n## ", 1)[0]
    return len([line for line in block.splitlines() if line.strip()])


def _looks_like_chapter(title: str) -> bool:
    clean = title.lower().replace("ё", "е")
    return bool(re.search(r"\b(?:глава\s*)?[1-9](?:[\s.:\-—]|$)", clean)) or any(
        alias in clean for alias in ("введение", "обзор", "теория", "практика", "задани")
    )


def _example_count(markdown: str, metadata: Mapping[str, Any] | None) -> int:
    metadata_examples = 0
    for key in ("examples", "theory_parts", "practice_tasks"):
        value = (metadata or {}).get(key)
        if isinstance(value, Sequence) and not isinstance(value, str):
            metadata_examples += len(value)
    return max(metadata_examples, len(EXAMPLE_RE.findall(_mask_code(markdown))))


def _preview(text: str, *, limit: int = 80) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    return compact if len(compact) <= limit else compact[: limit - 1].rstrip() + "…"
