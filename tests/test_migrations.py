from __future__ import annotations

import os
from pathlib import Path
from importlib import import_module

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError


def _database_url() -> str | None:
    if url := os.getenv("DATABASE_URL"):
        return url
    env_path = Path(".env")
    if not env_path.exists():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and stripped.startswith("DATABASE_URL="):
            return stripped.split("=", 1)[1].strip().strip("\"'")
    return None


def _psycopg_url(url: str) -> str:
    return "postgresql+psycopg://" + url.removeprefix("postgresql://") if url.startswith("postgresql://") else url


def test_alembic_chain_points_to_current_head() -> None:
    script = ScriptDirectory.from_config(Config("alembic.ini"))

    assert script.get_heads() == ["018"]
    assert len(list(script.walk_revisions())) == 18


def test_reference_catalog_revision_declares_key_tables() -> None:
    migration = import_module("migrations.versions.013_add_reference_catalog_schema")

    assert migration.KEY_CATALOG_TABLES <= set(migration.CATALOG_TABLES)
    assert {
        "source_workbook",
        "skill_alias",
        "ai_analysis_run",
        "ai_analysis_suggestion",
        "review_queue",
    } <= set(migration.CATALOG_TABLES)


def test_curriculum_plan_revision_declares_alias_columns() -> None:
    migration = import_module("migrations.versions.014_add_curriculum_plan_tables")

    assert migration.CURRICULUM_ALIAS_FIELD_TO_COLUMN["order"] == "project_order"
    assert set(migration.CURRICULUM_ALIAS_FIELD_TO_COLUMN) == {
        "block_name",
        "block_goals",
        "order",
        "title",
        "description",
        "expert_notes",
        "learning_outcomes",
        "skills",
        "audience_level",
        "required_tools",
        "sjm",
        "storytelling_type",
        "format",
        "additional_materials",
        "group_size",
        "workload_hours",
        "workload_days",
        "total_workload_days",
        "xp",
        "passing_threshold",
        "required_software",
        "platform_name",
        "gitlab_link",
    }
    assert {
        "block_name",
        "block_goals",
        "project_order",
        "title",
        "description",
        "learning_outcomes",
        "skills",
        "required_tools",
        "sjm",
        "format",
        "workload_hours",
        "platform_name",
        "gitlab_link",
    } <= set(migration.CURRICULUM_PROJECT_COLUMNS)


def test_methodology_revision_loop_declares_key_tables() -> None:
    migration = import_module("migrations.versions.015_add_methodology_revision_loop")

    assert migration.REVISION_TABLES == {
        "methodology_revision_session",
        "methodology_revision_checkpoint",
        "methodology_revision_change_request",
    }


def test_intake_runtime_revision_declares_minimal_tables() -> None:
    migration = import_module("migrations.versions.016_add_intake_runtime_tables")

    assert migration.revision == "016"
    assert migration.down_revision == "015"
    assert migration.INTAKE_RUNTIME_TABLES == {"profile_brief", "intake_job"}


def test_artifact_template_revision_declares_key_tables() -> None:
    migration = import_module("migrations.versions.017_add_artifact_template_tables")

    assert migration.revision == "017"
    assert migration.down_revision == "016"
    assert migration.ARTIFACT_TEMPLATE_TABLES == {
        "curriculum_artifact_template",
        "curriculum_artifact_template_scope",
        "curriculum_artifact_template_proposal",
    }


def test_indicator_archive_revision_declares_status_column() -> None:
    migration = import_module("migrations.versions.018_add_indicator_archive_status")

    assert migration.revision == "018"
    assert migration.down_revision == "017"
    assert migration.ARCHIVE_COLUMNS == {"indicator_row.status"}


def test_database_url_connects_when_postgres_is_available() -> None:
    url = _database_url()
    if not url:
        pytest.skip("DATABASE_URL is not configured.")

    engine = create_engine(_psycopg_url(url), connect_args={"connect_timeout": 2})
    try:
        with engine.connect() as connection:
            assert connection.execute(text("select 1")).scalar_one() == 1
    except SQLAlchemyError as exc:
        pytest.skip(f"PostgreSQL is not available: {exc.__class__.__name__}")
