from __future__ import annotations

from copy import deepcopy
from typing import Any, Protocol


class RepositoryError(ValueError):
    """Raised when repository operations cannot satisfy the requested mutation."""


class CellRepository(Protocol):
    """Persistence boundary for Personal Intelligence Cell runtime state.

    Implementations may be in-memory, Postgres-backed, or test doubles. The
    service layer owns domain validation and policy boundaries; repositories own
    durable storage semantics and object isolation.
    """

    def create(self, collection: str, obj: dict[str, Any]) -> dict[str, Any]: ...

    def put(self, collection: str, key: str, obj: dict[str, Any]) -> dict[str, Any]: ...

    def get(self, collection: str, key: str) -> dict[str, Any]: ...

    def list(self, collection: str) -> list[dict[str, Any]]: ...

    def exists(self, collection: str, key: str) -> bool: ...


class InMemoryCellRepository:
    """Small copy-on-write repository for the first cell-service runtime lane."""

    COLLECTIONS = {
        "cells",
        "cell_configs",
        "sources",
        "watches",
        "watch_patterns",
        "signals",
        "feed_items",
        "intent_events",
        "feedback_events",
        "cell_archives",
    }

    def __init__(self) -> None:
        self._store: dict[str, dict[str, dict[str, Any]]] = {name: {} for name in self.COLLECTIONS}

    def create(self, collection: str, obj: dict[str, Any]) -> dict[str, Any]:
        bucket = self._bucket(collection)
        obj_id = self._object_id(obj)
        if obj_id in bucket:
            raise RepositoryError(f"{collection} already contains {obj_id}")
        bucket[obj_id] = deepcopy(obj)
        return deepcopy(obj)

    def put(self, collection: str, key: str, obj: dict[str, Any]) -> dict[str, Any]:
        bucket = self._bucket(collection)
        bucket[key] = deepcopy(obj)
        return deepcopy(obj)

    def get(self, collection: str, key: str) -> dict[str, Any]:
        bucket = self._bucket(collection)
        try:
            return deepcopy(bucket[key])
        except KeyError as exc:
            raise RepositoryError(f"{collection} missing {key}") from exc

    def list(self, collection: str) -> list[dict[str, Any]]:
        bucket = self._bucket(collection)
        return [deepcopy(value) for value in bucket.values()]

    def exists(self, collection: str, key: str) -> bool:
        return key in self._bucket(collection)

    def _bucket(self, collection: str) -> dict[str, dict[str, Any]]:
        if collection not in self._store:
            raise RepositoryError(f"unknown collection: {collection}")
        return self._store[collection]

    def _object_id(self, obj: dict[str, Any]) -> str:
        obj_id = obj.get("id")
        if not isinstance(obj_id, str) or not obj_id:
            raise RepositoryError("object id must be a non-empty string")
        return obj_id
