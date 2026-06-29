"""Add Spravochnik intake runtime tables.

Revision ID: 016
Revises: 015
Create Date: 2026-06-22 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None
INTAKE_RUNTIME_TABLES = {"profile_brief", "intake_job"}


def upgrade() -> None:
    op.create_table(
        "profile_brief",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=True),
        sa.Column("seniority", sa.Text(), nullable=True),
        sa.Column("domain", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table(
        "intake_job",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("brief_id", sa.Integer(), sa.ForeignKey("profile_brief.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_kind", sa.Text(), nullable=False),
        sa.Column("source_name", sa.Text(), nullable=True),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("brief_text", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("current_stage", sa.Text(), nullable=True),
        sa.Column("progress_note", sa.Text(), nullable=True),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("result_payload", sa.JSON(), nullable=True),
        sa.Column("use_council", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("source_kind IN ('text', 'file')", name="ck_intake_job_source_kind"),
        sa.CheckConstraint("status IN ('pending', 'running', 'succeeded', 'failed')", name="ck_intake_job_status"),
    )
    op.create_index("idx_intake_job_created", "intake_job", ["created_at"])
    op.create_index("idx_intake_job_status", "intake_job", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_intake_job_status", table_name="intake_job")
    op.drop_index("idx_intake_job_created", table_name="intake_job")
    op.drop_table("intake_job")
    op.drop_table("profile_brief")
