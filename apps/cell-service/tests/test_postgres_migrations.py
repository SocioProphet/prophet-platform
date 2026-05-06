from __future__ import annotations

from pathlib import Path
from typing import Any

from cell_service.postgres_migrations import LEDGER_TABLE_SQL, apply_migrations, dry_run_summary, migration_plan


class FakeCursor:
    def __init__(self, rows: list[Any] | None = None) -> None:
        self._rows = rows or []

    def fetchone(self) -> Any:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[Any]:
        return self._rows


class FakeMigrationConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.applied: dict[str, str] = {}
        self.committed = False

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> FakeCursor:
        self.calls.append((sql, params))
        compact = " ".join(sql.split())
        if compact.startswith("SELECT version, sha256 FROM cell_schema_migrations"):
            return FakeCursor(rows=[(version, sha) for version, sha in sorted(self.applied.items())])
        if compact.startswith("INSERT INTO cell_schema_migrations"):
            version, sha = str(params[0]), str(params[1])
            self.applied[version] = sha
            return FakeCursor()
        return FakeCursor()

    def commit(self) -> None:
        self.committed = True


def test_dry_run_summary_reports_migrations() -> None:
    summary = dry_run_summary()
    assert summary["ok"] is True
    assert summary["mode"] == "dry_run"
    assert summary["migration_count"] >= 1
    assert summary["migrations"][0]["version"].endswith(".sql")


def test_apply_migrations_records_versions() -> None:
    conn = FakeMigrationConnection()
    plan_before = migration_plan(conn)
    assert plan_before
    assert all(item.applied is False for item in plan_before)

    plan_after = apply_migrations(conn)
    assert conn.committed is True
    assert all(item.applied is True for item in plan_after)
    executed_sql = "\n".join(sql for sql, _ in conn.calls)
    assert LEDGER_TABLE_SQL.splitlines()[0] in executed_sql
    assert "cell_schema_migrations" in executed_sql
    assert "CREATE TABLE IF NOT EXISTS cell_cells" in executed_sql


def test_migration_plan_uses_sha_match_for_applied_state(tmp_path: Path) -> None:
    migration = tmp_path / "0001.sql"
    migration.write_text("CREATE TABLE example(id text primary key);\n", encoding="utf-8")
    conn = FakeMigrationConnection()
    first = migration_plan(conn, tmp_path)[0]
    conn.applied[first.version] = first.sha256

    second = migration_plan(conn, tmp_path)[0]
    assert second.applied is True
