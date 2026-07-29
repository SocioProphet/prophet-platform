"""The two doors out — both injectable, so the emitter's semantics are proven on fakes.

- HellGraphWriter → hellgraph-service POST /api/graph/node|edge. THE log; nuggets enter
                    the platform exactly the way MarketDataEvents do (market-replay
                    precedent), and prophet-materializer-clickhouse tails the same log.
- GatewayClient   → compute-gateway POST /v1/compute kind=nugget-emit. THE receipt spine.
                    Not a fourth lineage: the same door, the same hash chain and the same
                    Ed25519 attestation the materializer and the lifecycle warden use.
"""
from __future__ import annotations

import json
import os
from typing import Any

import httpx

TIMEOUT = float(os.getenv("HTTP_TIMEOUT_SECONDS", "30"))


class EmitError(RuntimeError):
    """hellgraph-service unreachable or refused a write — retry, never crash-loop."""


class GatewayError(RuntimeError):
    """Receipt minting failed — the batch MUST NOT be marked emitted (fail-closed)."""


class HellGraphWriter:
    """POST /api/graph/node|edge. addNode is an upsert (safe to repeat); addEdge is NOT —
    a re-added edge mints a NEW log event and a duplicate downstream row, which is why the
    emitter tracks completed writes individually instead of replaying whole batches."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def _post(self, path: str, payload: dict[str, Any]) -> None:
        try:
            r = httpx.post(f"{self.base_url}{path}", json=payload, timeout=TIMEOUT)
        except httpx.HTTPError as e:
            raise EmitError(f"hellgraph unreachable: {e}") from e
        if r.status_code != 200:
            raise EmitError(f"hellgraph {r.status_code} on {path}: {r.text[:300]}")

    def post_node(self, node_id: str, labels: list[str], properties: dict[str, Any]) -> None:
        self._post("/api/graph/node", {"id": node_id, "labels": labels,
                                       "properties": properties})

    def post_edge(self, label: str, from_id: str, to_id: str) -> None:
        self._post("/api/graph/edge", {"label": label, "from": from_id, "to": to_id})


class GatewayClient:
    """Seals one receipt per emitted document on the estate spine: POST /v1/compute with
    the `nugget-emit` kind. The gateway hash-chains + Ed25519-attests it; the spec IS the
    receipt's inputs, so inputs_sha binds {doc_ref, content_hash, raw_sha256, nugget_count,
    warrant_counts, validation_failures, batch_hash} into the chain — the seal covers what
    went onto the graph AND how many candidates were REJECTED, so a silent drop in
    extraction quality is visible on the receipt, not just on /healthz.

    Any failure — transport, auth, non-ok status — raises GatewayError, so the caller
    cannot count an unattested batch as emitted."""

    def __init__(self, base_url: str, token: str, project: str = "default") -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.project = project

    def mint(self, *, doc_ref: str, content_hash: str, raw_sha256: str, media_type: str,
             nugget_count: int, warrant_counts: dict[str, int], validation_failures: int,
             batch_hash: str) -> dict[str, Any]:
        req = {
            "kind": "nugget-emit",
            "project": self.project,
            "actor": "nugget-extractor",
            "spec": {
                "doc_ref": doc_ref, "content_hash": content_hash,
                "raw_sha256": raw_sha256, "media_type": media_type,
                "nugget_count": nugget_count, "warrant_counts": warrant_counts,
                "validation_failures": validation_failures, "batch_hash": batch_hash,
            },
        }
        try:
            r = httpx.post(f"{self.base_url}/v1/compute", json=req,
                           headers={"Authorization": f"Bearer {self.token}"},
                           timeout=TIMEOUT)
        except httpx.HTTPError as e:
            raise GatewayError(f"compute-gateway unreachable: {e}") from e
        if r.status_code != 200:
            raise GatewayError(f"compute-gateway {r.status_code}: {r.text[:500]}")
        result = r.json()
        if result.get("status") != "ok" or not result.get("receipt"):
            raise GatewayError(f"nugget-emit receipt refused: {json.dumps(result)[:500]}")
        return result["receipt"]


__all__ = ["EmitError", "GatewayError", "GatewayClient", "HellGraphWriter"]
