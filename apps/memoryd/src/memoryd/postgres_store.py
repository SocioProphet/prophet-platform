from __future__ import annotations

import asyncio
import json
from typing import Any
from uuid import uuid4

try:
    import psycopg
except Exception:  # pragma: no cover
    psycopg = None  # type: ignore[assignment]

from .models import EventRecord, MeshResource, MemoryHit, RecallRequest, WriteRequest, dump_model, event_context_from_payload, parse_model
from .qdrant_index import QdrantMemoryIndex
from .store import compile_workload_config_from_resources, dedupe_hits, scope_bonus_for_request, token_overlap, tokenize


class PostgresStore:
    def __init__(self, *, dsn: str, schema: str = 'memorymesh', vector_index: QdrantMemoryIndex | None = None) -> None:
        self.dsn = dsn
        self.schema = schema
        self._vector_index = vector_index
        if psycopg is None:
            raise RuntimeError('psycopg is required for PostgresStore')

    async def init(self) -> None:
        await asyncio.to_thread(self._migrate)
        if self._vector_index is not None:
            await self._vector_index.ensure_collection()

    async def close(self) -> None:
        return None

    def _connect(self):
        return psycopg.connect(self.dsn)

    def _migrate(self) -> None:
        statements = [
            f'CREATE SCHEMA IF NOT EXISTS {self.schema}',
            f'''
            CREATE TABLE IF NOT EXISTS {self.schema}.resources (
                kind TEXT NOT NULL,
                namespace TEXT NOT NULL,
                name TEXT NOT NULL,
                resource JSONB NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (kind, namespace, name)
            )
            ''',
            f'''
            CREATE TABLE IF NOT EXISTS {self.schema}.events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                payload JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL
            )
            ''',
            f'''
            CREATE TABLE IF NOT EXISTS {self.schema}.memories (
                memory_id TEXT PRIMARY KEY,
                text_content TEXT NOT NULL,
                memory_class TEXT NOT NULL,
                tags JSONB NOT NULL,
                metadata JSONB NOT NULL,
                event_id TEXT NOT NULL,
                envelope JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            ''',
            f"CREATE INDEX IF NOT EXISTS idx_{self.schema}_memories_user_id ON {self.schema}.memories ((envelope->>'user_id'))",
            f"CREATE INDEX IF NOT EXISTS idx_{self.schema}_memories_workload_id ON {self.schema}.memories ((envelope->>'workload_id'))",
            # Read-enforced revocation column (added defensively for pre-existing tables).
            f'ALTER TABLE {self.schema}.memories ADD COLUMN IF NOT EXISTS revoked BOOLEAN NOT NULL DEFAULT FALSE',
        ]
        with self._connect() as conn:
            with conn.cursor() as cur:
                for statement in statements:
                    cur.execute(statement)
            conn.commit()

    @staticmethod
    def resource_key(kind: str, namespace: str, name: str) -> str:
        return f'{kind}:{namespace}:{name}'

    async def apply_resource(self, resource: MeshResource) -> str:
        return await asyncio.to_thread(self._apply_resource_sync, resource)

    def _apply_resource_sync(self, resource: MeshResource) -> str:
        key = self.resource_key(resource.kind, resource.metadata.namespace, resource.metadata.name)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f'''
                    INSERT INTO {self.schema}.resources(kind, namespace, name, resource, updated_at)
                    VALUES (%s, %s, %s, %s::jsonb, NOW())
                    ON CONFLICT (kind, namespace, name)
                    DO UPDATE SET resource = EXCLUDED.resource, updated_at = NOW()
                    ''',
                    (resource.kind, resource.metadata.namespace, resource.metadata.name, json.dumps(dump_model(resource))),
                )
            conn.commit()
        return key

    async def get_resource(self, kind: str, namespace: str, name: str) -> MeshResource | None:
        return await asyncio.to_thread(self._get_resource_sync, kind, namespace, name)

    def _get_resource_sync(self, kind: str, namespace: str, name: str) -> MeshResource | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f'SELECT resource FROM {self.schema}.resources WHERE kind = %s AND namespace = %s AND name = %s',
                    (kind, namespace, name),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return parse_model(MeshResource, row[0])

    async def append_event(self, event_type: str, payload: dict) -> EventRecord:
        return await asyncio.to_thread(self._append_event_sync, event_type, payload)

    def _append_event_sync(self, event_type: str, payload: dict) -> EventRecord:
        event = EventRecord(event_type=event_type, payload=payload, **event_context_from_payload(payload))
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f'INSERT INTO {self.schema}.events(event_id, event_type, payload, created_at) VALUES (%s, %s, %s::jsonb, %s)',
                    (event.event_id, event.event_type, json.dumps(event.payload), event.created_at),
                )
            conn.commit()
        return event

    async def list_events(self, limit: int = 50) -> list[EventRecord]:
        return await asyncio.to_thread(self._list_events_sync, limit)

    def _list_events_sync(self, limit: int) -> list[EventRecord]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f'SELECT event_id, event_type, payload, created_at FROM {self.schema}.events ORDER BY created_at DESC LIMIT %s',
                    (limit,),
                )
                rows = cur.fetchall()
        events: list[EventRecord] = []
        for row in rows:
            payload = row[2]
            events.append(
                EventRecord(
                    event_id=row[0],
                    event_type=row[1],
                    payload=payload,
                    created_at=row[3],
                    **event_context_from_payload(payload),
                )
            )
        return events

    async def compile_workload_config(self, workload_id: str):
        return await asyncio.to_thread(self._compile_workload_config_sync, workload_id)

    def _compile_workload_config_sync(self, workload_id: str):
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(f'SELECT resource FROM {self.schema}.resources')
                rows = cur.fetchall()
        resources = [parse_model(MeshResource, row[0]) for row in rows]
        return compile_workload_config_from_resources(resources, workload_id=workload_id)

    async def add_local_memory(self, request: WriteRequest, event_id: str) -> str:
        memory_id = uuid4().hex
        await asyncio.to_thread(self._add_local_memory_sync, request, event_id, memory_id)
        if self._vector_index is not None:
            await self._vector_index.upsert_memory(request, memory_id=memory_id, event_id=event_id)
        return memory_id

    def _add_local_memory_sync(self, request: WriteRequest, event_id: str, memory_id: str) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f'''
                    INSERT INTO {self.schema}.memories(memory_id, text_content, memory_class, tags, metadata, event_id, envelope)
                    VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s, %s::jsonb)
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
        # Read-enforced revocation for externally-indexed vector hits.
        if vector_hits:
            revoked = await asyncio.to_thread(self._revoked_ids_sync)
            merged = [hit for hit in merged if hit.memory_id not in revoked]
        merged.sort(key=lambda hit: hit.score, reverse=True)
        return merged[: request.top_k]

    def _revoked_ids_sync(self) -> set[str]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(f'SELECT memory_id FROM {self.schema}.memories WHERE revoked = TRUE')
                rows = cur.fetchall()
        return {row[0] for row in rows}

    async def revoke_memory(self, memory_id: str) -> bool:
        return await asyncio.to_thread(self._revoke_memory_sync, memory_id)

    def _revoke_memory_sync(self, memory_id: str) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f'UPDATE {self.schema}.memories SET revoked = TRUE WHERE memory_id = %s AND revoked = FALSE',
                    (memory_id,),
                )
                changed = cur.rowcount > 0
            conn.commit()
        return changed

    def _search_lexical_sync(self, request: RecallRequest) -> list[MemoryHit]:
        limit = max(request.top_k * 20, 100)
        with self._connect() as conn:
            with conn.cursor() as cur:
                if request.envelope.workspace_id is None:
                    cur.execute(
                        f'''
                        SELECT memory_id, text_content, tags, metadata, event_id, envelope
                        FROM {self.schema}.memories
                        WHERE revoked = FALSE
                          AND (envelope->>'user_id') = %s
                          AND (envelope->>'workload_id') = %s
                        ORDER BY created_at DESC
                        LIMIT %s
                        ''',
                        (request.envelope.user_id, request.envelope.workload_id, limit),
                    )
                else:
                    cur.execute(
                        f'''
                        SELECT memory_id, text_content, tags, metadata, event_id, envelope
                        FROM {self.schema}.memories
                        WHERE revoked = FALSE
                          AND (envelope->>'user_id') = %s
                          AND (envelope->>'workload_id') = %s
                          AND (envelope->>'workspace_id') = %s
                        ORDER BY created_at DESC
                        LIMIT %s
                        ''',
                        (request.envelope.user_id, request.envelope.workload_id, request.envelope.workspace_id, limit),
                    )
                rows = cur.fetchall()
        query_tokens = tokenize(request.query)
        hits: list[MemoryHit] = []
        for memory_id, text_content, tags, metadata, event_id, envelope in rows:
            env = envelope or {}
            scope_bonus, scope_name = scope_bonus_for_request(request, env)
            if scope_bonus < 0:
                continue
            overlap = token_overlap(query_tokens, tokenize(text_content))
            if overlap <= 0 and request.query.lower() not in text_content.lower():
                continue
            hits.append(
                MemoryHit(
                    memory_id=memory_id,
                    text=text_content,
                    score=overlap + scope_bonus,
                    source='memoryd.postgres',
                    scope=scope_name,
                    tags=list(tags or []),
                    metadata=dict(metadata or {}),
                    event_id=event_id,
                )
            )
        return hits

    async def health(self) -> dict[str, Any]:
        status: dict[str, Any] = {'backend': 'postgres', 'schema': self.schema}
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(f'SELECT COUNT(*) FROM {self.schema}.events')
                    row = cur.fetchone()
                    status['event_count'] = int(row[0]) if row else 0
        except Exception as exc:  # pragma: no cover
            status['error'] = str(exc)
        if self._vector_index is not None:
            status['vector_index'] = await self._vector_index.health()
        return status
