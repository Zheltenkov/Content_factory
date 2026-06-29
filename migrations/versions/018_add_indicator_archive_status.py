"""add indicator archive status

Revision ID: 018
Revises: 017
Create Date: 2026-06-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None

ARCHIVE_COLUMNS = {"indicator_row.status"}


def upgrade() -> None:
    op.add_column("indicator_row", sa.Column("status", sa.Text(), nullable=False, server_default="active"))
    op.create_check_constraint("ck_indicator_row_status", "indicator_row", "status IN ('active', 'deprecated')")
    op.create_index("idx_indicator_row_status", "indicator_row", ["status", "competency_skill_id"])


def downgrade() -> None:
    op.drop_index("idx_indicator_row_status", table_name="indicator_row")
    op.drop_constraint("ck_indicator_row_status", "indicator_row", type_="check")
    op.drop_column("indicator_row", "status")
