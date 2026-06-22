"""Translator service: Markdown/document translation and subtitle artifacts."""

from __future__ import annotations

import json
import re
import uuid
import zipfile
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from typing import Any, Callable
from xml.etree import ElementTree

from pydantic import BaseModel, ConfigDict, Field

from app.core.llm import StructuredPrompt, complete_typed, load_prompt
from app.core.llm.client import create_llm_client


SUPPORTED_LANGUAGES = {"ru", "en", "kg", "uz", "tg"}
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_H2_SPLIT_RE = re.compile(r"(?=^##\s+)", re.MULTILINE)
_CODE_BLOCK_RE = re.compile(r"```(?P<header>[^\n]*)\n(?P<body>.*?)```", re.DOTALL | re.MULTILINE)
_BLOCK_RE = re.compile(r"\[\[\[BLOCK_(\d+)]]]")
_CYRILLIC_RE = re.compile(r"[а-яА-ЯёЁ]")
_CYRILLIC_WORD_RE = re.compile(r"[А-Яа-яЁёҒғӢӣҚқӮӯҲҳҶҷҢңҮүӨөІіЄєЇїЎў]{2,}")
_LATIN_WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9_+/#.-]{2,}\b")
_LANG_FINGERPRINTS = {"tg": set("ғӣқӯҳҷҶҲҚӮҒӢ"), "kg": set("ңүөҮӨҢ")}
_SCRIPT_LATIN_ALLOWLIST = {
    "api",
    "backend",
    "cli",
    "css",
    "devops",
    "docker",
    "git",
    "github",
    "gitlab",
    "html",
    "http",
    "https",
    "json",
    "markdown",
    "openapi",
    "pdf",
    "postgresql",
    "pytest",
    "readme",
    "rest",
    "sql",
    "url",
    "vtt",
    "yaml",
}


@dataclass(frozen=True)
class TranslationLanguageProfile:
    code: str
    name: str
    prompt_label: str
    expected_script: str
    script_instruction: str


LANGUAGE_PROFILES = {
    "en": TranslationLanguageProfile(
        "en",
        "английский",
        "английский язык",
        "latin",
        "пиши переводимый текст английской латиницей; кириллица допустима только в коде, ссылках и именах",
    ),
    "kg": TranslationLanguageProfile(
        "kg",
        "киргизский",
        "кыргызский / киргизский язык",
        "cyrillic",
        "пиши переводимый текст кыргызской кириллицей; латиница допустима только для технических терминов",
    ),
    "uz": TranslationLanguageProfile(
        "uz",
        "узбекский",
        "узбекский язык",
        "latin",
        "пиши переводимый текст современной узбекской латиницей; кириллица допустима только в коде и ссылках",
    ),
    "tg": TranslationLanguageProfile(
        "tg",
        "таджикский",
        "таджикский язык",
        "cyrillic",
        "пиши переводимый текст современной таджикской кириллицей; латиница допустима только для технических терминов",
    ),
}


@dataclass(frozen=True)
class ProtectedBlock:
    id: int
    block_type: str
    content: str


@dataclass(frozen=True)
class TranslationArtifact:
    filename: str
    media_type: str
    content: bytes


@dataclass
class TranslationJob:
    request_id: str
    status: str
    phase: str | None = None
    target_language: str | None = None
    job_type: str = "document"
    original_markdown: str | None = None
    translated_markdown: str | None = None
    translated_subtitles: str | None = None
    original_transcript: str | None = None
    error: str | None = None
    progress: float | None = None
    error_code: str | None = None
    source_filename: str | None = None
    source_format: str | None = None
    result_links: dict[str, str] = field(default_factory=dict)
    artifacts: dict[str, TranslationArtifact] = field(default_factory=dict)

    def status_payload(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "status": self.status,
            "phase": self.phase,
            "original_markdown": self.original_markdown,
            "translated_markdown": self.translated_markdown,
            "target_language": self.target_language,
            "error": self.error,
            "job_type": self.job_type,
            "translated_subtitles": self.translated_subtitles,
            "original_transcript": self.original_transcript,
            "progress": self.progress,
            "error_code": self.error_code,
            "result_links": self.result_links or None,
            "source_filename": self.source_filename,
            "source_format": self.source_format,
        }


class SegmentTranslation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    text: str


class SegmentTranslationBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segments: list[SegmentTranslation] = Field(default_factory=list)


class _PlainHtmlTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())

    def text(self) -> str:
        return "\n".join(self.parts)


def get_translation_language_profile(language_code: str) -> TranslationLanguageProfile:
    normalized = (language_code or "").lower().strip()
    if normalized in LANGUAGE_PROFILES:
        return LANGUAGE_PROFILES[normalized]
    return TranslationLanguageProfile(
        normalized or "unknown",
        normalized or "целевой язык",
        normalized or "целевой язык",
        "unknown",
        "соблюдай стандартную письменность целевого языка",
    )


def protect_blocks(markdown: str) -> tuple[str, list[ProtectedBlock]]:
    blocks: list[ProtectedBlock] = []

    def replace(match: re.Match[str]) -> str:
        block_id = len(blocks)
        header = match.group("header") or ""
        block_type = "mermaid" if "mermaid" in header.lower() else "code"
        blocks.append(ProtectedBlock(block_id, block_type, match.group(0)))
        return f"\n<!-- PROTECTED_BLOCK id={block_id} type={block_type} -->\n[[[BLOCK_{block_id}]]]\n"

    return _CODE_BLOCK_RE.sub(replace, markdown or ""), blocks


def restore_blocks(markdown: str, blocks: list[ProtectedBlock]) -> str:
    by_id = {block.id: block.content for block in blocks}

    def replace(match: re.Match[str]) -> str:
        return by_id.get(int(match.group(1)), "")

    restored = _BLOCK_RE.sub(replace, markdown or "")
    restored = re.sub(r"<!--\s*PROTECTED_BLOCK\s+id=\d+\s+type=\w+\s*-->\s*\n?", "", restored)
    return re.sub(r"\n{3,}", "\n\n", restored).strip()


def extract_document_text(filename: str, content: bytes) -> tuple[str, str]:
    suffix = Path(filename or "document.txt").suffix.lower()
    if suffix in {"", ".txt", ".md", ".markdown"}:
        return _decode_text(content), suffix or ".txt"
    if suffix in {".html", ".htm"}:
        parser = _PlainHtmlTextExtractor()
        parser.feed(_decode_text(content))
        return parser.text(), suffix
    if suffix == ".docx":
        return _extract_docx_text(content), suffix
    if suffix == ".pdf":
        return _decode_text(content), suffix
    raise ValueError(f"Неподдерживаемый формат документа: {suffix}")


def parse_transcript(content: bytes, *, transcript_text: str | None = None) -> list[dict[str, Any]]:
    text = transcript_text.strip() if transcript_text else _decode_text(content).strip()
    if not text:
        raise ValueError("Для video-порта нужен transcript_text или файл субтитров/транскрипта")
    if text.startswith("[") or text.startswith("{"):
        payload = json.loads(text)
        items = payload.get("segments", payload) if isinstance(payload, dict) else payload
        return [_segment(item, idx) for idx, item in enumerate(items, 1) if str(item.get("text", "")).strip()]
    if "-->" in text:
        return _parse_timed_subtitles(text)
    return [{"id": idx, "start": (idx - 1) * 4.0, "end": idx * 4.0, "text": line.strip()} for idx, line in enumerate(text.splitlines(), 1) if line.strip()]


def build_srt(segments: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for index, segment in enumerate(segments, 1):
        text = str(segment.get("text") or "").strip()
        if not text:
            continue
        lines.extend(
            [
                str(index),
                f"{_format_ts(segment.get('start', 0), comma=True)} --> {_format_ts(segment.get('end', 0), comma=True)}",
                text.replace("\n", " "),
                "",
            ]
        )
    return "\n".join(lines).strip()


def build_vtt(segments: list[dict[str, Any]]) -> str:
    lines = ["WEBVTT", ""]
    for segment in segments:
        text = str(segment.get("text") or "").strip()
        if text:
            lines.extend(
                [
                    f"{_format_ts(segment.get('start', 0))} --> {_format_ts(segment.get('end', 0))}",
                    text.replace("\n", " "),
                    "",
                ]
            )
    return "\n".join(lines).strip()


def build_ass(segments: list[dict[str, Any]], style_preset: str = "boxed") -> str:
    style = "1,2,1,2,10,10,30,1" if style_preset == "outline" else "3,2,1,2,10,10,30,1"
    header = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,{style}\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    body = [
        f"Dialogue: 0,{_format_ass_ts(seg.get('start', 0))},{_format_ass_ts(seg.get('end', 0))},Default,,0,0,0,,{str(seg.get('text', '')).replace('{', '{{').replace('}', '}}')}"
        for seg in segments
        if str(seg.get("text") or "").strip()
    ]
    return header + "\n".join(body)


class TranslatorService:
    def __init__(self, client_factory: Callable[..., Any] = create_llm_client) -> None:
        self.client_factory = client_factory
        self.jobs: dict[str, TranslationJob] = {}

    def start_readme(
        self,
        markdown: str,
        target_language: str,
        *,
        translation_mode: str = "literal",
        llm_provider: str | None = None,
    ) -> TranslationJob:
        job = self._new_job("document", target_language)
        job.original_markdown = markdown
        self._run_document_job(job, markdown, target_language, translation_mode, llm_provider)
        return job

    def start_document(
        self,
        filename: str,
        content: bytes,
        target_language: str,
        *,
        translation_mode: str = "literal",
        llm_provider: str | None = None,
    ) -> TranslationJob:
        text, suffix = extract_document_text(filename, content)
        job = self._new_job("document", target_language)
        job.original_markdown = text
        job.source_filename = filename
        job.source_format = suffix.lstrip(".")
        self._run_document_job(job, text, target_language, translation_mode, llm_provider)
        return job

    def start_video(
        self,
        filename: str,
        content: bytes,
        target_language: str,
        *,
        transcript_text: str | None = None,
        output_mode: str = "subtitles_only",
        subtitle_style: str = "boxed",
        llm_provider: str | None = None,
    ) -> TranslationJob:
        self._ensure_language(target_language)
        job = self._new_job("video", target_language)
        job.source_filename = filename
        job.source_format = Path(filename or "transcript.txt").suffix.lower().lstrip(".") or "txt"
        try:
            job.phase = "parse_transcript"
            segments = parse_transcript(content, transcript_text=transcript_text)
            job.original_transcript = json.dumps(segments, ensure_ascii=False)
            translated = self._translate_segments(segments, target_language, self._client(llm_provider))
            job.phase = "build_subtitles"
            self._attach_subtitle_artifacts(job, translated, subtitle_style)
            if output_mode in {"burned_video", "both"}:
                job.error_code = "video_burn_deferred"
            job.status = "completed"
            job.progress = 100.0
            job.phase = "completed"
        except Exception as exc:  # noqa: BLE001 - API exposes failure state instead of crashing worker
            job.status = "failed"
            job.error = str(exc)
            job.error_code = "video_translation_failed"
        return job

    def get_job(self, request_id: str) -> TranslationJob | None:
        return self.jobs.get(request_id)

    def get_artifact(self, request_id: str, artifact_type: str) -> TranslationArtifact | None:
        job = self.get_job(request_id)
        return None if job is None else job.artifacts.get(artifact_type)

    def _run_document_job(
        self,
        job: TranslationJob,
        markdown: str,
        target_language: str,
        translation_mode: str,
        llm_provider: str | None,
    ) -> None:
        self._ensure_language(target_language)
        if not markdown.strip():
            raise ValueError("Исходный документ пуст")
        try:
            job.phase = "translate"
            job.translated_markdown = self.translate_markdown(
                markdown,
                target_language,
                translation_mode=translation_mode,
                client=self._client(llm_provider),
                progress_callback=lambda phase: setattr(job, "phase", phase),
            )
            job.status = "completed"
            job.progress = 100.0
            job.phase = "completed"
        except Exception as exc:  # noqa: BLE001 - matches legacy async job semantics
            job.status = "failed"
            job.error = str(exc)
            job.error_code = "document_translation_failed"

    def translate_markdown(
        self,
        markdown: str,
        target_language: str,
        *,
        translation_mode: str = "literal",
        client: Any | None = None,
        progress_callback: Callable[[str], None] | None = None,
        strict: bool = False,
    ) -> str:
        if target_language == "ru":
            return markdown
        self._ensure_language(target_language)
        profile = get_translation_language_profile(target_language)
        detected = detect_source_language(markdown)
        if detected == target_language:
            message = f"Документ уже на целевом языке ({profile.name})"
            if strict:
                raise ValueError(message)
            return markdown

        llm = client or self._client(None)
        protected, blocks = protect_blocks(markdown)
        system = load_prompt("translator", "system").render(
            target_language=profile.prompt_label,
            script_instruction=profile.script_instruction,
        )
        attempts = [(translation_mode, 10000), ("literal", 7000), ("literal", 5000)]
        last_translation = markdown
        last_issues: list[str] = []
        for mode, max_len in attempts:
            translated = self._translate_chunks(protected, profile, system, llm, max_len)
            translated = restore_blocks(translated, blocks)
            if mode == "combined":
                translated = self._combine_with_refine(translated, profile, llm)
            translated = cleanup_translation(translated, markdown)
            if progress_callback:
                progress_callback("validate")
            translated = self._repair_untranslated(markdown, translated, profile, system, llm, progress_callback)
            valid, issues = validate_translation(markdown, translated, target_language)
            last_translation, last_issues = translated, issues
            if valid:
                return translated
        if strict and last_issues:
            raise ValueError("; ".join(last_issues[:5]))
        return last_translation

    def _translate_chunks(
        self,
        protected: str,
        profile: TranslationLanguageProfile,
        system: str,
        client: Any,
        max_len: int,
    ) -> str:
        chunks = split_for_translation(protected, max_len)
        results = []
        for chunk in chunks:
            user = load_prompt("translator", "translate_chunk").render(
                target_language=profile.prompt_label,
                script_instruction=profile.script_instruction,
                markdown=chunk,
            )
            results.append(cleanup_model_prefix(client.complete(system=system, user=user, temperature=0.2)))
        return "\n\n".join(results)

    def _repair_untranslated(
        self,
        original: str,
        translated: str,
        profile: TranslationLanguageProfile,
        system: str,
        client: Any,
        progress_callback: Callable[[str], None] | None,
    ) -> str:
        untranslated = validate_language_coverage(original, translated)
        if not untranslated:
            return translated
        if progress_callback:
            progress_callback("repair")
        original_sections = split_by_headings(original)
        translated_sections = split_by_headings(translated)
        for index, _heading, _ratio in untranslated[:4]:
            if index >= len(original_sections) or index >= len(translated_sections):
                continue
            source_heading, source_body = original_sections[index]
            original_section = f"{source_heading}\n\n{source_body}".strip() if source_heading else source_body
            user = load_prompt("translator", "repair_section").render(
                target_language=profile.prompt_label,
                script_instruction=profile.script_instruction,
                markdown=original_section,
            )
            repaired = cleanup_model_prefix(client.complete(system=system, user=user, temperature=0.2))
            old_heading, old_body = translated_sections[index]
            old_section = f"{old_heading}\n\n{old_body}".strip() if old_heading else old_body
            if repaired.strip():
                translated = translated.replace(old_section, repaired.strip(), 1)
        return cleanup_translation(translated, original)

    def _combine_with_refine(self, translated: str, profile: TranslationLanguageProfile, client: Any) -> str:
        refine_user = load_prompt("translator", "refine").render(
            target_language=profile.prompt_label,
            script_instruction=profile.script_instruction,
            markdown=translated,
        )
        refined = cleanup_model_prefix(client.complete(system=load_prompt("translator", "system").render(
            target_language=profile.prompt_label,
            script_instruction=profile.script_instruction,
        ), user=refine_user, temperature=0.3))
        combine_user = load_prompt("translator", "combine").render(
            target_language=profile.prompt_label,
            script_instruction=profile.script_instruction,
            literal_markdown=translated,
            refined_markdown=refined,
        )
        return cleanup_model_prefix(client.complete(system=load_prompt("translator", "system").render(
            target_language=profile.prompt_label,
            script_instruction=profile.script_instruction,
        ), user=combine_user, temperature=0.2))

    def _translate_segments(self, segments: list[dict[str, Any]], target_language: str, client: Any) -> list[dict[str, Any]]:
        if target_language == "ru":
            return segments
        profile = get_translation_language_profile(target_language)
        payload = [
            {
                "id": int(segment.get("id", index)),
                "text_ru": str(segment.get("text", "")),
                "context_before": str(segments[index - 2].get("text", "")) if index > 1 else "",
                "context_after": str(segments[index].get("text", "")) if index < len(segments) else "",
            }
            for index, segment in enumerate(segments, 1)
        ]
        prompt = load_prompt("translator", "video_segments").render(
            target_language=profile.prompt_label,
            script_instruction=profile.script_instruction,
            segments_json=json.dumps(payload, ensure_ascii=False),
        )
        try:
            batch = complete_typed(
                StructuredPrompt(system="Return only JSON matching the requested schema.", user=prompt),
                SegmentTranslationBatch,
                client=client,
                retries=1,
                temperature=0,
            )
            translated_by_id = {item.id: item.text for item in batch.segments}
        except Exception:
            translated_by_id = {}
        return [{**segment, "text": translated_by_id.get(int(segment.get("id", index)), str(segment.get("text", "")))} for index, segment in enumerate(segments, 1)]

    def _attach_subtitle_artifacts(self, job: TranslationJob, segments: list[dict[str, Any]], style: str) -> None:
        stem = _safe_stem(job.source_filename or "subtitles")
        srt = build_srt(segments)
        vtt = build_vtt(segments)
        ass = build_ass(segments, style)
        transcript = json.dumps(segments, ensure_ascii=False, indent=2)
        job.translated_subtitles = srt
        for key, content, media_type, suffix in (
            ("srt", srt, "text/plain; charset=utf-8", "srt"),
            ("vtt", vtt, "text/vtt; charset=utf-8", "vtt"),
            ("ass", ass, "text/x-ssa; charset=utf-8", "ass"),
            ("transcript", transcript, "application/json; charset=utf-8", "json"),
        ):
            filename = f"{stem}_{job.target_language}.{suffix}"
            job.artifacts[key] = TranslationArtifact(filename, media_type, content.encode("utf-8"))
            job.result_links[key] = filename

    def _new_job(self, job_type: str, target_language: str) -> TranslationJob:
        job = TranslationJob(
            request_id=str(uuid.uuid4()),
            status="in_progress",
            phase="queued",
            target_language=target_language,
            job_type=job_type,
            progress=0.0,
        )
        self.jobs[job.request_id] = job
        return job

    def _client(self, provider: str | None) -> Any:
        return self.client_factory(provider=provider)

    @staticmethod
    def _ensure_language(target_language: str) -> None:
        if target_language not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Неподдерживаемый язык перевода: {target_language!r}")


def split_for_translation(markdown: str, max_length: int) -> list[str]:
    text = (markdown or "").strip()
    if not text:
        return []
    if len(text) <= max_length:
        return [text]
    chunks: list[str] = []
    current = ""
    for section in [part for part in _H2_SPLIT_RE.split(text) if part.strip()]:
        if len(section) > max_length:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(_split_long_section(section, max_length))
            continue
        candidate = f"{current}\n\n{section}".strip() if current else section
        if len(candidate) > max_length:
            chunks.append(current.strip())
            current = section
        else:
            current = candidate
    if current:
        chunks.append(current.strip())
    return chunks


def validate_translation(original: str, translated: str, target_language: str) -> tuple[bool, list[str]]:
    issues = validate_structure(original, translated)
    issues.extend(f"Секция [{idx}] {heading[:50]!r} не переведена (similarity={ratio:.2f})" for idx, heading, ratio in validate_language_coverage(original, translated))
    issues.extend(validate_script_coverage(translated, target_language))
    return not issues, issues


def validate_structure(original: str, translated: str) -> list[str]:
    issues: list[str] = []
    original_headings = [(len(m.group(1)), m.group(2).strip()) for m in _HEADING_RE.finditer(original)]
    translated_headings = [(len(m.group(1)), m.group(2).strip()) for m in _HEADING_RE.finditer(translated)]
    if len(original_headings) != len(translated_headings):
        issues.append(f"Количество заголовков не совпадает: оригинал {len(original_headings)}, перевод {len(translated_headings)}")
    for index, ((orig_level, _), (trans_level, _)) in enumerate(zip(original_headings, translated_headings), 1):
        if orig_level != trans_level:
            issues.append(f"Несовпадение уровня заголовка #{index}: оригинал H{orig_level}, перевод H{trans_level}")
    for pattern, label in ((r"```mermaid", "mermaid диаграмм"), (r"\$\$.*?\$\$", "блочных формул")):
        original_count = len(re.findall(pattern, original, re.IGNORECASE | re.DOTALL))
        translated_count = len(re.findall(pattern, translated, re.IGNORECASE | re.DOTALL))
        if original_count != translated_count:
            issues.append(f"Количество {label} не совпадает: оригинал {original_count}, перевод {translated_count}")
    if _count_tables(original) != _count_tables(translated):
        issues.append(f"Количество таблиц не совпадает: оригинал {_count_tables(original)}, перевод {_count_tables(translated)}")
    return issues


def validate_language_coverage(original: str, translated: str) -> list[tuple[int, str, float]]:
    untranslated: list[tuple[int, str, float]] = []
    for index, ((orig_heading, orig_body), (trans_heading, trans_body)) in enumerate(zip(split_by_headings(original), split_by_headings(translated))):
        source_text = _extract_text_content(orig_body)
        translated_text = _extract_text_content(trans_body)
        if not _has_translation_signal(source_text):
            continue
        ratio = SequenceMatcher(None, source_text, translated_text).ratio()
        if ratio > 0.70:
            untranslated.append((index, trans_heading or orig_heading or f"(section {index})", ratio))
    return untranslated


def validate_script_coverage(translated: str, target_language: str) -> list[str]:
    profile = get_translation_language_profile(target_language)
    if profile.expected_script not in {"latin", "cyrillic"}:
        return []
    text = _strip_markdown_for_script_check(translated)
    cyrillic = _CYRILLIC_WORD_RE.findall(text)
    latin = [word for word in _LATIN_WORD_RE.findall(text) if not _is_allowed_latin_token(word)]
    if profile.expected_script == "latin" and len(cyrillic) >= 6:
        return [f"Нарушена письменность для {profile.name}: найден кириллический текст ({', '.join(cyrillic[:6])})"]
    if profile.expected_script == "cyrillic" and len(latin) >= 8 and len(latin) > max(4, int(len(cyrillic) * 0.35)):
        return [f"Нарушена письменность для {profile.name}: найдено слишком много латиницы ({', '.join(latin[:6])})"]
    return []


def detect_source_language(markdown: str) -> str | None:
    text = _extract_text_content(markdown)
    total_alpha = sum(1 for char in text if char.isalpha())
    if total_alpha < 20:
        return None
    cyrillic_count = len(_CYRILLIC_RE.findall(text))
    if cyrillic_count / max(total_alpha, 1) < 0.3:
        return "en"
    for code, chars in _LANG_FINGERPRINTS.items():
        if sum(1 for char in text if char in chars) >= 5:
            return code
    return "ru" if cyrillic_count / max(total_alpha, 1) > 0.5 else None


def split_by_headings(markdown: str) -> list[tuple[str, str]]:
    positions = [(match.start(), match.group(0)) for match in _HEADING_RE.finditer(markdown or "")]
    if not positions:
        return [("", markdown or "")]
    parts: list[tuple[str, str]] = []
    if positions[0][0] > 0:
        parts.append(("", markdown[: positions[0][0]].strip()))
    for index, (position, heading) in enumerate(positions):
        end = positions[index + 1][0] if index + 1 < len(positions) else len(markdown)
        parts.append((heading, markdown[position + len(heading) : end].strip()))
    return parts


def cleanup_translation(translated: str, original: str) -> str:
    cleaned = cleanup_model_prefix(translated)
    for pattern in (r"^#\s+README\s*$", r"^#\s+Translation\s*$", r"^#\s+Translated\s+README\s*$"):
        if not re.search(pattern, original, re.MULTILINE | re.IGNORECASE):
            cleaned = re.sub(pattern, "", cleaned, flags=re.MULTILINE | re.IGNORECASE)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def cleanup_model_prefix(text: str) -> str:
    cleaned = (text or "").strip()
    for prefix in ("Вот перевод:\n\n", "Перевод:\n\n", "Итоговый перевод:\n\n", "Вот итоговый документ:\n\n"):
        if cleaned.startswith(prefix):
            return cleaned[len(prefix) :].strip()
    return cleaned


def _decode_text(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def _extract_docx_text(content: bytes) -> str:
    with zipfile.ZipFile(BytesIO(content)) as archive:
        xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []
    for paragraph in root.findall(".//w:p", ns):
        parts = [node.text or "" for node in paragraph.findall(".//w:t", ns)]
        if "".join(parts).strip():
            paragraphs.append("".join(parts))
    return "\n\n".join(paragraphs)


def _extract_text_content(markdown: str) -> str:
    text = re.sub(r"```.*?```", " ", markdown or "", flags=re.DOTALL)
    text = re.sub(r"!\[[^\]]*]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]+)]\([^)]*\)", r" \1 ", text)
    text = re.sub(r"`[^`]+`|<!--.*?-->|\[\[\[BLOCK_\d+]]]|\|[-: ]+\||[#*_|>~\-[\]()]", " ", text, flags=re.DOTALL)
    return re.sub(r"\s+", " ", text).strip()


def _has_translation_signal(text: str) -> bool:
    if len(text.strip()) < 20:
        return False
    alpha_count = sum(1 for char in text if char.isalpha())
    words = _CYRILLIC_WORD_RE.findall(text) + _LATIN_WORD_RE.findall(text)
    prose = [word for word in words if len(word) >= 3 and not _looks_technical(word)]
    return alpha_count >= 30 and len(prose) >= 4


def _strip_markdown_for_script_check(markdown: str) -> str:
    text = re.sub(r"```.*?```|`[^`]+`|https?://\S+|<!--.*?-->|\[\[\[BLOCK_\d+]]]", " ", markdown or "", flags=re.DOTALL)
    return re.sub(r"!\[[^\]]*]\([^)]*\)|\[[^\]]*]\([^)]*\)", " ", text)


def _looks_technical(word: str) -> bool:
    value = word.lower().strip("._-/#")
    return value in _SCRIPT_LATIN_ALLOWLIST or any(char.isdigit() for char in value) or any(char in value for char in "_/\\.%#+-")


def _is_allowed_latin_token(word: str) -> bool:
    value = word.lower().strip("._-/#")
    return value in _SCRIPT_LATIN_ALLOWLIST or bool(re.search(r"[/_.#0-9]", word)) or (word.isupper() and len(word) <= 8)


def _count_tables(markdown: str) -> int:
    lines = [line.strip() for line in (markdown or "").splitlines()]
    return sum(1 for index, line in enumerate(lines[:-1]) if line.startswith("|") and "|" in line[1:] and "---" in lines[index + 1])


def _split_long_section(section: str, max_length: int) -> list[str]:
    chunks: list[str] = []
    current = ""
    for paragraph in [item for item in re.split(r"\n\n+", section) if item.strip()]:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= max_length:
            current = candidate
        else:
            if current:
                chunks.append(current)
            chunks.extend(paragraph[i : i + max_length].strip() for i in range(0, len(paragraph), max_length))
            current = ""
    if current:
        chunks.append(current)
    return [chunk for chunk in chunks if chunk]


def _parse_timed_subtitles(text: str) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n").replace("WEBVTT", "").strip())
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        timing_index = next((idx for idx, line in enumerate(lines) if "-->" in line), None)
        if timing_index is None:
            continue
        start_s, end_s = [part.strip() for part in lines[timing_index].split("-->", 1)]
        body = " ".join(lines[timing_index + 1 :]).strip()
        if body:
            segments.append({"id": len(segments) + 1, "start": _parse_ts(start_s), "end": _parse_ts(end_s), "text": body})
    return segments


def _segment(item: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "id": int(item.get("id", index)),
        "start": float(item.get("start", (index - 1) * 4.0) or 0.0),
        "end": float(item.get("end", index * 4.0) or 0.0),
        "text": str(item.get("text", "")).strip(),
    }


def _format_ts(seconds: Any, *, comma: bool = False) -> str:
    value = float(seconds or 0)
    hours = int(value // 3600)
    minutes = int((value % 3600) // 60)
    secs = int(value % 60)
    millis = int((value % 1) * 1000)
    sep = "," if comma else "."
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{sep}{millis:03d}"


def _format_ass_ts(seconds: Any) -> str:
    value = float(seconds or 0)
    hours = int(value // 3600)
    minutes = int((value % 3600) // 60)
    secs = int(value % 60)
    centis = int((value % 1) * 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def _parse_ts(value: str) -> float:
    head = value.split()[0].replace(",", ".")
    hours, minutes, seconds = head.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _safe_stem(filename: str) -> str:
    stem = Path(filename).stem or "translation"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("._") or "translation"
