#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "contracts" / "crystal-atlas" / "schemas"

REQUIRED = {
    "exchange-envelope.v0.schema.json": ["exchange_id", "exchange_kind", "tenant_id", "actor_id", "source_endpoint", "destination_endpoint", "asset_refs", "policy_ref", "idempotency_key", "trace_ref", "created_at"],
    "graph-node.v0.schema.json": ["node_id", "tenant_id", "node_kind", "display_name", "created_at", "updated_at"],
    "graph-edge.v0.schema.json": ["edge_id", "tenant_id", "edge_type", "src", "dst", "created_at", "updated_at"],
    "claim.v0.schema.json": ["claim_id", "tenant_id", "subject_ref", "predicate", "created_at"],
    "evidence.v0.schema.json": ["evidence_id", "tenant_id", "source_ref", "observed_at", "ingested_at", "receipt_ref"],
    "policy-decision.v0.schema.json": ["decision_id", "tenant_id", "actor_id", "subject_ref", "policy_ref", "decision", "created_at"],
}


def fail(msg: str) -> int:
    print(f"standards-check: FAIL: {msg}")
    return 1


def main() -> int:
    if not SCHEMAS.exists():
        return fail(f"missing schema dir: {SCHEMAS}")
    for fname, required in REQUIRED.items():
        path = SCHEMAS / fname
        if not path.exists():
            return fail(f"missing required schema: {fname}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("additionalProperties", None) is not False:
            return fail(f"{fname} must set additionalProperties=false")
        props = set((payload.get("properties") or {}).keys())
        missing = [k for k in required if k not in props]
        if missing:
            return fail(f"{fname} missing props: {missing}")
        req = set(payload.get("required") or [])
        missing_req = [k for k in required if k not in req]
        if missing_req:
            return fail(f"{fname} missing required fields: {missing_req}")
    print("standards-check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
