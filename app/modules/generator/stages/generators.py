"""G4c heavy generators: formula/table/diagram assets, datasets and code examples."""

from __future__ import annotations

import base64
import csv
import io
import json
import re
import zipfile
from typing import Any, Literal
from xml.sax.saxutils import escape

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.llm.prompt_loader import PromptNotFoundError, load_prompt
from app.core.llm.structured import StructuredPrompt, complete_typed
from app.core.models import ArtifactRef, CurriculumContext, GeneratedDoc
from app.modules.generator.stages.head import _coerce_context
from app.modules.generator.stages.practice import EvidenceSpec, PracticeTask, is_solution_like_material_ref

DatasetType = Literal["csv", "json", "txt", "md", "xlsx"]
DatasetEncoding = Literal["utf-8", "utf-8-sig", "base64"]

FILE_RE = re.compile(r"\b(?:materials/|data/)?([\w\-_]+\.(?:csv|json|txt|md|xlsx?))\b", re.I)
FENCE_RE = re.compile(r"```[a-zA-Z0-9_-]*\n([\s\S]*?)\n```", re.M)
MERMAID_STYLE_RE = re.compile(r"%%\{init[\s\S]*?\}%%|^\s*(?:classDef|class|style|linkStyle)\b.*$", re.I | re.M)
WORDS_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9_/-]*")
LATIN_ID_RE = re.compile(r"[^a-z0-9_]+")


class FormulaParameter(BaseModel):
    """One formula parameter explanation."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    description: str


class FormulaAsset(BaseModel):
    """Deterministic formula generated for a theory part."""

    model_config = ConfigDict(extra="forbid")

    part_index: int = Field(ge=1)
    label: str
    latex: str
    parameters: list[FormulaParameter] = Field(default_factory=list)
    description: str = ""


class TableAsset(BaseModel):
    """Deterministic markdown table generated for a theory part."""

    model_config = ConfigDict(extra="forbid")

    part_index: int = Field(ge=1)
    label: str
    md_table: str
    description: str = ""


class VisualAsset(BaseModel):
    """Deterministic Mermaid diagram generated for a theory/practice workflow."""

    model_config = ConfigDict(extra="forbid")

    part_index: int = Field(ge=1)
    label: str
    mermaid: str
    description: str = ""


class DatasetFile(BaseModel):
    """Generated raw material file for a practice task."""

    model_config = ConfigDict(extra="forbid")

    path: str
    filename: str
    file_type: DatasetType
    mime_type: str
    encoding: DatasetEncoding
    content_text: str | None = None
    content_base64: str | None = None
    size_bytes: int
    source_task_index: int | None = None
    evidence_spec: dict[str, Any] | None = None

    @field_validator("path")
    @classmethod
    def path_is_material(cls, value: str) -> str:
        path = value.replace("\\", "/")
        if not path.startswith(("materials/", "data/")):
            path = f"materials/{path.split('/')[-1]}"
        return path


class CodeExample(BaseModel):
    """Small validated code snippet inserted into theory."""

    model_config = ConfigDict(extra="forbid")

    part_index: int = Field(default=1, ge=1)
    label: str
    language: str
    code: str
    explanation: str = ""

    @field_validator("code")
    @classmethod
    def code_is_not_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("code example cannot be empty")
        return value

    @field_validator("explanation")
    @classmethod
    def explanation_is_compact(cls, value: str) -> str:
        return _limit_sentences(value, 3)


class GeneratorDraft(BaseModel):
    """Optional typed LLM supplement. Deterministic generators remain authoritative."""

    model_config = ConfigDict(extra="forbid")

    code_examples: list[CodeExample] = Field(default_factory=list)
    dataset_notes: dict[str, str] = Field(default_factory=dict)


class GeneratorAssetsResult(BaseModel):
    """Full G4c stage output."""

    model_config = ConfigDict(extra="forbid")

    formulas: list[FormulaAsset] = Field(default_factory=list)
    tables: list[TableAsset] = Field(default_factory=list)
    visuals: list[VisualAsset] = Field(default_factory=list)
    dataset_files: list[DatasetFile] = Field(default_factory=list)
    code_examples: list[CodeExample] = Field(default_factory=list)
    markdown: str
    warnings: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)


def run(ctx: dict[str, Any], augment: str = "") -> dict[str, Any]:
    """Engine adapter for ``EngineStage('generator.generators', run)``."""
    context = _coerce_context(ctx)
    markdown = str(ctx.get("markdown") or "")
    draft = _llm_draft(context, markdown, ctx, ctx.get("llm_client"), augment) if ctx.get("llm_client") else None
    result = generate_assets(context, markdown=markdown, engine_context=ctx, draft=draft)
    artifacts = _artifact_refs(result.dataset_files)
    return {
        "generated_assets": result.model_dump(mode="json"),
        "formula_assets": {
            "formulas": [item.model_dump(mode="json") for item in result.formulas],
            "tables": [item.model_dump(mode="json") for item in result.tables],
            "visuals": [item.model_dump(mode="json") for item in result.visuals],
        },
        "dataset_files": [item.model_dump(mode="json") for item in result.dataset_files],
        "code_examples": [item.model_dump(mode="json") for item in result.code_examples],
        "generator_asset_warnings": result.warnings,
        "generator_asset_issues": result.issues,
        "artifacts": [item.model_dump(mode="json") for item in artifacts],
        "markdown": result.markdown,
        "generated_doc": GeneratedDoc(
            markdown=result.markdown,
            artifacts=artifacts,
            metadata={
                "artifact_target": "readme_assets",
                "formula_count": len(result.formulas),
                "table_count": len(result.tables),
                "visual_count": len(result.visuals),
                "dataset_file_count": len(result.dataset_files),
                "code_example_count": len(result.code_examples),
            },
        ),
    }


def generate_assets(
    context: CurriculumContext,
    *,
    markdown: str = "",
    engine_context: dict[str, Any] | None = None,
    draft: GeneratorDraft | None = None,
) -> GeneratorAssetsResult:
    """Generate deterministic heavy assets and insert references into markdown."""
    state = dict(engine_context or {})
    base_markdown = markdown or f"# {context.current_project_title}\n\n## Глава 2. Теория\n\n## Глава 3. Практика"
    theory_parts = _coerce_theory_parts(state.get("theory_parts"), base_markdown)
    tasks = _coerce_tasks(state.get("practice_tasks"))
    evidence_specs = _coerce_evidence_specs(state)
    warnings: list[str] = []

    formulas, tables, visuals = _generate_learning_assets(context, theory_parts)
    dataset_files = _generate_dataset_files(context, tasks, evidence_specs, draft, warnings)
    code_examples = _generate_code_examples(context, theory_parts, draft)

    final_markdown = _insert_theory_assets(base_markdown, formulas, tables, visuals)
    final_markdown = _insert_code_examples(final_markdown, code_examples)
    final_markdown = _append_dataset_manifest(final_markdown, dataset_files)

    issues = []
    if tasks and not dataset_files and _mentions_file_inputs(tasks):
        issues.append("generators.dataset_files_empty")
    return GeneratorAssetsResult(
        formulas=formulas,
        tables=tables,
        visuals=visuals,
        dataset_files=dataset_files,
        code_examples=code_examples,
        markdown=_normalize_markdown(final_markdown),
        warnings=warnings,
        issues=issues,
    )


def _llm_draft(context: CurriculumContext, markdown: str, state: dict[str, Any], client: Any, augment: str) -> GeneratorDraft | None:
    try:
        template = load_prompt("generator", "generators")
    except PromptNotFoundError:
        return None
    payload = {
        "curriculum_context": context.model_dump(mode="json"),
        "theory_parts": state.get("theory_parts") or [],
        "practice_tasks": state.get("practice_tasks") or [],
        "evidence_specs": state.get("evidence_specs") or [],
        "markdown": markdown[:9000],
        "augment": augment,
    }
    prompt = template.render(context_json=json.dumps(payload, ensure_ascii=False, indent=2))
    try:
        return complete_typed(
            StructuredPrompt(
                system="Return only valid JSON for GeneratorDraft. Do not generate formulas.",
                user=prompt,
                kwargs={"temperature": 0.2, "max_tokens": 5000},
            ),
            GeneratorDraft,
            client=client,
            retries=1,
        )
    except Exception:
        return None


def _generate_learning_assets(
    context: CurriculumContext,
    theory_parts: list[dict[str, Any]],
) -> tuple[list[FormulaAsset], list[TableAsset], list[VisualAsset]]:
    if not theory_parts:
        return [], [], []
    first = theory_parts[0]
    part_index = int(first.get("index") or 1)
    topic_text = _topic_text(context, first)
    formulas = [_formula_for_context(context, part_index, topic_text)]
    tables = [_comparison_table(context, part_index)]
    visuals = [_workflow_visual(context, part_index)]
    return formulas, tables, visuals


def _formula_for_context(context: CurriculumContext, part_index: int, topic_text: str) -> FormulaAsset:
    text = topic_text.lower()
    if any(token in text for token in ("api", "rest", "тест", "quality", "качест", "провер")):
        return FormulaAsset(
            part_index=part_index,
            label="Доля успешно проверенных сценариев",
            latex=r"Q_{pass} = \frac{N_{pass}}{N_{total}} \times 100\%",
            parameters=[
                FormulaParameter(symbol="Q_{pass}", description="процент сценариев, прошедших проверку"),
                FormulaParameter(symbol="N_{pass}", description="количество успешных проверок"),
                FormulaParameter(symbol="N_{total}", description="общее количество проверяемых сценариев"),
            ],
            description="Используй формулу, чтобы отделить ощущение готовности от измеримого качества артефакта.",
        )
    if any(token in text for token in ("риск", "инцид", "безопас", "монитор")):
        return FormulaAsset(
            part_index=part_index,
            label="Приоритет риска",
            latex=r"R = P \times I",
            parameters=[
                FormulaParameter(symbol="R", description="приоритет риска"),
                FormulaParameter(symbol="P", description="вероятность возникновения"),
                FormulaParameter(symbol="I", description="влияние на пользователя или команду"),
            ],
            description="Формула помогает выбрать, какие ограничения проверять первыми.",
        )
    return FormulaAsset(
        part_index=part_index,
        label="Полнота выполнения проекта",
        latex=r"C = \frac{A_{done}}{A_{planned}} \times 100\%",
        parameters=[
            FormulaParameter(symbol="C", description="процент закрытых проверяемых действий"),
            FormulaParameter(symbol="A_{done}", description="количество выполненных действий"),
            FormulaParameter(symbol="A_{planned}", description="количество запланированных действий"),
        ],
        description="Формула задаёт измеримый критерий прогресса без привязки к конкретной реализации.",
    )


def _comparison_table(context: CurriculumContext, part_index: int) -> TableAsset:
    outcomes = context.current_project_learning_outcomes or ["Сформировать проверяемый артефакт"]
    skills = context.current_project_skills or ["Работа с проектным контекстом"]
    rows = [
        ("Контракт", _pick(skills, 0), "Есть явные входы, выходы и критерии приёмки"),
        ("Реализация", _pick(outcomes, 0), "Артефакт можно открыть, проверить и улучшить"),
        ("Проверка", _pick(skills + outcomes, 1), "P2P видит доказательства, а не только описание намерений"),
    ]
    md_table = "\n".join(
        [
            "| Зона решения | На что опирается | Как проверить |",
            "|---|---|---|",
            *[f"| {zone} | {anchor} | {check} |" for zone, anchor, check in rows],
        ]
    )
    return TableAsset(
        part_index=part_index,
        label="Связь теории, практики и проверки",
        md_table=md_table,
        description="Таблица связывает понятия главы с будущими практическими артефактами.",
    )


def _workflow_visual(context: CurriculumContext, part_index: int) -> VisualAsset:
    artifact = _clean_mermaid_label(context.current_project_platform_name or context.current_project_title or "Артефакт")
    mermaid = _normalize_mermaid(
        "\n".join(
            [
                "flowchart TD",
                "    A[Raw materials] --> B[Разбор ограничения]",
                f"    B --> C[{artifact}]",
                "    C --> D[P2P проверка]",
                "    D --> E[Итерация улучшения]",
            ]
        )
    )
    return VisualAsset(
        part_index=part_index,
        label="Поток работы над артефактом",
        mermaid=mermaid,
        description="Диаграмма показывает путь от сырого входа к проверяемому результату.",
    )


def _generate_dataset_files(
    context: CurriculumContext,
    tasks: list[PracticeTask],
    evidence_specs: list[EvidenceSpec],
    draft: GeneratorDraft | None,
    warnings: list[str],
) -> list[DatasetFile]:
    spec_index = _index_specs(evidence_specs)
    result: list[DatasetFile] = []
    seen: set[str] = set()
    draft_notes = draft.dataset_notes if draft else {}

    for task_index, task in enumerate(tasks, 1):
        refs = _file_refs(task.input_data)
        for spec in evidence_specs:
            if spec.source_task_index in (None, task_index) and spec.path not in refs:
                refs.append(spec.path)
        for raw_ref in refs:
            path = _material_path(raw_ref)
            filename = path.split("/")[-1]
            if path.lower() in seen:
                continue
            seen.add(path.lower())
            if not _should_generate_file(task, filename):
                continue
            spec = spec_index.get(path.lower()) or spec_index.get(filename.lower())
            description = _file_description(task.input_data, filename, spec)
            note = draft_notes.get(path) or draft_notes.get(filename) or ""
            item = _dataset_file(context, task, task_index, path, description, spec, note)
            if item is None:
                warnings.append(f"generators.dataset_unsupported:{path}")
                continue
            result.append(item)
    return result


def _dataset_file(
    context: CurriculumContext,
    task: PracticeTask,
    task_index: int,
    path: str,
    description: str,
    spec: EvidenceSpec | None,
    note: str,
) -> DatasetFile | None:
    filename = path.split("/")[-1]
    ext = filename.rsplit(".", 1)[-1].lower()
    file_type: DatasetType = "xlsx" if ext in {"xlsx", "xls"} else ext  # type: ignore[assignment]
    rows = _dataset_rows(context, task, description, note)
    if file_type == "csv":
        content = _csv_text(rows)
        return _text_dataset(path, filename, file_type, "text/csv", "utf-8-sig", "\ufeff" + content, task_index, spec)
    if file_type == "json":
        content = json.dumps({"data": rows, "source": "generator.generators"}, ensure_ascii=False, indent=2)
        return _text_dataset(path, filename, file_type, "application/json", "utf-8", content, task_index, spec)
    if file_type == "txt":
        content = _txt_text(context, task, rows)
        return _text_dataset(path, filename, file_type, "text/plain", "utf-8", content, task_index, spec)
    if file_type == "md":
        content = _md_text(context, task, spec, note)
        return _text_dataset(path, filename, file_type, "text/markdown", "utf-8", content, task_index, spec)
    if file_type == "xlsx":
        data = _xlsx_bytes(rows)
        return DatasetFile(
            path=path,
            filename=filename,
            file_type="xlsx",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            encoding="base64",
            content_base64=base64.b64encode(data).decode("ascii"),
            size_bytes=len(data),
            source_task_index=task_index,
            evidence_spec=spec.model_dump(mode="json") if spec else None,
        )
    return None


def _text_dataset(
    path: str,
    filename: str,
    file_type: DatasetType,
    mime_type: str,
    encoding: DatasetEncoding,
    content: str,
    task_index: int,
    spec: EvidenceSpec | None,
) -> DatasetFile:
    return DatasetFile(
        path=path,
        filename=filename,
        file_type=file_type,
        mime_type=mime_type,
        encoding=encoding,
        content_text=content,
        size_bytes=len(content.encode("utf-8")),
        source_task_index=task_index,
        evidence_spec=spec.model_dump(mode="json") if spec else None,
    )


def _dataset_rows(context: CurriculumContext, task: PracticeTask, description: str, note: str) -> list[dict[str, Any]]:
    columns = _columns_from_description(description) or _default_columns(context, task)
    row_count = _row_count(description, default=6)
    rows: list[dict[str, Any]] = []
    for index in range(1, row_count + 1):
        row: dict[str, Any] = {}
        for col in columns:
            row[col] = _value_for_column(col, index, context, task, note)
        rows.append(row)
    return rows


def _columns_from_description(text: str) -> list[str]:
    match = re.search(r"(?:столбцы?|колонки?|поля?|columns?)\s*[:\-]?\s*([^\n.]+)", text, re.I)
    if not match:
        return []
    raw = re.split(r"[,;/]|\s+и\s+", match.group(1))
    columns = [_safe_column_name(item) for item in raw]
    return [col for col in columns if col][:8]


def _default_columns(context: CurriculumContext, task: PracticeTask) -> list[str]:
    text = _topic_text(context, {"body": task.input_data, "title": task.title}).lower()
    if any(token in text for token in ("api", "rest", "endpoint", "latency")):
        return ["id", "endpoint", "status_code", "latency_ms", "result"]
    if any(token in text for token in ("user", "клиент", "пользователь")):
        return ["id", "segment", "action", "status", "comment"]
    return ["id", "artifact", "status", "risk", "comment"]


def _value_for_column(column: str, index: int, context: CurriculumContext, task: PracticeTask, note: str) -> Any:
    low = column.lower()
    if low in {"id", "row_id", "record_id"}:
        return index
    if "endpoint" in low:
        return _pick(["/health", "/api/projects", "/api/tasks", "/api/reviews"], index - 1)
    if "status_code" in low or low == "code":
        return _pick([200, 201, 400, 404, 500], index - 1)
    if "latency" in low or "time" in low:
        return 80 + index * 17
    if "status" in low or "result" in low:
        return _pick(["ok", "needs_review", "blocked", "fixed"], index - 1)
    if "risk" in low:
        return _pick(["низкий", "средний", "высокий"], index - 1)
    if "segment" in low:
        return _pick(["новый пользователь", "опытный пользователь", "администратор"], index - 1)
    if "action" in low:
        return _pick(["создал заявку", "проверил контракт", "исправил ошибку"], index - 1)
    if "artifact" in low:
        return task.artifact_location or context.current_project_platform_name or context.current_project_title
    if "comment" in low or "note" in low:
        return _limit_text(note or task.constraints_or_risk or context.sjm_context or "наблюдение из сырого материала", 90)
    return f"{_safe_column_name(column) or 'value'}_{index}"


def _csv_text(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _txt_text(context: CurriculumContext, task: PracticeTask, rows: list[dict[str, Any]]) -> str:
    lines = [
        f"Проект: {context.current_project_title}",
        f"Задача: {task.title}",
        f"Контекст: {task.situation}",
        "Наблюдения:",
    ]
    for row in rows[:8]:
        lines.append("- " + "; ".join(f"{key}={value}" for key, value in row.items()))
    return "\n".join(lines)


def _md_text(context: CurriculumContext, task: PracticeTask, spec: EvidenceSpec | None, note: str) -> str:
    contains = spec.contains if spec else []
    excludes = spec.excludes if spec else []
    derive = spec.student_must_derive if spec else []
    return _normalize_markdown(
        "\n".join(
            [
                f"# Raw evidence: {task.title}",
                "",
                f"Проект: {context.current_project_title}",
                f"Ситуация: {task.situation}",
                f"Ограничение: {task.constraints_or_risk or 'не задано'}",
                "",
                "## Что есть в материале",
                *[f"- {item}" for item in (contains or ["описание наблюдений", "факты для анализа", "контекст принятия решения"])],
                "",
                "## Чего здесь нет",
                *[f"- {item}" for item in (excludes or ["готового решения", "финального артефакта", "оценки за студента"])],
                "",
                "## Что должен вывести студент",
                *[f"- {item}" for item in (derive or ["структурированный вывод", "аргументированное решение", "проверяемый артефакт"])],
                "",
                note.strip(),
            ]
        )
    )


def _xlsx_bytes(rows: list[dict[str, Any]]) -> bytes:
    headers = list(rows[0].keys()) if rows else ["id", "value"]
    sheet_rows = [headers, *[[row.get(header, "") for header in headers] for row in rows]]
    sheet_xml = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>',
    ]
    for r_idx, row in enumerate(sheet_rows, 1):
        sheet_xml.append(f'<row r="{r_idx}">')
        for c_idx, value in enumerate(row, 1):
            cell = f"{_excel_col(c_idx)}{r_idx}"
            sheet_xml.append(f'<c r="{cell}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>')
        sheet_xml.append("</row>")
    sheet_xml.append("</sheetData></worksheet>")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _XLSX_CONTENT_TYPES)
        zf.writestr("_rels/.rels", _XLSX_ROOT_RELS)
        zf.writestr("xl/workbook.xml", _XLSX_WORKBOOK)
        zf.writestr("xl/_rels/workbook.xml.rels", _XLSX_WORKBOOK_RELS)
        zf.writestr("xl/worksheets/sheet1.xml", "".join(sheet_xml))
    return buffer.getvalue()


def _generate_code_examples(
    context: CurriculumContext,
    theory_parts: list[dict[str, Any]],
    draft: GeneratorDraft | None,
) -> list[CodeExample]:
    if not _should_generate_code(context):
        return []
    language = _detect_language([*context.current_project_skills, *context.current_project_required_software, *context.current_project_required_tools])
    if draft and draft.code_examples:
        valid = [_validate_code_example(item, language) for item in draft.code_examples]
        return [item for item in valid if item is not None][:2]
    part_index = int((theory_parts[0] if theory_parts else {}).get("index") or 1)
    return [_deterministic_code_example(context, language, part_index)]


def _deterministic_code_example(context: CurriculumContext, language: str, part_index: int) -> CodeExample:
    if language == "sql":
        code = """SELECT endpoint, COUNT(*) AS checks, AVG(latency_ms) AS avg_latency
FROM api_checks
WHERE status_code >= 400
GROUP BY endpoint
ORDER BY checks DESC;"""
        label = "Агрегация проблемных API-проверок"
    elif language == "javascript":
        code = """const checks = [{ status: 200, latencyMs: 120 }, { status: 500, latencyMs: 340 }];
const report = checks.map((item) => ({
  ok: item.status < 400,
  slow: item.latencyMs > 250,
}));
console.log(report);"""
        label = "Проверка ответов API"
    elif language == "bash":
        code = """#!/usr/bin/env bash
set -euo pipefail
curl -s "$API_URL/health" | tee materials/health.json
python -m json.tool materials/health.json >/dev/null"""
        label = "Мини-проверка health endpoint"
    else:
        code = """def summarize_checks(rows):
    total = len(rows)
    passed = sum(1 for row in rows if row["status_code"] < 400)
    return {
        "passed_ratio": round(passed / total, 2) if total else 0,
        "needs_review": [row for row in rows if row["status_code"] >= 400],
    }"""
        label = "Подсчёт качества API-проверок"
        language = "python"
    return CodeExample(
        part_index=part_index,
        label=label,
        language=language,
        code=code,
        explanation="Пример показывает, как превратить сырые наблюдения в проверяемый сигнал для артефакта проекта.",
    )


def _validate_code_example(example: CodeExample, fallback_language: str) -> CodeExample | None:
    try:
        language = example.language.strip().lower() or fallback_language
        code = FENCE_RE.sub(lambda match: match.group(1), example.code).strip()
        if not code:
            return None
        lines = code.splitlines()
        if len(lines) > 30:
            code = "\n".join(lines[:30])
        return CodeExample(
            part_index=example.part_index,
            label=_limit_text(example.label, 70) or "Пример кода",
            language=language,
            code=code,
            explanation=example.explanation,
        )
    except Exception:
        return None


def _insert_theory_assets(
    markdown: str,
    formulas: list[FormulaAsset],
    tables: list[TableAsset],
    visuals: list[VisualAsset],
) -> str:
    assets_by_part: dict[int, list[str]] = {}
    for formula in formulas:
        assets_by_part.setdefault(formula.part_index, []).append(_render_formula(formula))
    for table in tables:
        assets_by_part.setdefault(table.part_index, []).append(_render_table(table))
    for visual in visuals:
        assets_by_part.setdefault(visual.part_index, []).append(_render_visual(visual))
    result = markdown
    for part_index, blocks in sorted(assets_by_part.items()):
        result = _insert_before_part_example(result, part_index, "\n\n".join(blocks))
    return result


def _insert_code_examples(markdown: str, examples: list[CodeExample]) -> str:
    result = markdown
    for example in examples:
        result = _insert_before_part_example(result, example.part_index, _render_code_example(example))
    return result


def _insert_before_part_example(markdown: str, part_index: int, block: str) -> str:
    if not block.strip():
        return markdown
    pattern = re.compile(rf"(###\s+2\.{part_index}\.[\s\S]*?)(\n\*\*Пример:\*\*)", re.M)
    if pattern.search(markdown):
        return pattern.sub(lambda match: f"{match.group(1).rstrip()}\n\n{block.strip()}\n{match.group(2)}", markdown, count=1)
    marker = "\n## Глава 3"
    if marker in markdown:
        return markdown.replace(marker, f"\n\n{block.strip()}\n{marker}", 1)
    return f"{markdown.rstrip()}\n\n{block.strip()}"


def _append_dataset_manifest(markdown: str, files: list[DatasetFile]) -> str:
    if not files:
        return markdown
    lines = ["## Материалы к практике", ""]
    for item in files:
        lines.append(f"- `{item.path}` ({item.file_type}, {item.size_bytes} байт) — сырой материал для задания {item.source_task_index or '?'}.")
    manifest = "\n".join(lines)
    pattern = re.compile(r"^##\s+Материалы к практике[\s\S]*?(?=^##\s+Чек-лист|\Z)", re.M)
    if pattern.search(markdown):
        return pattern.sub(manifest + "\n\n", markdown, count=1)
    checklist = re.search(r"^##\s+Чек-лист", markdown, re.M)
    if checklist:
        return markdown[: checklist.start()].rstrip() + "\n\n" + manifest + "\n\n" + markdown[checklist.start() :]
    return markdown.rstrip() + "\n\n" + manifest


def _render_formula(item: FormulaAsset) -> str:
    params = "\n".join(f"- `${param.symbol}` — {param.description}." for param in item.parameters)
    return _normalize_markdown(
        f"**Формула. {item.label}**\n\n$$\n{item.latex}\n$$\n\n{params}\n\n{item.description}"
    )


def _render_table(item: TableAsset) -> str:
    return _normalize_markdown(f"**Таблица. {item.label}**\n\n{item.md_table}\n\n{item.description}")


def _render_visual(item: VisualAsset) -> str:
    return _normalize_markdown(f"**Диаграмма. {item.label}**\n\n```mermaid\n{item.mermaid}\n```\n\n{item.description}")


def _render_code_example(item: CodeExample) -> str:
    return _normalize_markdown(
        f"**Пример кода. {item.label}**\n\n```{item.language}\n{item.code}\n```\n\n{item.explanation}"
    )


def _coerce_theory_parts(raw: Any, markdown: str) -> list[dict[str, Any]]:
    if isinstance(raw, list) and raw:
        parts = []
        for index, item in enumerate(raw, 1):
            if isinstance(item, BaseModel):
                item = item.model_dump(mode="json")
            if isinstance(item, dict):
                parts.append({"index": int(item.get("index") or index), "title": str(item.get("title") or ""), "body": str(item.get("body") or "")})
        if parts:
            return parts
    parsed = []
    matches = list(re.finditer(r"^###\s+2\.(\d+)\.\s*(.+?)\s*$", markdown, re.M))
    for offset, match in enumerate(matches):
        end = matches[offset + 1].start() if offset + 1 < len(matches) else len(markdown)
        parsed.append({"index": int(match.group(1)), "title": match.group(2), "body": markdown[match.end() : end]})
    return parsed


def _coerce_tasks(raw: Any) -> list[PracticeTask]:
    if not isinstance(raw, list):
        return []
    tasks = []
    for item in raw:
        try:
            tasks.append(item if isinstance(item, PracticeTask) else PracticeTask.model_validate(item))
        except Exception:
            continue
    return tasks


def _coerce_evidence_specs(state: dict[str, Any]) -> list[EvidenceSpec]:
    raw = state.get("evidence_specs")
    if not raw and isinstance(state.get("artifact_chain_plan"), dict):
        raw = state["artifact_chain_plan"].get("evidence_specs")
    if not isinstance(raw, list):
        return []
    specs = []
    for item in raw:
        try:
            specs.append(item if isinstance(item, EvidenceSpec) else EvidenceSpec.model_validate(item))
        except Exception:
            continue
    return specs


def _file_refs(input_data: str) -> list[str]:
    refs = []
    for match in FILE_RE.finditer(input_data or ""):
        raw = match.group(0).replace("\\", "/")
        refs.append(raw if "/" in raw else f"materials/{match.group(1)}")
    return refs


def _should_generate_file(task: PracticeTask, filename: str) -> bool:
    text = f"{task.input_data} {task.goal}".lower()
    if is_solution_like_material_ref(filename, context=task.input_data):
        return False
    creation = [
        r"\bсоздать\s+(?:файл|датасет|данные|набор)",
        r"\bсгенерировать\s+(?:файл|датасет|данные|набор)",
        r"\bнаписать\s+код\s+для\s+(?:создания|генерации)",
        r"\bразработать\s+функцию\s+для\s+(?:создания|генерации)",
        r"\bgenerate\s+(?:file|dataset|data)",
        r"\bcreate\s+(?:file|dataset|data)",
    ]
    return not any(re.search(pattern, text) and filename.lower() in text for pattern in creation)


def _file_description(input_data: str, filename: str, spec: EvidenceSpec | None) -> str:
    parts = []
    if spec:
        parts.extend(spec.contains)
        parts.extend(spec.student_must_derive)
    if re.search(r"(?:столбцы?|колонки?|поля?|columns?|строк[аи]?|запис(?:ей|и)|rows?|records?)", input_data or "", re.I):
        parts.append(input_data)
    sentences = re.split(r"[.!?]\s+", input_data or "")
    parts.extend(sentence.strip() for sentence in sentences if filename.lower() in sentence.lower())
    return ". ".join(part for part in parts if part)


def _normalize_mermaid(code: str) -> str:
    code = FENCE_RE.sub(lambda match: match.group(1), code or "")
    code = code.replace("\\n", "\n")
    code = MERMAID_STYLE_RE.sub("", code)
    lines = [line.rstrip() for line in code.splitlines() if line.strip()]
    if not lines:
        return ""
    first = lines[0].strip()
    if first == "graph":
        lines[0] = "flowchart TD"
    elif first.startswith("graph ") and not re.match(r"graph\s+(TD|LR|TB|BT)\b", first):
        lines[0] = "flowchart TD"
    elif first == "flowchart":
        lines[0] = "flowchart TD"
    normalized = "\n".join(lines)
    if not _valid_mermaid(normalized):
        return "flowchart TD\n    A[Raw materials] --> B[Artifact]\n    B --> C[P2P]"
    return normalized


def _valid_mermaid(code: str) -> bool:
    starts = ("flowchart TD", "flowchart LR", "flowchart TB", "flowchart BT", "graph TD", "graph LR", "sequenceDiagram", "stateDiagram")
    return any(code.strip().startswith(start) for start in starts)


def _should_generate_code(context: CurriculumContext) -> bool:
    if _content_type(context) == "no_code":
        return False
    text = _topic_text(context, {}).lower()
    return any(
        token in text
        for token in ("python", "javascript", "java", "go", "rust", "c++", "sql", "api", "backend", "код", "программ", "скрипт")
    )


def _detect_language(skills: list[str]) -> str:
    text = " ".join(skills).lower()
    if any(token in text for token in ("javascript", " js", "node")):
        return "javascript"
    if "java" in text and "javascript" not in text:
        return "java"
    if "golang" in text or re.search(r"\bgo\b", text):
        return "go"
    if "rust" in text:
        return "rust"
    if any(token in text for token in ("cpp", "c++", "c plus")):
        return "cpp"
    if re.search(r"\bc\b", text) and "c++" not in text:
        return "c"
    if "bash" in text or "shell" in text:
        return "bash"
    if "sql" in text:
        return "sql"
    return "python"


def _content_type(context: CurriculumContext) -> str:
    text = f"{context.direction} {context.current_project_title} {' '.join(context.current_project_skills)}".lower()
    if any(token in text for token in ("pjm", "product", "design", "маркет", "презентац", "документ")):
        return "no_code"
    if any(token in text for token in ("sql", "api", "backend", "python", "javascript", "java", "devops")):
        return "hard_code"
    return "low_code"


def _topic_text(context: CurriculumContext, part: dict[str, Any]) -> str:
    return " ".join(
        [
            context.direction,
            context.block_name,
            context.current_project_title,
            context.current_project_description,
            " ".join(context.current_project_learning_outcomes),
            " ".join(context.current_project_skills),
            " ".join(context.current_project_required_tools),
            " ".join(context.current_project_required_software),
            context.sjm_context or "",
            str(part.get("title") or ""),
            str(part.get("body") or ""),
        ]
    )


def _artifact_refs(files: list[DatasetFile]) -> list[ArtifactRef]:
    refs = []
    for item in files:
        refs.append(
            ArtifactRef(
                artifact_id=f"dataset:{item.path}",
                kind=item.file_type,
                family="dataset",
                path=item.path,
                mime_type=item.mime_type,
                metadata={"size_bytes": item.size_bytes, "encoding": item.encoding, "source_task_index": item.source_task_index},
            )
        )
    return refs


def _index_specs(specs: list[EvidenceSpec]) -> dict[str, EvidenceSpec]:
    result = {}
    for spec in specs:
        path = _material_path(spec.path).lower()
        result[path] = spec
        result[path.split("/")[-1]] = spec
    return result


def _material_path(raw: str) -> str:
    path = str(raw or "").replace("\\", "/").strip("` ")
    if not path:
        return "materials/source.md"
    if not path.startswith(("materials/", "data/")):
        return f"materials/{path.split('/')[-1]}"
    return path


def _mentions_file_inputs(tasks: list[PracticeTask]) -> bool:
    return any(FILE_RE.search(task.input_data or "") for task in tasks)


def _row_count(text: str, *, default: int) -> int:
    match = re.search(r"(?:строк[аи]?|запис(?:ей|и)|rows?|records?)\s*[:\-]?\s*(\d+)", text, re.I)
    if not match:
        return default
    return max(2, min(100, int(match.group(1))))


def _safe_column_name(value: str) -> str:
    text = value.strip().lower()
    text = text.replace("идентификатор", "id").replace("статус", "status").replace("комментарий", "comment")
    text = re.sub(r"[^a-zа-яё0-9_ -]", "", text)
    if re.search(r"[a-z]", text):
        text = LATIN_ID_RE.sub("_", text)
    else:
        mapping = {"пользователь": "user", "сегмент": "segment", "действие": "action", "риск": "risk", "результат": "result"}
        text = mapping.get(text.strip(), "")
    return text.strip("_")


def _excel_col(index: int) -> str:
    result = ""
    while index:
        index, rem = divmod(index - 1, 26)
        result = chr(65 + rem) + result
    return result


def _clean_mermaid_label(value: str) -> str:
    text = re.sub(r"[\[\]{}<>|]", " ", value)
    return _limit_text(re.sub(r"\s+", " ", text).strip(), 42) or "Artifact"


def _limit_sentences(value: str, limit: int) -> str:
    sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+", value or "") if item.strip()]
    result = " ".join(sentences[:limit]) if sentences else (value or "").strip()
    return result[:400].strip()


def _limit_text(value: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _pick(items: list[Any], index: int) -> str:
    clean = [str(item).strip() for item in items if str(item).strip()]
    return clean[index % len(clean)] if clean else "проверяемый результат"


def _normalize_markdown(text: str) -> str:
    text = re.sub(r"[ \t]+\n", "\n", text or "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


_XLSX_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>"""
_XLSX_ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""
_XLSX_WORKBOOK = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="Данные" sheetId="1" r:id="rId1"/></sheets>
</workbook>"""
_XLSX_WORKBOOK_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>"""
