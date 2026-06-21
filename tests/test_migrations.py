from __future__ import annotations

import os
from pathlib import Path

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


def test_alembic_chain_points_to_current_cg_head() -> None:
    script = ScriptDirectory.from_config(Config("alembic.ini"))

    assert script.get_heads() == ["012"]
    assert len(list(script.walk_revisions())) == 12


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
