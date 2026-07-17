from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, TypeVar
from uuid import uuid4

from pydantic import BaseModel, Field


T = TypeVar('T', bound=BaseModel)
DEFAULT_SCOPE_ORDER = ['run', 'agent', 'user']


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def dump_model(model: Any) -> dict[str, Any]:
    if hasattr(model, 'model_dump'):
        return model.model_dump()  # type: ignore[no-any-return]
    if hasattr(model, 'dict'):
        return model.dict()  # type: ignore[no-any-return]
    raise TypeError(f'Object {type(model)!r} does not support model dumping')


def parse_model(model_type: type[T], payload: dict[str, Any]) -> T:
    if hasattr(model_type, 'model_validate'):
        return model_type.model_validate(payload)  # type: ignore[return-value]
    return model_type.parse_obj(payload)  # type: ignore[return-value]


def stable_object_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str).encode('utf-8')).hexdigest()


def event_context_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    envelope = payload.get('envelope') or {}
    if not isinstance(envelope, dict):
        envelope = {}
    return {
        'workload_id': payload.get('workload_id') or envelope.get('workload_id'),
        'run_id': payload.get('run_id') or envelope.get('run_id'),
        'workspace_id': payload.get('workspace_id') or envelope.get('workspace_id'),
        'user_id': payload.get('user_id') or envelope.get('user_id'),
        'agent_id': payload.get('agent_id') or envelope.get('agent_id'),
        'evidence_refs': list(payload.get('evidence_refs') or []),
    }


class MemoryClass(str, Enum):
    interaction = 'interaction'
    fact = 'fact'
    preference = 'preference'
    decision = 'decision'
    summary = 'summary'
    scratch = 'scratch'


class ResourceMetadata(BaseModel):
    namespace: str = 'default'
    name: str
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)


class MeshResource(BaseModel):
    apiVersion: str = 'memorymesh.socioprophet.io/v1alpha1'
    kind: Literal['MemoryAttachment', 'GlobalRecallPolicy', 'MemoryPeer', 'ExportPolicy', 'ConflictPolicy']
    metadata: ResourceMetadata
    spec: dict[str, Any] = Field(default_factory=dict)


class ApplyResourceResponse(BaseModel):
    applied: bool
    resource_key: str
    event_id: str
    config_hash: str | None = None


class ScopeEnvelope(BaseModel):
    user_id: str
    agent_id: str
    run_id: str
    workload_id: str
    workspace_id: str | None = None
    channel: str | None = None
    thread_id: str | None = None
    source_interface: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RecallRequest(BaseModel):
    envelope: ScopeEnvelope
    query: str
    top_k: int = Field(default=5, ge=1, le=50)
    scope_order: list[str] = Field(default_factory=lambda: list(DEFAULT_SCOPE_ORDER))
    include_relations: bool = False
    include_raw_events: bool = False
    filters: dict[str, Any] = Field(default_factory=dict)
    query_vector: list[float] | None = None


class MemoryHit(BaseModel):
    memory_id: str
    text: str
    score: float
    source: str
    scope: str
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    event_id: str | None = None


class CompiledWorkloadConfig(BaseModel):
    workload_id: str
    recall_scope_order: list[str] = Field(default_factory=lambda: list(DEFAULT_SCOPE_ORDER))
    recall_top_k_limit: int = 10
    local_first: bool = True
    writeback_enabled: bool = True
    allow_backend_persistence: bool = True
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    peers: list[dict[str, Any]] = Field(default_factory=list)
    export_policies: list[dict[str, Any]] = Field(default_factory=list)
    conflict_policies: list[dict[str, Any]] = Field(default_factory=list)
    config_hash: str = ''


class RecallResponse(BaseModel):
    query: str
    hits: list[MemoryHit]
    compiled_policy: dict[str, Any]
    local_hit_count: int = 0
    backend_hit_count: int = 0
    truncated: bool = False
    event_id: str | None = None


class WriteRequest(BaseModel):
    envelope: ScopeEnvelope
    content: str = Field(min_length=1)
    memory_class: MemoryClass = MemoryClass.interaction
    persist_to_backend: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    vector: list[float] | None = None


class WriteResponse(BaseModel):
    event_id: str
    memory_id: str | None = None
    backend_memory_ids: list[str] = Field(default_factory=list)
    stored_locally: bool = True


class RevokeRequest(BaseModel):
    # Read-enforced revocation (see docs/architecture/memory-distribution-grant.md).
    # Tombstoning a memory here removes it from every subsequent recall on this node,
    # so a revoked memory cannot be served even before a full sync reconciles it away.
    memory_id: str = Field(min_length=1)
    reason: str | None = None
    revocation_ref: str | None = None
    tombstone_ref: str | None = None
    # Upstream provenance refs this memory contributed to the graph, so revocation can
    # supersede the derived edges too. The canonical memory://{id} ref is always added.
    provenance_refs: list[str] = Field(default_factory=list)


class RevokeResponse(BaseModel):
    memory_id: str
    revoked: bool
    event_id: str
    graph_retract: dict[str, Any] = Field(default_factory=dict)


class EventRecord(BaseModel):
    event_id: str = Field(default_factory=lambda: uuid4().hex)
    event_type: str
    event_version: str = 'v1'
    payload: dict[str, Any]
    created_at: datetime = Field(default_factory=utcnow)
    workload_id: str | None = None
    run_id: str | None = None
    workspace_id: str | None = None
    user_id: str | None = None
    agent_id: str | None = None
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
