from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4

from .models import EventRecord, MeshResource, MemoryHit, RecallRequest, WriteRequest, dump_model, event_context_from_payload, parse_model
from .qdrant_index import QdrantMemoryIndex
from .store import compile_workload_config_from_resources, dedupe_hits, scope_bonus_for_request, token_overlap, tokenize


class SQLiteStore:
    def __init__(self, *, db_path: str, vector_index: QdrantMemoryIndex | None = None) -> None:
        self.db_path = db_path
        self._vector_index = vector_index

    async def init(self) -> None:
        await asyncio.to_thread(self._ensure_parent_dir)
        await asyncio.to_thread(self._migrate)
        if self._vector_index is not None:
            await self._vector_index.ensure_collection()

    async def close(self) -> None:
        return None

    def _ensure_parent_dir(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _migrate(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                '''
                CREATE TABLE IF NOT EXISTS resources (
                    kind TEXT NOT NULL,
                    namespace TEXT NOT NULL,
                    name TEXT NOT NULL,
                    resource_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (kind, namespace, name)
                );
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS memories (
                    memory_id TEXT PRIMARY KEY,
                    text_content TEXT NOT NULL,
                    memory_class TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    envelope_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_memories_created_at ON memories(created_at DESC);
                '''
            )
            # Read-enforced revocation column (added defensively for pre-existing DBs).
            columns = {row['name'] for row in conn.execute('PRAGMA table_info(memories)').fetchall()}
            if 'revoked' not in columns:
                conn.execute('ALTER TABLE memories ADD COLUMN revoked INTEGER NOT NULL DEFAULT 0')
            conn.commit()

    @staticmethod
    def resource_key(kind: str, namespace: str, name: str) -> str:
        return f'{kind}:{namespace}:{name}'

    async def apply_resource(self, resource: MeshResource) -> str:
        return await asyncio.to_thread(self._apply_resource_sync, resource)

    def _apply_resource_sync(self, resource: MeshResource) -> str:
        with self._connect() as conn:
            conn.execute(
                '''
                INSERT OR REPLACE INTO resources(kind, namespace, name, resource_json, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''',
                (resource.kind, resource.metadata.namespace, resource.metadata.name, json.dumps(dump_model(resource))),
            )
            conn.commit()
        return self.resource_key(resource.kind, resource.metadata.namespace, resource.metadata.name)

    async def get_resource(self, kind: str, namespace: str, name: str) -> MeshResource | None:
        return await asyncio.to_thread(self._get_resource_sync, kind, namespace, name)

    def _get_resource_sync(self, kind: str, namespace: str, name: str) -> MeshResource | None:
        with self._connect() as conn:
            row = conn.execute(
                'SELECT resource_json FROM resources WHERE kind = ? AND namespace = ? AND name = ?',
                (kind, namespace, name),
            ).fetchone()
        if row is None:
            return None
        return parse_model(MeshResource, json.loads(row['resource_json']))

    async def append_event(self, event_type: str, payload: dict) -> EventRecord:
        return await asyncio.to_thread(self._append_event_sync, event_type, payload)

    def _append_event_sync(self, event_type: str, payload: dict) -> EventRecord:
        event = EventRecord(event_type=event_type, payload=payload, **event_context_from_payload(payload))
        with self._connect() as conn:
            conn.execute(
                'INSERT INTO events(event_id, event_type, payload_json, created_at) VALUES (?, ?, ?, ?)',
                (event.event_id, event.event_type, json.dumps(event.payload), event.created_at.isoformat()),
            )
            conn.commit()
        return event

    async def list_events(self, limit: int = 50) -> list[EventRecord]:
        return await asyncio.to_thread(self._list_events_sync, limit)

    def _list_events_sync(self, limit: int) -> list[EventRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                'SELECT event_id, event_type, payload_json, created_at FROM events ORDER BY created_at DESC LIMIT ?',
                (limit,),
            ).fetchall()
        events: list[EventRecord] = []
        for row in rows:
            payload = json.loads(row['payload_json'])
            events.append(
                EventRecord(
                    event_id=row['event_id'],
                    event_type=row['event_type'],
                    payload=payload,
                    created_at=row['created_at'],
                    **event_context_from_payload(payload),
                )
            )
        return events

    async def compile_workload_config(self, workload_id: str):
        return await asyncio.to_thread(self._compile_workload_config_sync, workload_id)

    def _compile_workload_config_sync(self, workload_id: str):
        with self._connect() as conn:
            rows = conn.execute('SELECT resource_json FROM resources').fetchall()
        resources = [parse_model(MeshResource, json.loads(row['resource_json'])) for row in rows]
        return compile_workload_config_from_resources(resources, workload_id=workload_id)

    async def add_local_memory(self, request: WriteRequest, event_id: str) -> str:
        memory_id = uuid4().hex
        await asyncio.to_thread(self._add_local_memory_sync, request, event_id, memory_id)
        if self._vector_index is not None:
            await self._vector_index.upsert_memory(request, memory_id=memory_id, event_id=event_id)
        return memory_id

    def _add_local_memory_sync(self, request: WriteRequest, event_id: str, memory_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                '''
                INSERT INTO memories(memory_id, text_content, memory_class, tags_json, metadata_json, event_id, envelope_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    memory_id,
                    request.content,
                    request.memory_class.value,
                    json.dumps(list(request.tags)),
                    json.dumps(dict(request.metadata)),
                    event_id,
                    json.dumps(dump_model(request.envelope)),
                ),
            )
            conn.commit()

    async def search_local_memories(self, request: RecallRequest) -> list[MemoryHit]:
        lexical_hits = await asyncio.to_thread(self._search_lexical_sync, request)
        vector_hits = await self._vector_index.search(request) if self._vector_index is not None and request.query_vector else []
        merged = dedupe_hits(lexical_hits + vector_hits)
        # Read-enforced revocation for vector hits: the lexical query already excludes
        # revoked rows, but vector hits come from an external index that may still hold
        # the tombstoned vector, so drop anything revoked before returning.
        if vector_hits:
            revoked = await asyncio.to_thread(self._revoked_ids_sync)
            merged = [hit for hit in merged if hit.memory_id not in revoked]
        merged.sort(key=lambda hit: hit.score, reverse=True)
        return merged[: request.top_k]

    def _revoked_ids_sync(self) -> set[str]:
        with self._connect() as conn:
            rows = conn.execute('SELECT memory_id FROM memories WHERE revoked = 1').fetchall()
        return {row['memory_id'] for row in rows}

    async def revoke_memory(self, memory_id: str) -> bool:
        return await asyncio.to_thread(self._revoke_memory_sync, memory_id)

    def _revoke_memory_sync(self, memory_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute('UPDATE memories SET revoked = 1 WHERE memory_id = ? AND revoked = 0', (memory_id,))
            conn.commit()
            return cur.rowcount > 0

    def _search_lexical_sync(self, request: RecallRequest) -> list[MemoryHit]:
        with self._connect() as conn:
            rows = conn.execute(
                'SELECT memory_id, text_content, tags_json, metadata_json, event_id, envelope_json FROM memories WHERE revoked = 0 ORDER BY created_at DESC LIMIT ?',
                (max(request.top_k * 20, 100),),
            ).fetchall()
        query_tokens = tokenize(request.query)
        hits: list[MemoryHit] = []
        for row in rows:
            envelope = json.loads(row['envelope_json'])
            scope_bonus, scope_name = scope_bonus_for_request(request, envelope)
            if scope_bonus < 0:
                continue
            text_content = row['text_content']
            overlap = token_overlap(query_tokens, tokenize(text_content))
            if overlap <= 0 and request.query.lower() not in text_content.lower():
                continue
            hits.append(
                MemoryHit(
                    memory_id=row['memory_id'],
                    text=text_content,
                    score=overlap + scope_bonus,
                    source='memoryd.sqlite',
                    scope=scope_name,
                    tags=list(json.loads(row['tags_json'])),
                    metadata=dict(json.loads(row['metadata_json'])),
                    event_id=row['event_id'],
                )
            )
        return hits

    async def health(self) -> dict:
        status: dict = {'backend': 'sqlite', 'path': self.db_path}
        try:
            with self._connect() as conn:
                row = conn.execute('SELECT COUNT(*) AS count FROM events').fetchone()
            status['event_count'] = int(row['count']) if row else 0
        except Exception as exc:  # pragma: no cover
            status['error'] = str(exc)
        if self._vector_index is not None:
            status['vector_index'] = await self._vector_index.health()
        return status
