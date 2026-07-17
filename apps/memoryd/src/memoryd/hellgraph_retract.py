"""HellGraph retract binding for memoryd — propagates revocation into the graph lane.

When a memory is revoked, its derived edges in the managed HellGraph must be superseded
too, otherwise the revoked knowledge stays queryable in the graph even though recall no
longer serves it. HellGraph is a downstream *materialization* of memory, never the
canonical store, so memoryd only needs the retract half of the contract here:

  POST {HELLGRAPH_URL}/v1/retract  {"provenance_refs": [...]}  → supersede derived edges

Graceful-degrade like mem0_client / qdrant_index: if HELLGRAPH_URL is unset the binding is
disabled and returns an inert result, so memoryd runs (and tests pass) without a live graph.
The workspace_ingestion service owns the full CSKG ingest path; this binding deliberately
does not duplicate it.
"""
from __future__ import annotations

import os
from typing import Any

import httpx


class HellGraphRetractClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None, timeout_seconds: float = 10.0) -> None:
        self.base_url = (base_url if base_url is not None else os.getenv('HELLGRAPH_URL', '')).rstrip('/')
        self.api_key = api_key if api_key is not None else os.getenv('HELLGRAPH_API_KEY', '')
        self.timeout_seconds = timeout_seconds

    @property
    def enabled(self) -> bool:
        return bool(self.base_url)

    @property
    def headers(self) -> dict[str, str]:
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['x-api-key'] = self.api_key
        return headers

    async def retract(self, source_refs: list[str]) -> dict[str, Any]:
        """Supersede every graph edge derived from the given provenance/source refs."""
        if not self.enabled:
            return {'retracted': False, 'reason': 'hellgraph disabled', 'source_refs': source_refs}
        if not source_refs:
            return {'retracted': False, 'reason': 'no source refs', 'source_refs': source_refs}
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f'{self.base_url}/v1/retract',
                json={'provenance_refs': source_refs},
                headers=self.headers,
            )
            response.raise_for_status()
            return dict(response.json())


def revocation_source_refs(memory_id: str, extra_refs: list[str] | None = None) -> list[str]:
    """Collect the provenance refs a revoked memory contributed to the graph.

    Every memoryd memory contributes edges under the canonical self-ref
    ``memory://{memory_id}``; callers that know additional upstream provenance refs
    (e.g. a WorkspaceSource id the memory was derived from) pass them as ``extra_refs``
    so those edges are superseded too.
    """
    refs: list[str] = [f'memory://{memory_id}']
    for ref in extra_refs or []:
        if isinstance(ref, str) and ref and ref not in refs:
            refs.append(ref)
    return refs
