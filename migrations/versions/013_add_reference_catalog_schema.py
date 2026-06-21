"""Add reference catalog schema.

Revision ID: 013
Revises: 012
Create Date: 2026-06-21 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None

CATALOG_TABLES = (
    "ingest_run",
    "source_workbook",
    "source_sheet",
    "source_block",
    "profile",
    "profile_source",
    "proficiency_scale",
    "proficiency_level",
    "dimension",
    "competency",
    "typed_competency",
    "profile_competency",
    "skill",
    "skill_alias",
    "competency_skill",
    "typed_competency_skill",
    "indicator_row",
    "indicator_row_meta",
    "indicator_level_cell",
    "taxonomy_node",
    "taxonomy_edge",
    "skill_taxonomy",
    "course",
    "project",
    "project_indicator",
    "ai_analysis_run",
    "ai_analysis_suggestion",
    "review_queue",
)
KEY_CATALOG_TABLES = {
    "ingest_run",
    "source_workbook",
    "profile",
    "competency",
    "skill",
    "skill_alias",
    "ai_analysis_run",
    "ai_analysis_suggestion",
    "review_queue",
}


def id_col() -> sa.Column[int]:
    return sa.Column("id", sa.Integer(), primary_key=True)


def text_col(name: str, nullable: bool = True, unique: bool = False, default: str | None = None) -> sa.Column[str]:
    return sa.Column(name, sa.Text(), nullable=nullable, unique=unique, server_default=default)


def int_col(name: str, nullable: bool = True, default: str | None = None) -> sa.Column[int]:
    return sa.Column(name, sa.Integer(), nullable=nullable, server_default=default)


def float_col(name: str, nullable: bool = True) -> sa.Column[float]:
    return sa.Column(name, sa.Float(), nullable=nullable)


def ts_col(name: str, nullable: bool = True, default_now: bool = False) -> sa.Column[object]:
    return sa.Column(name, sa.DateTime(), nullable=nullable, server_default=sa.text("CURRENT_TIMESTAMP") if default_now else None)


def check(name: str, expression: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(expression, name=name)


def fk_col(name: str, target: str, nullable: bool = False, ondelete: str = "CASCADE") -> sa.Column[int]:
    return sa.Column(name, sa.Integer(), sa.ForeignKey(target, ondelete=ondelete), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "ingest_run",
        id_col(),
        ts_col("started_at", nullable=False, default_now=True),
        ts_col("finished_at"),
        text_col("source_root", nullable=False),
        text_col("status", nullable=False, default="active"),
        sa.Column("summary_json", sa.JSON(), nullable=True),
        check("ck_ingest_run_status", "status IN ('running', 'completed', 'failed')"),
    )
    op.create_table(
        "source_workbook",
        id_col(),
        fk_col("ingest_run_id", "ingest_run.id"),
        text_col("file_path", nullable=False),
        text_col("file_name", nullable=False),
        text_col("sha256", nullable=False),
        ts_col("last_modified_utc"),
        text_col("source_kind", nullable=False),
        check("ck_source_workbook_kind", "source_kind IN ('role_profile', 'template', 'draft', 'reference')"),
        sa.UniqueConstraint("ingest_run_id", "file_path", name="uq_source_workbook_run_path"),
    )
    op.create_table(
        "source_sheet",
        id_col(),
        fk_col("source_workbook_id", "source_workbook.id"),
        text_col("sheet_name", nullable=False),
        int_col("sheet_order", nullable=False),
        int_col("is_skipped", nullable=False, default="0"),
        text_col("skip_reason"),
        check("ck_source_sheet_skipped", "is_skipped IN (0, 1)"),
        sa.UniqueConstraint("source_workbook_id", "sheet_order", name="uq_source_sheet_order"),
    )
    op.create_table(
        "source_block",
        id_col(),
        fk_col("source_sheet_id", "source_sheet.id"),
        int_col("block_no", nullable=False),
        int_col("header_row_number", nullable=False),
        int_col("level_row_number"),
        int_col("end_row_number"),
        text_col("raw_title"),
        text_col("raw_description"),
        text_col("raw_prerequisites"),
        text_col("raw_scale_signature"),
        sa.UniqueConstraint("source_sheet_id", "block_no", name="uq_source_block_no"),
    )
    op.create_table(
        "profile",
        id_col(),
        text_col("slug", nullable=False, unique=True),
        text_col("name", nullable=False),
        text_col("source_kind", nullable=False),
        text_col("notes"),
        check("ck_profile_source_kind", "source_kind IN ('role_profile', 'template', 'draft', 'reference')"),
    )
    op.create_table(
        "profile_source",
        id_col(),
        fk_col("profile_id", "profile.id"),
        fk_col("source_workbook_id", "source_workbook.id"),
        text_col("version_label"),
        int_col("is_primary", nullable=False, default="1"),
        check("ck_profile_source_primary", "is_primary IN (0, 1)"),
        sa.UniqueConstraint("profile_id", "source_workbook_id", name="uq_profile_source_workbook"),
    )
    op.create_table(
        "proficiency_scale",
        id_col(),
        text_col("code", nullable=False, unique=True),
        text_col("title", nullable=False),
        text_col("normalized_signature", nullable=False, unique=True),
        text_col("description"),
    )
    op.create_table(
        "proficiency_level",
        id_col(),
        fk_col("scale_id", "proficiency_scale.id"),
        text_col("code", nullable=False),
        text_col("title", nullable=False),
        int_col("sort_order", nullable=False),
        text_col("canonical_band"),
        sa.UniqueConstraint("scale_id", "code", name="uq_proficiency_level_code"),
        sa.UniqueConstraint("scale_id", "title", name="uq_proficiency_level_title"),
    )
    op.create_table("dimension", id_col(), text_col("code", nullable=False, unique=True), text_col("title", nullable=False))
    _seed_dimensions()
    op.create_table(
        "competency",
        id_col(),
        text_col("normalized_title", nullable=False, unique=True),
        text_col("title", nullable=False),
        text_col("description"),
        text_col("status", nullable=False),
        check("ck_competency_status", "status IN ('active', 'candidate', 'deprecated')"),
    )
    op.create_table(
        "typed_competency",
        id_col(),
        text_col("normalized_name", nullable=False, unique=True),
        text_col("name", nullable=False, unique=True),
        int_col("sort_order", nullable=False),
        text_col("source", nullable=False, default="manual"),
        text_col("status", nullable=False, default="active"),
        check("ck_typed_competency_source", "source IN ('manual', 'live_snapshot', 'derived')"),
        check("ck_typed_competency_status", "status IN ('active', 'candidate', 'deprecated')"),
    )
    op.create_table(
        "profile_competency",
        id_col(),
        fk_col("profile_id", "profile.id"),
        fk_col("competency_id", "competency.id"),
        fk_col("source_block_id", "source_block.id"),
        fk_col("scale_id", "proficiency_scale.id", nullable=True, ondelete="SET NULL"),
        text_col("title_in_source"),
        text_col("description_in_source"),
        text_col("prerequisites_text"),
        int_col("sort_order", nullable=False),
        text_col("review_state", nullable=False, default="accepted"),
        check("ck_profile_competency_review", "review_state IN ('accepted', 'needs_review', 'draft')"),
        sa.UniqueConstraint("profile_id", "source_block_id", name="uq_profile_competency_block"),
    )
    op.create_table(
        "skill",
        id_col(),
        text_col("normalized_name", nullable=False, unique=True),
        text_col("canonical_name", nullable=False),
        text_col("skill_type", nullable=False, default="unknown"),
        text_col("status", nullable=False, default="active"),
        check("ck_skill_type", "skill_type IN ('hard', 'soft', 'domain', 'tool', 'process', 'unknown')"),
        check("ck_skill_status", "status IN ('active', 'candidate', 'deprecated')"),
    )
    op.create_table(
        "skill_alias",
        id_col(),
        fk_col("skill_id", "skill.id"),
        text_col("alias", nullable=False),
        text_col("normalized_alias", nullable=False),
        text_col("source"),
        sa.UniqueConstraint("skill_id", "normalized_alias", name="uq_skill_alias_normalized"),
    )
    op.create_table(
        "competency_skill",
        id_col(),
        fk_col("profile_competency_id", "profile_competency.id"),
        fk_col("skill_id", "skill.id", nullable=True, ondelete="SET NULL"),
        text_col("source_skill_name", nullable=False),
        int_col("skill_order", nullable=False),
        text_col("review_state", nullable=False, default="accepted"),
        check("ck_competency_skill_review", "review_state IN ('accepted', 'needs_review', 'draft')"),
        sa.UniqueConstraint("profile_competency_id", "skill_order", name="uq_competency_skill_order"),
    )
    op.create_table(
        "typed_competency_skill",
        id_col(),
        fk_col("typed_competency_id", "typed_competency.id"),
        fk_col("skill_id", "skill.id", nullable=True, ondelete="SET NULL"),
        text_col("source_skill_name", nullable=False),
        int_col("sort_order", nullable=False),
        text_col("resolution_status", nullable=False, default="matched"),
        text_col("match_note"),
        text_col("source", nullable=False, default="manual"),
        check("ck_typed_competency_skill_resolution", "resolution_status IN ('matched', 'alias', 'manual', 'fuzzy', 'missing')"),
        check("ck_typed_competency_skill_source", "source IN ('manual', 'live_snapshot', 'derived')"),
        sa.UniqueConstraint("typed_competency_id", "source_skill_name", name="uq_typed_competency_skill_source"),
    )
    op.create_table(
        "indicator_row",
        id_col(),
        fk_col("competency_skill_id", "competency_skill.id"),
        fk_col("dimension_id", "dimension.id", ondelete="RESTRICT"),
        int_col("source_row_number", nullable=False),
        int_col("inherited_skill", nullable=False, default="0"),
        int_col("inherited_dimension", nullable=False, default="0"),
        text_col("base_text"),
        text_col("raw_number"),
        text_col("notes"),
        check("ck_indicator_row_inherited_skill", "inherited_skill IN (0, 1)"),
        check("ck_indicator_row_inherited_dimension", "inherited_dimension IN (0, 1)"),
        sa.UniqueConstraint("competency_skill_id", "source_row_number", name="uq_indicator_row_source"),
    )
    op.create_table(
        "indicator_row_meta",
        id_col(),
        fk_col("indicator_row_id", "indicator_row.id"),
        text_col("meta_key", nullable=False),
        text_col("meta_value", nullable=False),
        sa.UniqueConstraint("indicator_row_id", "meta_key", name="uq_indicator_row_meta_key"),
    )
    op.create_table(
        "indicator_level_cell",
        id_col(),
        fk_col("indicator_row_id", "indicator_row.id"),
        fk_col("proficiency_level_id", "proficiency_level.id", nullable=True, ondelete="SET NULL"),
        text_col("raw_level_label", nullable=False),
        text_col("raw_value", nullable=False),
        text_col("value_kind", nullable=False),
        int_col("sort_order", nullable=False),
        check("ck_indicator_level_cell_kind", "value_kind IN ('text', 'marker_plus', 'marker_minus', 'numeric', 'blank')"),
        sa.UniqueConstraint("indicator_row_id", "raw_level_label", "sort_order", name="uq_indicator_level_cell"),
    )
    _create_taxonomy_and_project_tables()
    _create_ai_and_review_tables()
    _create_indexes()
    _create_views()


def _seed_dimensions() -> None:
    op.bulk_insert(
        sa.table("dimension", sa.column("code", sa.Text()), sa.column("title", sa.Text())),
        [
            {"code": "knowledge", "title": "Знает"},
            {"code": "ability", "title": "Умеет"},
            {"code": "proficiency", "title": "Владеет"},
            {"code": "understanding", "title": "Понимает"},
            {"code": "unspecified", "title": "Не указано"},
        ],
    )


def _create_taxonomy_and_project_tables() -> None:
    op.create_table(
        "taxonomy_node",
        id_col(),
        text_col("normalized_name", nullable=False, unique=True),
        text_col("name", nullable=False),
        text_col("node_type", nullable=False),
        fk_col("parent_id", "taxonomy_node.id", nullable=True, ondelete="SET NULL"),
        text_col("description"),
        check("ck_taxonomy_node_type", "node_type IN ('domain', 'topic', 'tool', 'method', 'concept', 'role')"),
    )
    op.create_table(
        "taxonomy_edge",
        id_col(),
        fk_col("from_node_id", "taxonomy_node.id"),
        fk_col("to_node_id", "taxonomy_node.id"),
        text_col("relation_type", nullable=False),
        float_col("weight"),
        check("ck_taxonomy_edge_relation", "relation_type IN ('parent_of', 'depends_on', 'related_to', 'uses', 'part_of')"),
        sa.UniqueConstraint("from_node_id", "to_node_id", "relation_type", name="uq_taxonomy_edge"),
    )
    op.create_table(
        "skill_taxonomy",
        fk_col("skill_id", "skill.id"),
        fk_col("taxonomy_node_id", "taxonomy_node.id"),
        text_col("relation_type", nullable=False),
        check("ck_skill_taxonomy_relation", "relation_type IN ('belongs_to', 'depends_on', 'uses', 'recommended_for')"),
        sa.PrimaryKeyConstraint("skill_id", "taxonomy_node_id", "relation_type", name="pk_skill_taxonomy"),
    )
    op.create_table("course", id_col(), text_col("code", nullable=False, unique=True), text_col("title", nullable=False), text_col("description"))
    op.create_table(
        "project",
        id_col(),
        text_col("external_id"),
        text_col("code", nullable=False, unique=True),
        text_col("title", nullable=False),
        fk_col("course_id", "course.id", nullable=True, ondelete="SET NULL"),
        text_col("description"),
        text_col("repo_url"),
        int_col("time_hours"),
        int_col("is_active", nullable=False, default="1"),
        ts_col("created_at", nullable=False, default_now=True),
        ts_col("updated_at"),
        check("ck_project_active", "is_active IN (0, 1)"),
    )
    op.create_table(
        "project_indicator",
        id_col(),
        fk_col("project_id", "project.id"),
        fk_col("indicator_level_cell_id", "indicator_level_cell.id", nullable=True, ondelete="SET NULL"),
        fk_col("indicator_row_id", "indicator_row.id", nullable=True, ondelete="SET NULL"),
        text_col("source", nullable=False, default="manual"),
        float_col("confidence"),
        text_col("note"),
        ts_col("created_at", nullable=False, default_now=True),
        check("ck_project_indicator_source", "source IN ('manual', 'ai_chatgpt', 'ai_deepseek', 'import')"),
    )


def _create_ai_and_review_tables() -> None:
    op.create_table(
        "ai_analysis_run",
        id_col(),
        fk_col("project_id", "project.id"),
        text_col("provider", nullable=False),
        text_col("status", nullable=False),
        ts_col("started_at", nullable=False, default_now=True),
        ts_col("finished_at"),
        text_col("prompt_version"),
        text_col("raw_output"),
        text_col("summary"),
        check("ck_ai_analysis_run_provider", "provider IN ('chatgpt', 'deepseek', 'other')"),
        check("ck_ai_analysis_run_status", "status IN ('queued', 'running', 'completed', 'failed')"),
    )
    op.create_table(
        "ai_analysis_suggestion",
        id_col(),
        fk_col("run_id", "ai_analysis_run.id"),
        fk_col("project_indicator_id", "project_indicator.id", nullable=True, ondelete="SET NULL"),
        fk_col("competency_id", "competency.id", nullable=True, ondelete="SET NULL"),
        fk_col("skill_id", "skill.id", nullable=True, ondelete="SET NULL"),
        fk_col("indicator_row_id", "indicator_row.id", nullable=True, ondelete="SET NULL"),
        text_col("suggested_text"),
        text_col("suggested_dimension"),
        text_col("rationale"),
        float_col("confidence"),
        text_col("decision", nullable=False, default="pending"),
        check("ck_ai_analysis_suggestion_decision", "decision IN ('pending', 'accepted', 'rejected')"),
        sa.UniqueConstraint("run_id", "indicator_row_id", "suggested_text", name="uq_ai_analysis_suggestion_text"),
    )
    op.create_table(
        "review_queue",
        id_col(),
        text_col("entity_type", nullable=False),
        int_col("entity_id"),
        text_col("source_ref"),
        text_col("reason_code", nullable=False),
        text_col("severity", nullable=False),
        text_col("details"),
        text_col("status", nullable=False, default="open"),
        text_col("resolution_note"),
        ts_col("reviewed_at"),
        ts_col("updated_at"),
        ts_col("created_at", nullable=False, default_now=True),
        check(
            "ck_review_queue_entity_type",
            "entity_type IN ('workbook', 'sheet', 'block', 'competency', 'skill', 'indicator_row', 'profile', 'project', 'project_indicator', 'ai_analysis_run', 'prerequisite_edge')",
        ),
        check("ck_review_queue_severity", "severity IN ('info', 'warning', 'error')"),
        check("ck_review_queue_status", "status IN ('open', 'resolved', 'ignored')"),
    )


def _create_indexes() -> None:
    for index_name, table_name, columns in (
        ("idx_source_sheet_workbook", "source_sheet", ["source_workbook_id", "is_skipped"]),
        ("idx_source_block_sheet", "source_block", ["source_sheet_id", "block_no"]),
        ("idx_typed_competency_order", "typed_competency", ["sort_order", "name"]),
        ("idx_profile_competency_profile", "profile_competency", ["profile_id", "sort_order"]),
        ("idx_profile_competency_competency", "profile_competency", ["competency_id"]),
        ("idx_skill_alias_normalized", "skill_alias", ["normalized_alias"]),
        ("idx_competency_skill_profile_competency", "competency_skill", ["profile_competency_id", "skill_order"]),
        ("idx_competency_skill_skill", "competency_skill", ["skill_id"]),
        ("idx_typed_competency_skill_typed_competency", "typed_competency_skill", ["typed_competency_id", "sort_order"]),
        ("idx_typed_competency_skill_skill", "typed_competency_skill", ["skill_id", "resolution_status"]),
        ("idx_indicator_row_skill", "indicator_row", ["competency_skill_id", "source_row_number"]),
        ("idx_indicator_level_row", "indicator_level_cell", ["indicator_row_id", "sort_order"]),
        ("idx_project_course", "project", ["course_id", "is_active"]),
        ("idx_project_indicator_project", "project_indicator", ["project_id", "source"]),
        ("idx_project_indicator_indicator_row", "project_indicator", ["indicator_row_id"]),
        ("idx_ai_analysis_run_project", "ai_analysis_run", ["project_id", "provider", "status"]),
        ("idx_ai_analysis_suggestion_run", "ai_analysis_suggestion", ["run_id", "decision"]),
        ("idx_review_queue_status", "review_queue", ["status", "severity", "reason_code"]),
    ):
        op.create_index(index_name, table_name, columns)


def _create_views() -> None:
    op.execute(
        """
        CREATE VIEW v_skill_usage AS
        SELECT
            s.id AS skill_id,
            s.canonical_name,
            s.normalized_name,
            COUNT(DISTINCT cs.profile_competency_id) AS competency_links,
            COUNT(DISTINCT pc.profile_id) AS profile_count
        FROM skill s
        JOIN competency_skill cs ON cs.skill_id = s.id
        JOIN profile_competency pc ON pc.id = cs.profile_competency_id
        GROUP BY s.id, s.canonical_name, s.normalized_name
        """
    )
    op.execute(
        """
        CREATE VIEW v_pending_reviews AS
        SELECT id, entity_type, entity_id, source_ref, reason_code, severity, details, status, created_at
        FROM review_queue
        WHERE status = 'open'
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_pending_reviews")
    op.execute("DROP VIEW IF EXISTS v_skill_usage")
    for table_name in reversed(CATALOG_TABLES):
        op.drop_table(table_name)
