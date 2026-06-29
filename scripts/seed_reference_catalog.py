"""Seed the unified Postgres reference catalog from the legacy Spravochnik SQLite.

The Spravochnik catalog data (competencies, skills, aliases, indicators, profiles,
review queue, provenance) is not stored in git — it lives in the database. This
script reloads it into Postgres from the legacy SQLite snapshot, so a fresh or
recreated database can be repopulated with one command.

It copies every table common to both schemas (intersection of columns), in a single
FK-deferred transaction (requires a superuser to set ``session_replication_role``),
idempotently (DELETE + reload), then repairs serial sequences. Legacy-only tables
(``indicator``, ``skill_group``, ``skill_set*``, ``evidence_*``, ``curriculum_plan_row``,
…) have no home in the evolved schema and are skipped and reported.

Usage::

    python scripts/seed_reference_catalog.py             # dry-run (counts only)
    python scripts/seed_reference_catalog.py --apply     # perform the load
    python scripts/seed_reference_catalog.py --apply --sqlite path/to/catalog.sqlite

DATABASE_URL is read from settings/.env and normalized to the psycopg driver.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import Connection, create_engine, text

# Allow running as a plain script (`python scripts/...`) without installation.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config.settings import get_settings  # noqa: E402

DEFAULT_SQLITE = "legacy/Spravochnik/artifacts/skills_catalog.sqlite"
# Schema/meta tables that must never be copied.
SCHEMA_TABLES = {"alembic_version", "schema_migration"}
# Operational/transient state from the legacy working session — NOT reference data.
# The review queue, intake/ingest jobs and AI-analysis runs are another methodologist's
# in-flight decisions; a fresh catalog must not inherit them.
TRANSIENT_TABLES = {
    "review_queue",
    "intake_job",
    "ingest_run",
    "ai_analysis_run",
    "ai_analysis_suggestion",
}
SKIP_TABLES = SCHEMA_TABLES | TRANSIENT_TABLES
VERIFY_TABLES = (
    "competency",
    "skill",
    "skill_alias",
    "indicator_row",
    "competency_skill",
    "profile",
    "profile_competency",
    "review_queue",
)


def _pg_url() -> str:
    url = get_settings().database_url
    if not url:
        raise SystemExit("DATABASE_URL is not configured")
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def _common_tables(sl: sqlite3.Connection, con: Connection) -> tuple[list[str], list[str]]:
    sl_tables = {r[0] for r in sl.execute("select name from sqlite_master where type='table'")}
    pg_tables = {
        r[0]
        for r in con.execute(
            text(
                "select table_name from information_schema.tables "
                "where table_schema='public' and table_type='BASE TABLE'"
            )
        )
    }
    common = sorted((sl_tables & pg_tables) - SKIP_TABLES)
    legacy_only = sorted(sl_tables - pg_tables - SKIP_TABLES)
    return common, legacy_only


def seed(sqlite_path: str, apply: bool) -> None:
    if not Path(sqlite_path).exists():
        raise SystemExit(f"SQLite snapshot not found: {sqlite_path}")

    sl = sqlite3.connect(sqlite_path)
    engine = create_engine(_pg_url())
    with engine.begin() as con:
        common, legacy_only = _common_tables(sl, con)

        pg_cols: dict[str, dict[str, str]] = {}
        for table in common:
            pg_cols[table] = {
                r[0]: r[1]
                for r in con.execute(
                    text(
                        "select column_name, data_type from information_schema.columns "
                        "where table_schema='public' and table_name=:t"
                    ),
                    {"t": table},
                )
            }

        if apply:
            con.execute(text("SET session_replication_role = replica"))
            for table in common:
                con.execute(text(f'DELETE FROM "{table}"'))

        report: list[tuple[str, int, int]] = []
        for table in common:
            sl_cols = [c[1] for c in sl.execute(f'PRAGMA table_info("{table}")')]
            cols = [c for c in sl_cols if c in pg_cols[table]]
            if not cols:
                report.append((table, 0, 0))
                continue
            quoted = ", ".join(f'"{c}"' for c in cols)
            rows = sl.execute(f'SELECT {quoted} FROM "{table}"').fetchall()
            if apply and rows:
                bool_cols = {c for c in cols if pg_cols[table][c] == "boolean"}
                stmt = text(
                    f'INSERT INTO "{table}" ({quoted}) '
                    f"VALUES ({', '.join(':' + c for c in cols)})"
                )
                batch = []
                for row in rows:
                    record = dict(zip(cols, row))
                    for bc in bool_cols:
                        if record[bc] is not None:
                            record[bc] = bool(record[bc])
                    batch.append(record)
                con.execute(stmt, batch)
            report.append((table, len(rows), len(cols)))

        if apply:
            for table in common:
                if "id" not in pg_cols[table]:
                    continue
                seq = con.execute(text("select pg_get_serial_sequence(:t, 'id')"), {"t": table}).scalar()
                if seq:
                    con.execute(text(f"select setval('{seq}', coalesce((select max(id) from \"{table}\"), 1))"))
            con.execute(text("SET session_replication_role = default"))

        _print_report(con, common, legacy_only, report, apply)


def _print_report(
    con: Connection,
    common: list[str],
    legacy_only: list[str],
    report: list[tuple[str, int, int]],
    apply: bool,
) -> None:
    print(f"=== {'APPLIED' if apply else 'DRY-RUN'} @ {datetime.now():%Y-%m-%d %H:%M:%S} ===")
    print(f"common tables: {len(common)}  legacy-only (skipped): {len(legacy_only)}")
    for table, rows, cols in report:
        print(f"  {table:38} rows={rows:6}  cols={cols}")
    if legacy_only:
        print("legacy-only skipped:", " ".join(legacy_only))
    if apply:
        print("=== verify ===")
        for table in VERIFY_TABLES:
            count = con.execute(text(f'select count(*) from "{table}"')).scalar()
            print(f"  {table:24} {count}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Postgres reference catalog from legacy SQLite.")
    parser.add_argument("--apply", action="store_true", help="perform the load (default: dry-run)")
    parser.add_argument("--sqlite", default=DEFAULT_SQLITE, help=f"legacy snapshot path (default: {DEFAULT_SQLITE})")
    args = parser.parse_args()
    seed(args.sqlite, args.apply)


if __name__ == "__main__":
    main()
