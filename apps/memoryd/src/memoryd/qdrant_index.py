from __future__ import annotations

from typing import Any

import httpx

from .models import MemoryHit, RecallRequest, WriteRequest
from .store import scope_bonus_for_request


class QdrantMemoryIndex:
    def __init__(
        self,
        *,
        url: str,
        api_key: str | None,
        collection_name: str,
        vector_size: int,
        distance: str = 'Cosine',
        enabled: bool = False,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.url = url.rstrip('/')
        self.api_key = api_key or ''
        self.collection_name = collection_name
        self.vector_size = vector_size
        self.distance = distance
        self.enabled = enabled and bool(url)
        self.timeout_seconds = timeout_seconds
        self._initialized = False

    @property
    def headers(self) -> dict[str, str]:
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['api-key'] = self.api_key
        return headers

    async def ensure_collection(self) -> None:
        if not self.enabled or self._initialized:
            return
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.put(
                f'{self.url}/collections/{self.collection_name}',
                json={'vectors': {'size': self.vector_size, 'distance': self.distance}},
                headers=self.headers,
            )
            response.raise_for_status()
        self._initialized = True

    async def upsert_memory(self, request: WriteRequest, *, memory_id: str, event_id: str) -> None:
        if not self.enabled or not request.vector:
            return
        await self.ensure_collection()
        payload = {
            'text': request.content,
            'memory_class': request.memory_class.value,
            'tags': list(request.tags),
            'metadata': dict(request.metadata),
            'event_id': event_id,
            'envelope': request.envelope.dict() if hasattr(request.envelope, 'dict') else request.envelope.model_dump(),
            'user_id': request.envelope.user_id,
            'agent_id': request.envelope.agent_id,
            'run_id': request.envelope.run_id,
            'workload_id': request.envelope.workload_id,
            'workspace_id': request.envelope.workspace_id,
            'source_interface': request.envelope.source_interface,
        }
        point = {'id': memory_id, 'vector': request.vector, 'payload': payload}
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.put(
                f'{self.url}/collections/{self.collection_name}/points',
                params={'wait': 'true'},
                json={'points': [point]},
                headers=self.headers,
            )
            response.raise_for_status()

    async def search(self, request: RecallRequest) -> list[MemoryHit]:
        if not self.enabled or not request.query_vector:
            return []
        await self.ensure_collection()
        must_filters: list[dict[str, Any]] = [
            {'key': 'user_id', 'match': {'value': request.envelope.user_id}},
            {'key': 'workload_id', 'match': {'value': request.envelope.workload_id}},
        ]
        if request.envelope.workspace_id is not None:
            must_filters.append({'key': 'workspace_id', 'match': {'value': request.envelope.workspace_id}})

        body: dict[str, Any] = {
            'query': request.query_vector,
            'limit': request.top_k,
            'with_payload': True,
            'filter': {'must': must_filters},
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f'{self.url}/collections/{self.collection_name}/points/query',
                json=body,
                headers=self.headers,
            )
            response.raise_for_status()
            data = response.json()

        points = []
        if isinstance(data, dict):
            result = data.get('result') or {}
            if isinstance(result, dict) and isinstance(result.get('points'), list):
                points = result['points']

        hits: list[MemoryHit] = []
        for item in points:
            if not isinstance(item, dict):
                continue
            payload: dict[str, Any] = dict(item.get('payload') or {})
            envelope = payload.get('envelope') or {}
            scope_bonus, scope_name = scope_bonus_for_request(request, envelope)
            if scope_bonus < 0:
                continue
            score = float(item.get('score') or 0.0) + (scope_bonus / 100.0)
            hits.append(
                MemoryHit(
                    memory_id=str(item.get('id')),
                    text=str(payload.get('text', '')),
                    score=score,
                    source='memoryd.qdrant',
                    scope=scope_name,
                    tags=list(payload.get('tags') or []),
                    metadata=dict(payload.get('metadata') or {}),
                    event_id=payload.get('event_id'),
                )
            )
        return hits

    async def health(self) -> dict[str, Any]:
        if not self.enabled:
            return {'enabled': False}
        try:
            await self.ensure_collection()
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(f'{self.url}/collections/{self.collection_name}', headers=self.headers)
                response.raise_for_status()
            return {'enabled': True, 'collection': self.collection_name}
        except Exception as exc:  # pragma: no cover
            return {'enabled': True, 'error': str(exc)}
