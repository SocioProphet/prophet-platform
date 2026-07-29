"""The two doors out — both injectable, so the emitter's semantics are proven on fakes.

- HellGraphWriter -> hellgraph-service POST /api/graph/node|edge. THE log; device
  readings enter the platform exactly the way MarketDataEvents and KnowledgeNuggets do
  (market-replay / nugget-extractor precedent), and the same materializer tails it.
- GatewayClient   -> compute-gateway POST /v1/compute kind=materialize. THE receipt
  spine. NOT a fifth lineage: the same door, the same hash chain and the same Ed25519
  attestation the materializer, the lifecycle warden and the extraction spine use.

WHY kind=materialize AND NOT A NEW KIND. The four spine kinds are materialize,
governance, engine-seal and nugget-emit. `governance` requires an audit_head this
service does not have; `engine-seal` hard-refuses anything that is not a HellGraph
enrich/explore receipt (it RECOMPUTES the seal); `nugget-emit` refuses warrant_counts
outside the KnowledgeNugget taxonomy, so using it would mean lying about warrants.
`materialize` is the one whose spec is domain-neutral, and there is already an in-repo
precedent for reusing it across domains: hellgraph-service's membrane seals EffectDecision
rows with kind=materialize under the comment "reuse its shape, no new kind". A device
batch fills the fields honestly — source is the device, sink is the log, table is the
node label, the cursors are the device's own reading sequence, and batch_hash binds the
exact bytes emitted.

The one honest caveat: the registry stamps `materialize` with the epistemic warrant
`derived`, while a raw sensor value would want `observed`. That is defensible here
because the receipt is not about the measurement — it attests that N readings with this
batch hash were materialized onto the log through this cut. It is a claim about the
materialization, which is derived. If a future device family needs `observed` at the
receipt level, that is an argument for a fifth kind made deliberately, not a reason to
mint one in passing.
"""
from __future__ import annotations

import json
from typing import Any

import httpx

TIMEOUT = 10.0

#: The graph node label readings land under. Also the `table` on the sealed receipt.
READING_LABEL = "DeviceReading"
DEVICE_LABEL = "Device"
PROFILE_LABEL = "DeviceProfile"
ABSENCE_LABEL = "NullAbsenceRecord"
KKO_TYPE_LABEL = "KkoType"

EDGE_FROM_DEVICE = "fromDevice"
EDGE_DECLARED_BY = "declaredBy"
EDGE_CONFORMS_TO = "conformsTo"
EDGE_KKO_TYPE = "kkoType"
EDGE_ABSENCE = "absenceTypedBy"


class EmitError(RuntimeError):
    """A graph write did not land. The batch stays pending and resumes at the same op."""


class GatewayError(RuntimeError):
    """The receipt was refused. Nothing is counted as emitted without one."""


class HellGraphWriter:
    """The one door onto the log: POST /api/graph/node|edge on hellgraph-service.

    addNode is an UPSERT and is safe to repeat. addEdge is NOT — a re-added edge mints a
    second log event and a duplicate downstream row — which is why the emitter tracks a
    per-write cursor and never re-sends the half of a batch that already landed.
    """

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
        self._post("/api/graph/node", {"id": node_id, "labels": labels, "properties": properties})

    def post_edge(self, label: str, from_id: str, to_id: str) -> None:
        self._post("/api/graph/edge", {"label": label, "from": from_id, "to": to_id})


class GatewayClient:
    """Seals one receipt per emitted batch on the estate spine.

    The spec IS the receipt's inputs, so inputs_sha binds {source, sink, table,
    from_cursor, to_cursor, row_count, batch_hash} into the chain — the seal covers the
    exact readings that went onto the graph, in order. Any failure (transport, auth,
    non-ok status, missing receipt) raises, so the caller cannot count an unattested
    batch as emitted.

    Idempotent by construction: an identical spec re-POSTed after a crash hits the
    gateway's content-addressed memo and returns the SAME receipt id with memoized=true,
    rather than minting a duplicate on the chain.
    """

    def __init__(self, base_url: str, token: str, project: str = "default") -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.project = project

    def mint(
        self,
        *,
        device_ref: str,
        from_cursor: int,
        to_cursor: int,
        row_count: int,
        batch_hash: str,
    ) -> dict[str, Any]:
        req = {
            "kind": "materialize",
            "project": self.project,
            "actor": "device-service",
            "spec": {
                "source": device_ref,
                "sink": "hellgraph",
                "table": READING_LABEL,
                "from_cursor": from_cursor,
                "to_cursor": to_cursor,
                "row_count": row_count,
                "batch_hash": batch_hash,
            },
        }
        try:
            r = httpx.post(
                f"{self.base_url}/v1/compute",
                json=req,
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=TIMEOUT,
            )
        except httpx.HTTPError as e:
            raise GatewayError(f"compute-gateway unreachable: {e}") from e
        if r.status_code != 200:
            raise GatewayError(f"compute-gateway {r.status_code}: {r.text[:500]}")
        result = r.json()
        # An adapter-level refusal is HTTP 200 with status="error" in the body, so the
        # status code alone is not the check.
        if result.get("status") != "ok" or not result.get("receipt"):
            raise GatewayError(f"materialize receipt refused: {json.dumps(result)[:500]}")
        return result["receipt"]
