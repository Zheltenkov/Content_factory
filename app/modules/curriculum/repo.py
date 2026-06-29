"""Repository layer for curriculum/reference catalog tables.

This is the only runtime module that owns SQL for the catalog schema. Pipeline
stages pass typed core models in and out; storage details stay here.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
import difflib
from functools import lru_cache
import json
import re
import unicodedata
from typing import Any, Literal, cast
from collections.abc import Iterable, Iterator

import sqlalchemy as sa
from sqlalchemy.engine import Connection, Engine

from app.core.config import get_settings
from app.core.models import Competency, CompetencyIndicator, CurriculumContext, UPProject, UPSkeleton

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
CURRICULUM_ALIAS_FIELD_TO_COLUMN = {
    "block_name": "block_name",
    "block_goals": "block_goals",
    "order": "project_order",
    "title": "title",
    "description": "description",
    "expert_notes": "expert_notes",
    "learning_outcomes": "learning_outcomes",
    "skills": "skills",
    "audience_level": "audience_level",
    "required_tools": "required_tools",
    "sjm": "sjm",
    "storytelling_type": "storytelling_type",
    "format": "format",
    "additional_materials": "additional_materials",
    "group_size": "group_size",
    "workload_hours": "workload_hours",
    "workload_days": "workload_days",
    "total_workload_days": "total_workload_days",
    "xp": "xp",
    "passing_threshold": "passing_threshold",
    "required_software": "required_software",
    "platform_name": "platform_name",
    "gitlab_link": "gitlab_link",
}
CURRICULUM_PROJECT_COLUMNS = tuple(CURRICULUM_ALIAS_FIELD_TO_COLUMN.values())

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
    sa.Column("status", sa.Text(), nullable=False, server_default="active"),
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
CURRICULUM_PLAN = sa.Table(
    "curriculum_plan",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("profile_id", sa.Integer(), sa.ForeignKey("profile.id", ondelete="SET NULL")),
    sa.Column("source_policy", sa.Text(), nullable=False, server_default="accepted_only"),
    sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
    sa.Column("title", sa.Text(), nullable=False),
    sa.Column("direction", sa.Text(), nullable=False, server_default=""),
    sa.Column("version", sa.Text(), nullable=False, server_default="v1"),
    sa.Column("author_ref", sa.Text()),
    sa.Column("total_blocks", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("total_projects", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("total_hours", sa.Float(), nullable=False, server_default="0"),
    sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    sa.CheckConstraint("status IN ('built', 'deferred', 'draft', 'invalid', 'archived')", name="ck_curriculum_plan_status"),
)
CURRICULUM_PROJECT = sa.Table(
    "curriculum_project",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("plan_id", sa.Integer(), sa.ForeignKey("curriculum_plan.id", ondelete="CASCADE"), nullable=False),
    sa.Column("row_number", sa.Integer(), nullable=False),
    sa.Column("block_index", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("project_index_in_block", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("block_name", sa.Text()),
    sa.Column("block_goals", sa.Text()),
    sa.Column("project_order", sa.Integer(), nullable=False),
    sa.Column("title", sa.Text(), nullable=False),
    sa.Column("description", sa.Text()),
    sa.Column("expert_notes", sa.Text()),
    sa.Column("learning_outcomes", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    sa.Column("skills", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    sa.Column("audience_level", sa.Text()),
    sa.Column("required_tools", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    sa.Column("sjm", sa.Text()),
    sa.Column("storytelling_type", sa.Text()),
    sa.Column("format", sa.Text(), nullable=False, server_default="individual"),
    sa.Column("additional_materials", sa.Text()),
    sa.Column("group_size", sa.Integer(), nullable=False, server_default="1"),
    sa.Column("workload_hours", sa.Float(), nullable=False, server_default="0"),
    sa.Column("workload_days", sa.Float()),
    sa.Column("total_workload_days", sa.Float()),
    sa.Column("xp", sa.Integer()),
    sa.Column("passing_threshold", sa.Float()),
    sa.Column("required_software", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    sa.Column("platform_name", sa.Text()),
    sa.Column("gitlab_link", sa.Text()),
    sa.Column("outcomes_know", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    sa.Column("outcomes_can", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    sa.Column("outcomes_skills", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    sa.Column("competency_refs", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    sa.Column("artifacts_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    sa.CheckConstraint("project_order > 0", name="ck_curriculum_project_order_positive"),
    sa.CheckConstraint("group_size > 0", name="ck_curriculum_project_group_positive"),
    sa.UniqueConstraint("plan_id", "row_number", name="uq_curriculum_project_plan_row"),
)
sa.Index("idx_curriculum_plan_profile_status", CURRICULUM_PLAN.c.profile_id, CURRICULUM_PLAN.c.status)
sa.Index("idx_curriculum_plan_updated", CURRICULUM_PLAN.c.updated_at)
sa.Index("idx_curriculum_project_plan_order", CURRICULUM_PROJECT.c.plan_id, CURRICULUM_PROJECT.c.project_order)
sa.Index("idx_curriculum_project_block", CURRICULUM_PROJECT.c.plan_id, CURRICULUM_PROJECT.c.block_name, CURRICULUM_PROJECT.c.project_order)

PROFILE_BRIEF = sa.Table(
    "profile_brief",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("raw_text", sa.Text(), nullable=False),
    sa.Column("role", sa.Text()),
    sa.Column("seniority", sa.Text()),
    sa.Column("domain", sa.Text()),
    sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
)
INTAKE_JOB = sa.Table(
    "intake_job",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("brief_id", sa.Integer(), sa.ForeignKey("profile_brief.id", ondelete="SET NULL")),
    sa.Column("source_kind", sa.Text(), nullable=False),
    sa.Column("source_name", sa.Text()),
    sa.Column("file_path", sa.Text()),
    sa.Column("brief_text", sa.Text(), nullable=False),
    sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
    sa.Column("current_stage", sa.Text()),
    sa.Column("progress_note", sa.Text()),
    sa.Column("error_text", sa.Text()),
    sa.Column("result_payload", sa.JSON()),
    sa.Column("use_council", sa.Integer(), nullable=False, server_default="1"),
    sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    sa.Column("started_at", sa.DateTime()),
    sa.Column("finished_at", sa.DateTime()),
    sa.CheckConstraint("source_kind IN ('text', 'file')", name="ck_intake_job_source_kind"),
    sa.CheckConstraint("status IN ('pending', 'running', 'succeeded', 'failed')", name="ck_intake_job_status"),
)
sa.Index("idx_intake_job_created", INTAKE_JOB.c.created_at)
sa.Index("idx_intake_job_status", INTAKE_JOB.c.status, INTAKE_JOB.c.created_at)
CURRICULUM_ARTIFACT_TEMPLATE = sa.Table(
    "curriculum_artifact_template",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("code", sa.Text(), nullable=False, unique=True),
    sa.Column("title", sa.Text(), nullable=False),
    sa.Column("artifact_family", sa.Text(), nullable=False),
    sa.Column("artifact_description", sa.Text(), nullable=False),
    sa.Column("project_name_pattern", sa.Text()),
    sa.Column("materials_pattern", sa.Text()),
    sa.Column("storytelling_pattern", sa.Text()),
    sa.Column("validation_criteria", sa.Text()),
    sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
    sa.Column("status", sa.Text(), nullable=False, server_default="active"),
    sa.Column("source", sa.Text(), nullable=False, server_default="manual"),
    sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    sa.Column("updated_at", sa.DateTime()),
    sa.CheckConstraint("artifact_family IN ('analysis','document','configuration','design','production','practice')", name="ck_artifact_template_family"),
    sa.CheckConstraint("status IN ('active','draft','deprecated')", name="ck_artifact_template_status"),
)
CURRICULUM_ARTIFACT_TEMPLATE_SCOPE = sa.Table(
    "curriculum_artifact_template_scope",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("template_id", sa.Integer(), sa.ForeignKey("curriculum_artifact_template.id", ondelete="CASCADE"), nullable=False),
    sa.Column("scope_type", sa.Text(), nullable=False),
    sa.Column("scope_id", sa.Integer()),
    sa.Column("scope_name", sa.Text()),
    sa.Column("normalized_scope_name", sa.Text()),
    sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
    sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    sa.CheckConstraint("scope_type IN ('taxonomy_node','skill_group','coverage_area','any')", name="ck_artifact_template_scope_type"),
    sa.UniqueConstraint("template_id", "scope_type", "scope_id", "normalized_scope_name", name="uq_artifact_template_scope"),
)
CURRICULUM_ARTIFACT_TEMPLATE_PROPOSAL = sa.Table(
    "curriculum_artifact_template_proposal",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("brief_id", sa.Integer(), sa.ForeignKey("profile_brief.id", ondelete="CASCADE"), nullable=False),
    sa.Column("plan_id", sa.Integer(), sa.ForeignKey("curriculum_plan.id", ondelete="SET NULL")),
    sa.Column("status", sa.Text(), nullable=False, server_default="open"),
    sa.Column("code", sa.Text(), nullable=False),
    sa.Column("title", sa.Text(), nullable=False),
    sa.Column("artifact_family", sa.Text(), nullable=False),
    sa.Column("scope_type", sa.Text(), nullable=False, server_default="coverage_area"),
    sa.Column("scope_names_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    sa.Column("artifact_description", sa.Text(), nullable=False),
    sa.Column("project_name_pattern", sa.Text()),
    sa.Column("materials_pattern", sa.Text()),
    sa.Column("storytelling_pattern", sa.Text()),
    sa.Column("validation_criteria", sa.Text()),
    sa.Column("covered_skill_ids_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    sa.Column("covered_skill_names_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    sa.Column("rationale", sa.Text()),
    sa.Column("confidence", sa.Float(), nullable=False, server_default="0.75"),
    sa.Column("source", sa.Text(), nullable=False, server_default="deterministic_proposer"),
    sa.Column("accepted_template_id", sa.Integer(), sa.ForeignKey("curriculum_artifact_template.id", ondelete="SET NULL")),
    sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    sa.Column("updated_at", sa.DateTime()),
    sa.CheckConstraint("status IN ('open','accepted','rejected')", name="ck_artifact_template_proposal_status"),
    sa.CheckConstraint("artifact_family IN ('analysis','document','configuration','design','production','practice')", name="ck_artifact_template_proposal_family"),
    sa.CheckConstraint("scope_type IN ('taxonomy_node','skill_group','coverage_area','any')", name="ck_artifact_template_proposal_scope"),
    sa.UniqueConstraint("brief_id", "code", name="uq_artifact_template_proposal_brief_code"),
)
sa.Index("idx_artifact_template_status", CURRICULUM_ARTIFACT_TEMPLATE.c.status, CURRICULUM_ARTIFACT_TEMPLATE.c.artifact_family, CURRICULUM_ARTIFACT_TEMPLATE.c.priority)
sa.Index("idx_artifact_template_scope", CURRICULUM_ARTIFACT_TEMPLATE_SCOPE.c.scope_type, CURRICULUM_ARTIFACT_TEMPLATE_SCOPE.c.normalized_scope_name)
sa.Index("idx_artifact_template_proposal_brief", CURRICULUM_ARTIFACT_TEMPLATE_PROPOSAL.c.brief_id, CURRICULUM_ARTIFACT_TEMPLATE_PROPOSAL.c.status, CURRICULUM_ARTIFACT_TEMPLATE_PROPOSAL.c.id)


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


@dataclass(frozen=True)
class CompetencyMatch:
    competency_id: int
    title: str
    status: str
    match_type: Literal["title", "alias", "provenance"]
    matched_name: str


@dataclass(frozen=True)
class CurriculumPlanSaveResult:
    plan_id: int
    project_count: int


@dataclass(frozen=True)
class CurriculumProjectRecord:
    project_id: int
    plan_id: int
    row_number: int
    project: UPProject


@lru_cache
def _default_engine() -> Engine:
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required for curriculum repository")
    return sa.create_engine(_psycopg_url(settings.database_url), pool_pre_ping=True)


def default_curriculum_repo() -> "CurriculumCatalogRepo":
    return CurriculumCatalogRepo(_default_engine())


def create_catalog_schema(bind: Engine | Connection) -> None:
    """Create the catalog table subset used by this repo in tests/dev DBs."""
    metadata.create_all(bind)
    repo = CurriculumCatalogRepo(bind)
    repo.ensure_dimensions()


def normalize_catalog_key(value: object | None) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold().replace("ё", "е")
    text = re.sub(r"[^0-9a-zа-я+ ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _psycopg_url(url: str) -> str:
    return "postgresql+psycopg://" + url.removeprefix("postgresql://") if url.startswith("postgresql://") else url


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
            skill = self._get_skill(con, skill_id)
            assert skill is not None  # just upserted/updated above
            return skill

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

    def get_reference_skill(self, skill_id: int) -> dict[str, object] | None:
        """Return one catalog skill with aliases, competency links and editable indicators."""
        with self._connect() as con:
            skill = self._get_skill(con, skill_id)
            if skill is None:
                return None
            links = self._skill_links(con, skill_id)
            return {
                "skill_id": skill.skill_id,
                "canonical_name": skill.canonical_name,
                "normalized_name": skill.normalized_name,
                "skill_type": skill.skill_type,
                "status": skill.status,
                "aliases": list(skill.aliases),
                "links": links,
                "indicators": [indicator for link in links for indicator in cast("list[Any]", link["indicators"])],
            }

    def create_group_skill(
        self,
        competency_id: int,
        *,
        canonical_name: str,
        skill_type: str = "unknown",
        status: CatalogStatus = "active",
        aliases: Iterable[str] = (),
    ) -> dict[str, object] | None:
        """Create or reuse a skill and attach it to a competency group."""
        with self._connect() as con:
            competency = con.execute(COMPETENCY.select().where(COMPETENCY.c.id == competency_id)).mappings().first()
            competency_title = str(competency["title"]) if competency is not None else ""
        if not competency_title:
            return None
        skill = self.upsert_skill(canonical_name, skill_type=skill_type, status=status, aliases=aliases, alias_source="reference-ui")
        self.ensure_skill_competency_link(
            skill.skill_id,
            skill_name=skill.canonical_name,
            competency_title=competency_title,
            indicators=None,
            source_note="reference-ui",
        )
        return self.get_reference_skill(skill.skill_id)

    def create_reference_indicator(
        self,
        skill_id: int,
        *,
        text: str,
        dimension_code: str = "unspecified",
        notes: str = "reference-ui",
    ) -> dict[str, object] | None:
        clean_text = _clean_title(text, fallback="")
        if not clean_text:
            return None
        with self._connect() as con:
            link_id = self._first_competency_skill_id(con, skill_id)
            skill = self._get_skill(con, skill_id)
        if skill is None:
            return None
        if link_id is None:
            created = self.ensure_skill_competency_link(
                skill.skill_id,
                skill_name=skill.canonical_name,
                competency_title=DEFAULT_COMPETENCY_TITLE,
                indicators=None,
                source_note="reference-ui",
            )
            link_id = created.competency_skill_id
        if link_id is None:
            return None
        with self._connect() as con:
            dimension_id = _ensure_dimension(con, dimension_code)
            row_id, _created = _ensure_indicator_row(con, link_id, dimension_id, clean_text, notes)
            _ensure_indicator_level_cell(con, row_id, _level_label_for_dimension(dimension_code), clean_text)
            return self._reference_indicator(con, row_id)

    def update_reference_indicator(
        self,
        indicator_id: int,
        *,
        text: str | None = None,
        dimension_code: str | None = None,
        notes: str | None = None,
    ) -> dict[str, object] | None:
        with self._connect() as con:
            row = con.execute(INDICATOR_ROW.select().where(INDICATOR_ROW.c.id == indicator_id)).mappings().first()
            if row is None:
                return None
            values: dict[str, object] = {}
            if text is not None:
                clean_text = _clean_title(text, fallback="")
                if clean_text:
                    values["base_text"] = clean_text
            if dimension_code is not None:
                values["dimension_id"] = _ensure_dimension(con, dimension_code)
            if notes is not None:
                values["notes"] = notes
            if values:
                con.execute(INDICATOR_ROW.update().where(INDICATOR_ROW.c.id == indicator_id).values(**values))
            return self._reference_indicator(con, indicator_id)

    def delete_reference_indicator(self, indicator_id: int) -> bool:
        with self._connect() as con:
            exists = con.execute(sa.select(INDICATOR_ROW.c.id).where(INDICATOR_ROW.c.id == indicator_id)).scalar_one_or_none()
            if exists is None:
                return False
            con.execute(INDICATOR_ROW.update().where(INDICATOR_ROW.c.id == indicator_id).values(status="deprecated"))
            return True

    def reference_archive(self, *, query: str = "", scope: str = "all", limit: int = 100) -> dict[str, object]:
        """Return archived catalog groups, skills and indicators for catalog-admin."""

        normalized_query = normalize_catalog_key(query)
        safe_scope = scope if scope in {"all", "groups", "skills", "indicators"} else "all"
        with self._connect() as con:
            groups = self._archived_groups(con, normalized_query, limit) if safe_scope in {"all", "groups"} else []
            skills = self._archived_skills(con, normalized_query, limit) if safe_scope in {"all", "skills"} else []
            indicators = self._archived_indicators(con, normalized_query, limit) if safe_scope in {"all", "indicators"} else []
            return {
                "query": query,
                "scope": safe_scope,
                "groups": groups,
                "skills": skills,
                "indicators": indicators,
                "counts": {"groups": len(groups), "skills": len(skills), "indicators": len(indicators)},
            }

    def restore_reference_archive_item(self, kind: Literal["group", "skill", "indicator"], item_id: int) -> dict[str, object]:
        """Restore an archived catalog item and required parent records."""

        with self._connect() as con:
            if kind == "group":
                row = con.execute(sa.select(COMPETENCY.c.id).where(COMPETENCY.c.id == item_id)).mappings().first()
                if row is None:
                    return {"status": "missing", "kind": kind, "id": item_id}
                con.execute(COMPETENCY.update().where(COMPETENCY.c.id == item_id).values(status="active"))
                return {"status": "restored", "kind": kind, "id": item_id}
            if kind == "skill":
                skill = con.execute(sa.select(SKILL.c.id).where(SKILL.c.id == item_id)).mappings().first()
                if skill is None:
                    return {"status": "missing", "kind": kind, "id": item_id}
                con.execute(SKILL.update().where(SKILL.c.id == item_id).values(status="active"))
                self._restore_skill_parents(con, item_id)
                return {"status": "restored", "kind": kind, "id": item_id}
            indicator = con.execute(sa.select(INDICATOR_ROW.c.id, INDICATOR_ROW.c.competency_skill_id).where(INDICATOR_ROW.c.id == item_id)).mappings().first()
            if indicator is None:
                return {"status": "missing", "kind": kind, "id": item_id}
            con.execute(INDICATOR_ROW.update().where(INDICATOR_ROW.c.id == item_id).values(status="active"))
            self._restore_competency_skill_parents(con, int(indicator["competency_skill_id"]))
            return {"status": "restored", "kind": kind, "id": item_id}

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

    def list_candidate_competencies(self, *, limit: int = 100) -> dict[str, object]:
        """Return candidate competency review workspace for the catalog-admin UI."""

        with self._connect() as con:
            profile_id = _select_id(con, PROFILE, PROFILE.c.slug == SERVICE_PROFILE_SLUG)
            if profile_id is None:
                return {"candidates": [], "competency_options": [], "open_count": 0}
            review_sq = (
                sa.select(
                    REVIEW_QUEUE.c.entity_id.label("competency_id"),
                    sa.func.min(REVIEW_QUEUE.c.id).label("review_id"),
                    sa.func.max(REVIEW_QUEUE.c.reason_code).label("reason_code"),
                    sa.func.max(REVIEW_QUEUE.c.details).label("details"),
                    sa.func.max(REVIEW_QUEUE.c.created_at).label("created_at"),
                )
                .where(REVIEW_QUEUE.c.entity_type == "competency", REVIEW_QUEUE.c.status == "open")
                .group_by(REVIEW_QUEUE.c.entity_id)
                .subquery()
            )
            stmt = (
                sa.select(
                    PROFILE_COMPETENCY.c.id.label("profile_competency_id"),
                    PROFILE_COMPETENCY.c.review_state,
                    COMPETENCY.c.id.label("competency_id"),
                    COMPETENCY.c.title,
                    COMPETENCY.c.status,
                    review_sq.c.review_id,
                    review_sq.c.reason_code,
                    review_sq.c.details,
                    review_sq.c.created_at,
                    sa.func.count(sa.distinct(COMPETENCY_SKILL.c.id)).label("skill_count"),
                )
                .select_from(
                    PROFILE_COMPETENCY.join(COMPETENCY, COMPETENCY.c.id == PROFILE_COMPETENCY.c.competency_id)
                    .outerjoin(COMPETENCY_SKILL, COMPETENCY_SKILL.c.profile_competency_id == PROFILE_COMPETENCY.c.id)
                    .outerjoin(review_sq, review_sq.c.competency_id == COMPETENCY.c.id)
                )
                .where(
                    PROFILE_COMPETENCY.c.profile_id == profile_id,
                    sa.or_(
                        PROFILE_COMPETENCY.c.review_state == "needs_review",
                        COMPETENCY.c.status == "candidate",
                        review_sq.c.review_id.is_not(None),
                    ),
                )
                .group_by(
                    PROFILE_COMPETENCY.c.id,
                    PROFILE_COMPETENCY.c.review_state,
                    COMPETENCY.c.id,
                    COMPETENCY.c.title,
                    COMPETENCY.c.status,
                    review_sq.c.review_id,
                    review_sq.c.reason_code,
                    review_sq.c.details,
                    review_sq.c.created_at,
                )
                .order_by(PROFILE_COMPETENCY.c.id.desc())
                .limit(limit)
            )
            candidates = []
            for row in con.execute(stmt).mappings().all():
                item = dict(row)
                item["profile_competency_id"] = int(item["profile_competency_id"])
                item["competency_id"] = int(item["competency_id"])
                item["review_id"] = int(item["review_id"]) if item["review_id"] is not None else None
                item["skill_count"] = int(item["skill_count"] or 0)
                item["skills"] = self._candidate_competency_skills(con, item["profile_competency_id"])
                similar = self._candidate_competency_similarity(con, item["competency_id"], item["profile_competency_id"])
                item["similar_competencies"] = similar
                item["nearest_competency"] = similar[0] if similar else None
                candidates.append(item)
            return {
                "candidates": candidates,
                "competency_options": self._candidate_competency_options(con),
                "open_count": sum(1 for item in candidates if item["review_state"] == "needs_review" or item["review_id"] is not None),
            }

    def rename_candidate_competency(self, competency_id: int, new_title: str) -> dict[str, object]:
        title = _clean_title(new_title, fallback="")
        if not title:
            return {"status": "empty_title", "competency_id": competency_id}
        normalized_title = normalize_catalog_key(title)
        with self._connect() as con:
            existing = con.execute(
                sa.select(COMPETENCY.c.id).where(COMPETENCY.c.normalized_title == normalized_title, COMPETENCY.c.id != competency_id)
            ).scalar_one_or_none()
            if existing is not None:
                return {"status": "conflict", "competency_id": competency_id, "target_competency_id": int(existing)}
            result = con.execute(
                COMPETENCY.update()
                .where(COMPETENCY.c.id == competency_id)
                .values(title=title, normalized_title=normalized_title)
            )
            if result.rowcount <= 0:
                return {"status": "missing", "competency_id": competency_id}
            con.execute(PROFILE_COMPETENCY.update().where(PROFILE_COMPETENCY.c.competency_id == competency_id).values(title_in_source=title))
            con.execute(
                SOURCE_BLOCK.update()
                .where(
                    SOURCE_BLOCK.c.id.in_(
                        sa.select(PROFILE_COMPETENCY.c.source_block_id).where(PROFILE_COMPETENCY.c.competency_id == competency_id)
                    )
                )
                .values(raw_title=title)
            )
            return {"status": "renamed", "competency_id": competency_id, "title": title}

    def resolve_candidate_competency(self, competency_id: int, action: Literal["accept", "reject", "review"], note: str = "") -> dict[str, object]:
        now = datetime.now(UTC)
        status_by_action = {"accept": "active", "reject": "deprecated", "review": "candidate"}
        state_by_action = {"accept": "accepted", "reject": "rejected", "review": "needs_review"}
        review_status = {"accept": "resolved", "reject": "ignored", "review": "open"}[action]
        with self._connect() as con:
            if _select_id(con, COMPETENCY, COMPETENCY.c.id == competency_id) is None:
                return {"status": "missing", "competency_id": competency_id}
            con.execute(COMPETENCY.update().where(COMPETENCY.c.id == competency_id).values(status=status_by_action[action]))
            pc_ids = [
                int(value)
                for value in con.execute(
                    sa.select(PROFILE_COMPETENCY.c.id).where(PROFILE_COMPETENCY.c.competency_id == competency_id)
                ).scalars()
            ]
            con.execute(
                PROFILE_COMPETENCY.update()
                .where(PROFILE_COMPETENCY.c.competency_id == competency_id)
                .values(review_state=state_by_action[action])
            )
            if pc_ids:
                con.execute(
                    COMPETENCY_SKILL.update()
                    .where(COMPETENCY_SKILL.c.profile_competency_id.in_(pc_ids))
                    .values(review_state=state_by_action[action])
                )
            update = (
                REVIEW_QUEUE.update()
                .where(REVIEW_QUEUE.c.entity_type == "competency", REVIEW_QUEUE.c.entity_id == competency_id)
                .values(
                    status=review_status,
                    resolution_note=note.strip() or None,
                    reviewed_at=None if action == "review" else now,
                    updated_at=now,
                )
            )
            result = con.execute(update)
            if action == "review" and result.rowcount <= 0:
                self.enqueue_review(
                    entity_type="competency",
                    entity_id=competency_id,
                    source_ref="reference-ui",
                    reason_code="candidate_reopened",
                    severity="warning",
                    details=note.strip() or "Кандидатная competency возвращена на проверку.",
                    _connection=con,
                )
            return {"status": action, "competency_id": competency_id}

    def move_candidate_competency_skill(self, competency_skill_id: int, target_competency_id: int) -> dict[str, object]:
        with self._connect() as con:
            return self._move_candidate_competency_skill(con, competency_skill_id, target_competency_id)

    def merge_candidate_competency(self, competency_id: int, target_competency_id: int) -> dict[str, object]:
        if competency_id == target_competency_id:
            return {"status": "same_competency", "competency_id": competency_id}
        with self._connect() as con:
            links = [
                int(value)
                for value in con.execute(
                    sa.select(COMPETENCY_SKILL.c.id)
                    .select_from(COMPETENCY_SKILL.join(PROFILE_COMPETENCY, PROFILE_COMPETENCY.c.id == COMPETENCY_SKILL.c.profile_competency_id))
                    .where(PROFILE_COMPETENCY.c.competency_id == competency_id)
                ).scalars()
            ]
            moved = 0
            for link_id in links:
                result = self._move_candidate_competency_skill(con, link_id, target_competency_id)
                if result.get("status") in {"moved", "deduplicated"}:
                    moved += 1
            con.execute(COMPETENCY.update().where(COMPETENCY.c.id == competency_id).values(status="deprecated"))
            self._resolve_candidate_review_queue(con, competency_id, "ignored", f"Слито с competency #{target_competency_id}.")
            return {"status": "merged", "competency_id": competency_id, "target_competency_id": target_competency_id, "moved": moved}

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

    def list_review_queue(
        self,
        *,
        status: ReviewStatus | None = "open",
        severity: str | None = None,
        reason_code: str | None = None,
        entity_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, object]]:
        with self._connect() as con:
            stmt = REVIEW_QUEUE.select().order_by(REVIEW_QUEUE.c.id).limit(limit)
            if status is not None:
                stmt = stmt.where(REVIEW_QUEUE.c.status == status)
            if severity is not None:
                stmt = stmt.where(REVIEW_QUEUE.c.severity == severity)
            if reason_code is not None:
                stmt = stmt.where(REVIEW_QUEUE.c.reason_code == reason_code)
            if entity_type is not None:
                stmt = stmt.where(REVIEW_QUEUE.c.entity_type == entity_type)
            return [dict(row) for row in con.execute(stmt).mappings().all()]

    def resolve_review_item(
        self, review_id: int, *, status: Literal["resolved", "ignored", "open"], note: str = ""
    ) -> bool:
        now = datetime.now(UTC)
        # Returning an item to the queue (open) clears the resolution timestamp.
        reviewed_at = None if status == "open" else now
        with self._connect() as con:
            result = con.execute(
                REVIEW_QUEUE.update()
                .where(REVIEW_QUEUE.c.id == review_id)
                .values(status=status, resolution_note=note, reviewed_at=reviewed_at, updated_at=now)
            )
            return result.rowcount > 0

    def list_artifact_templates(self, *, active_only: bool = False) -> list[dict[str, object]]:
        """Load methodologist-managed UP artifact templates with scopes."""
        with self._connect() as con:
            stmt = CURRICULUM_ARTIFACT_TEMPLATE.select().order_by(
                CURRICULUM_ARTIFACT_TEMPLATE.c.priority,
                CURRICULUM_ARTIFACT_TEMPLATE.c.id,
            )
            if active_only:
                stmt = stmt.where(CURRICULUM_ARTIFACT_TEMPLATE.c.status == "active")
            return [self._artifact_template_payload(con, row) for row in con.execute(stmt).mappings().all()]

    def get_artifact_template(self, template_id: int) -> dict[str, object] | None:
        with self._connect() as con:
            row = con.execute(CURRICULUM_ARTIFACT_TEMPLATE.select().where(CURRICULUM_ARTIFACT_TEMPLATE.c.id == template_id)).mappings().first()
            return self._artifact_template_payload(con, row) if row is not None else None

    def upsert_artifact_template(
        self,
        *,
        code: str,
        title: str,
        artifact_family: str,
        artifact_description: str,
        project_name_pattern: str = "",
        materials_pattern: str = "",
        storytelling_pattern: str = "",
        validation_criteria: str = "",
        priority: int = 100,
        status: Literal["active", "draft", "deprecated"] = "active",
        source: str = "methodologist",
        scopes: Iterable[dict[str, object]] = (),
    ) -> dict[str, object]:
        normalized_code = _slug_catalog_key(code or title)
        clean_title = _clean_title(title, fallback="Шаблон артефакта")
        now = datetime.now(UTC)
        with self._connect() as con:
            existing = con.execute(
                sa.select(CURRICULUM_ARTIFACT_TEMPLATE.c.id).where(CURRICULUM_ARTIFACT_TEMPLATE.c.code == normalized_code)
            ).scalar_one_or_none()
            values = {
                "code": normalized_code,
                "title": clean_title,
                "artifact_family": artifact_family or "practice",
                "artifact_description": artifact_description.strip(),
                "project_name_pattern": project_name_pattern.strip(),
                "materials_pattern": materials_pattern.strip(),
                "storytelling_pattern": storytelling_pattern.strip(),
                "validation_criteria": validation_criteria.strip(),
                "priority": int(priority or 100),
                "status": status,
                "source": source or "methodologist",
                "updated_at": now,
            }
            if existing is None:
                template_id = _insert_id(con, CURRICULUM_ARTIFACT_TEMPLATE.insert().values(**values))
            else:
                template_id = int(existing)
                con.execute(CURRICULUM_ARTIFACT_TEMPLATE.update().where(CURRICULUM_ARTIFACT_TEMPLATE.c.id == template_id).values(**values))
            self._replace_artifact_template_scopes(con, template_id, scopes)
            row = con.execute(CURRICULUM_ARTIFACT_TEMPLATE.select().where(CURRICULUM_ARTIFACT_TEMPLATE.c.id == template_id)).mappings().one()
            return self._artifact_template_payload(con, row)

    def list_curriculum_template_proposals(
        self,
        plan_id: int,
        *,
        status: Literal["open", "accepted", "rejected"] | None = None,
    ) -> list[dict[str, object]]:
        with self._connect() as con:
            stmt = CURRICULUM_ARTIFACT_TEMPLATE_PROPOSAL.select().where(CURRICULUM_ARTIFACT_TEMPLATE_PROPOSAL.c.plan_id == plan_id)
            if status:
                stmt = stmt.where(CURRICULUM_ARTIFACT_TEMPLATE_PROPOSAL.c.status == status)
            stmt = stmt.order_by(
                sa.case(
                    (CURRICULUM_ARTIFACT_TEMPLATE_PROPOSAL.c.status == "open", 0),
                    (CURRICULUM_ARTIFACT_TEMPLATE_PROPOSAL.c.status == "accepted", 1),
                    else_=2,
                ),
                CURRICULUM_ARTIFACT_TEMPLATE_PROPOSAL.c.id,
            )
            return [_proposal_from_row(row) for row in con.execute(stmt).mappings().all()]

    def generate_curriculum_template_proposals(self, plan_id: int, *, max_proposals: int = 10) -> list[dict[str, object]]:
        plan = self.load_curriculum_plan(plan_id)
        if plan is None:
            return []
        grouped: dict[str, list[CurriculumProjectRecord]] = {}
        for record in self.list_curriculum_projects(plan_id):
            grouped.setdefault(record.project.block or "Без блока", []).append(record)
        brief_id = self.create_profile_brief(
            f"Template proposal workspace for curriculum plan #{plan_id}: {plan.title}",
            spec={"source": "curriculum_template_proposals", "plan_id": plan_id, "title": plan.title, "direction": plan.direction},
        )
        with self._connect() as con:
            con.execute(
                CURRICULUM_ARTIFACT_TEMPLATE_PROPOSAL.delete().where(
                    CURRICULUM_ARTIFACT_TEMPLATE_PROPOSAL.c.plan_id == plan_id,
                    CURRICULUM_ARTIFACT_TEMPLATE_PROPOSAL.c.status == "open",
                )
            )
            for index, (block_name, records) in enumerate(
                sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0]))[:max_proposals],
                start=1,
            ):
                con.execute(
                    CURRICULUM_ARTIFACT_TEMPLATE_PROPOSAL.insert().values(
                        **_template_proposal_for_block(plan_id, brief_id, block_name, records, index)
                    )
                )
        return self.list_curriculum_template_proposals(plan_id)

    def update_curriculum_template_proposal(self, proposal_id: int, patch: dict[str, object]) -> dict[str, object] | None:
        with self._connect() as con:
            row = con.execute(
                CURRICULUM_ARTIFACT_TEMPLATE_PROPOSAL.select().where(CURRICULUM_ARTIFACT_TEMPLATE_PROPOSAL.c.id == proposal_id)
            ).mappings().first()
            if row is None:
                return None
            values = _proposal_update_values(row, patch)
            if values:
                values["updated_at"] = datetime.now(UTC)
                con.execute(
                    CURRICULUM_ARTIFACT_TEMPLATE_PROPOSAL.update()
                    .where(CURRICULUM_ARTIFACT_TEMPLATE_PROPOSAL.c.id == proposal_id)
                    .values(**values)
                )
            updated = con.execute(
                CURRICULUM_ARTIFACT_TEMPLATE_PROPOSAL.select().where(CURRICULUM_ARTIFACT_TEMPLATE_PROPOSAL.c.id == proposal_id)
            ).mappings().one()
            return _proposal_from_row(updated)

    def accept_curriculum_template_proposal(self, proposal_id: int) -> dict[str, object] | None:
        with self._connect() as con:
            row = con.execute(
                CURRICULUM_ARTIFACT_TEMPLATE_PROPOSAL.select().where(CURRICULUM_ARTIFACT_TEMPLATE_PROPOSAL.c.id == proposal_id)
            ).mappings().first()
            if row is None:
                return None
            proposal = _proposal_from_row(row)
        template = self.upsert_artifact_template(
            code=str(proposal["code"]),
            title=str(proposal["title"]),
            artifact_family=str(proposal["artifact_family"]),
            artifact_description=str(proposal["artifact_description"]),
            project_name_pattern=str(proposal["project_name_pattern"]),
            materials_pattern=str(proposal["materials_pattern"]),
            storytelling_pattern=str(proposal["storytelling_pattern"]),
            validation_criteria=str(proposal["validation_criteria"]),
            priority=80,
            status="active",
            source="proposal_accept",
            scopes=[
                {"scope_type": str(proposal["scope_type"]), "scope_name": scope_name, "weight": 1.0}
                for scope_name in (cast("list[str]", proposal["scope_names"]) or ["*"])
            ],
        )
        with self._connect() as con:
            con.execute(
                CURRICULUM_ARTIFACT_TEMPLATE_PROPOSAL.update()
                .where(CURRICULUM_ARTIFACT_TEMPLATE_PROPOSAL.c.id == proposal_id)
                .values(status="accepted", accepted_template_id=int(cast(int, template["id"])), updated_at=datetime.now(UTC))
            )
            updated = con.execute(
                CURRICULUM_ARTIFACT_TEMPLATE_PROPOSAL.select().where(CURRICULUM_ARTIFACT_TEMPLATE_PROPOSAL.c.id == proposal_id)
            ).mappings().one()
            return _proposal_from_row(updated)

    def reject_curriculum_template_proposal(self, proposal_id: int) -> dict[str, object] | None:
        return self.update_curriculum_template_proposal(proposal_id, {"status": "rejected"})

    def set_artifact_template_status(self, template_id: int, status: Literal["active", "draft", "deprecated"]) -> dict[str, object] | None:
        with self._connect() as con:
            result = con.execute(
                CURRICULUM_ARTIFACT_TEMPLATE.update()
                .where(CURRICULUM_ARTIFACT_TEMPLATE.c.id == template_id)
                .values(status=status, updated_at=datetime.now(UTC))
            )
            if result.rowcount <= 0:
                return None
            row = con.execute(CURRICULUM_ARTIFACT_TEMPLATE.select().where(CURRICULUM_ARTIFACT_TEMPLATE.c.id == template_id)).mappings().one()
            return self._artifact_template_payload(con, row)

    def create_profile_brief(self, raw_text: str, *, spec: dict[str, Any] | None = None) -> int:
        spec = spec or {}
        with self._connect() as con:
            return _insert_id(
                con,
                PROFILE_BRIEF.insert().values(
                    raw_text=raw_text,
                    role=spec.get("role"),
                    seniority=spec.get("seniority"),
                    domain=spec.get("domain"),
                    metadata_json=spec,
                ),
            )

    def create_intake_job(
        self,
        *,
        brief_text: str,
        source_kind: Literal["text", "file"] = "text",
        source_name: str | None = None,
        file_path: str | None = None,
        use_council: bool = True,
    ) -> dict[str, object]:
        now = datetime.now(UTC)
        with self._connect() as con:
            job_id = _insert_id(
                con,
                INTAKE_JOB.insert().values(
                    source_kind=source_kind,
                    source_name=source_name,
                    file_path=file_path,
                    brief_text=brief_text,
                    use_council=1 if use_council else 0,
                    created_at=now,
                    updated_at=now,
                ),
            )
        return self.get_intake_job(job_id) or {"id": job_id}

    def update_intake_job(self, job_id: int, **patch: Any) -> dict[str, object] | None:
        if not patch:
            return self.get_intake_job(job_id)
        patch["updated_at"] = datetime.now(UTC)
        with self._connect() as con:
            result = con.execute(INTAKE_JOB.update().where(INTAKE_JOB.c.id == job_id).values(**patch))
            if result.rowcount <= 0:
                return None
        return self.get_intake_job(job_id)

    def get_intake_job(self, job_id: int) -> dict[str, object] | None:
        with self._connect() as con:
            row = con.execute(INTAKE_JOB.select().where(INTAKE_JOB.c.id == job_id)).mappings().first()
            return _intake_job_from_row(row) if row else None

    def list_intake_jobs(self, *, limit: int = 8) -> list[dict[str, object]]:
        with self._connect() as con:
            rows = con.execute(INTAKE_JOB.select().order_by(INTAKE_JOB.c.created_at.desc(), INTAKE_JOB.c.id.desc()).limit(limit)).mappings().all()
            return [_intake_job_from_row(row) for row in rows]

    def reference_summary(self) -> dict[str, int]:
        """Return catalog counters for the reference dashboard."""

        with self._connect() as con:
            return {
                "competencies": int(con.execute(sa.select(sa.func.count()).select_from(COMPETENCY)).scalar() or 0),
                "skills": int(con.execute(sa.select(sa.func.count()).select_from(SKILL).where(SKILL.c.status != "deprecated")).scalar() or 0),
                "indicators": int(con.execute(sa.select(sa.func.count()).select_from(INDICATOR_ROW)).scalar() or 0),
                "open_reviews": int(
                    con.execute(
                        sa.select(sa.func.count()).select_from(REVIEW_QUEUE).where(REVIEW_QUEUE.c.status == "open")
                    ).scalar()
                    or 0
                ),
            }

    def list_reference_competencies(
        self,
        *,
        query: str = "",
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, object]]:
        """List competency cards with counts used by the reference UI."""

        normalized_query = normalize_catalog_key(query)
        with self._connect() as con:
            stmt = COMPETENCY.select().order_by(COMPETENCY.c.title, COMPETENCY.c.id).limit(limit)
            if normalized_query:
                stmt = stmt.where(
                    sa.or_(
                        COMPETENCY.c.normalized_title.like(f"%{normalized_query}%"),
                        sa.func.lower(COMPETENCY.c.description).like(f"%{query.lower()}%"),
                    )
                )
            if status:
                stmt = stmt.where(COMPETENCY.c.status == status)
            return [self._reference_competency_summary(con, row) for row in con.execute(stmt).mappings().all()]

    def find_competency_match(
        self,
        title: str,
        *,
        aliases: Iterable[str] = (),
    ) -> CompetencyMatch | None:
        """Resolve a found competency without creating duplicates.

        Matching is intentionally read-only: exact catalog title first, then
        provenance titles (`profile_competency.title_in_source`) that came from
        source workbooks or accepted intake rows.
        """

        primary_normalized = normalize_catalog_key(title)
        alias_names = [alias for alias in aliases if normalize_catalog_key(alias)]
        alias_normalized = {normalize_catalog_key(alias) for alias in alias_names}
        normalized_names = {name for name in [primary_normalized, *alias_normalized] if name}
        if not normalized_names:
            return None
        normalized_to_name = {
            normalize_catalog_key(name): name
            for name in [title, *alias_names]
            if normalize_catalog_key(name)
        }
        with self._connect() as con:
            exact_stmt = sa.select(
                COMPETENCY.c.id,
                COMPETENCY.c.title,
                COMPETENCY.c.status,
                COMPETENCY.c.normalized_title,
            )
            exact_title = (
                con.execute(exact_stmt.where(COMPETENCY.c.normalized_title == primary_normalized).limit(1))
                .mappings()
                .first()
                if primary_normalized
                else None
            )
            if exact_title is not None:
                return CompetencyMatch(
                    competency_id=int(exact_title["id"]),
                    title=str(exact_title["title"]),
                    status=str(exact_title["status"]),
                    match_type="title",
                    matched_name=str(exact_title["title"]),
                )
            if alias_normalized:
                exact_alias = (
                    con.execute(
                        exact_stmt.where(COMPETENCY.c.normalized_title.in_(list(alias_normalized)))
                        .order_by(COMPETENCY.c.id)
                        .limit(1)
                    )
                    .mappings()
                    .first()
                )
                if exact_alias is not None:
                    normalized_title = str(exact_alias["normalized_title"])
                    return CompetencyMatch(
                        competency_id=int(exact_alias["id"]),
                        title=str(exact_alias["title"]),
                        status=str(exact_alias["status"]),
                        match_type="alias",
                        matched_name=normalized_to_name.get(normalized_title, str(exact_alias["title"])),
                    )

            stmt = (
                sa.select(
                    COMPETENCY.c.id,
                    COMPETENCY.c.title,
                    COMPETENCY.c.status,
                    PROFILE_COMPETENCY.c.title_in_source,
                )
                .select_from(PROFILE_COMPETENCY.join(COMPETENCY, COMPETENCY.c.id == PROFILE_COMPETENCY.c.competency_id))
                .order_by(COMPETENCY.c.id, PROFILE_COMPETENCY.c.id)
            )
            for row in con.execute(stmt).mappings().all():
                source_title = str(row["title_in_source"] or "")
                if normalize_catalog_key(source_title) in normalized_names:
                    return CompetencyMatch(
                        competency_id=int(row["id"]),
                        title=str(row["title"]),
                        status=str(row["status"]),
                        match_type="provenance",
                        matched_name=source_title,
                    )
        return None

    def get_reference_competency(self, competency_id: int) -> dict[str, object] | None:
        """Return competency detail with skills, aliases, indicators and level cells."""

        with self._connect() as con:
            row = con.execute(COMPETENCY.select().where(COMPETENCY.c.id == competency_id)).mappings().first()
            if row is None:
                return None
            return {
                **self._reference_competency_summary(con, row),
                "skills": self._reference_competency_skills(con, competency_id),
            }

    def create_reference_group(
        self,
        *,
        title: str,
        description: str = "",
        status: str = "active",
    ) -> dict[str, object] | None:
        """Create an empty competency group explicitly (methodologist action, no review)."""

        clean_title = _clean_title(title, DEFAULT_COMPETENCY_TITLE)
        normalized_title = normalize_catalog_key(clean_title)
        with self._connect() as con:
            existing = con.execute(
                sa.select(COMPETENCY.c.id).where(COMPETENCY.c.normalized_title == normalized_title)
            ).scalar_one_or_none()
            if existing is not None:
                return None
            competency_id = _insert_id(
                con,
                COMPETENCY.insert().values(
                    normalized_title=normalized_title,
                    title=clean_title,
                    description=description.strip() or "Группа создана методологом.",
                    status=status,
                ),
            )
        return self.get_reference_competency(competency_id)

    def update_reference_competency(
        self,
        competency_id: int,
        *,
        title: str | None = None,
        description: str | None = None,
        status: CatalogStatus | None = None,
    ) -> dict[str, object] | None:
        """Patch editable competency fields and return the refreshed detail."""

        with self._connect() as con:
            existing = con.execute(COMPETENCY.select().where(COMPETENCY.c.id == competency_id)).mappings().first()
            if existing is None:
                return None
            values: dict[str, object] = {}
            if title is not None:
                clean_title = _clean_title(title, fallback=str(existing["title"]))
                values.update(title=clean_title, normalized_title=normalize_catalog_key(clean_title))
            if description is not None:
                values["description"] = description.strip()
            if status is not None:
                values["status"] = status
            if values:
                con.execute(COMPETENCY.update().where(COMPETENCY.c.id == competency_id).values(**values))
            row = con.execute(COMPETENCY.select().where(COMPETENCY.c.id == competency_id)).mappings().one()
            return {
                **self._reference_competency_summary(con, row),
                "skills": self._reference_competency_skills(con, competency_id),
            }

    def list_reference_profiles(self, *, include_service: bool = False, limit: int = 100) -> list[dict[str, object]]:
        """List source profiles with competency/skill/indicator counters."""

        with self._connect() as con:
            stmt = PROFILE.select().order_by(PROFILE.c.name, PROFILE.c.id).limit(limit)
            if not include_service:
                stmt = stmt.where(PROFILE.c.slug != SERVICE_PROFILE_SLUG)
            rows = con.execute(stmt).mappings().all()
            return [self._reference_profile_summary(con, row) for row in rows]

    def get_reference_profile(self, profile_id: int) -> dict[str, object] | None:
        """Return one profile with competency, skill and indicator tree."""

        with self._connect() as con:
            row = con.execute(PROFILE.select().where(PROFILE.c.id == profile_id)).mappings().first()
            if row is None:
                return None
            return {
                **self._reference_profile_summary(con, row),
                "competencies": self._reference_profile_competencies(con, profile_id),
            }

    def save_curriculum_plan(
        self,
        up: UPSkeleton,
        *,
        profile_id: int | None = None,
        source_policy: str = "accepted_only",
        author_ref: str | None = None,
    ) -> CurriculumPlanSaveResult:
        payload = up.model_dump(mode="json")
        with self._connect() as con:
            now = datetime.now(UTC)
            plan_id = _insert_id(
                con,
                CURRICULUM_PLAN.insert().values(
                    profile_id=profile_id,
                    source_policy=source_policy,
                    status=up.status,
                    title=up.title,
                    direction=up.direction,
                    version=up.version,
                    author_ref=author_ref,
                    total_blocks=len(up.blocks),
                    total_projects=len(up.rows),
                    total_hours=sum(project.hours_astro for project in up.rows),
                    metadata_json=up.metadata,
                    payload_json=payload,
                    updated_at=now,
                ),
            )
            block_indexes: dict[str, int] = {}
            block_counts: dict[str, int] = {}
            cumulative_days = 0.0
            for row_number, project in enumerate(sorted(up.rows, key=lambda item: item.order), start=1):
                block_name = project.block or "Без блока"
                block_indexes.setdefault(block_name, len(block_indexes) + 1)
                block_counts[block_name] = block_counts.get(block_name, 0) + 1
                workload_days = _optional_float(project.metadata.get("workload_days"))
                if workload_days is not None:
                    cumulative_days += workload_days
                con.execute(
                    CURRICULUM_PROJECT.insert().values(
                        **_project_values(
                            plan_id=plan_id,
                            row_number=row_number,
                            block_index=block_indexes[block_name],
                            project_index_in_block=block_counts[block_name],
                            project=project,
                            total_workload_days=cumulative_days if workload_days is not None else _optional_float(project.metadata.get("total_workload_days")),
                        )
                    )
            )
            return CurriculumPlanSaveResult(plan_id=plan_id, project_count=len(up.rows))

    def list_curriculum_plans(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, object]]:
        with self._connect() as con:
            stmt = CURRICULUM_PLAN.select().order_by(CURRICULUM_PLAN.c.updated_at.desc(), CURRICULUM_PLAN.c.id.desc()).limit(limit)
            if status:
                stmt = stmt.where(CURRICULUM_PLAN.c.status == status)
            return [
                {
                    "plan_id": int(row["id"]),
                    "status": row["status"],
                    "title": row["title"],
                    "direction": row["direction"],
                    "version": row["version"],
                    "source_policy": row["source_policy"],
                    "total_blocks": int(row["total_blocks"] or 0),
                    "total_projects": int(row["total_projects"] or 0),
                    "total_hours": float(row["total_hours"] or 0.0),
                    "updated_at": _iso_or_none(row["updated_at"]),
                    "created_at": _iso_or_none(row["created_at"]),
                }
                for row in con.execute(stmt).mappings().all()
            ]

    def load_curriculum_plan(self, plan_id: int) -> UPSkeleton | None:
        with self._connect() as con:
            plan = con.execute(CURRICULUM_PLAN.select().where(CURRICULUM_PLAN.c.id == plan_id)).mappings().first()
            if plan is None:
                return None
            rows = con.execute(
                CURRICULUM_PROJECT.select()
                .where(CURRICULUM_PROJECT.c.plan_id == plan_id)
                .order_by(CURRICULUM_PROJECT.c.row_number, CURRICULUM_PROJECT.c.id)
            ).mappings().all()
            projects = [_project_from_row(row) for row in rows]
            metadata = dict(_json_object(plan["metadata_json"]))
            metadata.update({"plan_id": int(plan["id"]), "source_policy": plan["source_policy"]})
            return UPSkeleton(
                status=plan["status"],
                title=plan["title"],
                direction=plan["direction"] or "",
                version=plan["version"] or "v1",
                rows=projects,
                metadata=metadata,
            )

    def get_context(
        self,
        plan_id: int,
        project_order: int,
        *,
        block_name: str | None = None,
        cross_block_depth: int = 2,
    ) -> CurriculumContext | None:
        plan = self.load_curriculum_plan(plan_id)
        if plan is None:
            return None
        return plan.build_context(
            project_order,
            block_name=block_name,
            cross_block_depth=cross_block_depth,
            plan_id=plan_id,
        )

    def replace_curriculum_plan(
        self,
        plan_id: int,
        up: UPSkeleton,
        *,
        profile_id: int | None = None,
        source_policy: str | None = None,
        author_ref: str | None = None,
    ) -> bool:
        with self._connect() as con:
            existing = con.execute(CURRICULUM_PLAN.select().where(CURRICULUM_PLAN.c.id == plan_id)).mappings().first()
            if existing is None:
                return False
            now = datetime.now(UTC)
            con.execute(CURRICULUM_PROJECT.delete().where(CURRICULUM_PROJECT.c.plan_id == plan_id))
            con.execute(
                CURRICULUM_PLAN.update()
                .where(CURRICULUM_PLAN.c.id == plan_id)
                .values(
                    profile_id=profile_id if profile_id is not None else existing["profile_id"],
                    source_policy=source_policy or existing["source_policy"],
                    status=up.status,
                    title=up.title,
                    direction=up.direction,
                    version=up.version,
                    author_ref=author_ref if author_ref is not None else existing["author_ref"],
                    total_blocks=len(up.blocks),
                    total_projects=len(up.rows),
                    total_hours=sum(project.hours_astro for project in up.rows),
                    metadata_json=up.metadata,
                    payload_json=up.model_dump(mode="json"),
                    updated_at=now,
                )
            )
            self._insert_projects(con, plan_id, up.rows)
            return True

    def delete_curriculum_plan(self, plan_id: int) -> bool:
        with self._connect() as con:
            result = con.execute(CURRICULUM_PLAN.delete().where(CURRICULUM_PLAN.c.id == plan_id))
            return result.rowcount > 0

    def add_curriculum_project(self, plan_id: int, project: UPProject) -> CurriculumProjectRecord | None:
        with self._connect() as con:
            if con.execute(sa.select(CURRICULUM_PLAN.c.id).where(CURRICULUM_PLAN.c.id == plan_id)).scalar_one_or_none() is None:
                return None
            row_number = _next_int(con, CURRICULUM_PROJECT.c.row_number, CURRICULUM_PROJECT.c.plan_id == plan_id)
            block_index, project_index = self._project_position(con, plan_id, project.block)
            values = _project_values(
                plan_id=plan_id,
                row_number=row_number,
                block_index=block_index,
                project_index_in_block=project_index,
                project=project,
                total_workload_days=_optional_float(project.metadata.get("total_workload_days")),
            )
            project_id = _insert_id(con, CURRICULUM_PROJECT.insert().values(**values))
            self._refresh_plan_summary(con, plan_id)
            return CurriculumProjectRecord(project_id=project_id, plan_id=plan_id, row_number=row_number, project=project)

    def get_curriculum_project(self, project_id: int) -> CurriculumProjectRecord | None:
        with self._connect() as con:
            row = con.execute(CURRICULUM_PROJECT.select().where(CURRICULUM_PROJECT.c.id == project_id)).mappings().first()
            if row is None:
                return None
            return CurriculumProjectRecord(
                project_id=int(row["id"]),
                plan_id=int(row["plan_id"]),
                row_number=int(row["row_number"]),
                project=_project_from_row(row),
            )

    def list_curriculum_projects(self, plan_id: int) -> list[CurriculumProjectRecord]:
        with self._connect() as con:
            rows = con.execute(
                CURRICULUM_PROJECT.select()
                .where(CURRICULUM_PROJECT.c.plan_id == plan_id)
                .order_by(CURRICULUM_PROJECT.c.row_number, CURRICULUM_PROJECT.c.id)
            ).mappings().all()
            return [
                CurriculumProjectRecord(
                    project_id=int(row["id"]),
                    plan_id=int(row["plan_id"]),
                    row_number=int(row["row_number"]),
                    project=_project_from_row(row),
                )
                for row in rows
            ]

    def update_curriculum_project(self, project_id: int, project: UPProject) -> CurriculumProjectRecord | None:
        with self._connect() as con:
            row = con.execute(CURRICULUM_PROJECT.select().where(CURRICULUM_PROJECT.c.id == project_id)).mappings().first()
            if row is None:
                return None
            values = _project_values(
                plan_id=int(row["plan_id"]),
                row_number=int(row["row_number"]),
                block_index=int(row["block_index"] or 0),
                project_index_in_block=int(row["project_index_in_block"] or 0),
                project=project,
                total_workload_days=_optional_float(project.metadata.get("total_workload_days")),
            )
            values.pop("plan_id", None)
            con.execute(CURRICULUM_PROJECT.update().where(CURRICULUM_PROJECT.c.id == project_id).values(**values))
            self._refresh_plan_summary(con, int(row["plan_id"]))
            return CurriculumProjectRecord(project_id=project_id, plan_id=int(row["plan_id"]), row_number=int(row["row_number"]), project=project)

    def delete_curriculum_project(self, project_id: int) -> bool:
        with self._connect() as con:
            row = con.execute(sa.select(CURRICULUM_PROJECT.c.plan_id).where(CURRICULUM_PROJECT.c.id == project_id)).mappings().first()
            if row is None:
                return False
            con.execute(CURRICULUM_PROJECT.delete().where(CURRICULUM_PROJECT.c.id == project_id))
            self._refresh_plan_summary(con, int(row["plan_id"]))
            return True

    def ensure_dimensions(self) -> None:
        with self._connect() as con:
            for code, title in DIMENSION_TITLES.items():
                if _select_id(con, DIMENSION, DIMENSION.c.code == code) is None:
                    con.execute(DIMENSION.insert().values(code=code, title=title))

    def _reference_competency_summary(self, con: Connection, row: sa.RowMapping) -> dict[str, object]:
        competency_id = int(row["id"])
        profile_count = con.execute(
            sa.select(sa.func.count(sa.distinct(PROFILE_COMPETENCY.c.profile_id))).where(
                PROFILE_COMPETENCY.c.competency_id == competency_id
            )
        ).scalar()
        skill_count = con.execute(
            sa.select(sa.func.count(sa.distinct(COMPETENCY_SKILL.c.skill_id)))
            .select_from(COMPETENCY_SKILL.join(PROFILE_COMPETENCY, PROFILE_COMPETENCY.c.id == COMPETENCY_SKILL.c.profile_competency_id))
            .where(PROFILE_COMPETENCY.c.competency_id == competency_id)
        ).scalar()
        indicator_count = con.execute(
            sa.select(sa.func.count(INDICATOR_ROW.c.id))
            .select_from(
                INDICATOR_ROW.join(COMPETENCY_SKILL, COMPETENCY_SKILL.c.id == INDICATOR_ROW.c.competency_skill_id).join(
                    PROFILE_COMPETENCY,
                    PROFILE_COMPETENCY.c.id == COMPETENCY_SKILL.c.profile_competency_id,
                )
            )
            .where(PROFILE_COMPETENCY.c.competency_id == competency_id)
        ).scalar()
        return {
            "id": competency_id,
            "title": row["title"],
            "description": row["description"] or "",
            "status": row["status"],
            "profile_count": int(profile_count or 0),
            "skill_count": int(skill_count or 0),
            "indicator_count": int(indicator_count or 0),
        }

    def _reference_competency_skills(self, con: Connection, competency_id: int) -> list[dict[str, object]]:
        stmt = (
            sa.select(
                COMPETENCY_SKILL.c.id.label("competency_skill_id"),
                COMPETENCY_SKILL.c.source_skill_name,
                COMPETENCY_SKILL.c.review_state,
                SKILL.c.id.label("skill_id"),
                SKILL.c.canonical_name,
                SKILL.c.skill_type,
                SKILL.c.status.label("skill_status"),
                PROFILE.c.id.label("profile_id"),
                PROFILE.c.name.label("profile_name"),
            )
            .select_from(
                COMPETENCY_SKILL.join(PROFILE_COMPETENCY, PROFILE_COMPETENCY.c.id == COMPETENCY_SKILL.c.profile_competency_id)
                .join(PROFILE, PROFILE.c.id == PROFILE_COMPETENCY.c.profile_id)
                .outerjoin(SKILL, SKILL.c.id == COMPETENCY_SKILL.c.skill_id)
            )
            .where(PROFILE_COMPETENCY.c.competency_id == competency_id)
            .order_by(PROFILE.c.name, COMPETENCY_SKILL.c.skill_order, COMPETENCY_SKILL.c.id)
        )
        skills: list[dict[str, object]] = []
        for row in con.execute(stmt).mappings().all():
            skill_id = int(row["skill_id"]) if row["skill_id"] is not None else None
            skills.append(
                {
                    "competency_skill_id": int(row["competency_skill_id"]),
                    "skill_id": skill_id,
                    "name": row["canonical_name"] or row["source_skill_name"],
                    "source_name": row["source_skill_name"],
                    "skill_type": row["skill_type"] or "unknown",
                    "status": row["skill_status"] or "missing",
                    "review_state": row["review_state"],
                    "profile_id": int(row["profile_id"]),
                    "profile_name": row["profile_name"],
                    "aliases": self._reference_skill_aliases(con, skill_id) if skill_id is not None else [],
                    "indicators": self._reference_indicators(con, int(row["competency_skill_id"])),
                }
            )
        return skills

    def _reference_indicators(self, con: Connection, competency_skill_id: int) -> list[dict[str, object]]:
        stmt = (
            sa.select(
                INDICATOR_ROW.c.id,
                INDICATOR_ROW.c.base_text,
                INDICATOR_ROW.c.raw_number,
                INDICATOR_ROW.c.notes,
                INDICATOR_ROW.c.status,
                DIMENSION.c.code.label("dimension_code"),
                DIMENSION.c.title.label("dimension_title"),
            )
            .select_from(INDICATOR_ROW.join(DIMENSION, DIMENSION.c.id == INDICATOR_ROW.c.dimension_id))
            .where(INDICATOR_ROW.c.competency_skill_id == competency_skill_id, INDICATOR_ROW.c.status != "deprecated")
            .order_by(INDICATOR_ROW.c.source_row_number, INDICATOR_ROW.c.id)
        )
        return [
            {
                "id": int(row["id"]),
                "text": row["base_text"] or "",
                "raw_number": row["raw_number"] or "",
                "notes": row["notes"] or "",
                "status": row["status"],
                "dimension_code": row["dimension_code"],
                "dimension_title": row["dimension_title"],
                "levels": self._reference_indicator_levels(con, int(row["id"])),
            }
            for row in con.execute(stmt).mappings().all()
        ]

    def _reference_indicator(self, con: Connection, indicator_id: int) -> dict[str, object] | None:
        stmt = (
            sa.select(
                INDICATOR_ROW.c.id,
                INDICATOR_ROW.c.competency_skill_id,
                INDICATOR_ROW.c.base_text,
                INDICATOR_ROW.c.raw_number,
                INDICATOR_ROW.c.notes,
                INDICATOR_ROW.c.status,
                DIMENSION.c.code.label("dimension_code"),
                DIMENSION.c.title.label("dimension_title"),
            )
            .select_from(INDICATOR_ROW.join(DIMENSION, DIMENSION.c.id == INDICATOR_ROW.c.dimension_id))
            .where(INDICATOR_ROW.c.id == indicator_id)
        )
        row = con.execute(stmt).mappings().first()
        if row is None:
            return None
        return {
            "id": int(row["id"]),
            "competency_skill_id": int(row["competency_skill_id"]),
            "text": row["base_text"] or "",
            "raw_number": row["raw_number"] or "",
            "notes": row["notes"] or "",
            "status": row["status"],
            "dimension_code": row["dimension_code"],
            "dimension_title": row["dimension_title"],
            "levels": self._reference_indicator_levels(con, int(row["id"])),
        }

    def _skill_links(self, con: Connection, skill_id: int) -> list[dict[str, object]]:
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
            )
            .select_from(
                COMPETENCY_SKILL.join(PROFILE_COMPETENCY, PROFILE_COMPETENCY.c.id == COMPETENCY_SKILL.c.profile_competency_id)
                .join(COMPETENCY, COMPETENCY.c.id == PROFILE_COMPETENCY.c.competency_id)
                .join(PROFILE, PROFILE.c.id == PROFILE_COMPETENCY.c.profile_id)
            )
            .where(COMPETENCY_SKILL.c.skill_id == skill_id)
            .order_by(PROFILE.c.name, COMPETENCY.c.title, COMPETENCY_SKILL.c.skill_order, COMPETENCY_SKILL.c.id)
        )
        return [
            {
                **dict(row),
                "competency_skill_id": int(row["competency_skill_id"]),
                "profile_competency_id": int(row["profile_competency_id"]),
                "competency_id": int(row["competency_id"]),
                "profile_id": int(row["profile_id"]),
                "indicators": self._reference_indicators(con, int(row["competency_skill_id"])),
            }
            for row in con.execute(stmt).mappings().all()
        ]

    def _first_competency_skill_id(self, con: Connection, skill_id: int) -> int | None:
        value = con.execute(
            sa.select(COMPETENCY_SKILL.c.id)
            .where(COMPETENCY_SKILL.c.skill_id == skill_id)
            .order_by(COMPETENCY_SKILL.c.skill_order, COMPETENCY_SKILL.c.id)
            .limit(1)
        ).scalar_one_or_none()
        return int(value) if value is not None else None

    def _archived_groups(self, con: Connection, normalized_query: str, limit: int) -> list[dict[str, object]]:
        stmt = COMPETENCY.select().where(COMPETENCY.c.status == "deprecated").order_by(COMPETENCY.c.title, COMPETENCY.c.id).limit(limit)
        if normalized_query:
            stmt = stmt.where(
                sa.or_(
                    COMPETENCY.c.normalized_title.like(f"%{normalized_query}%"),
                    sa.func.lower(COMPETENCY.c.description).like(f"%{normalized_query}%"),
                )
            )
        return [self._reference_competency_summary(con, row) for row in con.execute(stmt).mappings().all()]

    def _archived_skills(self, con: Connection, normalized_query: str, limit: int) -> list[dict[str, object]]:
        stmt = SKILL.select().where(SKILL.c.status == "deprecated").order_by(SKILL.c.canonical_name, SKILL.c.id).limit(limit)
        if normalized_query:
            matching_alias_skill_ids = sa.select(SKILL_ALIAS.c.skill_id).where(SKILL_ALIAS.c.normalized_alias.like(f"%{normalized_query}%"))
            stmt = stmt.where(sa.or_(SKILL.c.normalized_name.like(f"%{normalized_query}%"), SKILL.c.id.in_(matching_alias_skill_ids)))
        items: list[dict[str, object]] = []
        for row in con.execute(stmt).mappings().all():
            skill = self._skill_from_row(con, row)
            links = self._skill_links(con, skill.skill_id)
            indicator_count = con.execute(
                sa.select(sa.func.count())
                .select_from(INDICATOR_ROW.join(COMPETENCY_SKILL, COMPETENCY_SKILL.c.id == INDICATOR_ROW.c.competency_skill_id))
                .where(COMPETENCY_SKILL.c.skill_id == skill.skill_id)
            ).scalar()
            group_names = list(dict.fromkeys(str(link["competency_title"]) for link in links if link.get("competency_title")))
            items.append(
                {
                    "skill_id": skill.skill_id,
                    "canonical_name": skill.canonical_name,
                    "skill_type": skill.skill_type,
                    "status": skill.status,
                    "aliases": list(skill.aliases),
                    "group_names": group_names,
                    "indicator_count": int(indicator_count or 0),
                    "links": links,
                }
            )
        return items

    def _archived_indicators(self, con: Connection, normalized_query: str, limit: int) -> list[dict[str, object]]:
        stmt = (
            sa.select(
                INDICATOR_ROW.c.id,
                INDICATOR_ROW.c.competency_skill_id,
                INDICATOR_ROW.c.base_text,
                INDICATOR_ROW.c.raw_number,
                INDICATOR_ROW.c.notes,
                INDICATOR_ROW.c.status,
                DIMENSION.c.code.label("dimension_code"),
                DIMENSION.c.title.label("dimension_title"),
                SKILL.c.id.label("skill_id"),
                SKILL.c.canonical_name.label("skill_name"),
                SKILL.c.status.label("skill_status"),
                COMPETENCY.c.id.label("group_id"),
                COMPETENCY.c.title.label("group_name"),
                PROFILE.c.name.label("profile_name"),
            )
            .select_from(
                INDICATOR_ROW.join(DIMENSION, DIMENSION.c.id == INDICATOR_ROW.c.dimension_id)
                .join(COMPETENCY_SKILL, COMPETENCY_SKILL.c.id == INDICATOR_ROW.c.competency_skill_id)
                .outerjoin(SKILL, SKILL.c.id == COMPETENCY_SKILL.c.skill_id)
                .join(PROFILE_COMPETENCY, PROFILE_COMPETENCY.c.id == COMPETENCY_SKILL.c.profile_competency_id)
                .join(COMPETENCY, COMPETENCY.c.id == PROFILE_COMPETENCY.c.competency_id)
                .join(PROFILE, PROFILE.c.id == PROFILE_COMPETENCY.c.profile_id)
            )
            .where(INDICATOR_ROW.c.status == "deprecated")
            .order_by(COMPETENCY.c.title, SKILL.c.canonical_name, INDICATOR_ROW.c.source_row_number, INDICATOR_ROW.c.id)
            .limit(limit)
        )
        if normalized_query:
            query_like = f"%{normalized_query}%"
            stmt = stmt.where(
                sa.or_(
                    sa.func.lower(INDICATOR_ROW.c.base_text).like(query_like),
                    sa.func.lower(INDICATOR_ROW.c.notes).like(query_like),
                    SKILL.c.normalized_name.like(query_like),
                    COMPETENCY.c.normalized_title.like(query_like),
                    sa.func.lower(PROFILE.c.name).like(query_like),
                )
            )
        return [
            {
                "id": int(row["id"]),
                "competency_skill_id": int(row["competency_skill_id"]),
                "text": row["base_text"] or "",
                "raw_number": row["raw_number"] or "",
                "notes": row["notes"] or "",
                "status": row["status"],
                "dimension_code": row["dimension_code"],
                "dimension_title": row["dimension_title"],
                "skill_id": int(row["skill_id"]) if row["skill_id"] is not None else None,
                "skill_name": row["skill_name"] or "",
                "skill_status": row["skill_status"] or "missing",
                "group_id": int(row["group_id"]),
                "group_name": row["group_name"],
                "profile_name": row["profile_name"],
            }
            for row in con.execute(stmt).mappings().all()
        ]

    def _restore_skill_parents(self, con: Connection, skill_id: int) -> None:
        for competency_skill_id in con.execute(sa.select(COMPETENCY_SKILL.c.id).where(COMPETENCY_SKILL.c.skill_id == skill_id)).scalars():
            self._restore_competency_skill_parents(con, int(competency_skill_id))

    def _restore_competency_skill_parents(self, con: Connection, competency_skill_id: int) -> None:
        row = (
            con.execute(
                sa.select(COMPETENCY_SKILL.c.skill_id, PROFILE_COMPETENCY.c.id.label("profile_competency_id"), COMPETENCY.c.id.label("competency_id"))
                .select_from(
                    COMPETENCY_SKILL.join(PROFILE_COMPETENCY, PROFILE_COMPETENCY.c.id == COMPETENCY_SKILL.c.profile_competency_id).join(
                        COMPETENCY,
                        COMPETENCY.c.id == PROFILE_COMPETENCY.c.competency_id,
                    )
                )
                .where(COMPETENCY_SKILL.c.id == competency_skill_id)
            )
            .mappings()
            .first()
        )
        if row is None:
            return
        if row["skill_id"] is not None:
            con.execute(SKILL.update().where(SKILL.c.id == int(row["skill_id"])).values(status="active"))
        con.execute(PROFILE_COMPETENCY.update().where(PROFILE_COMPETENCY.c.id == int(row["profile_competency_id"])).values(review_state="accepted"))
        con.execute(COMPETENCY_SKILL.update().where(COMPETENCY_SKILL.c.id == competency_skill_id).values(review_state="accepted"))
        con.execute(COMPETENCY.update().where(COMPETENCY.c.id == int(row["competency_id"])).values(status="active"))

    def _artifact_template_payload(self, con: Connection, row: sa.RowMapping) -> dict[str, object]:
        template_id = int(row["id"])
        scopes = self._artifact_template_scopes(con, template_id)
        editable_scope = scopes[0] if scopes else {"scope_type": "coverage_area", "weight": 1.0}
        return {
            "id": template_id,
            "code": row["code"],
            "title": row["title"],
            "artifact_family": row["artifact_family"],
            "artifact_description": row["artifact_description"] or "",
            "project_name_pattern": row["project_name_pattern"] or "",
            "materials_pattern": row["materials_pattern"] or "",
            "storytelling_pattern": row["storytelling_pattern"] or "",
            "validation_criteria": row["validation_criteria"] or "",
            "priority": int(row["priority"] or 100),
            "status": row["status"],
            "source": row["source"] or "manual",
            "created_at": _iso_or_none(row["created_at"]),
            "updated_at": _iso_or_none(row["updated_at"]),
            "scopes": scopes,
            "scope_type": editable_scope.get("scope_type") or "coverage_area",
            "scope_weight": float(cast(float, editable_scope.get("weight") or 1.0)),
            "scope_names": [str(scope.get("scope_name") or "") for scope in scopes if scope.get("scope_type") != "any" and str(scope.get("scope_name") or "").strip()],
        }

    def _artifact_template_scopes(self, con: Connection, template_id: int) -> list[dict[str, object]]:
        rows = con.execute(
            CURRICULUM_ARTIFACT_TEMPLATE_SCOPE.select()
            .where(CURRICULUM_ARTIFACT_TEMPLATE_SCOPE.c.template_id == template_id)
            .order_by(CURRICULUM_ARTIFACT_TEMPLATE_SCOPE.c.weight.desc(), CURRICULUM_ARTIFACT_TEMPLATE_SCOPE.c.id)
        ).mappings()
        return [
            {
                "id": int(row["id"]),
                "template_id": int(row["template_id"]),
                "scope_type": row["scope_type"],
                "scope_id": int(row["scope_id"]) if row["scope_id"] is not None else None,
                "scope_name": row["scope_name"] or "",
                "normalized_scope_name": row["normalized_scope_name"] or normalize_catalog_key(row["scope_name"] or ""),
                "weight": float(row["weight"] or 1.0),
            }
            for row in rows
        ]

    def _replace_artifact_template_scopes(self, con: Connection, template_id: int, scopes: Iterable[dict[str, object]]) -> None:
        con.execute(CURRICULUM_ARTIFACT_TEMPLATE_SCOPE.delete().where(CURRICULUM_ARTIFACT_TEMPLATE_SCOPE.c.template_id == template_id))
        normalized_scopes = list(_normalize_artifact_template_scopes(scopes))
        if not normalized_scopes:
            normalized_scopes = [{"scope_type": "any", "scope_name": "", "normalized_scope_name": "", "weight": 1.0}]
        for scope in normalized_scopes:
            con.execute(
                CURRICULUM_ARTIFACT_TEMPLATE_SCOPE.insert().values(
                    template_id=template_id,
                    scope_type=scope["scope_type"],
                    scope_id=scope.get("scope_id"),
                    scope_name=scope.get("scope_name") or None,
                    normalized_scope_name=scope.get("normalized_scope_name") or None,
                    weight=float(cast(float, scope.get("weight") or 1.0)),
                )
            )

    def _candidate_competency_skills(self, con: Connection, profile_competency_id: int) -> list[dict[str, object]]:
        stmt = (
            sa.select(
                COMPETENCY_SKILL.c.id.label("competency_skill_id"),
                COMPETENCY_SKILL.c.skill_id,
                COMPETENCY_SKILL.c.source_skill_name,
                COMPETENCY_SKILL.c.review_state,
                SKILL.c.canonical_name,
                SKILL.c.status.label("skill_status"),
            )
            .select_from(COMPETENCY_SKILL.outerjoin(SKILL, SKILL.c.id == COMPETENCY_SKILL.c.skill_id))
            .where(COMPETENCY_SKILL.c.profile_competency_id == profile_competency_id)
            .order_by(COMPETENCY_SKILL.c.skill_order, COMPETENCY_SKILL.c.id)
        )
        return [
            {
                "competency_skill_id": int(row["competency_skill_id"]),
                "skill_id": int(row["skill_id"]) if row["skill_id"] is not None else None,
                "source_skill_name": row["source_skill_name"],
                "review_state": row["review_state"],
                "canonical_name": row["canonical_name"] or row["source_skill_name"],
                "skill_status": row["skill_status"] or "missing",
            }
            for row in con.execute(stmt).mappings().all()
        ]

    def _candidate_competency_options(self, con: Connection, limit: int = 200) -> list[dict[str, object]]:
        rows = con.execute(
            sa.select(COMPETENCY.c.id, COMPETENCY.c.title, COMPETENCY.c.status)
            .where(COMPETENCY.c.status == "active")
            .order_by(COMPETENCY.c.title, COMPETENCY.c.id)
            .limit(limit)
        ).mappings()
        return [{"id": int(row["id"]), "title": row["title"], "status": row["status"]} for row in rows]

    def _candidate_competency_similarity(
        self,
        con: Connection,
        competency_id: int,
        profile_competency_id: int,
        limit: int = 5,
    ) -> list[dict[str, object]]:
        candidate = con.execute(sa.select(COMPETENCY.c.id, COMPETENCY.c.title).where(COMPETENCY.c.id == competency_id)).mappings().first()
        if candidate is None:
            return []
        candidate_skills = {
            int(value)
            for value in con.execute(
                sa.select(COMPETENCY_SKILL.c.skill_id).where(
                    COMPETENCY_SKILL.c.profile_competency_id == profile_competency_id,
                    COMPETENCY_SKILL.c.skill_id.is_not(None),
                )
            ).scalars()
        }
        candidate_tokens = _competency_token_set(candidate["title"])
        active_rows = con.execute(
            sa.select(COMPETENCY.c.id, COMPETENCY.c.title, COMPETENCY.c.status)
            .where(COMPETENCY.c.status == "active", COMPETENCY.c.id != competency_id)
            .order_by(COMPETENCY.c.title, COMPETENCY.c.id)
        ).mappings()
        scored: list[dict[str, object]] = []
        for row in active_rows:
            target_tokens = _competency_token_set(row["title"])
            token_union = candidate_tokens | target_tokens
            token_overlap = len(candidate_tokens & target_tokens) / len(token_union) if token_union else 0.0
            title_ratio = difflib.SequenceMatcher(
                None,
                normalize_catalog_key(candidate["title"]),
                normalize_catalog_key(row["title"]),
            ).ratio()
            target_skills = self._competency_skill_ids(con, int(row["id"]))
            skill_overlap_count = len(candidate_skills & target_skills)
            skill_overlap = skill_overlap_count / max(1, len(candidate_skills)) if candidate_skills else 0.0
            score = round((0.45 * title_ratio + 0.35 * token_overlap + 0.20 * skill_overlap) * 100, 2)
            if score < 28 and skill_overlap_count == 0:
                continue
            label, recommendation = _competency_similarity_label(score)
            scored.append(
                {
                    "id": int(row["id"]),
                    "title": row["title"],
                    "status": row["status"],
                    "score": score,
                    "label": label,
                    "recommendation": recommendation,
                    "token_overlap_pct": round(token_overlap * 100, 2),
                    "title_similarity_pct": round(title_ratio * 100, 2),
                    "skill_overlap_count": skill_overlap_count,
                    "candidate_skill_count": len(candidate_skills),
                }
            )
        scored.sort(key=lambda item: (float(cast(float, item["score"])), int(cast(int, item["skill_overlap_count"]))), reverse=True)
        return scored[:limit]

    def _competency_skill_ids(self, con: Connection, competency_id: int) -> set[int]:
        rows = con.execute(
            sa.select(COMPETENCY_SKILL.c.skill_id)
            .select_from(COMPETENCY_SKILL.join(PROFILE_COMPETENCY, PROFILE_COMPETENCY.c.id == COMPETENCY_SKILL.c.profile_competency_id))
            .where(PROFILE_COMPETENCY.c.competency_id == competency_id, COMPETENCY_SKILL.c.skill_id.is_not(None))
        ).scalars()
        return {int(value) for value in rows}

    def _ensure_service_profile_competency(self, con: Connection, target_competency_id: int) -> int | None:
        target = con.execute(COMPETENCY.select().where(COMPETENCY.c.id == target_competency_id)).mappings().first()
        if target is None:
            return None
        context = self._ensure_catalog_context(con)
        source_block_id = self._ensure_source_block(con, context.source_sheet_id, str(target["title"]))
        profile_competency_id, _created = self._ensure_profile_competency(
            con,
            profile_id=context.profile_id,
            competency_id=target_competency_id,
            source_block_id=source_block_id,
            title=str(target["title"]),
            review_state="accepted",
        )
        return profile_competency_id

    def _move_candidate_competency_skill(
        self,
        con: Connection,
        competency_skill_id: int,
        target_competency_id: int,
    ) -> dict[str, object]:
        target_profile_competency_id = self._ensure_service_profile_competency(con, target_competency_id)
        if target_profile_competency_id is None:
            return {"status": "target_missing", "competency_skill_id": competency_skill_id}
        row = con.execute(
            sa.select(
                COMPETENCY_SKILL.c.id,
                COMPETENCY_SKILL.c.profile_competency_id,
                COMPETENCY_SKILL.c.skill_id,
                COMPETENCY_SKILL.c.source_skill_name,
                PROFILE_COMPETENCY.c.competency_id.label("source_competency_id"),
            )
            .select_from(COMPETENCY_SKILL.join(PROFILE_COMPETENCY, PROFILE_COMPETENCY.c.id == COMPETENCY_SKILL.c.profile_competency_id))
            .where(COMPETENCY_SKILL.c.id == competency_skill_id)
        ).mappings().first()
        if row is None:
            return {"status": "missing", "competency_skill_id": competency_skill_id}
        duplicate_id = None
        if row["skill_id"] is not None:
            duplicate_id = con.execute(
                sa.select(COMPETENCY_SKILL.c.id)
                .where(
                    COMPETENCY_SKILL.c.profile_competency_id == target_profile_competency_id,
                    COMPETENCY_SKILL.c.skill_id == row["skill_id"],
                )
                .limit(1)
            ).scalar_one_or_none()
        if duplicate_id is not None:
            con.execute(INDICATOR_ROW.update().where(INDICATOR_ROW.c.competency_skill_id == competency_skill_id).values(competency_skill_id=int(duplicate_id)))
            con.execute(COMPETENCY_SKILL.delete().where(COMPETENCY_SKILL.c.id == competency_skill_id))
            status = "deduplicated"
        else:
            next_order = _next_int(con, COMPETENCY_SKILL.c.skill_order, COMPETENCY_SKILL.c.profile_competency_id == target_profile_competency_id, step=10)
            con.execute(
                COMPETENCY_SKILL.update()
                .where(COMPETENCY_SKILL.c.id == competency_skill_id)
                .values(profile_competency_id=target_profile_competency_id, skill_order=next_order, review_state="accepted")
            )
            status = "moved"
        source_competency_id = int(row["source_competency_id"])
        self._close_candidate_competency_if_empty(
            con,
            source_competency_id,
            f"Все skills перенесены в existing competency #{target_competency_id}.",
        )
        return {"status": status, "competency_skill_id": competency_skill_id, "target_competency_id": target_competency_id}

    def _close_candidate_competency_if_empty(self, con: Connection, competency_id: int, note: str) -> bool:
        remaining = con.execute(
            sa.select(COMPETENCY_SKILL.c.id)
            .select_from(COMPETENCY_SKILL.join(PROFILE_COMPETENCY, PROFILE_COMPETENCY.c.id == COMPETENCY_SKILL.c.profile_competency_id))
            .where(PROFILE_COMPETENCY.c.competency_id == competency_id)
            .limit(1)
        ).scalar_one_or_none()
        if remaining is not None:
            return False
        con.execute(COMPETENCY.update().where(COMPETENCY.c.id == competency_id, COMPETENCY.c.status == "candidate").values(status="deprecated"))
        self._resolve_candidate_review_queue(con, competency_id, "ignored", note)
        return True

    def _resolve_candidate_review_queue(self, con: Connection, competency_id: int, status: ReviewStatus, note: str) -> None:
        now = datetime.now(UTC)
        con.execute(
            REVIEW_QUEUE.update()
            .where(REVIEW_QUEUE.c.entity_type == "competency", REVIEW_QUEUE.c.entity_id == competency_id)
            .values(status=status, resolution_note=note.strip() or None, reviewed_at=now if status != "open" else None, updated_at=now)
        )

    def _reference_indicator_levels(self, con: Connection, indicator_id: int) -> list[dict[str, object]]:
        stmt = (
            sa.select(
                INDICATOR_LEVEL_CELL.c.raw_level_label,
                INDICATOR_LEVEL_CELL.c.raw_value,
                INDICATOR_LEVEL_CELL.c.value_kind,
            )
            .where(INDICATOR_LEVEL_CELL.c.indicator_row_id == indicator_id)
            .order_by(INDICATOR_LEVEL_CELL.c.sort_order, INDICATOR_LEVEL_CELL.c.id)
        )
        return [
            {"label": row["raw_level_label"], "value": row["raw_value"], "kind": row["value_kind"]}
            for row in con.execute(stmt).mappings().all()
        ]

    def _reference_skill_aliases(self, con: Connection, skill_id: int) -> list[str]:
        return [
            str(alias)
            for alias in con.execute(
                sa.select(SKILL_ALIAS.c.alias).where(SKILL_ALIAS.c.skill_id == skill_id).order_by(SKILL_ALIAS.c.id)
            ).scalars()
        ]

    def _reference_profile_summary(self, con: Connection, row: sa.RowMapping) -> dict[str, object]:
        profile_id = int(row["id"])
        competency_count = con.execute(
            sa.select(sa.func.count(sa.distinct(PROFILE_COMPETENCY.c.competency_id))).where(
                PROFILE_COMPETENCY.c.profile_id == profile_id
            )
        ).scalar()
        skill_count = con.execute(
            sa.select(sa.func.count(sa.distinct(COMPETENCY_SKILL.c.skill_id)))
            .select_from(COMPETENCY_SKILL.join(PROFILE_COMPETENCY, PROFILE_COMPETENCY.c.id == COMPETENCY_SKILL.c.profile_competency_id))
            .where(PROFILE_COMPETENCY.c.profile_id == profile_id)
        ).scalar()
        indicator_count = con.execute(
            sa.select(sa.func.count(INDICATOR_ROW.c.id))
            .select_from(
                INDICATOR_ROW.join(COMPETENCY_SKILL, COMPETENCY_SKILL.c.id == INDICATOR_ROW.c.competency_skill_id).join(
                    PROFILE_COMPETENCY,
                    PROFILE_COMPETENCY.c.id == COMPETENCY_SKILL.c.profile_competency_id,
                )
            )
            .where(PROFILE_COMPETENCY.c.profile_id == profile_id)
        ).scalar()
        review_competencies = con.execute(
            sa.select(sa.func.count())
            .select_from(PROFILE_COMPETENCY)
            .where(PROFILE_COMPETENCY.c.profile_id == profile_id, PROFILE_COMPETENCY.c.review_state != "accepted")
        ).scalar()
        return {
            "id": profile_id,
            "slug": row["slug"],
            "name": row["name"],
            "source_kind": row["source_kind"],
            "notes": row["notes"] or "",
            "competency_count": int(competency_count or 0),
            "skill_count": int(skill_count or 0),
            "indicator_count": int(indicator_count or 0),
            "review_competencies": int(review_competencies or 0),
        }

    def _reference_profile_competencies(self, con: Connection, profile_id: int) -> list[dict[str, object]]:
        stmt = (
            sa.select(
                PROFILE_COMPETENCY.c.id.label("profile_competency_id"),
                PROFILE_COMPETENCY.c.title_in_source,
                PROFILE_COMPETENCY.c.description_in_source,
                PROFILE_COMPETENCY.c.prerequisites_text,
                PROFILE_COMPETENCY.c.sort_order,
                PROFILE_COMPETENCY.c.review_state,
                COMPETENCY.c.id.label("competency_id"),
                COMPETENCY.c.title,
                COMPETENCY.c.description,
                COMPETENCY.c.status,
            )
            .select_from(PROFILE_COMPETENCY.join(COMPETENCY, COMPETENCY.c.id == PROFILE_COMPETENCY.c.competency_id))
            .where(PROFILE_COMPETENCY.c.profile_id == profile_id)
            .order_by(PROFILE_COMPETENCY.c.sort_order, PROFILE_COMPETENCY.c.id)
        )
        competencies: list[dict[str, object]] = []
        for row in con.execute(stmt).mappings().all():
            skills = self._reference_profile_competency_skills(con, int(row["profile_competency_id"]))
            competencies.append(
                {
                    "profile_competency_id": int(row["profile_competency_id"]),
                    "competency_id": int(row["competency_id"]),
                    "title": row["title"],
                    "title_in_source": row["title_in_source"] or row["title"],
                    "description": row["description"] or "",
                    "description_in_source": row["description_in_source"] or "",
                    "prerequisites_text": row["prerequisites_text"] or "",
                    "status": row["status"],
                    "review_state": row["review_state"],
                    "sort_order": int(row["sort_order"] or 0),
                    "skill_count": len(skills),
                    "indicator_count": sum(len(cast("list[Any]", skill["indicators"])) for skill in skills),
                    "skills": skills,
                }
            )
        return competencies

    def _reference_profile_competency_skills(self, con: Connection, profile_competency_id: int) -> list[dict[str, object]]:
        stmt = (
            sa.select(
                COMPETENCY_SKILL.c.id.label("competency_skill_id"),
                COMPETENCY_SKILL.c.source_skill_name,
                COMPETENCY_SKILL.c.review_state,
                COMPETENCY_SKILL.c.skill_order,
                SKILL.c.id.label("skill_id"),
                SKILL.c.canonical_name,
                SKILL.c.skill_type,
                SKILL.c.status.label("skill_status"),
            )
            .select_from(COMPETENCY_SKILL.outerjoin(SKILL, SKILL.c.id == COMPETENCY_SKILL.c.skill_id))
            .where(COMPETENCY_SKILL.c.profile_competency_id == profile_competency_id)
            .order_by(COMPETENCY_SKILL.c.skill_order, COMPETENCY_SKILL.c.id)
        )
        skills: list[dict[str, object]] = []
        for row in con.execute(stmt).mappings().all():
            skill_id = int(row["skill_id"]) if row["skill_id"] is not None else None
            skills.append(
                {
                    "competency_skill_id": int(row["competency_skill_id"]),
                    "skill_id": skill_id,
                    "name": row["canonical_name"] or row["source_skill_name"],
                    "source_name": row["source_skill_name"],
                    "skill_type": row["skill_type"] or "unknown",
                    "status": row["skill_status"] or "missing",
                    "review_state": row["review_state"],
                    "skill_order": int(row["skill_order"] or 0),
                    "aliases": self._reference_skill_aliases(con, skill_id) if skill_id is not None else [],
                    "indicators": self._reference_indicators(con, int(row["competency_skill_id"])),
                }
            )
        return skills

    @contextmanager
    def _connect(self) -> Iterator[Connection]:
        if isinstance(self.bind, Engine):
            with self.bind.begin() as connection:
                yield connection
        else:
            yield self.bind

    def _insert_projects(self, con: Connection, plan_id: int, projects: list[UPProject]) -> None:
        block_indexes: dict[str, int] = {}
        block_counts: dict[str, int] = {}
        cumulative_days = 0.0
        for row_number, project in enumerate(sorted(projects, key=lambda item: item.order), start=1):
            block_name = project.block or "Без блока"
            block_indexes.setdefault(block_name, len(block_indexes) + 1)
            block_counts[block_name] = block_counts.get(block_name, 0) + 1
            workload_days = _optional_float(project.metadata.get("workload_days"))
            if workload_days is not None:
                cumulative_days += workload_days
            con.execute(
                CURRICULUM_PROJECT.insert().values(
                    **_project_values(
                        plan_id=plan_id,
                        row_number=row_number,
                        block_index=block_indexes[block_name],
                        project_index_in_block=block_counts[block_name],
                        project=project,
                        total_workload_days=cumulative_days
                        if workload_days is not None
                        else _optional_float(project.metadata.get("total_workload_days")),
                    )
                )
            )

    def _project_position(self, con: Connection, plan_id: int, block_name: str) -> tuple[int, int]:
        block = block_name or "Без блока"
        rows = con.execute(
            sa.select(CURRICULUM_PROJECT.c.block_name, CURRICULUM_PROJECT.c.block_index)
            .where(CURRICULUM_PROJECT.c.plan_id == plan_id)
            .order_by(CURRICULUM_PROJECT.c.row_number)
        ).mappings().all()
        block_indexes: dict[str, int] = {}
        for row in rows:
            existing_block = row["block_name"] or "Без блока"
            block_indexes.setdefault(existing_block, int(row["block_index"] or len(block_indexes) + 1))
        block_index = block_indexes.setdefault(block, len(block_indexes) + 1)
        project_index = (
            con.execute(
                sa.select(sa.func.count())
                .select_from(CURRICULUM_PROJECT)
                .where(CURRICULUM_PROJECT.c.plan_id == plan_id, CURRICULUM_PROJECT.c.block_name == block_name)
            ).scalar_one()
            or 0
        ) + 1
        return block_index, int(project_index)

    def _refresh_plan_summary(self, con: Connection, plan_id: int) -> None:
        projects = con.execute(CURRICULUM_PROJECT.select().where(CURRICULUM_PROJECT.c.plan_id == plan_id)).mappings().all()
        block_count = len({row["block_name"] or "Без блока" for row in projects})
        total_hours = sum(float(row["workload_hours"] or 0.0) for row in projects)
        plan = con.execute(CURRICULUM_PLAN.select().where(CURRICULUM_PLAN.c.id == plan_id)).mappings().first()
        if plan is None:
            return
        rows = [_project_from_row(row) for row in sorted(projects, key=lambda item: (int(item["row_number"]), int(item["id"])))]
        up = UPSkeleton(
            status=plan["status"],
            title=plan["title"],
            direction=plan["direction"] or "",
            version=plan["version"] or "v1",
            rows=rows,
            metadata=_json_object(plan["metadata_json"]),
        )
        con.execute(
            CURRICULUM_PLAN.update()
            .where(CURRICULUM_PLAN.c.id == plan_id)
            .values(
                total_blocks=block_count,
                total_projects=len(projects),
                total_hours=total_hours,
                payload_json=up.model_dump(mode="json"),
                updated_at=datetime.now(UTC),
            )
        )

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


def _template_proposal_for_block(
    plan_id: int,
    brief_id: int,
    block_name: str,
    records: list[CurriculumProjectRecord],
    index: int,
) -> dict[str, object]:
    projects = [record.project for record in sorted(records, key=lambda item: item.project.order)]
    titles = [project.title for project in projects if project.title.strip()]
    skills = sorted({ref.canonical_name for project in projects for ref in project.competency_refs if ref.canonical_name.strip()})
    tools = sorted({tool for project in projects for tool in project.required_tools if str(tool).strip()})
    family = _artifact_family_for_curriculum(block_name, skills, tools)
    title = f"{_artifact_family_title(family)}: {block_name}"
    skill_text = ", ".join(skills[:8]) if skills else ", ".join(titles[:4]) or block_name
    return {
        "brief_id": brief_id,
        "plan_id": plan_id,
        "status": "open",
        "code": _slug_catalog_key(f"plan-{plan_id}-{index}-{block_name}"),
        "title": title,
        "artifact_family": family,
        "scope_type": "coverage_area",
        "scope_names_json": [block_name],
        "artifact_description": f"Проверяемый артефакт по блоку «{block_name}»: студент применяет {skill_text}.",
        "project_name_pattern": f"{block_name}: прикладной артефакт",
        "materials_pattern": (
            f"Шаблон артефакта «{title}», исходные материалы проектов блока, инструменты: {', '.join(tools[:6]) or 'Git'}."
        ),
        "storytelling_pattern": "Участник действует в рабочем контексте команды и предъявляет артефакт, который можно проверить по критериям.",
        "validation_criteria": (
            "Артефакт приложен; критерии проверки воспроизводимы; результат связан с образовательными результатами блока."
        ),
        "covered_skill_ids_json": [],
        "covered_skill_names_json": skills,
        "rationale": f"В блоке {len(projects)} проектов; шаблон снижает generic-описания и задаёт единый проверяемый артефакт.",
        "confidence": 0.78 if len(projects) > 1 else 0.68,
        "source": "curriculum_plan_block",
        "updated_at": datetime.now(UTC),
    }


def _artifact_family_for_curriculum(block_name: str, skills: list[str], tools: list[str]) -> str:
    text = normalize_catalog_key(" ".join([block_name, *skills, *tools]))
    if any(token in text for token in ("api", "docker", "ci", "deploy", "linux", "postgres", "sql", "тест", "инфраструкт")):
        return "configuration"
    if any(token in text for token in ("архитект", "проектирован", "design", "ux", "ui")):
        return "design"
    if any(token in text for token in ("анализ", "исслед", "метрик", "data", "эксперимент")):
        return "analysis"
    if any(token in text for token in ("документ", "стратег", "презентац", "отч")):
        return "document"
    return "practice"


def _artifact_family_title(family: str) -> str:
    return {
        "analysis": "Аналитический шаблон",
        "document": "Документальный шаблон",
        "configuration": "Конфигурационный шаблон",
        "design": "Проектный шаблон",
        "production": "Рабочий шаблон",
        "practice": "Практический шаблон",
    }.get(family, "Практический шаблон")


def _proposal_update_values(row: sa.RowMapping, patch: dict[str, object]) -> dict[str, object]:
    values: dict[str, object] = {}
    text_fields = (
        "title",
        "artifact_family",
        "scope_type",
        "artifact_description",
        "project_name_pattern",
        "materials_pattern",
        "storytelling_pattern",
        "validation_criteria",
        "rationale",
        "status",
    )
    for field in text_fields:
        if field in patch and patch[field] is not None:
            values[field] = str(patch[field]).strip()
    if "scope_names" in patch and patch["scope_names"] is not None:
        values["scope_names_json"] = [str(item).strip() for item in _json_list(patch["scope_names"]) if str(item).strip()]
    if "confidence" in patch and patch["confidence"] is not None:
        values["confidence"] = float(cast(float, patch["confidence"]))
    if values.get("title") == "":
        values["title"] = row["title"]
    if values.get("artifact_description") == "":
        values["artifact_description"] = row["artifact_description"]
    return values


def _proposal_from_row(row: sa.RowMapping) -> dict[str, object]:
    return {
        "id": int(row["id"]),
        "brief_id": int(row["brief_id"]),
        "plan_id": int(row["plan_id"]) if row["plan_id"] is not None else None,
        "status": row["status"],
        "code": row["code"],
        "title": row["title"],
        "artifact_family": row["artifact_family"],
        "scope_type": row["scope_type"],
        "scope_names": [str(item) for item in _json_list(row["scope_names_json"]) if str(item).strip()],
        "artifact_description": row["artifact_description"] or "",
        "project_name_pattern": row["project_name_pattern"] or "",
        "materials_pattern": row["materials_pattern"] or "",
        "storytelling_pattern": row["storytelling_pattern"] or "",
        "validation_criteria": row["validation_criteria"] or "",
        "covered_skill_ids": [int(item) for item in _json_list(row["covered_skill_ids_json"]) if str(item).isdigit()],
        "covered_skill_names": [str(item) for item in _json_list(row["covered_skill_names_json"]) if str(item).strip()],
        "rationale": row["rationale"] or "",
        "confidence": float(row["confidence"] or 0.0),
        "source": row["source"] or "curriculum_plan_block",
        "accepted_template_id": int(row["accepted_template_id"]) if row["accepted_template_id"] is not None else None,
        "created_at": _iso_or_none(row["created_at"]),
        "updated_at": _iso_or_none(row["updated_at"]),
    }


def _project_values(
    *,
    plan_id: int,
    row_number: int,
    block_index: int,
    project_index_in_block: int,
    project: UPProject,
    total_workload_days: float | None,
) -> dict[str, object]:
    metadata_payload = project.metadata
    competency_refs = [ref.model_dump(mode="json") for ref in project.competency_refs]
    artifacts = [artifact.model_dump(mode="json") for artifact in project.artifacts]
    return {
        "plan_id": plan_id,
        "row_number": row_number,
        "block_index": block_index,
        "project_index_in_block": project_index_in_block,
        "block_name": project.block,
        "block_goals": project.block_goal,
        "project_order": project.order,
        "title": project.title,
        "description": project.description,
        "expert_notes": metadata_payload.get("expert_notes"),
        "learning_outcomes": project.learning_outcomes,
        "skills": [ref.canonical_name for ref in project.competency_refs],
        "audience_level": metadata_payload.get("audience_level"),
        "required_tools": project.required_tools,
        "sjm": project.storytelling,
        "storytelling_type": metadata_payload.get("storytelling_type"),
        "format": project.format,
        "additional_materials": project.materials,
        "group_size": project.group_size,
        "workload_hours": project.hours_astro,
        "workload_days": _optional_float(metadata_payload.get("workload_days")),
        "total_workload_days": total_workload_days,
        "xp": _optional_int(metadata_payload.get("xp")),
        "passing_threshold": _optional_float(metadata_payload.get("passing_threshold")),
        "required_software": project.required_software,
        "platform_name": metadata_payload.get("platform_name"),
        "gitlab_link": metadata_payload.get("gitlab_link"),
        "outcomes_know": project.outcomes_know,
        "outcomes_can": project.outcomes_can,
        "outcomes_skills": project.outcomes_skills,
        "competency_refs": competency_refs,
        "artifacts_json": artifacts,
        "metadata_json": metadata_payload,
        "payload_json": project.model_dump(mode="json"),
        "updated_at": datetime.now(UTC),
    }


def _project_from_row(row: sa.RowMapping) -> UPProject:
    payload = _json_object(row["payload_json"])
    if payload:
        return UPProject.model_validate(payload)
    return UPProject(
        block=row["block_name"] or "",
        block_goal=row["block_goals"] or "",
        order=int(row["project_order"]),
        title=row["title"],
        description=row["description"] or "",
        outcomes_know=_json_text_list(row["outcomes_know"]),
        outcomes_can=_json_text_list(row["outcomes_can"]),
        outcomes_skills=_json_text_list(row["outcomes_skills"]),
        competency_refs=_json_list(row["competency_refs"]),
        required_tools=_json_text_list(row["required_tools"]),
        required_software=_json_text_list(row["required_software"]),
        materials=row["additional_materials"] or "",
        storytelling=row["sjm"] or "",
        format=row["format"] or "individual",
        group_size=int(row["group_size"] or 1),
        hours_astro=float(row["workload_hours"] or 0.0),
        artifacts=_json_list(row["artifacts_json"]),
        metadata=_json_object(row["metadata_json"]),
    )


def _intake_job_from_row(row: sa.RowMapping) -> dict[str, object]:
    payload = _json_object(row["result_payload"])
    return {
        "id": int(row["id"]),
        "brief_id": int(row["brief_id"]) if row["brief_id"] is not None else None,
        "source_kind": row["source_kind"],
        "source_name": row["source_name"],
        "file_path": row["file_path"],
        "brief_text": row["brief_text"],
        "status": row["status"],
        "current_stage": row["current_stage"],
        "progress_note": row["progress_note"],
        "error_text": row["error_text"],
        "result_payload": payload,
        "use_council": bool(row["use_council"]),
        "created_at": _iso_or_none(row["created_at"]),
        "updated_at": _iso_or_none(row["updated_at"]),
        "started_at": _iso_or_none(row["started_at"]),
        "finished_at": _iso_or_none(row["finished_at"]),
    }


def _json_object(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return dict(decoded) if isinstance(decoded, dict) else {}
    return {}


def _json_list(value: object) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return []
        return decoded if isinstance(decoded, list) else []
    return []


def _json_text_list(value: object) -> list[str]:
    return [str(item) for item in _json_list(value) if str(item).strip()]


def _optional_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(cast(Any, value))
    except (TypeError, ValueError):
        return None


def _optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(cast(Any, value))
    except (TypeError, ValueError):
        return None


def _iso_or_none(value: object) -> str | None:
    return cast(Any, value).isoformat() if hasattr(value, "isoformat") else str(value) if value is not None else None


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


def _competency_token_set(value: object | None) -> set[str]:
    stopwords = {"и", "в", "во", "на", "для", "по", "с", "со", "к", "от", "до", "при", "или", "а", "the", "and", "of", "for"}
    return {token for token in normalize_catalog_key(value).split() if len(token) > 2 and token not in stopwords}


def _competency_similarity_label(score: float) -> tuple[str, str]:
    if score >= 82:
        return "Высокая похожесть", "merge"
    if score >= 62:
        return "Средняя похожесть", "review"
    return "Слабая похожесть", "create"


def _slug_catalog_key(value: str) -> str:
    normalized = normalize_catalog_key(value)
    slug = "-".join(part for part in normalized.split() if part)
    return slug or "item"


def _normalize_artifact_template_scopes(scopes: Iterable[dict[str, object]]) -> Iterator[dict[str, object]]:
    for scope in scopes:
        scope_type = str(scope.get("scope_type") or "coverage_area").strip() or "coverage_area"
        scope_name = str(scope.get("scope_name") or "").strip()
        if scope_type == "any":
            yield {"scope_type": "any", "scope_name": "", "normalized_scope_name": "", "weight": float(cast(float, scope.get("weight") or 1.0))}
            continue
        if not scope_name:
            continue
        yield {
            "scope_type": scope_type,
            "scope_id": _optional_int(scope.get("scope_id")),
            "scope_name": scope_name,
            "normalized_scope_name": str(scope.get("normalized_scope_name") or "").strip() or normalize_catalog_key(scope_name),
            "weight": float(cast(float, scope.get("weight") or 1.0)),
        }


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
        sa.select(INDICATOR_ROW.c.id, INDICATOR_ROW.c.status)
        .where(
            INDICATOR_ROW.c.competency_skill_id == competency_skill_id,
            INDICATOR_ROW.c.dimension_id == dimension_id,
            INDICATOR_ROW.c.base_text == text,
        )
        .order_by(INDICATOR_ROW.c.id)
        .limit(1)
    ).scalar_one_or_none()
    if existing is not None:
        if existing["status"] == "deprecated":
            con.execute(INDICATOR_ROW.update().where(INDICATOR_ROW.c.id == existing["id"]).values(status="active", notes=source_note))
        return int(existing["id"]), False
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
