"""Regis ER spine — the opt-in, subscription-gated entity-resolution plane.

Executable spine (per regis-entity-graph ER/NER integration plan):
    event-ir/ingest -> resolve/entities -> policy/check -> graph/upsert -> proof

ARCHITECTURAL PRINCIPLE (Michael, 2026-07-03): this is an **opt-in subscription** cloud plane.
The sovereign **local-first core (Noetica) operates fully without it** — sensitive inference stays
on-device. This plane activates only under an explicit entitlement, and only ever sees data the
user opts to share (after local masking / policy-veto). Nothing here is required for Noetica to run.

Emitted envelopes conform to the regis-entity-graph domain schemas (vendored in ../schemas):
node.schema.json, graph_delta.schema.json, proof-certificate.schema.json.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from regis_acr_api.graph_backend import get_backend

router = APIRouter(prefix="/v1", tags=["er-spine"])

SCHEMA_VERSION = "0.1.0"
POLICY_VERSION = "policy://regis-acr/er-spine@0.1.0"
SOURCE_REPO = "SocioProphet/regis-entity-graph"

# --- the opt-in / subscription declaration (readable without entitlement) ------------------
PLANE_INFO: Dict[str, Any] = {
    "plane": "identity-entity-resolution",
    "activation": "opt-in-subscription",
    "local_first_core": "Noetica",
    "principle": (
        "This cloud entity-resolution plane is ADDITIVE and OPT-IN. The sovereign local-first core "
        "(Noetica) operates fully without it; sensitive inference stays on-device. This plane "
        "activates only under an explicit subscription entitlement and only sees data the user opts "
        "to share after local masking / policy-veto."
    ),
}

# --- entitlement gate: the subscription boundary -------------------------------------------
def require_entitlement(x_regis_entitlement: Optional[str] = Header(default=None)) -> Dict[str, str]:
    """Opt-in gate. Without a subscription entitlement the plane is inert (402), which is the
    point: Noetica never depends on this — you must explicitly turn it on."""
    if os.environ.get("REGIS_ENTITLEMENT_ALLOW_ALL") == "1":
        return {"subscription": "dev-allow-all"}
    if not x_regis_entitlement:
        raise HTTPException(
            status_code=402,
            detail=(
                "The Regis entity-resolution plane is an opt-in subscription. Provide an "
                "X-Regis-Entitlement token to activate it. The local-first Noetica core runs "
                "without this plane."
            ),
        )
    return {"subscription": x_regis_entitlement}


# --- graph backing: in-memory (local-first default) or hellgraph (opt-in, HELLGRAPH_SUPERPEER_URL) ---
# see graph_backend.get_backend(). Proofs + the event log are receipts, not graph atoms, so they
# stay in-process here.
_PROOFS: Dict[str, Dict[str, Any]] = {}
_EVENT_LOG: List[Dict[str, Any]] = []


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(obj: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def _make_node(node_id: str, kind: str, attrs: Dict[str, Any], scope: str, event_ids: List[str]) -> Dict[str, Any]:
    """Conforms to node.schema.json: valid_time=TimeRange{from,to}, system_time=SystemTimeRange
    {from_version,to_version}, provenance=Provenance{source_event_ids,artifact_ids}. `to`/`to_version`
    null = open-ended (current). Scope is carried on attrs (schema-open object)."""
    return {
        "node_id": node_id,
        "kind": kind,
        "valid_time": {"from": _now(), "to": None},
        "system_time": {"from_version": 0, "to_version": None},
        "attrs": {**attrs, "scope": scope},
        "provenance": {"source_event_ids": event_ids, "artifact_ids": []},
    }


def _make_delta(operations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Conforms to graph_delta.schema.json."""
    trace = _sha256(operations)
    return {
        "delta_id": f"delta-{uuid4()}",
        "schema_version": SCHEMA_VERSION,
        "emitted_at": _now(),
        "source_repo": SOURCE_REPO,
        "source_run_id": f"regis-acr-{uuid4()}",
        "trace_hash": trace,
        "operations": operations,
    }


def _make_proof(claim_type: str, result: str, evidence_refs: List[str]) -> Dict[str, Any]:
    """Conforms to proof-certificate.schema.json (result/claim_type enums; certificate_hash sha256:)."""
    body = {
        "proof_certificate_id": f"proof-{uuid4()}",
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "claim_type": claim_type,
        "result": result,
        "evidence_refs": evidence_refs or [f"artifact://regis-acr/{uuid4()}"],
    }
    body["certificate_hash"] = _sha256(body)
    _PROOFS[body["proof_certificate_id"]] = body
    return body


# --- request models -------------------------------------------------------------------------
class EventIR(BaseModel):
    event_id: str = Field(default_factory=lambda: f"evt-{uuid4()}")
    scope: str = Field(default="CITIZEN_FOG", description="fog-first scope realm")
    kind: str = "OBSERVATION"
    payload: Dict[str, Any] = Field(default_factory=dict)


class ResolveRequest(BaseModel):
    scope: str = "CITIZEN_FOG"
    mentions: List[Dict[str, Any]] = Field(default_factory=list)
    candidates: List[Dict[str, Any]] = Field(default_factory=list)


class PolicyCheckRequest(BaseModel):
    action: str = "MERGE"
    src_scope: str = "CITIZEN_FOG"
    dst_scope: str = "CITIZEN_FOG"


# --- the spine ------------------------------------------------------------------------------
@router.get("/plane-info")
def plane_info() -> Dict[str, Any]:
    """Readable without entitlement — states the opt-in / local-first principle."""
    b = get_backend()
    return {**PLANE_INFO, "graph_backend": b.name, "graph_backend_health": b.health()}


@router.post("/event-ir/ingest")
def event_ir_ingest(evt: EventIR, ent=Header(default=None, alias="X-Regis-Entitlement")) -> Dict[str, Any]:
    require_entitlement(ent)
    record = {"event_id": evt.event_id, "scope": evt.scope, "kind": evt.kind, "ingested_at": _now()}
    _EVENT_LOG.append(record)
    return {"accepted": True, "event": record, "log_len": len(_EVENT_LOG)}


@router.post("/policy/check")
def policy_check(req: PolicyCheckRequest, ent=Header(default=None, alias="X-Regis-Entitlement")) -> Dict[str, Any]:
    require_entitlement(ent)
    # policy veto: a merge that crosses a protective scope boundary is vetoed (identity-is-prime:
    # prime roles must not be silently multiplied across scopes).
    crossing = req.src_scope != req.dst_scope
    vetoed = req.action == "MERGE" and crossing
    decision = "VETOED" if vetoed else "ADMITTED"
    proof = _make_proof(
        "ProveScopePermission",
        "REFUTED" if vetoed else "VERIFIED",
        [f"scope://{req.src_scope}", f"scope://{req.dst_scope}"],
    )
    return {"decision": decision, "vetoed": vetoed, "reason": "cross-scope merge" if vetoed else "same-scope", "proof_ref": proof["proof_certificate_id"]}


@router.post("/resolve/entities")
def resolve_entities(req: ResolveRequest, ent=Header(default=None, alias="X-Regis-Entitlement")) -> Dict[str, Any]:
    require_entitlement(ent)
    node_id = f"entity-{uuid4()}"
    n_ev = max(len(req.mentions), len(req.candidates), 1)
    result = "VERIFIED" if n_ev >= 2 else "REQUIRES_REVIEW"  # explainable, uncertainty-aware
    event_ids = [m.get("event_id", f"evt-{i}") for i, m in enumerate(req.mentions)] or ["evt-none"]
    node = _make_node(node_id, "ENTITY_CLUSTER", {"n_mentions": len(req.mentions), "n_candidates": len(req.candidates)}, req.scope, event_ids)
    delta = _make_delta([{"kind": "UPSERT_NODE", "node": node}])
    get_backend().apply_delta(delta)
    proof = _make_proof("ProveLinkage", result, [f"mention://{i}" for i in range(len(req.mentions))] or ["mention://none"])
    return {
        "decision": "MERGE" if result == "VERIFIED" else "POSSIBLE_MATCH",
        "entity_id": node_id,
        "confidence": round(min(1.0, 0.5 + 0.2 * n_ev), 3),
        "result": result,
        "graph_delta": delta,
        "proof_ref": proof["proof_certificate_id"],
    }


@router.post("/graph/upsert")
def graph_upsert(delta: Dict[str, Any], ent=Header(default=None, alias="X-Regis-Entitlement")) -> Dict[str, Any]:
    require_entitlement(ent)
    applied = get_backend().apply_delta(delta)
    return {"applied": applied, "delta_id": delta.get("delta_id"), "backend": get_backend().name}


@router.get("/graph/entity/{node_id}")
def get_entity(node_id: str, ent=Header(default=None, alias="X-Regis-Entitlement")) -> Dict[str, Any]:
    require_entitlement(ent)
    node = get_backend().get(node_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"entity {node_id} not found")
    return node


@router.get("/proof/{proof_id}")
def get_proof(proof_id: str, ent=Header(default=None, alias="X-Regis-Entitlement")) -> Dict[str, Any]:
    require_entitlement(ent)
    proof = _PROOFS.get(proof_id)
    if not proof:
        raise HTTPException(status_code=404, detail=f"proof {proof_id} not found")
    return proof
