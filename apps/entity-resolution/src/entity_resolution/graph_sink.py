"""Live wiring: resolved entities -> HellGraph, plus a SHA-256 hash-chained
resolution receipt into the receipt spine.

This is the ``graph update -> proof artifact`` leg of the identity spine, over
HTTP against the estate's existing services (consume-not-fork):

* HellGraph (``hellgraph-service`` :8090) is the graph of record. We WRITE resolved
  entity nodes and same_as edges via ``POST /api/graph/node`` / ``/api/graph/edge``.
* compute-gateway (:8080) is the canonical hash-chained receipt emitter. We compute
  a SHA-256 receipt (FIPS authoritative) in the exact body shape the gateway seals
  (``kind, inputs_sha, outputs_sha, status, actor, epistemic_status, prev, ts`` with
  ``id = sha256(body)``) and best-effort seal it via ``POST /v1/engine-receipts``.

The locally-computed receipt is always returned and is self-verifying; remote
sealing is best-effort so the resolver degrades safely when the gateway token is
absent (it is fail-closed on auth) or the endpoint is unreachable.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any

import httpx

HELLGRAPH_URL = os.environ.get("HELLGRAPH_URL", "http://hellgraph-service:8090").rstrip("/")
COMPUTE_GATEWAY_URL = os.environ.get("COMPUTE_GATEWAY_URL", "http://compute-gateway:8080").rstrip("/")
HELLGRAPH_TOKEN = os.environ.get("HELLGRAPH_TOKEN", "")
COMPUTE_GATEWAY_TOKEN = os.environ.get("COMPUTE_GATEWAY_TOKEN", "")
RECEIPT_PROJECT = os.environ.get("ER_RECEIPT_PROJECT", "entity-resolution")


def sha(obj: Any) -> str:
    """SHA-256 over canonical JSON — byte-compatible with the compute-gateway spine
    (sort_keys, no ASCII escaping). FIPS: SHA-256 is authoritative."""
    return "sha256:" + hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


class GraphSink:
    """Writes resolved nodes/edges to HellGraph and seals a SHA-256 receipt.

    ``client`` is injectable so the live path is unit-testable against a mock
    transport without a cluster.
    """

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        hellgraph_url: str = HELLGRAPH_URL,
        compute_gateway_url: str = COMPUTE_GATEWAY_URL,
        hellgraph_token: str = HELLGRAPH_TOKEN,
        compute_gateway_token: str = COMPUTE_GATEWAY_TOKEN,
        prev_receipt_id: str | None = None,
    ) -> None:
        self._client = client or httpx.Client(timeout=10.0)
        self._owns_client = client is None
        self.hellgraph_url = hellgraph_url.rstrip("/")
        self.compute_gateway_url = compute_gateway_url.rstrip("/")
        self.hellgraph_token = hellgraph_token
        self.compute_gateway_token = compute_gateway_token
        self._prev = prev_receipt_id

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _hg_headers(self) -> dict[str, str]:
        h = {"content-type": "application/json"}
        if self.hellgraph_token:
            h["authorization"] = f"Bearer {self.hellgraph_token}"
        return h

    def upsert_node(self, node_id: str, labels: list[str], properties: dict[str, Any]) -> dict[str, Any]:
        r = self._client.post(
            f"{self.hellgraph_url}/api/graph/node",
            json={"id": node_id, "labels": labels, "properties": properties},
            headers=self._hg_headers(),
        )
        r.raise_for_status()
        return {"id": node_id, "status": r.status_code}

    def add_edge(self, label: str, src: str, dst: str, properties: dict[str, Any]) -> dict[str, Any]:
        r = self._client.post(
            f"{self.hellgraph_url}/api/graph/edge",
            json={"label": label, "from": src, "to": dst, "properties": properties},
            headers=self._hg_headers(),
        )
        r.raise_for_status()
        return {"label": label, "from": src, "to": dst, "status": r.status_code}

    def write_resolution(self, resolution: dict[str, Any]) -> dict[str, Any]:
        """Materialize a /resolve output: one node per canonical entity, one same_as
        edge per applied merge (from epistemic_edges)."""
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        for ent in resolution.get("entities", []):
            canon = ent["canonical"]
            nodes.append(self.upsert_node(
                ent["entity_id"],
                ["ENTITY_CLUSTER", "CanonicalEntity"],
                {
                    "name": canon["name"],
                    "survivor": canon["survivor"],
                    "size": ent["size"],
                    "members": ent["members"],
                    "scope": canon.get("scope", ""),
                    "primes": canon.get("primes", []),
                    "replay_key": resolution.get("replay_key", {}),
                },
            ))
        for e in resolution.get("epistemic_edges", []):
            edges.append(self.add_edge(
                "same_as",
                e["subject"],
                e["object"],
                {
                    "epistemic_class": e["epistemic_class"],
                    "confidence_type": e["confidence_type"],
                    "confidence_level": e["confidence_level"],
                    "confidence_score": e["confidence_score"],
                },
            ))
        return {"nodes": nodes, "edges": edges}

    def build_receipt(self, inputs: Any, outputs: Any, *, status: str = "ok",
                      actor: str = "entity-resolution", epistemic_status: str = "resolved") -> dict[str, Any]:
        """Compute a SHA-256 hash-chained receipt body + id (self-verifying, FIPS)."""
        body = {
            "project": RECEIPT_PROJECT,
            "kind": "entity_resolution",
            "backend": "entity-resolution",
            "runtime": "python",
            "inputs_sha": sha(inputs),
            "outputs_sha": sha(outputs),
            "status": status,
            "actor": actor,
            "epistemic_status": epistemic_status,
            "prev": self._prev,
            "ts": time.time(),
        }
        receipt = {"id": sha(body), **body}
        self._prev = receipt["id"]  # chain forward
        return receipt

    def emit_receipt(self, receipt: dict[str, Any]) -> dict[str, Any]:
        """Best-effort seal into the compute-gateway receipt spine. The local receipt
        is authoritative; remote sealing is degradeable (gateway is fail-closed on
        auth, so without a token this returns sealed=false with the reason)."""
        if not self.compute_gateway_token:
            return {"sealed": False, "reason": "no compute-gateway token configured"}
        try:
            r = self._client.post(
                f"{self.compute_gateway_url}/v1/engine-receipts",
                json={
                    "kind": "enrich",
                    "engineReceipt": receipt,
                    "subject": {"project": RECEIPT_PROJECT},
                    "project": RECEIPT_PROJECT,
                    "actor": "entity-resolution",
                },
                headers={"authorization": f"Bearer {self.compute_gateway_token}",
                         "content-type": "application/json"},
            )
        except httpx.HTTPError as exc:  # unreachable / timeout
            return {"sealed": False, "reason": f"transport: {exc.__class__.__name__}"}
        if r.status_code >= 400:
            return {"sealed": False, "reason": f"gateway {r.status_code}", "detail": r.text[:200]}
        return {"sealed": True, "response": r.json()}


def materialize(resolution: dict[str, Any], mention_set: dict[str, Any] | None = None,
                *, sink: GraphSink | None = None) -> dict[str, Any]:
    """Full graph-update -> proof leg: write resolved nodes/edges to HellGraph, then
    compute + emit a SHA-256 hash-chained receipt. Returns what actually landed."""
    own = sink is None
    sink = sink or GraphSink()
    try:
        graph = sink.write_resolution(resolution)
        receipt = sink.build_receipt(
            inputs={"mention_set": mention_set, "records": resolution.get("records")},
            outputs={"entities": resolution.get("entities"), "graph": graph},
        )
        seal = sink.emit_receipt(receipt)
        return {"graph": graph, "receipt": receipt, "seal": seal}
    finally:
        if own:
            sink.close()
