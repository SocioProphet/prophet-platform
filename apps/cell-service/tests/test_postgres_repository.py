from __future__ import annotations

import json
from typing import Any

import pytest

from cell_service.postgres_repository import PostgresCellRepository
from cell_service.repository import RepositoryError


class FakeCursor:
    def __init__(self, row: Any = None, rows: list[Any] | None = None) -> None:
        self._row = row
        self._rows = rows or []

    def fetchone(self) -> Any:
        return self._row

    def fetchall(self) -> list[Any]:
        return self._rows


class FakeConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.rows: dict[tuple[str, str], dict[str, Any]] = {}

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> FakeCursor:
        self.calls.append((sql, params))
        compact = " ".join(sql.split())
        table = self._table_from_sql(compact)
        if compact.startswith("SELECT 1"):
            key = str(params[0])
            return FakeCursor(row=(1,) if (table, key) in self.rows else None)
        if compact.startswith("SELECT body") and "WHERE" in compact:
            key = str(params[0])
            row = self.rows.get((table, key))
            return FakeCursor(row=(json.dumps(row),) if row is not None else None)
        if compact.startswith("SELECT body"):
            rows = [(json.dumps(body),) for (row_table, _), body in sorted(self.rows.items()) if row_table == table]
            return FakeCursor(rows=rows)
        if compact.startswith("INSERT INTO"):
            key = str(params[0])
            body = json.loads(params[1])
            self.rows[(table, key)] = body
            return FakeCursor()
        raise AssertionError(f"unexpected SQL: {compact}")

    def _table_from_sql(self, sql: str) -> str:
        tokens = sql.split()
        if tokens[0] == "INSERT":
            return tokens[2]
        if tokens[0] == "SELECT":
            return tokens[tokens.index("FROM") + 1]
        raise AssertionError(f"cannot parse table from SQL: {sql}")


def test_postgres_repository_create_get_list_put() -> None:
    conn = FakeConnection()
    repo = PostgresCellRepository(conn)

    cell = {
        "id": "cell://demo",
        "owner_ref": "human://demo",
        "kind": "personal",
        "policy_ref": "policy://demo",
        "memory_ref": "memory://demo",
        "created_at": "2026-05-04T00:00:00Z",
        "updated_at": "2026-05-04T00:00:00Z",
    }

    created = repo.create("cells", cell)
    assert created == cell
    assert repo.get("cells", "cell://demo") == cell
    assert repo.list("cells") == [cell]

    updated = dict(cell)
    updated["display_name"] = "Updated"
    repo.put("cells", "cell://demo", updated)
    assert repo.get("cells", "cell://demo")["display_name"] == "Updated"

    executed_sql = "\n".join(call[0] for call in conn.calls)
    assert "INSERT INTO cell_cells" in executed_sql
    assert "ON CONFLICT (id) DO UPDATE" in executed_sql


def test_postgres_repository_rejects_duplicate_create() -> None:
    conn = FakeConnection()
    repo = PostgresCellRepository(conn)
    source = {
        "id": "source://demo",
        "kind": "repo",
        "uri": "fixture://repo",
        "trust_profile": {},
        "crawl_profile": {},
        "provenance_profile": {},
        "policy_ref": "policy://source",
    }

    repo.create("sources", source)
    with pytest.raises(RepositoryError, match="already contains"):
        repo.create("sources", source)


def test_postgres_repository_cell_config_uses_cell_id_key() -> None:
    conn = FakeConnection()
    repo = PostgresCellRepository(conn)
    config = {
        "cell_id": "cell://demo",
        "data_location_policy": "local",
        "sync_policy": "manual",
        "backup_policy": "signed",
        "resource_budget_defaults": {},
        "local_first_mode": True,
    }

    repo.put("cell_configs", "cell://demo", config)
    assert repo.get("cell_configs", "cell://demo") == config
    assert any("INSERT INTO cell_configs (cell_id, body)" in call[0] for call in conn.calls)


def test_postgres_repository_unknown_collection_rejected() -> None:
    repo = PostgresCellRepository(FakeConnection())
    with pytest.raises(RepositoryError, match="unknown collection"):
        repo.list("missing")
