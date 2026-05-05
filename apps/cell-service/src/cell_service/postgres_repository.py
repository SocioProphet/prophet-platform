from __future__ import annotations

import json
from typing import Any, Protocol

from .repository import RepositoryError


class CursorLike(Protocol):
    def fetchone(self) -> Any: ...
    def fetchall(self) -> list[Any]: ...


class ConnectionLike(Protocol):
    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> CursorLike: ...


COLLECTION_TABLES: dict[str, str] = {
    "cells": "cell_cells",
    "cell_configs": "cell_configs",
    "sources": "cell_sources",
    "watches": "cell_watches",
    "watch_patterns": "cell_watch_patterns",
    "signals": "cell_signals",
    "feed_items": "cell_feed_items",
    "intent_events": "cell_intent_events",
    "feedback_events": "cell_feedback_events",
    "cell_archives": "cell_archives",
}

KEY_COLUMNS: dict[str, str] = {
    "cells": "id",
    "cell_configs": "cell_id",
    "sources": "id",
    "watches": "id",
    "watch_patterns": "id",
    "signals": "id",
    "feed_items": "id",
    "intent_events": "id",
    "feedback_events": "id",
    "cell_archives": "id",
}


class PostgresCellRepository:
    """Postgres repository seam for Personal Intelligence Cell control-plane state.

    This class intentionally depends on a tiny DB-API-like protocol instead of a
    concrete driver. Runtime wiring can pass psycopg/async bridge adapters later;
    unit tests can use a fake connection now. SQL writes use the `body` JSONB
    column as the canonical payload while selected relational columns in the
    migration remain available for indexing and constraints.
    """

    def __init__(self, connection: ConnectionLike) -> None:
        self._connection = connection

    def create(self, collection: str, obj: dict[str, Any]) -> dict[str, Any]:
        key = self._object_key(collection, obj)
        if self.exists(collection, key):
            raise RepositoryError(f"{collection} already contains {key}")
        sql = self._upsert_sql(collection)
        self._connection.execute(sql, self._params(collection, key, obj))
        return dict(obj)

    def put(self, collection: str, key: str, obj: dict[str, Any]) -> dict[str, Any]:
        sql = self._upsert_sql(collection)
        self._connection.execute(sql, self._params(collection, key, obj))
        return dict(obj)

    def get(self, collection: str, key: str) -> dict[str, Any]:
        table = self._table(collection)
        key_column = self._key_column(collection)
        row = self._connection.execute(
            f"SELECT body FROM {table} WHERE {key_column} = %s",
            (key,),
        ).fetchone()
        if row is None:
            raise RepositoryError(f"{collection} missing {key}")
        return self._body_from_row(row)

    def list(self, collection: str) -> list[dict[str, Any]]:
        table = self._table(collection)
        rows = self._connection.execute(f"SELECT body FROM {table} ORDER BY {self._key_column(collection)} ASC").fetchall()
        return [self._body_from_row(row) for row in rows]

    def exists(self, collection: str, key: str) -> bool:
        table = self._table(collection)
        key_column = self._key_column(collection)
        row = self._connection.execute(
            f"SELECT 1 FROM {table} WHERE {key_column} = %s LIMIT 1",
            (key,),
        ).fetchone()
        return row is not None

    def _table(self, collection: str) -> str:
        try:
            return COLLECTION_TABLES[collection]
        except KeyError as exc:
            raise RepositoryError(f"unknown collection: {collection}") from exc

    def _key_column(self, collection: str) -> str:
        try:
            return KEY_COLUMNS[collection]
        except KeyError as exc:
            raise RepositoryError(f"unknown collection: {collection}") from exc

    def _object_key(self, collection: str, obj: dict[str, Any]) -> str:
        key_column = self._key_column(collection)
        key = obj.get(key_column)
        if key is None and key_column == "cell_id":
            key = obj.get("cell_id")
        if key is None:
            key = obj.get("id")
        if not isinstance(key, str) or not key:
            raise RepositoryError(f"{collection} object missing non-empty key")
        return key

    def _upsert_sql(self, collection: str) -> str:
        table = self._table(collection)
        key_column = self._key_column(collection)
        return f"""
INSERT INTO {table} ({key_column}, body)
VALUES (%s, %s::jsonb)
ON CONFLICT ({key_column}) DO UPDATE SET body = EXCLUDED.body
""".strip()

    def _params(self, collection: str, key: str, obj: dict[str, Any]) -> tuple[Any, ...]:
        _ = self._table(collection)
        return (key, json.dumps(obj, sort_keys=True))

    def _body_from_row(self, row: Any) -> dict[str, Any]:
        body = row[0] if isinstance(row, tuple) else row
        if isinstance(body, str):
            decoded = json.loads(body)
        else:
            decoded = body
        if not isinstance(decoded, dict):
            raise RepositoryError("Postgres row body must decode to object")
        return decoded
