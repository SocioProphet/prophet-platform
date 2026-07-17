from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Protocol
from uuid import uuid4

from .models import (
    DEFAULT_SCOPE_ORDER,
    CompiledWorkloadConfig,
    EventRecord,
    MemoryHit,
    MeshResource,
    RecallRequest,
    WriteRequest,
    dump_model,
    event_context_from_payload,
    stable_object_hash,
)


DEFAULT_RECALL_SCOPE_ORDER = ['run', 'agent', 'user']
EXTENDED_RECALL_SCOPE_PREFIX = ['thread', 'channel', 'workspace']
LOCAL_SOURCE_PREFIXES = ('memoryd.',)


class StoreProtocol(Protocol):
    async def init(self) -> None: ...
    async def close(self) -> None: ...
    async def apply_resource(self, resource: MeshResource) -> str: ...
    async def get_resource(self, kind: str, namespace: str, name: str) -> MeshResource | None: ...
    async def append_event(self, event_type: str, payload: dict) -> EventRecord: ...
    async def list_events(self, limit: int = 50) -> list[EventRecord]: ...
    async def compile_workload_config(self, workload_id: str) -> CompiledWorkloadConfig: ...
    async def add_local_memory(self, request: WriteRequest, event_id: str) -> str: ...
    async def search_local_memories(self, request: RecallRequest) -> list[MemoryHit]: ...
    async def revoke_memory(self, memory_id: str) -> bool: ...
    async def health(self) -> dict: ...


class InMemoryStore:
    def __init__(self) -> None:
        self._resources: dict[str, MeshResource] = {}
        self._events: list[EventRecord] = []
        self._memories: dict[str, dict] = {}
        self._revoked: set[str] = set()
        self._resource_index: dict[str, list[str]] = defaultdict(list)

    async def init(self) -> None:
        return None

    async def close(self) -> None:
        return None

    @staticmethod
    def resource_key(kind: str, namespace: str, name: str) -> str:
        return f'{kind}:{namespace}:{name}'

    async def apply_resource(self, resource: MeshResource) -> str:
        key = self.resource_key(resource.kind, resource.metadata.namespace, resource.metadata.name)
        self._resources[key] = resource
        self._resource_index[resource.kind].append(key)
        return key

    async def get_resource(self, kind: str, namespace: str, name: str) -> MeshResource | None:
        return self._resources.get(self.resource_key(kind, namespace, name))

    async def append_event(self, event_type: str, payload: dict) -> EventRecord:
        event = EventRecord(event_type=event_type, payload=payload, **event_context_from_payload(payload))
        self._events.append(event)
        return event

    async def list_events(self, limit: int = 50) -> list[EventRecord]:
        return list(reversed(self._events[-limit:]))

    async def compile_workload_config(self, workload_id: str) -> CompiledWorkloadConfig:
        return compile_workload_config_from_resources(self._resources.values(), workload_id=workload_id)

    async def add_local_memory(self, request: WriteRequest, event_id: str) -> str:
        memory_id = uuid4().hex
        record = {
            'memory_id': memory_id,
            'text': request.content,
            'memory_class': request.memory_class.value,
            'tags': list(request.tags),
            'metadata': dict(request.metadata),
            'event_id': event_id,
            'envelope': dump_model(request.envelope),
        }
        self._memories[memory_id] = record
        return memory_id

    async def search_local_memories(self, request: RecallRequest) -> list[MemoryHit]:
        query_tokens = tokenize(request.query)
        hits: list[MemoryHit] = []
        for record in self._memories.values():
            # Read-enforced revocation: a tombstoned memory never surfaces in recall.
            if record['memory_id'] in self._revoked:
                continue
            env = record['envelope']
            scope_bonus, scope_name = scope_bonus_for_request(request, env)
            if scope_bonus < 0:
                continue
            overlap = token_overlap(query_tokens, tokenize(record['text']))
            if overlap <= 0 and request.query.lower() not in record['text'].lower():
                continue
            score = overlap + scope_bonus
            hits.append(
                MemoryHit(
                    memory_id=record['memory_id'],
                    text=record['text'],
                    score=score,
                    source='memoryd.memory',
                    scope=scope_name,
                    tags=record['tags'],
                    metadata=record['metadata'],
                    event_id=record['event_id'],
                )
            )
        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[: request.top_k]

    async def revoke_memory(self, memory_id: str) -> bool:
        # Tombstone the memory so recall never serves it again. Idempotent:
        # returns True only the first time a known memory is revoked.
        if memory_id not in self._memories or memory_id in self._revoked:
            return False
        self._revoked.add(memory_id)
        return True

    async def health(self) -> dict:
        return {
            'backend': 'memory',
            'resource_count': len(self._resources),
            'event_count': len(self._events),
            'memory_count': len(self._memories),
            'revoked_count': len(self._revoked),
        }


def compile_workload_config_from_resources(resources: Iterable[MeshResource], *, workload_id: str) -> CompiledWorkloadConfig:
    attachments: list[dict[str, Any]] = []
    peers: list[dict[str, Any]] = []
    export_policies: list[dict[str, Any]] = []
    conflict_policies: list[dict[str, Any]] = []
    recall_scope_order = list(DEFAULT_SCOPE_ORDER)
    recall_top_k_limit = 10
    local_first = True
    writeback_enabled = True
    allow_backend_persistence = True

    for resource in resources:
        spec = resource.spec or {}
        targets = set(spec.get('targetWorkloads') or spec.get('workloadIds') or [])
        applies = not targets or workload_id in targets or spec.get('workloadId') == workload_id or resource.metadata.name == workload_id
        if not applies:
            continue
        dumped = dump_model(resource)
        if resource.kind == 'MemoryAttachment':
            attachments.append(dumped)
            policy = spec.get('policy') or {}
            recall_scope_order = list(policy.get('scopeOrder') or policy.get('scope_order') or recall_scope_order)
            recall_top_k_limit = int(policy.get('topKLimit') or policy.get('recall_top_k') or recall_top_k_limit)
            writeback_enabled = bool(policy.get('writebackEnabled', policy.get('writeback_enabled', writeback_enabled)))
            allow_backend_persistence = bool(policy.get('allowBackendPersistence', policy.get('allow_backend_persistence', allow_backend_persistence)))
            local_first = bool(policy.get('localFirst', policy.get('local_first', local_first)))
        elif resource.kind == 'MemoryPeer':
            peers.append(dumped)
        elif resource.kind == 'ExportPolicy':
            export_policies.append(dumped)
        elif resource.kind == 'ConflictPolicy':
            conflict_policies.append(dumped)
        elif resource.kind == 'GlobalRecallPolicy':
            recall_scope_order = list(spec.get('scopeOrder') or spec.get('scope_order') or recall_scope_order)
            recall_top_k_limit = int(spec.get('topKLimit') or spec.get('recall_top_k') or recall_top_k_limit)
            local_first = bool(spec.get('localFirst', spec.get('local_first', local_first)))
            writeback_enabled = bool(spec.get('writebackEnabled', spec.get('writeback_enabled', writeback_enabled)))
            allow_backend_persistence = bool(spec.get('allowBackendPersistence', spec.get('allow_backend_persistence', allow_backend_persistence)))

    compiled = CompiledWorkloadConfig(
        workload_id=workload_id,
        recall_scope_order=recall_scope_order,
        recall_top_k_limit=recall_top_k_limit,
        local_first=local_first,
        writeback_enabled=writeback_enabled,
        allow_backend_persistence=allow_backend_persistence,
        attachments=attachments,
        peers=peers,
        export_policies=export_policies,
        conflict_policies=conflict_policies,
    )
    payload = dump_model(compiled)
    payload.pop('config_hash', None)
    compiled.config_hash = stable_object_hash(payload)
    return compiled


def tokenize(text: str) -> set[str]:
    return {token.strip('.,!?;:()[]{}').lower() for token in text.split() if token.strip()}


def token_overlap(query_tokens: set[str], text_tokens: set[str]) -> float:
    if not query_tokens or not text_tokens:
        return 0.0
    return float(len(query_tokens & text_tokens))


def build_scope_order(scope_order: list[str] | None) -> list[str]:
    ordered = list(EXTENDED_RECALL_SCOPE_PREFIX)
    for item in scope_order or DEFAULT_RECALL_SCOPE_ORDER:
        if item and item not in ordered:
            ordered.append(item)
    for fallback in DEFAULT_RECALL_SCOPE_ORDER:
        if fallback not in ordered:
            ordered.append(fallback)
    return ordered


def scope_name_for_request(request: RecallRequest, env: dict) -> str:
    req = request.envelope
    if env.get('user_id') != req.user_id:
        return 'none'
    if req.thread_id and env.get('thread_id') == req.thread_id:
        return 'thread'
    if req.channel and env.get('channel') == req.channel:
        return 'channel'
    if req.workspace_id and env.get('workspace_id') == req.workspace_id:
        return 'workspace'
    if env.get('run_id') == req.run_id:
        return 'run'
    if env.get('agent_id') == req.agent_id:
        return 'agent'
    return 'user'


def scope_rank(scope_name: str, scope_order: list[str] | None) -> int:
    ordered = build_scope_order(scope_order)
    if scope_name not in ordered:
        return 0
    return len(ordered) - ordered.index(scope_name)


def scope_bonus_for_request(request: RecallRequest, env: dict, scope_order: list[str] | None = None) -> tuple[float, str]:
    req = request.envelope
    if env.get('workload_id') and env.get('workload_id') != req.workload_id:
        return -1.0, 'none'
    if req.workspace_id is not None and env.get('workspace_id') is not None and env.get('workspace_id') != req.workspace_id:
        return -1.0, 'none'
    scope_name = scope_name_for_request(request, env)
    if scope_name == 'none':
        return -1.0, 'none'
    return float(scope_rank(scope_name, scope_order or request.scope_order)), scope_name


def hit_sort_key(hit: MemoryHit, *, scope_order: list[str] | None, local_first: bool) -> tuple[int, int, float]:
    local_source_bonus = 1 if local_first and hit.source.startswith(LOCAL_SOURCE_PREFIXES) else 0
    return local_source_bonus, scope_rank(hit.scope, scope_order), float(hit.score)


def rank_hits_by_policy(hits: list[MemoryHit], *, scope_order: list[str] | None, local_first: bool) -> list[MemoryHit]:
    return sorted(
        hits,
        key=lambda hit: hit_sort_key(hit, scope_order=scope_order, local_first=local_first),
        reverse=True,
    )


def dedupe_hits(hits: list[MemoryHit]) -> list[MemoryHit]:
    best_by_id: dict[str, MemoryHit] = {}
    for hit in hits:
        existing = best_by_id.get(hit.memory_id)
        if existing is None or hit.score > existing.score:
            best_by_id[hit.memory_id] = hit
    return list(best_by_id.values())
