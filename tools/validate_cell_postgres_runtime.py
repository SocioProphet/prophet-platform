#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION_MANAGER = ROOT / "apps/cell-service/src/cell_service/postgres_migrations.py"
POSTGRES_REPOSITORY = ROOT / "apps/cell-service/src/cell_service/postgres_repository.py"
CLI = ROOT / "apps/cell-service/src/cell_service/cli.py"
TESTS = ROOT / "apps/cell-service/tests/test_postgres_migrations.py"
MIGRATION_SQL = ROOT / "infra/datastores/postgres/migrations/cell/0001_personal_intelligence_cell.sql"


def fail(message: str) -> None:
    print(f"ERR: {message}", file=sys.stderr)
    raise SystemExit(2)


def require_file(path: Path) -> str:
    if not path.exists():
        fail(f"missing required file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8", errors="replace")


def require_markers(text: str, markers: list[str], where: str) -> None:
    for marker in markers:
        if marker not in text:
            fail(f"{where} missing marker: {marker}")


def main() -> None:
    migration_text = require_file(MIGRATION_MANAGER)
    repository_text = require_file(POSTGRES_REPOSITORY)
    cli_text = require_file(CLI)
    test_text = require_file(TESTS)
    sql_text = require_file(MIGRATION_SQL)

    require_markers(
        migration_text,
        [
            "class MigrationError",
            "LEDGER_TABLE_SQL",
            "cell_schema_migrations",
            "def connect_postgres",
            "CELL_DATABASE_URL",
            "DATABASE_URL",
            "def migration_plan",
            "def apply_migrations",
            "def dry_run_summary",
            "psycopg.connect",
        ],
        "Postgres migration manager",
    )
    require_markers(
        repository_text,
        [
            "class PostgresCellRepository",
            "COLLECTION_TABLES",
            "KEY_COLUMNS",
            "ON CONFLICT",
            "%s::jsonb",
        ],
        "Postgres repository",
    )
    require_markers(
        cli_text,
        [
            "postgres-plan",
            "postgres-migrate",
            "--postgres",
            "--migrate-first",
            "PostgresCellRepository",
            "apply_migrations",
            "migration_plan",
        ],
        "cell service CLI",
    )
    require_markers(
        test_text,
        [
            "test_dry_run_summary_reports_migrations",
            "test_apply_migrations_records_versions",
            "test_migration_plan_uses_sha_match_for_applied_state",
            "FakeMigrationConnection",
        ],
        "Postgres migration tests",
    )
    require_markers(
        sql_text,
        [
            "CREATE TABLE IF NOT EXISTS cell_cells",
            "body JSONB NOT NULL",
            "GENERATED ALWAYS AS",
            "CREATE INDEX IF NOT EXISTS idx_cell_signals_cell_watch",
        ],
        "Postgres migration SQL",
    )

    print("OK: cell Postgres runtime validation passed")


if __name__ == "__main__":
    main()
