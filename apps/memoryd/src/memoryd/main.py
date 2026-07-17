from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from urllib.parse import urlparse

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse

from .embedding import HashingEmbedder, build_embedder
from .mem0_client import Mem0RestClient
from .hellgraph_retract import HellGraphRetractClient, revocation_source_refs
from .models import (
    ApplyResourceResponse,
    DEFAULT_SCOPE_ORDER,
    CompiledWorkloadConfig,
    MeshResource,
    RecallRequest,
    RecallResponse,
    RevokeRequest,
    RevokeResponse,
    WriteRequest,
    WriteResponse,
    dump_model,
)
from .postgres_store import PostgresStore
from .qdrant_index import QdrantMemoryIndex
from .sqlite_store import SQLiteStore
from .store import InMemoryStore, StoreProtocol, dedupe_hits, rank_hits_by_policy


REQUIRE_API_KEY = os.getenv('MEMORYD_REQUIRE_API_KEY', 'false').lower() in {'1', 'true', 'yes'}
EXPECTED_API_KEY = os.getenv('MEMORYD_API_KEY', '')
STORE_URI = os.getenv('MEMORYMESH_STORE_URI', os.getenv('MEMORYD_STORE_URL', 'memory://'))
VECTOR_SIZE = int(os.getenv('MEMORYMESH_VECTOR_SIZE', '256'))
QDRANT_ENABLED = os.getenv('QDRANT_ENABLED', 'false').lower() in {'1', 'true', 'yes'}
QDRANT_URL = os.getenv('QDRANT_URL', '').rstrip('/')
QDRANT_API_KEY = os.getenv('QDRANT_API_KEY', '')
QDRANT_COLLECTION = os.getenv('QDRANT_COLLECTION', 'memorymesh-local')
QDRANT_DISTANCE = os.getenv('QDRANT_DISTANCE', 'Cosine')
EMBEDDING_SALT = os.getenv('MEMORYMESH_EMBEDDING_SALT', 'memorymesh-starter-v1')

mem0 = Mem0RestClient(
    base_url=os.getenv('MEM0_BASE_URL'),
    api_key=os.getenv('MEM0_API_KEY'),
    timeout_seconds=float(os.getenv('MEM0_TIMEOUT_SECONDS', '10')),
)

vector_index = QdrantMemoryIndex(
    url=QDRANT_URL,
    api_key=QDRANT_API_KEY or None,
    collection_name=QDRANT_COLLECTION,
    vector_size=VECTOR_SIZE,
    distance=QDRANT_DISTANCE,
    enabled=QDRANT_ENABLED and bool(QDRANT_URL),
    timeout_seconds=float(os.getenv('QDRANT_TIMEOUT_SECONDS', '10')),
)
embedder = build_embedder(dimension=VECTOR_SIZE, salt=EMBEDDING_SALT)

# Revocation propagates into the graph materialization (graceful-degrade if HELLGRAPH_URL unset).
hellgraph_retract = HellGraphRetractClient(
    base_url=os.getenv('HELLGRAPH_URL'),
    api_key=os.getenv('HELLGRAPH_API_KEY'),
    timeout_seconds=float(os.getenv('HELLGRAPH_TIMEOUT_SECONDS', '10')),
)


def build_store(store_uri: str) -> StoreProtocol:
    if not store_uri or store_uri == 'memory://':
        return InMemoryStore()
    if store_uri.startswith('sqlite:///'):
        parsed = urlparse(store_uri)
        return SQLiteStore(db_path=parsed.path, vector_index=vector_index if vector_index.enabled else None)
    if store_uri.startswith('postgresql://') or store_uri.startswith('postgres://'):
        return PostgresStore(dsn=store_uri, schema=os.getenv('MEMORYMESH_PG_SCHEMA', 'memorymesh'), vector_index=vector_index if vector_index.enabled else None)
    raise RuntimeError(f'Unsupported MEMORYMESH_STORE_URI: {store_uri}')


store: StoreProtocol = build_store(STORE_URI)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await store.init()
    yield
    await store.close()


app = FastAPI(title='memoryd', version='0.2.0', lifespan=lifespan)


async def require_api_key(x_api_key: str | None) -> None:
    if not REQUIRE_API_KEY:
        return
    if not EXPECTED_API_KEY:
        raise HTTPException(status_code=500, detail='memoryd api key enforcement enabled but MEMORYD_API_KEY is empty')
    if x_api_key != EXPECTED_API_KEY:
        raise HTTPException(status_code=401, detail='invalid api key')


def ensure_query_vector(request: RecallRequest) -> RecallRequest:
    if request.query_vector is None and vector_index.enabled:
        request.query_vector = embedder.embed(request.query)
    return request


def ensure_write_vector(request: WriteRequest) -> WriteRequest:
    if request.vector is None and vector_index.enabled:
        request.vector = embedder.embed(request.content)
    return request


def model_fields_set(model: Any) -> set[str]:
    fields_set = getattr(model, 'model_fields_set', None)
    if fields_set is None:
        fields_set = getattr(model, '__fields_set__', set())
    return set(fields_set)


def resolve_scope_order(request: RecallRequest, compiled: CompiledWorkloadConfig) -> list[str]:
    if 'scope_order' in model_fields_set(request) and request.scope_order:
        return list(request.scope_order)
    if compiled.recall_scope_order:
        return list(compiled.recall_scope_order)
    return list(DEFAULT_SCOPE_ORDER)


def iter_policy_maps(compiled: CompiledWorkloadConfig):
    for resource in compiled.attachments + compiled.export_policies + compiled.conflict_policies + compiled.peers:
        if not isinstance(resource, dict):
            continue
        spec = resource.get('spec') or {}
        if isinstance(spec, dict):
            yield spec
            nested = spec.get('policy')
            if isinstance(nested, dict):
                yield nested


def policy_flag(compiled: CompiledWorkloadConfig, names: tuple[str, ...], default: bool = False) -> bool:
    for policy in iter_policy_maps(compiled):
        for name in names:
            if name in policy:
                return bool(policy[name])
    return default


def infer_target_workloads(resource: MeshResource) -> list[str]:
    spec = resource.spec or {}
    targets: set[str] = set(spec.get('targetWorkloads') or spec.get('workloadIds') or [])
    workload_id = spec.get('workloadId')
    if isinstance(workload_id, str) and workload_id:
        targets.add(workload_id)
    return sorted(targets)


@app.get('/')
async def root() -> dict:
    return {
        'service': 'memoryd',
        'version': app.version,
        'store_uri': STORE_URI,
        'mem0_enabled': mem0.enabled,
        'vector_enabled': vector_index.enabled,
    }


@app.get('/healthz')
async def healthz() -> dict:
    return {
        'ok': True,
        'mem0_enabled': mem0.enabled,
        'store': await store.health(),
    }


@app.post('/v1/resources/apply', response_model=ApplyResourceResponse)
async def apply_resource(resource: MeshResource, x_api_key: str | None = Header(default=None)) -> ApplyResourceResponse:
    await require_api_key(x_api_key)
    key = await store.apply_resource(resource)
    event = await store.append_event('memory.resource.applied', {'resource': dump_model(resource), 'resource_key': key})

    config_hash: str | None = None
    target_workloads = infer_target_workloads(resource)
    if len(target_workloads) == 1:
        compiled = await store.compile_workload_config(workload_id=target_workloads[0])
        config_hash = compiled.config_hash
        await store.append_event(
            'memory.config.compiled',
            {'workload_id': target_workloads[0], 'config_hash': config_hash, 'resource_key': key},
        )

    return ApplyResourceResponse(applied=True, resource_key=key, event_id=event.event_id, config_hash=config_hash)


@app.get('/v1/resources/{kind}/{namespace}/{name}')
async def get_resource(kind: str, namespace: str, name: str, x_api_key: str | None = Header(default=None)) -> dict:
    await require_api_key(x_api_key)
    resource = await store.get_resource(kind=kind, namespace=namespace, name=name)
    if resource is None:
        raise HTTPException(status_code=404, detail='resource not found')
    return dump_model(resource)


@app.get('/v1/config/{workload_id}', response_model=CompiledWorkloadConfig)
async def get_compiled_config(workload_id: str, x_api_key: str | None = Header(default=None)) -> CompiledWorkloadConfig:
    await require_api_key(x_api_key)
    return await store.compile_workload_config(workload_id=workload_id)


async def config_stream(workload_id: str) -> AsyncIterator[str]:
    while True:
        compiled = await store.compile_workload_config(workload_id=workload_id)
        payload = json.dumps(dump_model(compiled), default=str)
        yield f'event: config\ndata: {payload}\n\n'
        await asyncio.sleep(15)


@app.get('/v1/watch/config/{workload_id}')
async def watch_workload_config(workload_id: str, x_api_key: str | None = Header(default=None)) -> StreamingResponse:
    await require_api_key(x_api_key)
    return StreamingResponse(config_stream(workload_id), media_type='text/event-stream')


@app.post('/v1/recall', response_model=RecallResponse)
async def recall(request: RecallRequest, x_api_key: str | None = Header(default=None)) -> RecallResponse:
    await require_api_key(x_api_key)
    request = ensure_query_vector(request)
    compiled = await store.compile_workload_config(workload_id=request.envelope.workload_id)
    request.scope_order = resolve_scope_order(request, compiled)
    request.top_k = min(request.top_k, compiled.recall_top_k_limit)

    await store.append_event(
        'memory.recall.started',
        {
            'envelope': dump_model(request.envelope),
            'query': request.query,
            'effective_scope_order': list(request.scope_order),
            'top_k': request.top_k,
            'config_hash': compiled.config_hash,
        },
    )

    if request.include_raw_events and not policy_flag(compiled, ('allowRawEvents', 'allow_raw_events'), default=False):
        denied_event = await store.append_event(
            'memory.recall.denied',
            {
                'envelope': dump_model(request.envelope),
                'query': request.query,
                'reason': 'raw event access denied by policy',
                'config_hash': compiled.config_hash,
            },
        )
        raise HTTPException(status_code=403, detail=f'raw event access denied by policy ({denied_event.event_id})')

    if request.include_relations and not policy_flag(compiled, ('allowRelations', 'allow_relations'), default=False):
        denied_event = await store.append_event(
            'memory.recall.denied',
            {
                'envelope': dump_model(request.envelope),
                'query': request.query,
                'reason': 'relation access denied by policy',
                'config_hash': compiled.config_hash,
            },
        )
        raise HTTPException(status_code=403, detail=f'relation access denied by policy ({denied_event.event_id})')

    local_hits = []
    backend_hits = []

    if compiled.local_first:
        local_hits = await store.search_local_memories(request)
        if len(local_hits) < request.top_k and mem0.enabled and compiled.allow_backend_persistence:
            try:
                backend_hits = await mem0.recall(request)
            except Exception as exc:  # pragma: no cover
                await store.append_event(
                    'backend.recall.error',
                    {'envelope': dump_model(request.envelope), 'error': str(exc), 'query': request.query},
                )
    else:
        if mem0.enabled and compiled.allow_backend_persistence:
            try:
                backend_hits = await mem0.recall(request)
            except Exception as exc:  # pragma: no cover
                await store.append_event(
                    'backend.recall.error',
                    {'envelope': dump_model(request.envelope), 'error': str(exc), 'query': request.query},
                )
        if len(backend_hits) < request.top_k:
            local_hits = await store.search_local_memories(request)

    merged = dedupe_hits(local_hits + backend_hits)
    ranked = rank_hits_by_policy(
        merged,
        scope_order=compiled.recall_scope_order,
        local_first=compiled.local_first,
    )
    final_hits = ranked[: min(request.top_k, compiled.recall_top_k_limit)]
    completed_event = await store.append_event(
        'memory.recall.completed',
        {
            'envelope': dump_model(request.envelope),
            'query': request.query,
            'local_hit_count': len(local_hits),
            'backend_hit_count': len(backend_hits),
            'returned_hit_count': len(final_hits),
            'config_hash': compiled.config_hash,
        },
    )
    return RecallResponse(
        query=request.query,
        hits=final_hits,
        compiled_policy=dump_model(compiled),
        local_hit_count=len(local_hits),
        backend_hit_count=len(backend_hits),
        truncated=len(ranked) > len(final_hits),
        event_id=completed_event.event_id,
    )


@app.post('/v1/write', response_model=WriteResponse)
async def write(request: WriteRequest, x_api_key: str | None = Header(default=None)) -> WriteResponse:
    await require_api_key(x_api_key)
    request = ensure_write_vector(request)
    compiled = await store.compile_workload_config(workload_id=request.envelope.workload_id)
    if not compiled.writeback_enabled:
        rejected_event = await store.append_event(
            'memory.write.rejected',
            {
                'envelope': dump_model(request.envelope),
                'content': request.content,
                'memory_class': request.memory_class.value,
                'metadata': request.metadata,
                'tags': request.tags,
                'reason': 'writeback disabled for workload',
                'config_hash': compiled.config_hash,
            },
        )
        raise HTTPException(status_code=403, detail=f'writeback disabled for workload ({rejected_event.event_id})')

    event = await store.append_event(
        'memory.write.accepted',
        {
            'envelope': dump_model(request.envelope),
            'content': request.content,
            'memory_class': request.memory_class.value,
            'metadata': request.metadata,
            'tags': request.tags,
            'config_hash': compiled.config_hash,
        },
    )
    local_memory_id = await store.add_local_memory(request=request, event_id=event.event_id)

    backend_memory_ids: list[str] = []
    persist_to_backend = request.persist_to_backend and compiled.allow_backend_persistence
    if persist_to_backend and mem0.enabled:
        try:
            backend_memory_ids = await mem0.write(request)
        except Exception as exc:  # pragma: no cover
            await store.append_event(
                'backend.write.error',
                {'envelope': dump_model(request.envelope), 'error': str(exc), 'event_id': event.event_id},
            )

    return WriteResponse(
        event_id=event.event_id,
        memory_id=local_memory_id,
        backend_memory_ids=backend_memory_ids,
        stored_locally=True,
    )


@app.post('/v1/revoke', response_model=RevokeResponse)
async def revoke(request: RevokeRequest, x_api_key: str | None = Header(default=None)) -> RevokeResponse:
    await require_api_key(x_api_key)
    revoked = await store.revoke_memory(request.memory_id)
    if not revoked:
        raise HTTPException(status_code=404, detail='memory not found or already revoked')

    # Propagate revocation into the HellGraph materialization: supersede the edges
    # derived from this memory so it is not queryable in the graph lane either.
    source_refs = revocation_source_refs(request.memory_id, request.provenance_refs)
    graph_result: dict[str, Any]
    try:
        graph_result = await hellgraph_retract.retract(source_refs)
    except Exception as exc:  # pragma: no cover
        graph_result = {'retracted': False, 'error': str(exc), 'source_refs': source_refs}

    event = await store.append_event(
        'memory.revocation_propagated',
        {
            'memory_id': request.memory_id,
            'reason': request.reason,
            'revocation_ref': request.revocation_ref,
            'tombstone_ref': request.tombstone_ref,
            'graph_source_refs': source_refs,
            'graph_retract': graph_result,
        },
    )
    return RevokeResponse(
        memory_id=request.memory_id,
        revoked=True,
        event_id=event.event_id,
        graph_retract=graph_result,
    )


@app.get('/v1/events')
async def list_events(limit: int = 50, x_api_key: str | None = Header(default=None)) -> dict:
    await require_api_key(x_api_key)
    items = [dump_model(item) for item in await store.list_events(limit=limit)]
    return {'items': items}
