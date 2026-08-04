"""The doors the percolator talks through — all injectable, so the loop's correctness (checkpoint
ordering, fail-closed receipts, tenant-scoped writes) is proven on fakes without a live cluster.

- GraphClient   → hellgraph-service reads: GET /api/graph/log (the change surface the loop tails) +
                  GET /api/graph/subgraph (the live state the dependency catalog is rebuilt from).
- GatewayClient → compute-gateway POST /v1/compute kind=materialize — ONE receipt per percolation
                  batch on the estate spine (never a parallel lineage). Any failure raises so the
                  batch is NOT checkpointed (fail-closed), mirroring prophet-materializer-clickhouse.

Writes to /api/graph/node|edge go through tools.hellgraph_percolation.writer_hellgraph.HellgraphServiceWriter,
which already speaks that surface (and stamps tenant_id + op_set on every object) — not re-implemented here.
"""
from __future__ import annotations

import json
import os
from typing import Any

import httpx

TIMEOUT = float(os.getenv("HTTP_TIMEOUT_SECONDS", "30"))


class GraphClient:
    """Read side of hellgraph-service. `poll` is since-EXCLUSIVE and returns the log contract verbatim
    ({events, cursor, version}); `read_subgraph` returns the whole property graph ({nodes, edgeList})
    the catalog is rebuilt from."""

    def __init__(self, base_url: str, *, subgraph_limit: int = 2000) -> None:
        self.base_url = base_url.rstrip("/")
        self.subgraph_limit = subgraph_limit

    def poll(self, since: int, limit: int) -> dict[str, Any]:
        r = httpx.get(f"{self.base_url}/api/graph/log",
                      params={"since": since, "limit": limit}, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()

    def read_subgraph(self) -> dict[str, Any]:
        # NOTE: /api/graph/subgraph caps at 2000 nodes with no pagination (hellgraph-service). For a
        # graph beyond that a paginated bulk export is needed — tracked as a follow-on; adequate for v1.
        r = httpx.get(f"{self.base_url}/api/graph/subgraph",
                      params={"limit": self.subgraph_limit}, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()


class GatewayError(RuntimeError):
    """Receipt minting failed — the percolation batch MUST NOT be checkpointed (fail-closed)."""


class GatewayClient:
    """Seals one receipt per percolation batch on the estate spine: POST /v1/compute kind=materialize.
    The gateway hash-chains + Ed25519-attests it. Any failure — transport, auth, non-ok status — raises
    GatewayError so the caller cannot checkpoint an unattested batch."""

    def __init__(self, base_url: str, token: str, project: str = "default") -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.project = project

    def mint(self, *, trigger: str, from_cursor: int, to_cursor: int, changed: int,
             materialized: int, batch_hash: str) -> dict[str, Any]:
        req = {
            "kind": "materialize",
            "project": self.project,
            "actor": "hellgraph-percolator",
            "spec": {
                "source": trigger,          # "log-tail" | "exchange-envelope"
                "sink": "hellgraph-graph",
                "table": "graph",
                "from_cursor": from_cursor, "to_cursor": to_cursor,
                "row_count": materialized,  # objects re-materialised in this batch
                "changed": changed,         # seed ids the trigger announced
                "batch_hash": batch_hash,
            },
        }
        try:
            r = httpx.post(f"{self.base_url}/v1/compute", json=req,
                           headers={"Authorization": f"Bearer {self.token}"}, timeout=TIMEOUT)
        except httpx.HTTPError as e:
            raise GatewayError(f"compute-gateway unreachable: {e}") from e
        if r.status_code != 200:
            raise GatewayError(f"compute-gateway {r.status_code}: {r.text[:500]}")
        result = r.json()
        if result.get("status") != "ok" or not result.get("receipt"):
            raise GatewayError(f"percolate receipt refused: {json.dumps(result)[:500]}")
        return result["receipt"]
