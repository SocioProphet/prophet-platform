from __future__ import annotations

from typing import Any

import httpx

from .models import MemoryHit, RecallRequest, WriteRequest, dump_model


class Mem0RestClient:
    def __init__(self, base_url: str | None, api_key: str | None, timeout_seconds: float = 10.0) -> None:
        self.base_url = (base_url or '').rstrip('/')
        self.api_key = api_key or ''
        self.timeout_seconds = timeout_seconds

    @property
    def enabled(self) -> bool:
        return bool(self.base_url)

    @property
    def headers(self) -> dict[str, str]:
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['X-API-Key'] = self.api_key
        return headers

    async def recall(self, request: RecallRequest) -> list[MemoryHit]:
        if not self.enabled:
            return []

        payload = {
            'query': request.query,
            'user_id': request.envelope.user_id,
            'agent_id': request.envelope.agent_id,
            'run_id': request.envelope.run_id,
            'limit': request.top_k,
            'filters': request.filters,
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(f'{self.base_url}/search', json=payload, headers=self.headers)
            response.raise_for_status()
            data = response.json()

        raw_results: list[dict[str, Any]] = []
        if isinstance(data, dict):
            if isinstance(data.get('results'), list):
                raw_results = data['results']
            elif isinstance(data.get('memories'), list):
                raw_results = data['memories']

        hits: list[MemoryHit] = []
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            text = item.get('memory') or item.get('text') or item.get('content') or ''
            memory_id = str(item.get('id') or item.get('memory_id') or '')
            score = float(item.get('score') or item.get('similarity') or 0)
            scope = 'user'
            if item.get('run_id') == request.envelope.run_id:
                scope = 'run'
            elif item.get('agent_id') == request.envelope.agent_id:
                scope = 'agent'
            hits.append(
                MemoryHit(
                    memory_id=memory_id or text[:16],
                    text=str(text),
                    score=score,
                    source='mem0',
                    scope=scope,
                    tags=list(item.get('tags') or []),
                    metadata={k: v for k, v in item.items() if k not in {'memory', 'text', 'content', 'score', 'similarity'}},
                )
            )
        return hits

    async def write(self, request: WriteRequest) -> list[str]:
        if not self.enabled:
            return []
        payload = {
            'messages': [
                {
                    'role': 'user',
                    'content': request.content,
                }
            ],
            'user_id': request.envelope.user_id,
            'agent_id': request.envelope.agent_id,
            'run_id': request.envelope.run_id,
            'metadata': {
                **request.metadata,
                'memory_class': request.memory_class.value,
                'tags': request.tags,
                'workload_id': request.envelope.workload_id,
                'source_interface': request.envelope.source_interface,
            },
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(f'{self.base_url}/memories', json=payload, headers=self.headers)
            response.raise_for_status()
            data = response.json()

        ids: list[str] = []
        if isinstance(data, dict):
            if isinstance(data.get('results'), list):
                for item in data['results']:
                    if isinstance(item, dict) and item.get('id'):
                        ids.append(str(item['id']))
            elif data.get('id'):
                ids.append(str(data['id']))
        return ids
