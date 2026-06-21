"""Add persistent curriculum plan tables.

Revision ID: 014
Revises: 013
Create Date: 2026-06-21 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None

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


def upgrade() -> None:
    op.create_table(
        "curriculum_plan",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("profile.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_policy", sa.Text(), nullable=False, server_default="accepted_only"),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("direction", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Text(), nullable=False, server_default="v1"),
        sa.Column("author_ref", sa.Text(), nullable=True),
        sa.Column("total_blocks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_projects", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_hours", sa.Float(), nullable=False, server_default="0"),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("status IN ('built', 'deferred', 'draft', 'invalid', 'archived')", name="ck_curriculum_plan_status"),
    )
    op.create_table(
        "curriculum_project",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("curriculum_plan.id", ondelete="CASCADE"), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("block_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("project_index_in_block", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("block_name", sa.Text(), nullable=True),
        sa.Column("block_goals", sa.Text(), nullable=True),
        sa.Column("project_order", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("expert_notes", sa.Text(), nullable=True),
        sa.Column("learning_outcomes", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("skills", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("audience_level", sa.Text(), nullable=True),
        sa.Column("required_tools", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("sjm", sa.Text(), nullable=True),
        sa.Column("storytelling_type", sa.Text(), nullable=True),
        sa.Column("format", sa.Text(), nullable=False, server_default="individual"),
        sa.Column("additional_materials", sa.Text(), nullable=True),
        sa.Column("group_size", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("workload_hours", sa.Float(), nullable=False, server_default="0"),
        sa.Column("workload_days", sa.Float(), nullable=True),
        sa.Column("total_workload_days", sa.Float(), nullable=True),
        sa.Column("xp", sa.Integer(), nullable=True),
        sa.Column("passing_threshold", sa.Float(), nullable=True),
        sa.Column("required_software", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("platform_name", sa.Text(), nullable=True),
        sa.Column("gitlab_link", sa.Text(), nullable=True),
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
    op.create_index("idx_curriculum_plan_profile_status", "curriculum_plan", ["profile_id", "status"])
    op.create_index("idx_curriculum_plan_updated", "curriculum_plan", ["updated_at"])
    op.create_index("idx_curriculum_project_plan_order", "curriculum_project", ["plan_id", "project_order"])
    op.create_index("idx_curriculum_project_block", "curriculum_project", ["plan_id", "block_name", "project_order"])


def downgrade() -> None:
    op.drop_index("idx_curriculum_project_block", table_name="curriculum_project")
    op.drop_index("idx_curriculum_project_plan_order", table_name="curriculum_project")
    op.drop_index("idx_curriculum_plan_updated", table_name="curriculum_plan")
    op.drop_index("idx_curriculum_plan_profile_status", table_name="curriculum_plan")
    op.drop_table("curriculum_project")
    op.drop_table("curriculum_plan")
