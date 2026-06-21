"""Canonical curriculum export contracts and 22-column CSV projection."""

from __future__ import annotations

import csv
import io
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.models import CompetencyRef, UPProject, UPSkeleton

CSV_COLUMNS: tuple[tuple[str, str], ...] = (
    ("block_name", "Тематический блок"),
    ("block_goals", "Цели блока"),
    ("order", "№"),
    ("title", "Название контентной единицы"),
    ("description", "Краткое описание"),
    ("outcomes_know", "Образовательные результаты: знает"),
    ("outcomes_can", "Образовательные результаты: умеет"),
    ("outcomes_skills", "Образовательные результаты: навык"),
    ("required_software", "Необходимое ПО"),
    ("additional_materials", "Дополнительные материалы для генерации"),
    ("sjm", "Сторителлинг"),
    ("format", "Формат"),
    ("group_size", "Кол-во в группе"),
    ("workload_hours", "Трудоемкость, астр.часы"),
    ("workload_days", "Трудоемкость, дни"),
    ("total_workload_days", "Общая трудоемкость, дни"),
    ("xp", "XP за проект"),
    ("passing_threshold", "% прохождения проекта"),
    ("p2p_count", "Количество p2p проверок"),
    ("skills", "Список навыков"),
    ("platform_name", "Название проекта на платформе и в GitLab"),
    ("gitlab_link", "Ссылки на GitLab"),
)
CSV_HEADERS: dict[str, str] = dict(CSV_COLUMNS)

CURRICULUM_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "block_name": ("тематический блок", "название всего блока (если делим на блоки)", ""),
    "block_goals": ("цели блока",),
    "order": ("№", "№ "),
    "title": ("название контентной единицы", "название проекта"),
    "description": ("краткое описание", "краткое описание проекта"),
    "outcomes_know": ("образовательные результаты: знает", "образовательные результаты - знает"),
    "outcomes_can": ("образовательные результаты: умеет", "образовательные результаты - умеет"),
    "outcomes_skills": ("образовательные результаты: навык", "образовательные результаты - навык"),
    "learning_outcomes": ("образовательные результаты", "образовательные результаты (знает, понимает, умеет)"),
    "skills": ("список навыков",),
    "required_tools": ("обязательные инструменты (через запятую)", "обязательные инструменты"),
    "required_software": ("необходимое по/веб", "необходимое по"),
    "additional_materials": ("дополнительные материалы", "дополнительные материалы для генерации"),
    "sjm": (
        "сторителлинг",
        "сторителтнг",
        "sjm",
        "sjm (описание ситуации/кейса, с которым сталкивается участник, сторителлинг или моделирование среды)",
    ),
    "format": ("формат",),
    "group_size": ("кол-во в группе",),
    "workload_hours": ("трудоемкость, астр.часы",),
    "workload_days": ("трудоемкость, дни",),
    "total_workload_days": ("общая трудоемкость, дни",),
    "xp": ("xp за проект",),
    "passing_threshold": ("% прохождения проекта",),
    "p2p_count": ("количество p2p проверок", "количество p2p-проверок"),
    "platform_name": ("название проекта на платформе и в gitlab",),
    "gitlab_link": ("ссылки на gitlab/google docs", "ссылки на gitlab"),
}


class CurriculumProjectExportV1(BaseModel):
    """One project row in the canonical export JSON."""

    model_config = ConfigDict(extra="forbid")

    block_name: str = "Без блока"
    block_goals: list[str] = Field(default_factory=list)
    order: int = Field(ge=1)
    title: str
    description: str = ""
    outcomes_know: list[str] = Field(default_factory=list)
    outcomes_can: list[str] = Field(default_factory=list)
    outcomes_skills: list[str] = Field(default_factory=list)
    required_software: list[str] = Field(default_factory=list)
    additional_materials: str = ""
    sjm: str = ""
    format: Literal["individual", "group", "pair", "workshop", "unknown"] = "individual"
    group_size: int = Field(default=1, ge=1)
    workload_hours: float = Field(default=0.0, ge=0.0)
    workload_days: float | None = None
    total_workload_days: float | None = None
    xp: int | None = None
    passing_threshold: float | None = None
    p2p_count: int | None = None
    skills: list[str] = Field(default_factory=list)
    platform_name: str = ""
    gitlab_link: str = ""

    @model_validator(mode="before")
    @classmethod
    def normalize_input(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        for key in (
            "block_goals",
            "outcomes_know",
            "outcomes_can",
            "outcomes_skills",
            "required_software",
            "skills",
        ):
            if key in payload:
                payload[key] = _split_items(payload[key])
        if "format" in payload:
            payload["format"] = _format(payload["format"])
        return payload

    @field_validator("title")
    @classmethod
    def title_is_not_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("project title must not be empty")
        return value


class CurriculumExportV1(BaseModel):
    """JSON export model from which the human CSV is produced."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["curriculum.export.v1"] = "curriculum.export.v1"
    title: str = "Учебный план"
    direction: str = ""
    status: Literal["built", "deferred", "draft"] = "built"
    projects: list[CurriculumProjectExportV1] = Field(default_factory=list)

    @classmethod
    def from_up_skeleton(cls, up: UPSkeleton) -> "CurriculumExportV1":
        return up_to_curriculum_export(up)

    @classmethod
    def from_csv(cls, text: str, *, title: str | None = None, direction: str | None = None) -> "CurriculumExportV1":
        return curriculum_export_from_csv(text, title=title, direction=direction)

    def to_up_skeleton(self) -> UPSkeleton:
        return curriculum_export_to_up(self)

    def to_csv(self) -> str:
        return curriculum_export_to_csv(self)


def up_to_curriculum_export(up: UPSkeleton) -> CurriculumExportV1:
    return CurriculumExportV1(
        title=up.title,
        direction=up.direction,
        status=up.status,
        projects=[_project_to_export(project) for project in sorted(up.rows, key=lambda item: item.order)],
    )


def curriculum_export_to_up(export: CurriculumExportV1) -> UPSkeleton:
    return UPSkeleton(
        status=export.status,
        title=export.title,
        direction=export.direction,
        rows=[_export_to_project(project) for project in export.projects],
    )


def curriculum_export_to_csv(export: CurriculumExportV1) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=[header for _, header in CSV_COLUMNS], delimiter=";")
    writer.writeheader()
    for project in sorted(export.projects, key=lambda item: item.order):
        writer.writerow(_export_csv_row(project))
    return buffer.getvalue()


def curriculum_export_from_csv(text: str, *, title: str | None = None, direction: str | None = None) -> CurriculumExportV1:
    rows = _read_csv_rows(text)
    if not rows:
        raise ValueError("CSV is empty")
    columns = _field_columns(rows[0])
    projects: list[CurriculumProjectExportV1] = []
    current_block = ""
    current_goals: list[str] = []
    inferred_order = 0

    for raw in rows[1:]:
        values = _row_values(raw, columns)
        if values.get("block_name"):
            current_block = values["block_name"]
        if values.get("block_goals"):
            current_goals = _split_items(values["block_goals"])
        title_value = values.get("title", "").strip()
        if not title_value or _normalize_column_name(title_value) in {"название проекта", "название контентной единицы"}:
            continue
        order = _to_int(values.get("order"), None)
        inferred_order = max(inferred_order + 1, order or 0)
        projects.append(
            CurriculumProjectExportV1(
                block_name=current_block or "Без блока",
                block_goals=current_goals,
                order=order or inferred_order,
                title=title_value,
                description=values.get("description", ""),
                outcomes_know=_split_items(values.get("outcomes_know")),
                outcomes_can=_split_items(values.get("outcomes_can") or values.get("learning_outcomes")),
                outcomes_skills=_split_items(values.get("outcomes_skills")),
                required_software=_split_items(values.get("required_software") or values.get("required_tools")),
                additional_materials=values.get("additional_materials", ""),
                sjm=values.get("sjm", ""),
                format=_format(values.get("format")),
                group_size=max(1, _to_int(values.get("group_size"), 1) or 1),
                workload_hours=max(0.0, _to_float(values.get("workload_hours"), 0.0) or 0.0),
                workload_days=_to_float(values.get("workload_days"), None),
                total_workload_days=_to_float(values.get("total_workload_days"), None),
                xp=_to_int(values.get("xp"), None),
                passing_threshold=_to_float(values.get("passing_threshold"), None),
                p2p_count=_to_int(values.get("p2p_count"), None),
                skills=_split_items(values.get("skills")),
                platform_name=values.get("platform_name", ""),
                gitlab_link=values.get("gitlab_link", ""),
            )
        )
    if not projects:
        raise ValueError("CSV contains no curriculum projects")
    return CurriculumExportV1(title=title or "Импортированный учебный план", direction=direction or "", projects=projects)


def up_to_csv(up: UPSkeleton) -> str:
    return up_to_curriculum_export(up).to_csv()


def up_from_csv(text: str, *, title: str | None = None, direction: str | None = None) -> UPSkeleton:
    return curriculum_export_from_csv(text, title=title, direction=direction).to_up_skeleton()


def _project_to_export(project: UPProject) -> CurriculumProjectExportV1:
    metadata = project.metadata
    return CurriculumProjectExportV1(
        block_name=project.block or "Без блока",
        block_goals=_split_items(project.block_goal),
        order=project.order,
        title=project.title,
        description=project.description,
        outcomes_know=project.outcomes_know,
        outcomes_can=project.outcomes_can,
        outcomes_skills=project.outcomes_skills,
        required_software=project.required_software or project.required_tools,
        additional_materials=project.materials,
        sjm=project.storytelling,
        format=project.format,
        group_size=project.group_size,
        workload_hours=project.hours_astro,
        workload_days=_to_float(metadata.get("workload_days"), None),
        total_workload_days=_to_float(metadata.get("total_workload_days"), None),
        xp=_to_int(metadata.get("xp"), None),
        passing_threshold=_to_float(metadata.get("passing_threshold"), None),
        p2p_count=_to_int(metadata.get("p2p_count"), None),
        skills=[ref.canonical_name for ref in project.competency_refs],
        platform_name=str(metadata.get("platform_name", "")),
        gitlab_link=str(metadata.get("gitlab_link", "")),
    )


def _export_to_project(project: CurriculumProjectExportV1) -> UPProject:
    metadata = {
        key: value
        for key, value in {
            "workload_days": project.workload_days,
            "total_workload_days": project.total_workload_days,
            "xp": project.xp,
            "passing_threshold": project.passing_threshold,
            "p2p_count": project.p2p_count,
            "platform_name": project.platform_name,
            "gitlab_link": project.gitlab_link,
        }.items()
        if value not in (None, "")
    }
    return UPProject(
        block=project.block_name,
        block_goal="\n".join(project.block_goals),
        order=project.order,
        title=project.title,
        description=project.description,
        outcomes_know=project.outcomes_know,
        outcomes_can=project.outcomes_can,
        outcomes_skills=project.outcomes_skills,
        competency_refs=[CompetencyRef.from_text(item) for item in project.skills],
        required_software=project.required_software,
        materials=project.additional_materials,
        storytelling=project.sjm,
        format=project.format,
        group_size=project.group_size,
        hours_astro=project.workload_hours,
        metadata=metadata,
    )


def _export_csv_row(project: CurriculumProjectExportV1) -> dict[str, object]:
    values = {
        "block_name": project.block_name,
        "block_goals": "\n".join(project.block_goals),
        "order": project.order,
        "title": project.title,
        "description": project.description,
        "outcomes_know": "\n".join(project.outcomes_know),
        "outcomes_can": "\n".join(project.outcomes_can),
        "outcomes_skills": "\n".join(project.outcomes_skills),
        "required_software": ", ".join(project.required_software),
        "additional_materials": project.additional_materials,
        "sjm": project.sjm,
        "format": project.format,
        "group_size": project.group_size,
        "workload_hours": project.workload_hours,
        "workload_days": _csv_optional(project.workload_days),
        "total_workload_days": _csv_optional(project.total_workload_days),
        "xp": _csv_optional(project.xp),
        "passing_threshold": _csv_optional(project.passing_threshold),
        "p2p_count": _csv_optional(project.p2p_count),
        "skills": ", ".join(project.skills),
        "platform_name": project.platform_name,
        "gitlab_link": project.gitlab_link,
    }
    return {CSV_HEADERS[field]: values[field] for field, _ in CSV_COLUMNS}


def _row_values(row: list[str], columns: dict[str, int]) -> dict[str, str]:
    return {field: _cell(row, index) for field, index in columns.items()}


def _read_csv_rows(text: str) -> list[list[str]]:
    sample = text[:4096]
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=";,").delimiter
    except csv.Error:
        first = text.splitlines()[0] if text.splitlines() else ""
        delimiter = ";" if first.count(";") >= first.count(",") else ","
    reader = csv.reader(io.StringIO(text.lstrip("\ufeff")), delimiter=delimiter)
    return [[cell.strip() for cell in row] for row in reader if any(cell.strip() for cell in row)]


def _field_columns(headers: list[str]) -> dict[str, int]:
    columns: dict[str, int] = {}
    for field, aliases in CURRICULUM_COLUMN_ALIASES.items():
        if field.startswith("outcomes_") or field == "learning_outcomes":
            continue
        index = _resolve_column(headers, aliases, allow_blank_first=field == "block_name")
        if index is not None:
            columns[field] = index
    columns.update(_outcome_columns(headers))
    if "title" not in columns:
        raise ValueError("CSV header must contain project title column")
    return columns


def _outcome_columns(headers: list[str]) -> dict[str, int]:
    columns: dict[str, int] = {}
    for field in ("outcomes_know", "outcomes_can", "outcomes_skills"):
        index = _resolve_column(headers, CURRICULUM_COLUMN_ALIASES[field])
        if index is not None:
            columns[field] = index

    generic = _resolve_columns(headers, CURRICULUM_COLUMN_ALIASES["learning_outcomes"])
    unused = [index for index in generic if index not in columns.values()]
    if len(unused) >= 3:
        columns.setdefault("outcomes_know", unused[0])
        columns.setdefault("outcomes_can", unused[1])
        columns.setdefault("outcomes_skills", unused[2])
    elif len(unused) >= 2:
        columns.setdefault("outcomes_know", unused[0])
        columns.setdefault("outcomes_can", unused[1])
    elif unused:
        columns.setdefault("learning_outcomes", unused[0])
    return columns


def _resolve_column(headers: list[str], aliases: tuple[str, ...], *, allow_blank_first: bool = False) -> int | None:
    normalized_headers = [_normalize_column_name(header) for header in headers]
    if allow_blank_first and normalized_headers and not normalized_headers[0]:
        return 0
    normalized_aliases = {_normalize_column_name(alias) for alias in aliases}
    for index, header in enumerate(normalized_headers):
        if header in normalized_aliases:
            return index
    return None


def _resolve_columns(headers: list[str], aliases: tuple[str, ...]) -> list[int]:
    normalized_aliases = {_normalize_column_name(alias) for alias in aliases}
    return [index for index, header in enumerate(headers) if _normalize_column_name(header) in normalized_aliases]


def _normalize_column_name(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").replace("\ufeff", "").strip().casefold())


def _cell(row: list[str], index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    return row[index].strip()


def _split_items(value: Any) -> list[str]:
    if isinstance(value, list):
        raw = value
    else:
        raw = re.split(r"[\n;,]+", str(value or ""))
    return [str(item).strip(" \t-") for item in raw if str(item).strip(" \t-")]


def _to_float(value: object, default: float | None) -> float | None:
    if value in (None, ""):
        return default
    try:
        return float(str(value).replace("%", "").replace(",", "."))
    except ValueError:
        return default


def _to_int(value: object, default: int | None) -> int | None:
    parsed = _to_float(value, None)
    return int(parsed) if parsed is not None else default


def _format(value: object) -> str:
    normalized = str(value or "").strip().casefold()
    if "груп" in normalized or normalized == "group":
        return "group"
    if normalized in {"парный", "pair"}:
        return "pair"
    if normalized in {"воркшоп", "workshop"}:
        return "workshop"
    if normalized in {"unknown", "неизвестно"}:
        return "unknown"
    return "individual"


def _csv_optional(value: object) -> object:
    return "" if value is None else value
