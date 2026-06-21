"""Repository layer for curriculum/reference catalog tables.

This is the only runtime module that owns SQL for the catalog schema. Pipeline
stages pass typed core models in and out; storage details stay here.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
import difflib
import json
import re
import unicodedata
from typing import Any, Iterable, Iterator, Literal

import sqlalchemy as sa
from sqlalchemy.engine import Connection, Engine

from app.core.models import Competency, CompetencyIndicator

CatalogStatus = Literal["active", "candidate", "deprecated"]
ReviewSeverity = Literal["info", "warning", "error"]
ReviewStatus = Literal["open", "resolved", "ignored"]

SERVICE_PROFILE_SLUG = "intake-accepted-skills"
SERVICE_PROFILE_NAME = "Живой справочник intake"
SERVICE_SOURCE_ROOT = "intake://catalog"
SERVICE_WORKBOOK_PATH = "intake://accepted-skills"
SERVICE_WORKBOOK_NAME = "Accepted intake skills"
SERVICE_SHEET_NAME = "Accepted skills"
DEFAULT_COMPETENCY_TITLE = "Прочие компетенции"
FUZZY_MATCH_MIN = 0.86

BLOOM_TO_DIMENSION = {
    "remember": "knowledge",
    "understand": "knowledge",
    "apply": "ability",
    "analyze": "ability",
    "evaluate": "proficiency",
    "create": "proficiency",
}
DIMENSION_TITLES = {
    "knowledge": "Знает",
    "understanding": "Понимает",
    "ability": "Умеет",
    "proficiency": "Владеет",
    "unspecified": "Не указано",
}

metadata = sa.MetaData()

INGEST_RUN = sa.Table(
    "ingest_run",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    sa.Column("finished_at", sa.DateTime()),
    sa.Column("source_root", sa.Text(), nullable=False),
    sa.Column("status", sa.Text(), nullable=False, server_default="completed"),
    sa.Column("summary_json", sa.JSON()),
)
SOURCE_WORKBOOK = sa.Table(
    "source_workbook",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("ingest_run_id", sa.Integer(), sa.ForeignKey("ingest_run.id", ondelete="CASCADE"), nullable=False),
    sa.Column("file_path", sa.Text(), nullable=False),
    sa.Column("file_name", sa.Text(), nullable=False),
    sa.Column("sha256", sa.Text(), nullable=False),
    sa.Column("last_modified_utc", sa.DateTime()),
    sa.Column("source_kind", sa.Text(), nullable=False),
    sa.UniqueConstraint("ingest_run_id", "file_path", name="uq_source_workbook_run_path"),
)
SOURCE_SHEET = sa.Table(
    "source_sheet",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("source_workbook_id", sa.Integer(), sa.ForeignKey("source_workbook.id", ondelete="CASCADE"), nullable=False),
    sa.Column("sheet_name", sa.Text(), nullable=False),
    sa.Column("sheet_order", sa.Integer(), nullable=False),
    sa.Column("is_skipped", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("skip_reason", sa.Text()),
    sa.UniqueConstraint("source_workbook_id", "sheet_order", name="uq_source_sheet_order"),
)
SOURCE_BLOCK = sa.Table(
    "source_block",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("source_sheet_id", sa.Integer(), sa.ForeignKey("source_sheet.id", ondelete="CASCADE"), nullable=False),
    sa.Column("block_no", sa.Integer(), nullable=False),
    sa.Column("header_row_number", sa.Integer(), nullable=False),
    sa.Column("level_row_number", sa.Integer()),
    sa.Column("end_row_number", sa.Integer()),
    sa.Column("raw_title", sa.Text()),
    sa.Column("raw_description", sa.Text()),
    sa.Column("raw_prerequisites", sa.Text()),
    sa.Column("raw_scale_signature", sa.Text()),
    sa.UniqueConstraint("source_sheet_id", "block_no", name="uq_source_block_no"),
)
PROFILE = sa.Table(
    "profile",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("slug", sa.Text(), nullable=False, unique=True),
    sa.Column("name", sa.Text(), nullable=False),
    sa.Column("source_kind", sa.Text(), nullable=False),
    sa.Column("notes", sa.Text()),
)
PROFILE_SOURCE = sa.Table(
    "profile_source",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("profile_id", sa.Integer(), sa.ForeignKey("profile.id", ondelete="CASCADE"), nullable=False),
    sa.Column("source_workbook_id", sa.Integer(), sa.ForeignKey("source_workbook.id", ondelete="CASCADE"), nullable=False),
    sa.Column("version_label", sa.Text()),
    sa.Column("is_primary", sa.Integer(), nullable=False, server_default="1"),
    sa.UniqueConstraint("profile_id", "source_workbook_id", name="uq_profile_source_workbook"),
)
DIMENSION = sa.Table(
    "dimension",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("code", sa.Text(), nullable=False, unique=True),
    sa.Column("title", sa.Text(), nullable=False),
)
COMPETENCY = sa.Table(
    "competency",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("normalized_title", sa.Text(), nullable=False, unique=True),
    sa.Column("title", sa.Text(), nullable=False),
    sa.Column("description", sa.Text()),
    sa.Column("status", sa.Text(), nullable=False),
)
SKILL = sa.Table(
    "skill",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("normalized_name", sa.Text(), nullable=False, unique=True),
    sa.Column("canonical_name", sa.Text(), nullable=False),
    sa.Column("skill_type", sa.Text(), nullable=False, server_default="unknown"),
    sa.Column("status", sa.Text(), nullable=False, server_default="active"),
)
SKILL_ALIAS = sa.Table(
    "skill_alias",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("skill_id", sa.Integer(), sa.ForeignKey("skill.id", ondelete="CASCADE"), nullable=False),
    sa.Column("alias", sa.Text(), nullable=False),
    sa.Column("normalized_alias", sa.Text(), nullable=False),
    sa.Column("source", sa.Text()),
    sa.UniqueConstraint("skill_id", "normalized_alias", name="uq_skill_alias_normalized"),
)
PROFILE_COMPETENCY = sa.Table(
    "profile_competency",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("profile_id", sa.Integer(), sa.ForeignKey("profile.id", ondelete="CASCADE"), nullable=False),
    sa.Column("competency_id", sa.Integer(), sa.ForeignKey("competency.id", ondelete="CASCADE"), nullable=False),
    sa.Column("source_block_id", sa.Integer(), sa.ForeignKey("source_block.id", ondelete="CASCADE"), nullable=False),
    sa.Column("scale_id", sa.Integer()),
    sa.Column("title_in_source", sa.Text()),
    sa.Column("description_in_source", sa.Text()),
    sa.Column("prerequisites_text", sa.Text()),
    sa.Column("sort_order", sa.Integer(), nullable=False),
    sa.Column("review_state", sa.Text(), nullable=False, server_default="accepted"),
    sa.UniqueConstraint("profile_id", "source_block_id", name="uq_profile_competency_block"),
)
COMPETENCY_SKILL = sa.Table(
    "competency_skill",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("profile_competency_id", sa.Integer(), sa.ForeignKey("profile_competency.id", ondelete="CASCADE"), nullable=False),
    sa.Column("skill_id", sa.Integer(), sa.ForeignKey("skill.id", ondelete="SET NULL")),
    sa.Column("source_skill_name", sa.Text(), nullable=False),
    sa.Column("skill_order", sa.Integer(), nullable=False),
    sa.Column("review_state", sa.Text(), nullable=False, server_default="accepted"),
    sa.UniqueConstraint("profile_competency_id", "skill_order", name="uq_competency_skill_order"),
)
INDICATOR_ROW = sa.Table(
    "indicator_row",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("competency_skill_id", sa.Integer(), sa.ForeignKey("competency_skill.id", ondelete="CASCADE"), nullable=False),
    sa.Column("dimension_id", sa.Integer(), sa.ForeignKey("dimension.id", ondelete="RESTRICT"), nullable=False),
    sa.Column("source_row_number", sa.Integer(), nullable=False),
    sa.Column("inherited_skill", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("inherited_dimension", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("base_text", sa.Text()),
    sa.Column("raw_number", sa.Text()),
    sa.Column("notes", sa.Text()),
    sa.UniqueConstraint("competency_skill_id", "source_row_number", name="uq_indicator_row_source"),
)
INDICATOR_LEVEL_CELL = sa.Table(
    "indicator_level_cell",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("indicator_row_id", sa.Integer(), sa.ForeignKey("indicator_row.id", ondelete="CASCADE"), nullable=False),
    sa.Column("proficiency_level_id", sa.Integer()),
    sa.Column("raw_level_label", sa.Text(), nullable=False),
    sa.Column("raw_value", sa.Text(), nullable=False),
    sa.Column("value_kind", sa.Text(), nullable=False),
    sa.Column("sort_order", sa.Integer(), nullable=False),
    sa.UniqueConstraint("indicator_row_id", "raw_level_label", "sort_order", name="uq_indicator_level_cell"),
)
REVIEW_QUEUE = sa.Table(
    "review_queue",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("entity_type", sa.Text(), nullable=False),
    sa.Column("entity_id", sa.Integer()),
    sa.Column("source_ref", sa.Text()),
    sa.Column("reason_code", sa.Text(), nullable=False),
    sa.Column("severity", sa.Text(), nullable=False),
    sa.Column("details", sa.Text()),
    sa.Column("status", sa.Text(), nullable=False, server_default="open"),
    sa.Column("resolution_note", sa.Text()),
    sa.Column("reviewed_at", sa.DateTime()),
    sa.Column("updated_at", sa.DateTime()),
    sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
)


@dataclass(frozen=True)
class CatalogSkill:
    skill_id: int
    canonical_name: str
    normalized_name: str
    skill_type: str = "unknown"
    status: CatalogStatus = "active"
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class CatalogContext:
    ingest_run_id: int
    source_workbook_id: int
    source_sheet_id: int
    profile_id: int


@dataclass(frozen=True)
class CompetencyLinkResult:
    status: str
    skill_id: int
    competency_id: int | None = None
    profile_competency_id: int | None = None
    competency_skill_id: int | None = None
    created_competency: bool = False
    created_profile_competency: bool = False
    created_competency_skill: bool = False
    needs_methodologist_review: bool = False
    created_review: bool = False
    created_indicator_rows: int = 0


def create_catalog_schema(bind: Engine | Connection) -> None:
    """Create the catalog table subset used by this repo in tests/dev DBs."""
    metadata.create_all(bind)
    repo = CurriculumCatalogRepo(bind)
    repo.ensure_dimensions()


def normalize_catalog_key(value: object | None) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold().replace("ё", "е")
    text = re.sub(r"[^0-9a-zа-я+ ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


class CurriculumCatalogRepo:
    """Postgres-ready catalog CRUD and resolution adapter."""

    def __init__(self, bind: Engine | Connection) -> None:
        self.bind = bind

    def upsert_skill(
        self,
        canonical_name: str,
        *,
        skill_type: str = "unknown",
        status: CatalogStatus = "active",
        aliases: Iterable[str] = (),
        alias_source: str = "manual",
    ) -> CatalogSkill:
        clean_name = _clean_title(canonical_name, fallback="Без названия")
        normalized_name = normalize_catalog_key(clean_name)
        with self._connect() as con:
            skill_id = _select_id(con, SKILL, SKILL.c.normalized_name == normalized_name)
            if skill_id is None:
                skill_id = _insert_id(
                    con,
                    SKILL.insert().values(
                        normalized_name=normalized_name,
                        canonical_name=clean_name,
                        skill_type=skill_type,
                        status=status,
                    ),
                )
            else:
                con.execute(
                    SKILL.update()
                    .where(SKILL.c.id == skill_id)
                    .values(canonical_name=clean_name, skill_type=skill_type, status=status)
                )
            for alias in aliases:
                self._ensure_skill_alias(con, skill_id, alias, alias_source)
            return self._get_skill(con, skill_id)

    def get_skill(self, skill_id: int) -> CatalogSkill | None:
        with self._connect() as con:
            return self._get_skill(con, skill_id)

    def list_skills(self, *, query: str = "", limit: int = 50, include_deprecated: bool = False) -> list[CatalogSkill]:
        normalized_query = normalize_catalog_key(query)
        with self._connect() as con:
            stmt = SKILL.select().order_by(SKILL.c.canonical_name).limit(limit)
            if normalized_query:
                stmt = stmt.where(SKILL.c.normalized_name.like(f"%{normalized_query}%"))
            if not include_deprecated:
                stmt = stmt.where(SKILL.c.status != "deprecated")
            rows = con.execute(stmt).mappings().all()
            return [self._skill_from_row(con, row) for row in rows]

    def update_skill(
        self,
        skill_id: int,
        *,
        canonical_name: str | None = None,
        skill_type: str | None = None,
        status: CatalogStatus | None = None,
        aliases: Iterable[str] | None = None,
    ) -> CatalogSkill | None:
        with self._connect() as con:
            current = self._get_skill(con, skill_id)
            if current is None:
                return None
            values: dict[str, object] = {}
            if canonical_name is not None:
                clean_name = _clean_title(canonical_name, fallback=current.canonical_name)
                values.update(canonical_name=clean_name, normalized_name=normalize_catalog_key(clean_name))
            if skill_type is not None:
                values["skill_type"] = skill_type
            if status is not None:
                values["status"] = status
            if values:
                con.execute(SKILL.update().where(SKILL.c.id == skill_id).values(**values))
            if aliases is not None:
                con.execute(SKILL_ALIAS.delete().where(SKILL_ALIAS.c.skill_id == skill_id))
                for alias in aliases:
                    self._ensure_skill_alias(con, skill_id, alias, "manual_update")
            return self._get_skill(con, skill_id)

    def delete_skill(self, skill_id: int, *, hard: bool = False) -> bool:
        with self._connect() as con:
            if self._get_skill(con, skill_id) is None:
                return False
            if hard:
                con.execute(SKILL_ALIAS.delete().where(SKILL_ALIAS.c.skill_id == skill_id))
                con.execute(SKILL.delete().where(SKILL.c.id == skill_id))
            else:
                con.execute(SKILL.update().where(SKILL.c.id == skill_id).values(status="deprecated"))
            return True

    def resolve_competency(self, item: Competency) -> Competency:
        names = _candidate_names(item)
        normalized_names = [normalize_catalog_key(name) for name in names if normalize_catalog_key(name)]
        with self._connect() as con:
            by_norm, alias_norm, fuzzy_index = self._load_resolution_index(con)
            for normalized in normalized_names:
                if normalized in by_norm:
                    return _with_resolution(item, by_norm[normalized], "matched", 1.0)
            for normalized in normalized_names:
                if normalized in alias_norm:
                    return _with_resolution(item, alias_norm[normalized], "alias", 1.0)
            best = _best_fuzzy_match(normalized_names, fuzzy_index)
            if best and best[1] >= FUZZY_MATCH_MIN:
                return _with_resolution(item, best[2], "fuzzy", round(best[1], 4))
            payload = item.model_dump()
            payload.update(resolution="new", match_score=round(best[1], 4) if best else 0.0)
            return Competency.model_validate(payload)

    def save_competency(self, item: Competency, *, source_note: str = "curriculum_repo") -> CompetencyLinkResult:
        skill = self.upsert_skill(item.canonical_name, aliases=item.aliases, alias_source=source_note)
        return self.ensure_skill_competency_link(
            skill.skill_id,
            skill_name=skill.canonical_name,
            competency_title=item.group or item.coverage_area or DEFAULT_COMPETENCY_TITLE,
            indicators=item.indicators,
            source_note=source_note,
        )

    def ensure_skill_competency_link(
        self,
        skill_id: int,
        *,
        skill_name: str,
        competency_title: str | None,
        indicators: Iterable[CompetencyIndicator | dict[str, Any]] | None = None,
        source_note: str = "intake_accept",
    ) -> CompetencyLinkResult:
        with self._connect() as con:
            if self._get_skill(con, skill_id) is None:
                return CompetencyLinkResult(status="missing_skill", skill_id=skill_id)
            context = self._ensure_catalog_context(con)
            competency_id, created_competency, clean_title, competency_status = self._ensure_competency(
                con,
                _clean_title(competency_title, DEFAULT_COMPETENCY_TITLE),
            )
            needs_review = competency_status != "active"
            review_state = "needs_review" if needs_review else "accepted"
            created_review = (
                self.enqueue_review(
                    entity_type="competency",
                    entity_id=competency_id,
                    source_ref=source_note,
                    reason_code="new_competency_candidate",
                    severity="warning",
                    details=f"Intake создал новую competency-кандидат «{clean_title}». Требуется проверка методологом.",
                    _connection=con,
                )
                is not None
                if needs_review
                else False
            )
            source_block_id = self._ensure_source_block(con, context.source_sheet_id, clean_title)
            profile_competency_id, created_profile_competency = self._ensure_profile_competency(
                con,
                profile_id=context.profile_id,
                competency_id=competency_id,
                source_block_id=source_block_id,
                title=clean_title,
                review_state=review_state,
            )
            competency_skill_id, created_competency_skill = self._ensure_competency_skill(
                con,
                profile_competency_id=profile_competency_id,
                skill_id=skill_id,
                skill_name=skill_name,
                review_state=review_state,
            )
            created_rows = self._ensure_indicators(con, competency_skill_id, indicators, source_note)
            return CompetencyLinkResult(
                status="linked",
                skill_id=skill_id,
                competency_id=competency_id,
                profile_competency_id=profile_competency_id,
                competency_skill_id=competency_skill_id,
                created_competency=created_competency,
                created_profile_competency=created_profile_competency,
                created_competency_skill=created_competency_skill,
                needs_methodologist_review=needs_review,
                created_review=created_review,
                created_indicator_rows=created_rows,
            )

    def list_skill_competency_links(self, skill_id: int) -> list[dict[str, object]]:
        with self._connect() as con:
            stmt = (
                sa.select(
                    COMPETENCY_SKILL.c.id.label("competency_skill_id"),
                    COMPETENCY_SKILL.c.review_state.label("competency_skill_state"),
                    COMPETENCY_SKILL.c.skill_order,
                    PROFILE_COMPETENCY.c.id.label("profile_competency_id"),
                    PROFILE_COMPETENCY.c.review_state.label("profile_competency_state"),
                    COMPETENCY.c.id.label("competency_id"),
                    COMPETENCY.c.title.label("competency_title"),
                    COMPETENCY.c.status.label("competency_status"),
                    PROFILE.c.id.label("profile_id"),
                    PROFILE.c.name.label("profile_name"),
                    sa.func.count(INDICATOR_ROW.c.id).label("indicator_row_count"),
                )
                .select_from(
                    COMPETENCY_SKILL.join(PROFILE_COMPETENCY, PROFILE_COMPETENCY.c.id == COMPETENCY_SKILL.c.profile_competency_id)
                    .join(COMPETENCY, COMPETENCY.c.id == PROFILE_COMPETENCY.c.competency_id)
                    .join(PROFILE, PROFILE.c.id == PROFILE_COMPETENCY.c.profile_id)
                    .outerjoin(INDICATOR_ROW, INDICATOR_ROW.c.competency_skill_id == COMPETENCY_SKILL.c.id)
                )
                .where(COMPETENCY_SKILL.c.skill_id == skill_id)
                .group_by(COMPETENCY_SKILL.c.id, PROFILE_COMPETENCY.c.id, COMPETENCY.c.id, PROFILE.c.id)
                .order_by(PROFILE.c.name, COMPETENCY.c.title, COMPETENCY_SKILL.c.skill_order, COMPETENCY_SKILL.c.id)
            )
            return [dict(row) for row in con.execute(stmt).mappings().all()]

    def set_competency_review_status(self, competency_id: int, *, accepted: bool) -> dict[str, object]:
        status = "active" if accepted else "deprecated"
        review_state = "accepted" if accepted else "draft"
        with self._connect() as con:
            if _select_id(con, COMPETENCY, COMPETENCY.c.id == competency_id) is None:
                return {"status": "missing", "competency_id": competency_id}
            con.execute(COMPETENCY.update().where(COMPETENCY.c.id == competency_id).values(status=status))
            con.execute(PROFILE_COMPETENCY.update().where(PROFILE_COMPETENCY.c.competency_id == competency_id).values(review_state=review_state))
            con.execute(
                COMPETENCY_SKILL.update()
                .where(
                    COMPETENCY_SKILL.c.profile_competency_id.in_(
                        sa.select(PROFILE_COMPETENCY.c.id).where(PROFILE_COMPETENCY.c.competency_id == competency_id)
                    )
                )
                .values(review_state=review_state)
            )
            return {"status": "accepted" if accepted else "rejected", "competency_id": competency_id}

    def enqueue_review(
        self,
        *,
        entity_type: str,
        entity_id: int | None,
        source_ref: str | None,
        reason_code: str,
        severity: ReviewSeverity = "info",
        details: str | dict[str, Any] = "",
        _connection: Connection | None = None,
    ) -> int | None:
        details_text = json.dumps(details, ensure_ascii=False) if isinstance(details, dict) else details
        con_cm = self._connect() if _connection is None else _existing_connection(_connection)
        with con_cm as con:
            existing = con.execute(
                sa.select(REVIEW_QUEUE.c.id)
                .where(
                    REVIEW_QUEUE.c.entity_type == entity_type,
                    REVIEW_QUEUE.c.entity_id == entity_id,
                    REVIEW_QUEUE.c.reason_code == reason_code,
                    REVIEW_QUEUE.c.status == "open",
                )
                .order_by(REVIEW_QUEUE.c.id)
                .limit(1)
            ).scalar_one_or_none()
            if existing is not None:
                return None
            return _insert_id(
                con,
                REVIEW_QUEUE.insert().values(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    source_ref=source_ref,
                    reason_code=reason_code,
                    severity=severity,
                    details=details_text,
                    status="open",
                ),
            )

    def list_review_queue(self, *, status: ReviewStatus | None = "open", limit: int = 100) -> list[dict[str, object]]:
        with self._connect() as con:
            stmt = REVIEW_QUEUE.select().order_by(REVIEW_QUEUE.c.id).limit(limit)
            if status is not None:
                stmt = stmt.where(REVIEW_QUEUE.c.status == status)
            return [dict(row) for row in con.execute(stmt).mappings().all()]

    def resolve_review_item(self, review_id: int, *, status: Literal["resolved", "ignored"], note: str = "") -> bool:
        now = datetime.now(UTC)
        with self._connect() as con:
            result = con.execute(
                REVIEW_QUEUE.update()
                .where(REVIEW_QUEUE.c.id == review_id)
                .values(status=status, resolution_note=note, reviewed_at=now, updated_at=now)
            )
            return result.rowcount > 0

    def ensure_dimensions(self) -> None:
        with self._connect() as con:
            for code, title in DIMENSION_TITLES.items():
                if _select_id(con, DIMENSION, DIMENSION.c.code == code) is None:
                    con.execute(DIMENSION.insert().values(code=code, title=title))

    @contextmanager
    def _connect(self) -> Iterator[Connection]:
        if isinstance(self.bind, Engine):
            with self.bind.begin() as connection:
                yield connection
        else:
            yield self.bind

    def _get_skill(self, con: Connection, skill_id: int) -> CatalogSkill | None:
        row = con.execute(SKILL.select().where(SKILL.c.id == skill_id)).mappings().first()
        return self._skill_from_row(con, row) if row else None

    def _skill_from_row(self, con: Connection, row: sa.RowMapping) -> CatalogSkill:
        aliases = tuple(
            con.execute(
                sa.select(SKILL_ALIAS.c.alias).where(SKILL_ALIAS.c.skill_id == int(row["id"])).order_by(SKILL_ALIAS.c.id)
            ).scalars()
        )
        return CatalogSkill(
            skill_id=int(row["id"]),
            canonical_name=str(row["canonical_name"]),
            normalized_name=str(row["normalized_name"]),
            skill_type=str(row["skill_type"] or "unknown"),
            status=str(row["status"] or "active"),  # type: ignore[arg-type]
            aliases=aliases,
        )

    def _ensure_skill_alias(self, con: Connection, skill_id: int, alias: object, source: str) -> bool:
        clean_alias = _clean_title(alias, fallback="")
        normalized_alias = normalize_catalog_key(clean_alias)
        if not normalized_alias:
            return False
        existing = con.execute(
            sa.select(SKILL_ALIAS.c.id).where(
                SKILL_ALIAS.c.skill_id == skill_id,
                SKILL_ALIAS.c.normalized_alias == normalized_alias,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return False
        con.execute(
            SKILL_ALIAS.insert().values(
                skill_id=skill_id,
                alias=clean_alias,
                normalized_alias=normalized_alias,
                source=source,
            )
        )
        return True

    def _load_resolution_index(
        self,
        con: Connection,
    ) -> tuple[dict[str, CatalogSkill], dict[str, CatalogSkill], dict[str, CatalogSkill]]:
        skills = {
            row["id"]: self._skill_from_row(con, row)
            for row in con.execute(SKILL.select().where(SKILL.c.status == "active")).mappings().all()
        }
        by_norm = {skill.normalized_name: skill for skill in skills.values()}
        alias_norm: dict[str, CatalogSkill] = {}
        for row in con.execute(SKILL_ALIAS.select().order_by(SKILL_ALIAS.c.id)).mappings().all():
            skill = skills.get(row["skill_id"])
            if skill is not None:
                alias_norm[str(row["normalized_alias"])] = skill
        return by_norm, alias_norm, {**by_norm, **alias_norm}

    def _ensure_catalog_context(self, con: Connection) -> CatalogContext:
        ingest_run_id = _ensure_row(
            con,
            INGEST_RUN,
            [INGEST_RUN.c.source_root == SERVICE_SOURCE_ROOT, INGEST_RUN.c.status == "completed"],
            source_root=SERVICE_SOURCE_ROOT,
            status="completed",
            summary_json={"source": "curriculum_repo"},
            finished_at=datetime.now(UTC),
        )
        workbook_id = _ensure_row(
            con,
            SOURCE_WORKBOOK,
            [SOURCE_WORKBOOK.c.ingest_run_id == ingest_run_id, SOURCE_WORKBOOK.c.file_path == SERVICE_WORKBOOK_PATH],
            ingest_run_id=ingest_run_id,
            file_path=SERVICE_WORKBOOK_PATH,
            file_name=SERVICE_WORKBOOK_NAME,
            sha256="service-generated",
            last_modified_utc=datetime.now(UTC),
            source_kind="draft",
        )
        sheet_id = _ensure_row(
            con,
            SOURCE_SHEET,
            [SOURCE_SHEET.c.source_workbook_id == workbook_id, SOURCE_SHEET.c.sheet_order == 1],
            source_workbook_id=workbook_id,
            sheet_name=SERVICE_SHEET_NAME,
            sheet_order=1,
            is_skipped=0,
        )
        profile_id = _ensure_row(
            con,
            PROFILE,
            [PROFILE.c.slug == SERVICE_PROFILE_SLUG],
            slug=SERVICE_PROFILE_SLUG,
            name=SERVICE_PROFILE_NAME,
            source_kind="draft",
            notes="Служебный профиль для подтвержденных intake-навыков.",
        )
        _ensure_row(
            con,
            PROFILE_SOURCE,
            [PROFILE_SOURCE.c.profile_id == profile_id, PROFILE_SOURCE.c.source_workbook_id == workbook_id],
            profile_id=profile_id,
            source_workbook_id=workbook_id,
            version_label="live",
            is_primary=1,
        )
        return CatalogContext(ingest_run_id, workbook_id, sheet_id, profile_id)

    def _ensure_competency(self, con: Connection, title: str) -> tuple[int, bool, str, str]:
        clean_title = _clean_title(title, DEFAULT_COMPETENCY_TITLE)
        normalized_title = normalize_catalog_key(clean_title)
        row = con.execute(sa.select(COMPETENCY.c.id, COMPETENCY.c.status).where(COMPETENCY.c.normalized_title == normalized_title)).mappings().first()
        if row:
            con.execute(COMPETENCY.update().where(COMPETENCY.c.id == row["id"]).values(title=clean_title))
            return int(row["id"]), False, clean_title, str(row["status"] or "candidate")
        competency_id = _insert_id(
            con,
            COMPETENCY.insert().values(
                normalized_title=normalized_title,
                title=clean_title,
                description="Кандидат создан автоматически при подтверждении нового навыка из intake.",
                status="candidate",
            ),
        )
        return competency_id, True, clean_title, "candidate"

    def _ensure_source_block(self, con: Connection, source_sheet_id: int, competency_title: str) -> int:
        existing = con.execute(
            sa.select(SOURCE_BLOCK.c.id)
            .where(SOURCE_BLOCK.c.source_sheet_id == source_sheet_id, SOURCE_BLOCK.c.raw_title == competency_title)
            .order_by(SOURCE_BLOCK.c.id)
            .limit(1)
        ).scalar_one_or_none()
        if existing is not None:
            return int(existing)
        next_no = _next_int(con, SOURCE_BLOCK.c.block_no, SOURCE_BLOCK.c.source_sheet_id == source_sheet_id, step=10)
        return _insert_id(
            con,
            SOURCE_BLOCK.insert().values(
                source_sheet_id=source_sheet_id,
                block_no=next_no,
                header_row_number=next_no,
                raw_title=competency_title,
                raw_description="Служебный блок intake для подтвержденных навыков.",
            ),
        )

    def _ensure_profile_competency(
        self,
        con: Connection,
        *,
        profile_id: int,
        competency_id: int,
        source_block_id: int,
        title: str,
        review_state: str,
    ) -> tuple[int, bool]:
        existing = con.execute(
            sa.select(PROFILE_COMPETENCY.c.id, PROFILE_COMPETENCY.c.review_state)
            .where(PROFILE_COMPETENCY.c.profile_id == profile_id, PROFILE_COMPETENCY.c.competency_id == competency_id)
            .order_by(PROFILE_COMPETENCY.c.id)
            .limit(1)
        ).mappings().first()
        if existing:
            final_state = "accepted" if existing["review_state"] == "accepted" else review_state
            con.execute(
                PROFILE_COMPETENCY.update()
                .where(PROFILE_COMPETENCY.c.id == existing["id"])
                .values(title_in_source=title, review_state=final_state)
            )
            return int(existing["id"]), False
        sort_order = _next_int(con, PROFILE_COMPETENCY.c.sort_order, PROFILE_COMPETENCY.c.profile_id == profile_id, step=10)
        return (
            _insert_id(
                con,
                PROFILE_COMPETENCY.insert().values(
                    profile_id=profile_id,
                    competency_id=competency_id,
                    source_block_id=source_block_id,
                    title_in_source=title,
                    sort_order=sort_order,
                    review_state=review_state,
                ),
            ),
            True,
        )

    def _ensure_competency_skill(
        self,
        con: Connection,
        *,
        profile_competency_id: int,
        skill_id: int,
        skill_name: str,
        review_state: str,
    ) -> tuple[int, bool]:
        existing = con.execute(
            sa.select(COMPETENCY_SKILL.c.id, COMPETENCY_SKILL.c.review_state)
            .where(COMPETENCY_SKILL.c.profile_competency_id == profile_competency_id, COMPETENCY_SKILL.c.skill_id == skill_id)
            .order_by(COMPETENCY_SKILL.c.id)
            .limit(1)
        ).mappings().first()
        if existing:
            final_state = "accepted" if existing["review_state"] == "accepted" else review_state
            con.execute(
                COMPETENCY_SKILL.update()
                .where(COMPETENCY_SKILL.c.id == existing["id"])
                .values(source_skill_name=skill_name, review_state=final_state)
            )
            return int(existing["id"]), False
        skill_order = _next_int(con, COMPETENCY_SKILL.c.skill_order, COMPETENCY_SKILL.c.profile_competency_id == profile_competency_id, step=10)
        return (
            _insert_id(
                con,
                COMPETENCY_SKILL.insert().values(
                    profile_competency_id=profile_competency_id,
                    skill_id=skill_id,
                    source_skill_name=skill_name,
                    skill_order=skill_order,
                    review_state=review_state,
                ),
            ),
            True,
        )

    def _ensure_indicators(
        self,
        con: Connection,
        competency_skill_id: int,
        indicators: Iterable[CompetencyIndicator | dict[str, Any]] | None,
        source_note: str,
    ) -> int:
        created = 0
        for indicator in indicators or []:
            payload = indicator.model_dump() if isinstance(indicator, CompetencyIndicator) else dict(indicator)
            text = " ".join(str(payload.get("text") or "").split())
            if not text:
                continue
            dimension_code = BLOOM_TO_DIMENSION.get(str(payload.get("bloom") or "").lower(), "unspecified")
            dimension_id = _ensure_dimension(con, dimension_code)
            row_id, row_created = _ensure_indicator_row(con, competency_skill_id, dimension_id, text, source_note)
            if row_created:
                created += 1
            _ensure_indicator_level_cell(con, row_id, _level_label_for_dimension(dimension_code), text)
        return created


@contextmanager
def _existing_connection(connection: Connection) -> Iterator[Connection]:
    yield connection


def _candidate_names(item: Competency) -> list[str]:
    names = [item.canonical_name, *(item.aliases or [])]
    if item.source_name:
        names.append(item.source_name)
    return list(dict.fromkeys(name for name in names if str(name).strip()))


def _with_resolution(item: Competency, skill: CatalogSkill, resolution: str, score: float) -> Competency:
    payload = item.model_dump()
    payload.update(
        catalog_id=skill.skill_id,
        canonical_name=skill.canonical_name,
        resolution=resolution,
        match_score=score,
        aliases=list(dict.fromkeys([item.canonical_name, *item.aliases, *skill.aliases])),
    )
    return Competency.model_validate(payload)


def _best_fuzzy_match(
    normalized_names: list[str],
    fuzzy_index: dict[str, CatalogSkill],
) -> tuple[str, float, CatalogSkill] | None:
    best: tuple[str, float, CatalogSkill] | None = None
    for normalized in normalized_names:
        for candidate, skill in fuzzy_index.items():
            score = difflib.SequenceMatcher(None, normalized, candidate).ratio()
            if best is None or score > best[1]:
                best = (candidate, score, skill)
    return best


def _clean_title(value: object | None, fallback: str = DEFAULT_COMPETENCY_TITLE) -> str:
    clean = " ".join(str(value or "").split()).strip(" .,-:;")
    return clean or fallback


def _insert_id(con: Connection, stmt: sa.Insert) -> int:
    result = con.execute(stmt)
    if result.inserted_primary_key and result.inserted_primary_key[0] is not None:
        return int(result.inserted_primary_key[0])
    return int(con.execute(sa.select(sa.func.max(stmt.table.c.id))).scalar_one())


def _select_id(con: Connection, table: sa.Table, *conditions: sa.ColumnElement[bool]) -> int | None:
    value = con.execute(sa.select(table.c.id).where(*conditions).order_by(table.c.id).limit(1)).scalar_one_or_none()
    return int(value) if value is not None else None


def _ensure_row(con: Connection, table: sa.Table, conditions: list[sa.ColumnElement[bool]], **values: object) -> int:
    existing_id = _select_id(con, table, *conditions)
    if existing_id is not None:
        return existing_id
    return _insert_id(con, table.insert().values(**values))


def _next_int(con: Connection, column: sa.Column[int], condition: sa.ColumnElement[bool], *, step: int = 1) -> int:
    current = con.execute(sa.select(sa.func.max(column)).where(condition)).scalar_one_or_none()
    return int(current or 0) + step


def _ensure_dimension(con: Connection, code: str) -> int:
    safe_code = code if code in DIMENSION_TITLES else "unspecified"
    existing = _select_id(con, DIMENSION, DIMENSION.c.code == safe_code)
    if existing is not None:
        return existing
    return _insert_id(con, DIMENSION.insert().values(code=safe_code, title=DIMENSION_TITLES[safe_code]))


def _ensure_indicator_row(
    con: Connection,
    competency_skill_id: int,
    dimension_id: int,
    text: str,
    source_note: str,
) -> tuple[int, bool]:
    existing = con.execute(
        sa.select(INDICATOR_ROW.c.id)
        .where(
            INDICATOR_ROW.c.competency_skill_id == competency_skill_id,
            INDICATOR_ROW.c.dimension_id == dimension_id,
            INDICATOR_ROW.c.base_text == text,
        )
        .order_by(INDICATOR_ROW.c.id)
        .limit(1)
    ).scalar_one_or_none()
    if existing is not None:
        return int(existing), False
    row_number = _next_int(con, INDICATOR_ROW.c.source_row_number, INDICATOR_ROW.c.competency_skill_id == competency_skill_id)
    row_id = _insert_id(
        con,
        INDICATOR_ROW.insert().values(
            competency_skill_id=competency_skill_id,
            dimension_id=dimension_id,
            source_row_number=row_number,
            inherited_skill=0,
            inherited_dimension=0,
            base_text=text,
            notes=source_note,
        ),
    )
    return row_id, True


def _ensure_indicator_level_cell(con: Connection, indicator_row_id: int, raw_level_label: str, raw_value: str) -> bool:
    existing = con.execute(
        sa.select(INDICATOR_LEVEL_CELL.c.id)
        .where(
            INDICATOR_LEVEL_CELL.c.indicator_row_id == indicator_row_id,
            INDICATOR_LEVEL_CELL.c.raw_level_label == raw_level_label,
            INDICATOR_LEVEL_CELL.c.raw_value == raw_value,
        )
        .order_by(INDICATOR_LEVEL_CELL.c.id)
        .limit(1)
    ).scalar_one_or_none()
    if existing is not None:
        return False
    sort_order = _next_int(con, INDICATOR_LEVEL_CELL.c.sort_order, INDICATOR_LEVEL_CELL.c.indicator_row_id == indicator_row_id)
    con.execute(
        INDICATOR_LEVEL_CELL.insert().values(
            indicator_row_id=indicator_row_id,
            raw_level_label=raw_level_label,
            raw_value=raw_value,
            value_kind="text",
            sort_order=sort_order,
        )
    )
    return True


def _level_label_for_dimension(dimension_code: str) -> str:
    if dimension_code == "knowledge":
        return "Знает"
    if dimension_code == "ability":
        return "Умеет"
    return "Владеет"
