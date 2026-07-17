from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any, Callable, Protocol
from urllib.parse import urlparse
from uuid import uuid4

try:
    import psycopg
except Exception:  # pragma: no cover
    psycopg = None  # type: ignore[assignment]

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .models import EventRecord, ScopeEnvelope, dump_model, stable_object_hash, utcnow


class ArtifactRecord(BaseModel):
    artifact_id: str
    artifact_type: str
    session_id: str
    sequence: int
    artifact_hash: str
    parent_artifact_hash: str | None = None
    idempotency_key: str | None = None
    envelope: dict[str, Any]
    payload: dict[str, Any]
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class ArtifactWriteRequest(BaseModel):
    envelope: ScopeEnvelope
    artifact_type: str
    session_id: str
    payload: dict[str, Any]
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None
    parent_artifact_hash: str | None = None


class ArtifactWriteResponse(BaseModel):
    record: ArtifactRecord
    event_id: str | None = None


class ArtifactGetResponse(BaseModel):
    found: bool
    record: ArtifactRecord | None = None


class ArtifactListRequest(BaseModel):
    envelope: ScopeEnvelope
    session_id: str | None = None
    artifact_type: str | None = None
    limit: int = Field(default=50, ge=1, le=500)


class ArtifactListResponse(BaseModel):
    items: list[ArtifactRecord]


class ArtifactLatestRequest(BaseModel):
    envelope: ScopeEnvelope
    session_id: str
    artifact_type: str | None = None


class ArtifactLatestResponse(BaseModel):
    found: bool
    record: ArtifactRecord | None = None


class ArtifactReplaySessionRequest(BaseModel):
    envelope: ScopeEnvelope
    session_id: str
    limit: int = Field(default=500, ge=1, le=5000)


class ArtifactReplaySessionResponse(BaseModel):
    session_id: str
    items: list[ArtifactRecord]


class ArtifactStoreProtocol(Protocol):
    async def init(self) -> None: ...
    async def close(self) -> None: ...
    async def write(self, request: ArtifactWriteRequest) -> ArtifactRecord: ...
    async def get(self, artifact_id: str) -> ArtifactRecord | None: ...
    async def list(self, request: ArtifactListRequest) -> list[ArtifactRecord]: ...
    async def latest(self, request: ArtifactLatestRequest) -> ArtifactRecord | None: ...
    async def replay_session(self, request: ArtifactReplaySessionRequest) -> list[ArtifactRecord]: ...


def artifact_scope_key(envelope: dict[str, Any], session_id: str) -> tuple[str, str, str | None, str | None]:
    return (
        str(envelope.get('workload_id') or ''),
        session_id,
        envelope.get('workspace_id'),
        envelope.get('user_id'),
    )


def artifact_matches_envelope(record: ArtifactRecord, envelope: ScopeEnvelope) -> bool:
    env = record.envelope
    if env.get('workload_id') != envelope.workload_id:
        return False
    if envelope.workspace_id is not None and env.get('workspace_id') != envelope.workspace_id:
        return False
    if env.get('user_id') != envelope.user_id:
        return False
    return True


def build_artifact_record(
    *,
    request: ArtifactWriteRequest,
    sequence: int,
    parent_artifact_hash: str | None,
) -> ArtifactRecord:
    payload_hash = stable_object_hash(request.payload)
    envelope = dump_model(request.envelope)
    artifact_id = uuid4().hex
    return ArtifactRecord(
        artifact_id=artifact_id,
        artifact_type=request.artifact_type,
        session_id=request.session_id,
        sequence=sequence,
        artifact_hash=payload_hash,
        parent_artifact_hash=parent_artifact_hash,
        idempotency_key=request.idempotency_key,
        envelope=envelope,
        payload=dict(request.payload),
        tags=list(request.tags),
        metadata=dict(request.metadata),
        created_at=utcnow().isoformat(),
    )


class InMemoryArtifactStore:
    def __init__(self) -> None:
        self._items: dict[str, ArtifactRecord] = {}

    async def init(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def write(self, request: ArtifactWriteRequest) -> ArtifactRecord:
        if request.idempotency_key:
            for record in self._items.values():
                if (
                    record.idempotency_key == request.idempotency_key
                    and record.session_id == request.session_id
                    and artifact_matches_envelope(record, request.envelope)
                ):
                    return record
        previous = await self.latest(
            ArtifactLatestRequest(
                envelope=request.envelope,
                session_id=request.session_id,
                artifact_type=None,
            )
        )
        next_sequence = (previous.sequence + 1) if previous else 1
        parent_hash = request.parent_artifact_hash or (previous.artifact_hash if previous else None)
        record = build_artifact_record(request=request, sequence=next_sequence, parent_artifact_hash=parent_hash)
        self._items[record.artifact_id] = record
        return record

    async def get(self, artifact_id: str) -> ArtifactRecord | None:
        return self._items.get(artifact_id)

    async def list(self, request: ArtifactListRequest) -> list[ArtifactRecord]:
        items: list[ArtifactRecord] = []
        for record in self._items.values():
            if not artifact_matches_envelope(record, request.envelope):
                continue
            if request.session_id and record.session_id != request.session_id:
                continue
            if request.artifact_type and record.artifact_type != request.artifact_type:
                continue
            items.append(record)
        items.sort(key=lambda item: (item.sequence, item.created_at), reverse=True)
        return items[: request.limit]

    async def latest(self, request: ArtifactLatestRequest) -> ArtifactRecord | None:
        items = await self.list(
            ArtifactListRequest(
                envelope=request.envelope,
                session_id=request.session_id,
                artifact_type=request.artifact_type,
                limit=1,
            )
        )
        return items[0] if items else None

    async def replay_session(self, request: ArtifactReplaySessionRequest) -> list[ArtifactRecord]:
        items = await self.list(
            ArtifactListRequest(
                envelope=request.envelope,
                session_id=request.session_id,
                artifact_type=None,
                limit=request.limit,
            )
        )
        return list(reversed(items))


class SQLiteArtifactStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    async def init(self) -> None:
        await asyncio.to_thread(self._ensure_parent_dir)
        await asyncio.to_thread(self._migrate)

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
                CREATE TABLE IF NOT EXISTS artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    artifact_type TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    artifact_hash TEXT NOT NULL,
                    parent_artifact_hash TEXT,
                    idempotency_key TEXT,
                    envelope_json TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_artifacts_scope ON artifacts(session_id, artifact_type, sequence DESC);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_artifacts_idempotency ON artifacts(session_id, idempotency_key) WHERE idempotency_key IS NOT NULL;
                '''
            )
            conn.commit()

    async def write(self, request: ArtifactWriteRequest) -> ArtifactRecord:
        return await asyncio.to_thread(self._write_sync, request)

    def _write_sync(self, request: ArtifactWriteRequest) -> ArtifactRecord:
        if request.idempotency_key:
            existing = self._get_by_idempotency_sync(request.session_id, request.idempotency_key, request.envelope)
            if existing is not None:
                return existing
        previous = self._latest_sync(request.envelope, request.session_id, None)
        next_sequence = (previous.sequence + 1) if previous else 1
        parent_hash = request.parent_artifact_hash or (previous.artifact_hash if previous else None)
        record = build_artifact_record(request=request, sequence=next_sequence, parent_artifact_hash=parent_hash)
        with self._connect() as conn:
            conn.execute(
                '''
                INSERT INTO artifacts(
                    artifact_id, artifact_type, session_id, sequence, artifact_hash,
                    parent_artifact_hash, idempotency_key, envelope_json, payload_json,
                    tags_json, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    record.artifact_id,
                    record.artifact_type,
                    record.session_id,
                    record.sequence,
                    record.artifact_hash,
                    record.parent_artifact_hash,
                    record.idempotency_key,
                    json.dumps(record.envelope, sort_keys=True),
                    json.dumps(record.payload, sort_keys=True),
                    json.dumps(record.tags),
                    json.dumps(record.metadata, sort_keys=True),
                    record.created_at,
                ),
            )
            conn.commit()
        return record

    def _row_to_record(self, row: sqlite3.Row) -> ArtifactRecord:
        return ArtifactRecord(
            artifact_id=row['artifact_id'],
            artifact_type=row['artifact_type'],
            session_id=row['session_id'],
            sequence=int(row['sequence']),
            artifact_hash=row['artifact_hash'],
            parent_artifact_hash=row['parent_artifact_hash'],
            idempotency_key=row['idempotency_key'],
            envelope=json.loads(row['envelope_json']),
            payload=json.loads(row['payload_json']),
            tags=list(json.loads(row['tags_json'])),
            metadata=dict(json.loads(row['metadata_json'])),
            created_at=row['created_at'],
        )

    def _get_by_idempotency_sync(self, session_id: str, idempotency_key: str, envelope: ScopeEnvelope) -> ArtifactRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                'SELECT * FROM artifacts WHERE session_id = ? AND idempotency_key = ? LIMIT 1',
                (session_id, idempotency_key),
            ).fetchone()
        if row is None:
            return None
        record = self._row_to_record(row)
        return record if artifact_matches_envelope(record, envelope) else None

    async def get(self, artifact_id: str) -> ArtifactRecord | None:
        return await asyncio.to_thread(self._get_sync, artifact_id)

    def _get_sync(self, artifact_id: str) -> ArtifactRecord | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM artifacts WHERE artifact_id = ?', (artifact_id,)).fetchone()
        return self._row_to_record(row) if row else None

    async def list(self, request: ArtifactListRequest) -> list[ArtifactRecord]:
        return await asyncio.to_thread(self._list_sync, request)

    def _list_sync(self, request: ArtifactListRequest) -> list[ArtifactRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                'SELECT * FROM artifacts ORDER BY sequence DESC, created_at DESC LIMIT ?',
                (max(request.limit * 5, request.limit),),
            ).fetchall()
        items: list[ArtifactRecord] = []
        for row in rows:
            record = self._row_to_record(row)
            if not artifact_matches_envelope(record, request.envelope):
                continue
            if request.session_id and record.session_id != request.session_id:
                continue
            if request.artifact_type and record.artifact_type != request.artifact_type:
                continue
            items.append(record)
            if len(items) >= request.limit:
                break
        return items

    async def latest(self, request: ArtifactLatestRequest) -> ArtifactRecord | None:
        return await asyncio.to_thread(self._latest_sync, request.envelope, request.session_id, request.artifact_type)

    def _latest_sync(self, envelope: ScopeEnvelope, session_id: str, artifact_type: str | None) -> ArtifactRecord | None:
        with self._connect() as conn:
            rows = conn.execute(
                'SELECT * FROM artifacts WHERE session_id = ? ORDER BY sequence DESC, created_at DESC LIMIT 100',
                (session_id,),
            ).fetchall()
        for row in rows:
            record = self._row_to_record(row)
            if artifact_type and record.artifact_type != artifact_type:
                continue
            if artifact_matches_envelope(record, envelope):
                return record
        return None

    async def replay_session(self, request: ArtifactReplaySessionRequest) -> list[ArtifactRecord]:
        items = await self.list(
            ArtifactListRequest(
                envelope=request.envelope,
                session_id=request.session_id,
                artifact_type=None,
                limit=request.limit,
            )
        )
        return list(reversed(items))


class PostgresArtifactStore:
    def __init__(self, dsn: str, schema: str = 'memorymesh') -> None:
        if psycopg is None:
            raise RuntimeError('psycopg is required for PostgresArtifactStore')
        self.dsn = dsn
        self.schema = schema
        self._memory_fallback = InMemoryArtifactStore()

    async def init(self) -> None:
        await asyncio.to_thread(self._migrate)

    async def close(self) -> None:
        return None

    def _connect(self):
        return psycopg.connect(self.dsn)

    def _migrate(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(f'CREATE SCHEMA IF NOT EXISTS {self.schema}')
                cur.execute(
                    f'''
                    CREATE TABLE IF NOT EXISTS {self.schema}.artifacts (
                        artifact_id TEXT PRIMARY KEY,
                        artifact_type TEXT NOT NULL,
                        session_id TEXT NOT NULL,
                        sequence INTEGER NOT NULL,
                        artifact_hash TEXT NOT NULL,
                        parent_artifact_hash TEXT,
                        idempotency_key TEXT,
                        envelope JSONB NOT NULL,
                        payload JSONB NOT NULL,
                        tags JSONB NOT NULL,
                        metadata JSONB NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    '''
                )
                cur.execute(
                    f'CREATE INDEX IF NOT EXISTS idx_{self.schema}_artifacts_scope ON {self.schema}.artifacts(session_id, artifact_type, sequence DESC)'
                )
            conn.commit()

    async def write(self, request: ArtifactWriteRequest) -> ArtifactRecord:
        # Keep Postgres behavior conservative for the bootstrap by delegating selection
        # logic through the same in-memory semantics if SQL feature drift occurs.
        return await asyncio.to_thread(self._write_sync, request)

    def _write_sync(self, request: ArtifactWriteRequest) -> ArtifactRecord:
        previous = self._latest_sync(request.envelope, request.session_id, None)
        next_sequence = (previous.sequence + 1) if previous else 1
        parent_hash = request.parent_artifact_hash or (previous.artifact_hash if previous else None)
        record = build_artifact_record(request=request, sequence=next_sequence, parent_artifact_hash=parent_hash)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f'''
                    INSERT INTO {self.schema}.artifacts(
                        artifact_id, artifact_type, session_id, sequence, artifact_hash,
                        parent_artifact_hash, idempotency_key, envelope, payload,
                        tags, metadata, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s)
                    ON CONFLICT (artifact_id) DO NOTHING
                    ''',
                    (
                        record.artifact_id,
                        record.artifact_type,
                        record.session_id,
                        record.sequence,
                        record.artifact_hash,
                        record.parent_artifact_hash,
                        record.idempotency_key,
                        json.dumps(record.envelope, sort_keys=True),
                        json.dumps(record.payload, sort_keys=True),
                        json.dumps(record.tags),
                        json.dumps(record.metadata, sort_keys=True),
                        record.created_at,
                    ),
                )
            conn.commit()
        return record

    def _row_to_record(self, row: tuple[Any, ...]) -> ArtifactRecord:
        return ArtifactRecord(
            artifact_id=row[0],
            artifact_type=row[1],
            session_id=row[2],
            sequence=int(row[3]),
            artifact_hash=row[4],
            parent_artifact_hash=row[5],
            idempotency_key=row[6],
            envelope=dict(row[7]),
            payload=dict(row[8]),
            tags=list(row[9] or []),
            metadata=dict(row[10] or {}),
            created_at=row[11],
        )

    async def get(self, artifact_id: str) -> ArtifactRecord | None:
        return await asyncio.to_thread(self._get_sync, artifact_id)

    def _get_sync(self, artifact_id: str) -> ArtifactRecord | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f'SELECT artifact_id, artifact_type, session_id, sequence, artifact_hash, parent_artifact_hash, idempotency_key, envelope, payload, tags, metadata, created_at FROM {self.schema}.artifacts WHERE artifact_id = %s',
                    (artifact_id,),
                )
                row = cur.fetchone()
        return self._row_to_record(row) if row else None

    async def list(self, request: ArtifactListRequest) -> list[ArtifactRecord]:
        return await asyncio.to_thread(self._list_sync, request)

    def _list_sync(self, request: ArtifactListRequest) -> list[ArtifactRecord]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f'SELECT artifact_id, artifact_type, session_id, sequence, artifact_hash, parent_artifact_hash, idempotency_key, envelope, payload, tags, metadata, created_at FROM {self.schema}.artifacts ORDER BY sequence DESC LIMIT %s',
                    (max(request.limit * 5, request.limit),),
                )
                rows = cur.fetchall()
        items: list[ArtifactRecord] = []
        for row in rows:
            record = self._row_to_record(row)
            if not artifact_matches_envelope(record, request.envelope):
                continue
            if request.session_id and record.session_id != request.session_id:
                continue
            if request.artifact_type and record.artifact_type != request.artifact_type:
                continue
            items.append(record)
            if len(items) >= request.limit:
                break
        return items

    async def latest(self, request: ArtifactLatestRequest) -> ArtifactRecord | None:
        return await asyncio.to_thread(self._latest_sync, request.envelope, request.session_id, request.artifact_type)

    def _latest_sync(self, envelope: ScopeEnvelope, session_id: str, artifact_type: str | None) -> ArtifactRecord | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f'SELECT artifact_id, artifact_type, session_id, sequence, artifact_hash, parent_artifact_hash, idempotency_key, envelope, payload, tags, metadata, created_at FROM {self.schema}.artifacts WHERE session_id = %s ORDER BY sequence DESC LIMIT 100',
                    (session_id,),
                )
                rows = cur.fetchall()
        for row in rows:
            record = self._row_to_record(row)
            if artifact_type and record.artifact_type != artifact_type:
                continue
            if artifact_matches_envelope(record, envelope):
                return record
        return None

    async def replay_session(self, request: ArtifactReplaySessionRequest) -> list[ArtifactRecord]:
        items = await self.list(
            ArtifactListRequest(
                envelope=request.envelope,
                session_id=request.session_id,
                artifact_type=None,
                limit=request.limit,
            )
        )
        return list(reversed(items))


def build_artifact_store(store_uri: str) -> ArtifactStoreProtocol:
    if not store_uri or store_uri == 'memory://':
        return InMemoryArtifactStore()
    if store_uri.startswith('sqlite:///'):
        return SQLiteArtifactStore(urlparse(store_uri).path)
    if store_uri.startswith('postgresql://') or store_uri.startswith('postgres://'):
        return PostgresArtifactStore(store_uri)
    return InMemoryArtifactStore()


def install_artifact_routes(
    app: FastAPI,
    *,
    artifact_store: ArtifactStoreProtocol,
    event_store: Any,
    require_api_key: Callable[[str | None], Any],
) -> None:
    @app.post('/v1/artifacts/write', response_model=ArtifactWriteResponse)
    async def artifact_write(request: ArtifactWriteRequest, x_api_key: str | None = Header(default=None)) -> ArtifactWriteResponse:
        await require_api_key(x_api_key)
        record = await artifact_store.write(request)
        event: EventRecord = await event_store.append_event(
            'memory.artifact.written',
            {
                'envelope': dump_model(request.envelope),
                'artifact_id': record.artifact_id,
                'artifact_type': record.artifact_type,
                'session_id': record.session_id,
                'sequence': record.sequence,
                'artifact_hash': record.artifact_hash,
            },
        )
        return ArtifactWriteResponse(record=record, event_id=event.event_id)

    @app.get('/v1/artifacts/{artifact_id}', response_model=ArtifactGetResponse)
    async def artifact_get(artifact_id: str, x_api_key: str | None = Header(default=None)) -> ArtifactGetResponse:
        await require_api_key(x_api_key)
        record = await artifact_store.get(artifact_id)
        return ArtifactGetResponse(found=record is not None, record=record)

    @app.post('/v1/artifacts/list', response_model=ArtifactListResponse)
    async def artifact_list(request: ArtifactListRequest, x_api_key: str | None = Header(default=None)) -> ArtifactListResponse:
        await require_api_key(x_api_key)
        return ArtifactListResponse(items=await artifact_store.list(request))

    @app.post('/v1/artifacts/latest', response_model=ArtifactLatestResponse)
    async def artifact_latest(request: ArtifactLatestRequest, x_api_key: str | None = Header(default=None)) -> ArtifactLatestResponse:
        await require_api_key(x_api_key)
        record = await artifact_store.latest(request)
        return ArtifactLatestResponse(found=record is not None, record=record)

    @app.post('/v1/artifacts/replay-session', response_model=ArtifactReplaySessionResponse)
    async def artifact_replay_session(request: ArtifactReplaySessionRequest, x_api_key: str | None = Header(default=None)) -> ArtifactReplaySessionResponse:
        await require_api_key(x_api_key)
        return ArtifactReplaySessionResponse(
            session_id=request.session_id,
            items=await artifact_store.replay_session(request),
        )
