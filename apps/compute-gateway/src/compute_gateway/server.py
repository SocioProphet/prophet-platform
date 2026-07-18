"""compute-gateway — one governed door for every kind of compute.

POST /v1/compute takes a ComputeRequest, gates it (auth + uniform entitlement),
routes it to the owning backend adapter, seals the universal hash-chained
receipt, types the output's warrant, and writes the run's provenance subgraph
back to the graph. Notebook and graph queries go through the exact same path —
the walking skeleton of "any compute, one contract".
"""
from __future__ import annotations

import os

from fastapi import Depends, FastAPI, Header, HTTPException

from . import adapters, receipts, registry, zerotrust
from .contract import ComputeRequest, ComputeResult

app = FastAPI(title="compute-gateway", version="0.1.0")

GATEWAY_TOKEN = os.getenv("GATEWAY_TOKEN", "")
WRITE_PROVENANCE = os.getenv("GATEWAY_WRITE_PROVENANCE", "true").lower() == "true"
MEMOIZE = os.getenv("GATEWAY_MEMOIZE", "true").lower() == "true"

# content-addressed compute memo: sha(project|kind|backend|spec) → prior ComputeResult.
# Identical inputs return the identical sealed proof — Flyte/Pachyderm-style memoization,
# but the cached artifact IS the receipt. Bounded so it can't grow unbounded.
_MEMO: "dict[str, ComputeResult]" = {}
_MEMO_MAX = int(os.getenv("GATEWAY_MEMO_MAX", "2048"))


def _memo_key(project: str, kind: str, backend: str, spec: dict) -> str:
    return receipts.sha({"project": project, "kind": kind, "backend": backend, "spec": spec})


def require_token(authorization: str = Header(default="")) -> None:
    if not GATEWAY_TOKEN:
        raise HTTPException(status_code=503, detail="gateway token not configured (fail-closed)")
    if authorization.removeprefix("Bearer ").strip() != GATEWAY_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "service": "compute-gateway", "kinds": list(registry.KINDS)}


@app.get("/v1/contract")
def contract() -> dict:
    """The contract itself, as JSON schema — the spine everything conforms to."""
    return {"request": ComputeRequest.model_json_schema(),
            "result": ComputeResult.model_json_schema()}


@app.get("/v1/registry")
def registry_view(project: str = "default", entitlement: str | None = None,
                  _: None = Depends(require_token)) -> dict:
    return {"project": project, "kinds": registry.catalog(project, entitlement)}


@app.post("/v1/compute", response_model=ComputeResult)
async def compute(req: ComputeRequest, _: None = Depends(require_token)) -> ComputeResult:
    # 1) resolve kind + backend
    try:
        kind, _def, backend = registry.resolve(req.kind, req.backend)
    except registry.UnknownKind:
        raise HTTPException(status_code=422, detail=f"unknown compute kind: {req.kind}")
    except registry.UnknownBackend as e:
        raise HTTPException(status_code=422, detail=str(e))

    epistemic = registry.epistemic_for(kind)

    # 2) the UNIFORM pay-gate — one gate for all compute (like Databricks/Foundry,
    #    but sovereign + per-kind/per-backend). Fail-closed with an honest 402.
    entitled = registry.entitled(req.project, kind, backend, req.entitlement)

    # 3) ZERO-TRUST grant check (OUR kernel) — emitted before any dispatch. Under
    #    ZEROTRUST_ENFORCE, user-code compute with no capability grant fails closed
    #    even when entitled (a paid entitlement is not a capability grant).
    check, permitted = zerotrust.grant_check(
        project=req.project, kind=kind, backend=backend, actor=req.actor,
        grant_id=req.grant_id, entitled=entitled)
    if not permitted:
        return ComputeResult(
            status="entitlement_required" if not entitled else "grant_required",
            kind=kind, backend=backend, epistemic_status=epistemic,
            entitlement_required=not entitled, grant_check=check,
            message=check["result"]["reason"])

    # 4) content-addressed memo — identical inputs return the identical sealed proof
    key = _memo_key(req.project, kind, backend, req.spec)
    if MEMOIZE and not req.no_cache and key in _MEMO:
        cached = _MEMO[key].model_copy(deep=True)
        cached.memoized = True
        cached.grant_check = check
        return cached

    # 5) route to the backend adapter (raw outputs; no receipt yet)
    raw = await adapters.dispatch(kind, backend, req.spec, req.project, req.session)
    status = raw["status"]

    # 6) SEAL the universal receipt — the same for a cell, a query, anything
    receipt = receipts.seal(
        req.project, kind=kind, backend=backend, runtime=raw["runtime"],
        inputs=req.spec, outputs=[o.model_dump() for o in raw["outputs"]],
        status=status, actor=req.actor, epistemic_status=epistemic)

    # 7) provenance subgraph — compute + knowledge, one object model
    delta = adapters.build_delta(req.project, kind, backend, receipt.id, epistemic,
                                 inputs_sha=receipt.inputs_sha, outputs_sha=receipt.outputs_sha)
    if WRITE_PROVENANCE and status == "ok":
        delta.written = await adapters.write_provenance(delta)

    # 8) render the signed receipt as a zero-trust AttestationBundle
    attestation = zerotrust.attestation_bundle(receipt)

    result = ComputeResult(
        status=status, kind=kind, backend=backend, epistemic_status=epistemic,
        outputs=raw["outputs"], receipt=receipt, graph_delta=delta,
        error=raw.get("error"), degraded=raw.get("degraded"),
        grant_check=check, attestation=attestation, memoized=False)

    # 9) memoize successful, deterministic-input runs (bounded)
    if MEMOIZE and not req.no_cache and status == "ok":
        if len(_MEMO) >= _MEMO_MAX:
            _MEMO.pop(next(iter(_MEMO)))
        _MEMO[key] = result
    return result


@app.get("/v1/capability-registry")
def capability_registry_view(_: None = Depends(require_token)) -> dict:
    """The gateway declared to OUR zero-trust kernel — every compute kind is an MCP
    tool with an effect, danger class, and trust hints. Conforms to
    mcp-a2a-zero-trust `capability_registry.schema.json` (validated at startup)."""
    return zerotrust.capability_registry()


@app.get("/v1/attestation")
def attestation_view(project: str = "default", receipt_id: str | None = None,
                     _: None = Depends(require_token)) -> dict:
    """AttestationBundle(s) over sealed receipts — the kernel/agentplane consume
    these to gate downstream actions on proof. `cosign_valid` reflects a verifying
    Ed25519 signature over the in-toto Statement."""
    ch = receipts.chain(project)
    if receipt_id:
        match = next((r for r in ch if r.id == receipt_id), None)
        if match is None:
            raise HTTPException(status_code=404, detail=f"no receipt {receipt_id} in project {project}")
        return {"project": project, "attestation": zerotrust.attestation_bundle(match)}
    return {"project": project, "count": len(ch),
            "attestations": [zerotrust.attestation_bundle(r) for r in ch]}


@app.get("/v1/receipts")
def receipts_view(project: str = "default", _: None = Depends(require_token)) -> dict:
    ch = receipts.chain(project)
    return {"project": project, "count": len(ch), "receipts": [r.model_dump() for r in ch]}


@app.get("/v1/receipts/verify")
def receipts_verify(project: str = "default", _: None = Depends(require_token)) -> dict:
    return receipts.verify(project)
