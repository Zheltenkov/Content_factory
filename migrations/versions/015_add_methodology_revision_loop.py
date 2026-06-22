"""Add methodology human-in-the-loop revision tables.

Revision ID: 015
Revises: 014
Create Date: 2026-06-22 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None

REVISION_TABLES = {
    "methodology_revision_session",
    "methodology_revision_checkpoint",
    "methodology_revision_change_request",
}


def upgrade() -> None:
    op.create_table(
        "methodology_revision_session",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("artifact_ref", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.Text(), nullable=False, server_default="open"),
        sa.Column("current_node", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint(
            "status IN ('open', 'approved', 'rejected', 'rolled_back', 'closed')",
            name="ck_methodology_revision_session_status",
        ),
    )
    op.create_table(
        "methodology_revision_checkpoint",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("methodology_revision_session.id", ondelete="CASCADE"), nullable=False),
        sa.Column("checkpoint_id", sa.Text(), nullable=False),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("node_id", sa.Text(), nullable=False),
        sa.Column("resume_from_node", sa.Text(), nullable=False),
        sa.Column("artifact_hash", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("context_snapshot_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'rolled_back')",
            name="ck_methodology_revision_checkpoint_status",
        ),
    )
    op.create_table(
        "methodology_revision_change_request",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("methodology_revision_session.id", ondelete="CASCADE"), nullable=False),
        sa.Column("checkpoint_row_id", sa.Integer(), sa.ForeignKey("methodology_revision_checkpoint.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("target_stage", sa.Text(), nullable=False),
        sa.Column("target_selector", sa.Text(), nullable=False, server_default=""),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("instruction", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("session_id", "action_id", name="uq_methodology_revision_change_action"),
        sa.CheckConstraint(
            "status IN ('pending', 'applied', 'skipped', 'rejected')",
            name="ck_methodology_revision_change_status",
        ),
    )
    op.create_index("idx_methodology_revision_session_run", "methodology_revision_session", ["run_id"])
    op.create_index(
        "idx_methodology_revision_checkpoint_session",
        "methodology_revision_checkpoint",
        ["session_id", "created_at"],
    )
    op.create_index(
        "idx_methodology_revision_change_pending",
        "methodology_revision_change_request",
        ["session_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("idx_methodology_revision_change_pending", table_name="methodology_revision_change_request")
    op.drop_index("idx_methodology_revision_checkpoint_session", table_name="methodology_revision_checkpoint")
    op.drop_index("idx_methodology_revision_session_run", table_name="methodology_revision_session")
    op.drop_table("methodology_revision_change_request")
    op.drop_table("methodology_revision_checkpoint")
    op.drop_table("methodology_revision_session")
