from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


class MigrationError(ValueError):
    """Raised when Postgres migration planning or execution fails."""


class MigrationCursorLike(Protocol):
    def fetchone(self) -> Any: ...
    def fetchall(self) -> list[Any]: ...


class MigrationConnectionLike(Protocol):
    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> MigrationCursorLike: ...


@dataclass(frozen=True)
class MigrationPlanItem:
    version: str
    path: str
    sha256: str
    applied: bool


LEDGER_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS cell_schema_migrations (
  version TEXT PRIMARY KEY,
  sha256 TEXT NOT NULL,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
""".strip()

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_MIGRATIONS_DIR = ROOT / "infra/datastores/postgres/migrations/cell"


def connect_postgres(database_url: str | None = None) -> Any:
    """Open a psycopg connection for live migration/replay use.

    The import is intentionally lazy so test and in-memory lanes do not require a
    Postgres driver. Runtime callers may pass `database_url` or set
    `CELL_DATABASE_URL` / `DATABASE_URL`.
    """

    dsn = database_url or os.getenv("CELL_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not dsn:
        raise MigrationError("missing database URL; set CELL_DATABASE_URL or DATABASE_URL")
    try:
        import psycopg  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - exercised only when optional driver missing
        raise MigrationError("psycopg is required for live Postgres connection") from exc
    return psycopg.connect(dsn)


def migration_files(migrations_dir: Path = DEFAULT_MIGRATIONS_DIR) -> list[Path]:
    if not migrations_dir.exists():
        raise MigrationError(f"missing migrations directory: {migrations_dir}")
    files = sorted(path for path in migrations_dir.glob("*.sql") if path.is_file())
    if not files:
        raise MigrationError(f"no Postgres migration files found in {migrations_dir}")
    return files


def migration_plan(connection: MigrationConnectionLike | None = None, migrations_dir: Path = DEFAULT_MIGRATIONS_DIR) -> list[MigrationPlanItem]:
    applied = _applied_versions(connection) if connection is not None else {}
    return [
        MigrationPlanItem(
            version=path.name,
            path=str(path),
            sha256=_sha256(path),
            applied=applied.get(path.name) == _sha256(path),
        )
        for path in migration_files(migrations_dir)
    ]


def apply_migrations(connection: MigrationConnectionLike, migrations_dir: Path = DEFAULT_MIGRATIONS_DIR) -> list[MigrationPlanItem]:
    _ensure_ledger(connection)
    plan = migration_plan(connection, migrations_dir)
    for item in plan:
        if item.applied:
            continue
        sql = Path(item.path).read_text(encoding="utf-8")
        connection.execute(sql)
        connection.execute(
            """
INSERT INTO cell_schema_migrations (version, sha256)
VALUES (%s, %s)
ON CONFLICT (version) DO UPDATE SET sha256 = EXCLUDED.sha256, applied_at = now()
""".strip(),
            (item.version, item.sha256),
        )
    _commit_if_available(connection)
    return migration_plan(connection, migrations_dir)


def dry_run_summary(migrations_dir: Path = DEFAULT_MIGRATIONS_DIR) -> dict[str, Any]:
    plan = migration_plan(None, migrations_dir)
    return {
        "ok": True,
        "mode": "dry_run",
        "migration_count": len(plan),
        "migrations": [item.__dict__ for item in plan],
    }


def _ensure_ledger(connection: MigrationConnectionLike) -> None:
    connection.execute(LEDGER_TABLE_SQL)


def _applied_versions(connection: MigrationConnectionLike | None) -> dict[str, str]:
    if connection is None:
        return {}
    _ensure_ledger(connection)
    rows = connection.execute("SELECT version, sha256 FROM cell_schema_migrations").fetchall()
    applied: dict[str, str] = {}
    for row in rows:
        version, sha = row[0], row[1]
        applied[str(version)] = str(sha)
    return applied


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _commit_if_available(connection: MigrationConnectionLike) -> None:
    commit = getattr(connection, "commit", None)
    if callable(commit):
        commit()
