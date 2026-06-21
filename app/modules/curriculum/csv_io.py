"""CSV import/export for persistent curriculum plans."""

from __future__ import annotations

import csv
import io
import re
from typing import Any

from app.core.models import CompetencyRef, UPProject, UPSkeleton

CURRICULUM_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "block_name": ("тематический блок", "название всего блока (если делим на блоки)"),
    "block_goals": ("цели блока",),
    "order": ("№",),
    "title": ("название проекта", "название контентной единицы"),
    "description": ("краткое описание проекта", "краткое описание"),
    "expert_notes": ("что нужно разработать эксперту",),
    "learning_outcomes": ("образовательные результаты (знает, понимает, умеет)", "образовательные результаты"),
    "skills": ("список навыков",),
    "audience_level": ("уровень аудитории",),
    "required_tools": ("обязательные инструменты (через запятую)", "обязательные инструменты"),
    "sjm": ("сторителлинг", "сторителтнг", "sjm"),
    "storytelling_type": ("тип сторителлинга", "storytelling type", "storytelling_type"),
    "format": ("формат",),
    "additional_materials": ("дополнительные материалы", "дополнительные материалы для генерации"),
    "group_size": ("кол-во в группе",),
    "workload_hours": ("трудоемкость, астр.часы",),
    "workload_days": ("трудоемкость, дни",),
    "total_workload_days": ("общая трудоемкость, дни",),
    "xp": ("xp за проект",),
    "passing_threshold": ("% прохождения проекта",),
    "required_software": ("необходимое по/веб", "необходимое по"),
    "platform_name": ("название проекта на платформе и в gitlab",),
    "gitlab_link": ("ссылки на gitlab/google docs", "ссылки на gitlab"),
}
CSV_HEADERS = {
    "block_name": "Тематический блок",
    "block_goals": "Цели блока",
    "order": "№",
    "title": "Название проекта",
    "description": "Краткое описание проекта",
    "expert_notes": "Что нужно разработать эксперту",
    "learning_outcomes": "Образовательные результаты",
    "skills": "Список навыков",
    "audience_level": "Уровень аудитории",
    "required_tools": "Обязательные инструменты",
    "sjm": "SJM",
    "storytelling_type": "Тип сторителлинга",
    "format": "Формат",
    "additional_materials": "Дополнительные материалы",
    "group_size": "Кол-во в группе",
    "workload_hours": "Трудоемкость, астр.часы",
    "workload_days": "Трудоемкость, дни",
    "total_workload_days": "Общая трудоемкость, дни",
    "xp": "XP за проект",
    "passing_threshold": "% прохождения проекта",
    "required_software": "Необходимое ПО",
    "platform_name": "Название проекта на платформе и в GitLab",
    "gitlab_link": "Ссылки на GitLab/Google Docs",
}


def up_from_csv(text: str, *, title: str | None = None, direction: str | None = None) -> UPSkeleton:
    rows = _read_csv_rows(text)
    if not rows:
        raise ValueError("CSV is empty")
    columns = _field_columns(rows[0])
    projects: list[UPProject] = []
    current_block = ""
    current_goal = ""
    for raw in rows[1:]:
        values = {field: _cell(raw, index) for field, index in columns.items()}
        if values.get("block_name"):
            current_block = values["block_name"]
        if values.get("block_goals"):
            current_goal = values["block_goals"]
        if not values.get("title"):
            continue
        order = _to_int(values.get("order"), len(projects) + 1) or len(projects) + 1
        outcomes = _split_items(values.get("learning_outcomes"))
        projects.append(
            UPProject(
                block=current_block or "Без блока",
                block_goal=current_goal,
                order=order,
                title=values["title"],
                description=values.get("description", ""),
                outcomes_can=outcomes,
                competency_refs=[CompetencyRef.from_text(item) for item in _split_items(values.get("skills"))],
                required_tools=_split_items(values.get("required_tools")),
                required_software=_split_items(values.get("required_software")),
                materials=values.get("additional_materials", ""),
                storytelling=values.get("sjm", ""),
                format=_format(values.get("format")),
                group_size=max(1, _to_int(values.get("group_size"), 1) or 1),
                hours_astro=max(0.0, _to_float(values.get("workload_hours"), 0.0) or 0.0),
                metadata={
                    key: value
                    for key, value in {
                        "expert_notes": values.get("expert_notes"),
                        "audience_level": values.get("audience_level"),
                        "storytelling_type": values.get("storytelling_type"),
                        "workload_days": _to_float(values.get("workload_days"), None),
                        "total_workload_days": _to_float(values.get("total_workload_days"), None),
                        "xp": _to_int(values.get("xp"), None),
                        "passing_threshold": _to_float(values.get("passing_threshold"), None),
                        "platform_name": values.get("platform_name"),
                        "gitlab_link": values.get("gitlab_link"),
                    }.items()
                    if value not in (None, "")
                },
            )
        )
    if not projects:
        raise ValueError("CSV contains no curriculum projects")
    return UPSkeleton(
        status="built",
        title=title or "Импортированный учебный план",
        direction=direction or "",
        rows=projects,
        metadata={"source": "csv_import"},
    )


def up_to_csv(up: UPSkeleton) -> str:
    buffer = io.StringIO()
    fields = tuple(CSV_HEADERS)
    writer = csv.DictWriter(buffer, fieldnames=[CSV_HEADERS[field] for field in fields], delimiter=";")
    writer.writeheader()
    for project in sorted(up.rows, key=lambda item: item.order):
        writer.writerow(_project_csv_row(project, fields))
    return buffer.getvalue()


def _project_csv_row(project: UPProject, fields: tuple[str, ...]) -> dict[str, object]:
    metadata = project.metadata
    values = {
        "block_name": project.block,
        "block_goals": project.block_goal,
        "order": project.order,
        "title": project.title,
        "description": project.description,
        "expert_notes": metadata.get("expert_notes", ""),
        "learning_outcomes": "\n".join(project.learning_outcomes),
        "skills": ", ".join(ref.canonical_name for ref in project.competency_refs),
        "audience_level": metadata.get("audience_level", ""),
        "required_tools": ", ".join(project.required_tools),
        "sjm": project.storytelling,
        "storytelling_type": metadata.get("storytelling_type", ""),
        "format": project.format,
        "additional_materials": project.materials,
        "group_size": project.group_size,
        "workload_hours": project.hours_astro,
        "workload_days": metadata.get("workload_days", ""),
        "total_workload_days": metadata.get("total_workload_days", ""),
        "xp": metadata.get("xp", ""),
        "passing_threshold": metadata.get("passing_threshold", ""),
        "required_software": ", ".join(project.required_software),
        "platform_name": metadata.get("platform_name", ""),
        "gitlab_link": metadata.get("gitlab_link", ""),
    }
    return {CSV_HEADERS[field]: values[field] for field in fields}


def _read_csv_rows(text: str) -> list[list[str]]:
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,")
        delimiter = dialect.delimiter
    except csv.Error:
        first = text.splitlines()[0] if text.splitlines() else ""
        delimiter = ";" if first.count(";") >= first.count(",") else ","
    return [[cell.strip() for cell in row] for row in csv.reader(io.StringIO(text.lstrip("\ufeff")), delimiter=delimiter) if any(cell.strip() for cell in row)]


def _field_columns(headers: list[str]) -> dict[str, int]:
    normalized_headers = [_normalize_column_name(header) for header in headers]
    columns: dict[str, int] = {}
    for field, aliases in CURRICULUM_COLUMN_ALIASES.items():
        normalized_aliases = {_normalize_column_name(alias) for alias in aliases}
        for index, header in enumerate(normalized_headers):
            if header in normalized_aliases:
                columns[field] = index
                break
    if "title" not in columns:
        raise ValueError("CSV header must contain project title column")
    return columns


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
    return [item.strip(" \t-") for item in raw if str(item).strip(" \t-")]


def _to_float(value: object, default: float | None) -> float | None:
    if value in (None, ""):
        return default
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return default


def _to_int(value: object, default: int | None) -> int | None:
    parsed = _to_float(value, None)
    return int(parsed) if parsed is not None else default


def _format(value: str) -> str:
    normalized = str(value or "").strip().casefold()
    if normalized in {"групповой", "group"}:
        return "group"
    if normalized in {"парный", "pair"}:
        return "pair"
    if normalized in {"воркшоп", "workshop"}:
        return "workshop"
    return "individual"
