"""add artifact template tables

Revision ID: 017
Revises: 016
Create Date: 2026-06-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None

ARTIFACT_TEMPLATE_TABLES = {
    "curriculum_artifact_template",
    "curriculum_artifact_template_scope",
    "curriculum_artifact_template_proposal",
}


def upgrade() -> None:
    op.create_table(
        "curriculum_artifact_template",
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
        sa.CheckConstraint(
            "artifact_family IN ('analysis','document','configuration','design','production','practice')",
            name="ck_artifact_template_family",
        ),
        sa.CheckConstraint("status IN ('active','draft','deprecated')", name="ck_artifact_template_status"),
    )
    op.create_table(
        "curriculum_artifact_template_scope",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("curriculum_artifact_template.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope_type", sa.Text(), nullable=False),
        sa.Column("scope_id", sa.Integer()),
        sa.Column("scope_name", sa.Text()),
        sa.Column("normalized_scope_name", sa.Text()),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint(
            "scope_type IN ('taxonomy_node','skill_group','coverage_area','any')",
            name="ck_artifact_template_scope_type",
        ),
        sa.UniqueConstraint("template_id", "scope_type", "scope_id", "normalized_scope_name", name="uq_artifact_template_scope"),
    )
    op.create_table(
        "curriculum_artifact_template_proposal",
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
        sa.CheckConstraint(
            "artifact_family IN ('analysis','document','configuration','design','production','practice')",
            name="ck_artifact_template_proposal_family",
        ),
        sa.CheckConstraint(
            "scope_type IN ('taxonomy_node','skill_group','coverage_area','any')",
            name="ck_artifact_template_proposal_scope",
        ),
        sa.UniqueConstraint("brief_id", "code", name="uq_artifact_template_proposal_brief_code"),
    )
    op.create_index(
        "idx_artifact_template_status",
        "curriculum_artifact_template",
        ["status", "artifact_family", "priority"],
    )
    op.create_index(
        "idx_artifact_template_scope",
        "curriculum_artifact_template_scope",
        ["scope_type", "normalized_scope_name"],
    )
    op.create_index(
        "idx_artifact_template_proposal_brief",
        "curriculum_artifact_template_proposal",
        ["brief_id", "status", "id"],
    )


def downgrade() -> None:
    op.drop_index("idx_artifact_template_proposal_brief", table_name="curriculum_artifact_template_proposal")
    op.drop_index("idx_artifact_template_scope", table_name="curriculum_artifact_template_scope")
    op.drop_index("idx_artifact_template_status", table_name="curriculum_artifact_template")
    op.drop_table("curriculum_artifact_template_proposal")
    op.drop_table("curriculum_artifact_template_scope")
    op.drop_table("curriculum_artifact_template")
