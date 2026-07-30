"""compute-gateway — one governed door for every kind of compute.

POST /v1/compute takes a ComputeRequest, gates it (auth + uniform entitlement),
routes it to the owning backend adapter, seals the universal hash-chained
receipt, types the output's warrant, and writes the run's provenance subgraph
back to the graph. Notebook and graph queries go through the exact same path —
the walking skeleton of "any compute, one contract".
"""
from __future__ import annotations

import os
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException

from pydantic import BaseModel

from . import artifacts, config_plane, engine, engine_receipts, grants, planner, receipts, registry, rocrate, signing, zerotrust
from .contract import ComputeRequest, ComputeResult

app = FastAPI(title="compute-gateway", version="0.1.0")

GATEWAY_TOKEN = os.getenv("GATEWAY_TOKEN", "")


def require_token(authorization: str = Header(default="")) -> None:
    if not GATEWAY_TOKEN:
        raise HTTPException(status_code=503, detail="gateway token not configured (fail-closed)")
    if authorization.removeprefix("Bearer ").strip() != GATEWAY_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")


@app.get("/healthz")
def healthz() -> dict:
    """Liveness + attestation posture. The signing block is the alarm: a misconfigured
    `GATEWAY_SIGNING_KEY` (bad base64, wrong length, corrupt seed) used to be silently
    downgraded to unsigned by `signing.load_signing_key()`, and `receipts.verify()`
    couldn't notice because it only rejects a present-but-invalid signature — so an
    operator lost signatures across the fleet with a green health check. `signing.state`
    surfaces that fault as 'error' here; `signed_ratio` reports the observed share of
    receipts in memory carrying a verifying signature (all projects, all chains)."""
    total = 0
    signed = 0
    for chain in receipts._CHAINS.values():
        for r in chain:
            total += 1
            if r.signature is not None and r.statement is not None and signing.verify_signature(
                    r.statement, r.signature, r.public_key):
                signed += 1
    return {
        "ok": True,
        "service": "compute-gateway",
        "kinds": list(registry.KINDS),
        "signing": {
            "state": signing.signing_state(),
            "signed": signed,
            "count": total,
            "signed_ratio": (signed / total) if total else None,
        },
    }


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
    """One governed door for every kind of compute. Unknown kind/backend is a 422
    (client error); everything else the engine resolves, gates (entitlement +
    zero-trust grant), memoizes, routes (or, for a `workflow`, orchestrates a DAG
    of governed sub-computes), seals, attests, and writes provenance for."""
    try:
        registry.resolve(req.kind, req.backend)
    except registry.UnknownKind:
        raise HTTPException(status_code=422, detail=f"unknown compute kind: {req.kind}")
    except registry.UnknownBackend as e:
        raise HTTPException(status_code=422, detail=str(e))
    return await engine.execute(req)


class PlanRequest(BaseModel):
    capabilities: list[str] = []
    project: str = "default"
    intent: str | None = None
    entitlement: str | None = None


@app.post("/v1/plan")
def plan_view(req: PlanRequest, _: None = Depends(require_token)) -> dict:
    """Plan a governed workflow over the capability registry (layer 6 — the
    registry as an agent action space). A PREVIEW: returns a runnable `workflow`
    spec + per-step entitlement/warrant, but executes nothing. Planning is free;
    hand `plan` to POST /v1/compute to run it under full governance."""
    return planner.plan(capabilities=req.capabilities, project=req.project,
                        intent=req.intent, entitlement=req.entitlement)


class GrantRequestBody(BaseModel):
    kind: str
    backend: str | None = None
    project: str = "default"
    actor: str = "user"
    session: str | None = None
    quorum_signatures: list[dict] | None = None   # [{spiffe_id, sig}] for HIGH-danger


@app.post("/v1/grants")
def grant_request(req: GrantRequestBody, _: None = Depends(require_token)) -> dict:
    """The full grant flow (deep kernel): PolicyDecision → (human quorum if HIGH) →
    issued Grant + ledger event. A HIGH-danger (user-code) op with no quorum
    signatures returns the decision + `quorum_required`, no grant. Present the
    returned grant_id on /v1/compute under ZEROTRUST_ENFORCE."""
    try:
        kind, _d, backend = registry.resolve(req.kind, req.backend)
    except (registry.UnknownKind, registry.UnknownBackend) as e:
        raise HTTPException(status_code=422, detail=str(e))
    return grants.request_grant(kind=kind, backend=backend, project=req.project,
                                actor=req.actor, session=req.session,
                                quorum_signatures=req.quorum_signatures)


@app.get("/v1/grants/ledger")
def grant_ledger(_: None = Depends(require_token)) -> dict:
    """The append-only grant ledger — issue / validate / revoke / deny events."""
    led = grants.ledger()
    return {"count": len(led), "events": led}


@app.post("/v1/grants/{grant_id}/revoke")
def grant_revoke(grant_id: str, _: None = Depends(require_token)) -> dict:
    """Revoke a grant. Authoritative — every subsequent check fails closed."""
    ok = grants.revoke(grant_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"no grant {grant_id}")
    return {"grant_id": grant_id, "revoked": True}


@app.get("/v1/grants/{grant_id}")
def grant_get(grant_id: str, _: None = Depends(require_token)) -> dict:
    g = grants.get(grant_id)
    if g is None:
        raise HTTPException(status_code=404, detail=f"no grant {grant_id}")
    return {"grant": g, "validity": grants.validate(grant_id)}


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


@app.get("/v1/artifacts/stats")
def artifacts_stats(_: None = Depends(require_token)) -> dict:
    """Content-addressed store stats — unique blobs vs total puts (dedup at work)."""
    return artifacts.stats()


@app.get("/v1/artifacts/{digest}")
def artifact_get(digest: str, _: None = Depends(require_token)) -> dict:
    """Fetch a blob by its content address. Digest carries the `sha256:` prefix."""
    blob = artifacts.get(digest)
    if blob is None:
        raise HTTPException(status_code=404, detail=f"no artifact {digest}")
    return {"digest": digest, "blob": blob}


@app.get("/v1/diff")
def diff_view(a: str, b: str, _: None = Depends(require_token)) -> dict:
    """Data-level diff of two runs by their receipt ids — shared/added/removed
    output blobs. Reproducibility you can see: identical inputs ⇒ identical digests."""
    return artifacts.diff(a, b)


@app.get("/v1/receipts/{receipt_id}/artifacts")
def receipt_artifacts(receipt_id: str, _: None = Depends(require_token)) -> dict:
    return {"receipt": receipt_id, "artifacts": artifacts.for_receipt(receipt_id)}


@app.get("/v1/receipts/{receipt_id}/ro-crate")
def ro_crate_view(receipt_id: str, project: str = "default",
                  _: None = Depends(require_token)) -> dict:
    """Export a sealed run as an RO-Crate 1.1 research object (JSON-LD) — the
    portable, citable, self-verifying packaging the science ecosystem speaks
    (Galaxy/WorkflowHub/Nextflow). Carries content-addressed I/O, PROV-O, and the
    embedded in-toto/Ed25519 attestation."""
    match = next((r for r in receipts.chain(project) if r.id == receipt_id), None)
    if match is None:
        raise HTTPException(status_code=404, detail=f"no receipt {receipt_id} in project {project}")
    return rocrate.build(match)


def _workflow_step_receipts(composite_id: str, chain: list) -> list:
    """Recover a workflow's ordered step receipts at export time. The composite's stored
    output blob carries `steps[].receipt` (data lineage from artifacts), so no engine state
    is needed — and with durable artifacts this survives a restart too."""
    by_id = {r.id: r for r in chain}
    for d in artifacts.for_receipt(composite_id):
        blob = artifacts.get(d)
        steps = blob.get("data", {}).get("steps") if isinstance(blob, dict) else None
        if steps:
            return [by_id[s["receipt"]] for s in steps
                    if isinstance(s, dict) and s.get("receipt") in by_id]
    return []


@app.get("/v1/workflows/{receipt_id}/ro-crate")
def workflow_ro_crate_view(receipt_id: str, project: str = "default",
                           _: None = Depends(require_token)) -> dict:
    """Export a WHOLE workflow run — the composite plus every step's receipt, I/O, and
    signed attestation — as ONE RO-Crate 1.1 research object. The single portable,
    self-verifying artifact that reconstructs the entire chain of custody; for a single
    run use /v1/receipts/{id}/ro-crate instead."""
    chain = receipts.chain(project)
    composite = next((r for r in chain if r.id == receipt_id), None)
    if composite is None:
        raise HTTPException(status_code=404, detail=f"no receipt {receipt_id} in project {project}")
    if composite.kind != "workflow":
        raise HTTPException(
            status_code=422,
            detail=f"receipt {receipt_id} is kind '{composite.kind}', not a workflow — "
                   f"use /v1/receipts/{receipt_id}/ro-crate")
    steps = _workflow_step_receipts(composite.id, chain)
    return rocrate.build_workflow(composite, steps)


class EngineSealBody(BaseModel):
    """W1.3 receipt unification — an ENGINE sealed() receipt presented for chaining."""
    kind: Literal["enrich", "explore"]
    engineReceipt: dict[str, Any]
    subject: dict[str, Any] = {}
    project: str = "default"
    actor: str = "hellgraph-service"
    entitlement: str | None = None


@app.post("/v1/engine-receipts")
async def engine_receipt_seal(body: EngineSealBody, _: None = Depends(require_token)) -> dict:
    """Chain a HellGraph ENGINE sealed() receipt (enrich | explore) into THE receipt
    spine. Runs through the exact same governed path as every compute (the
    `engine-seal` kind): entitle → memo → validate + RECOMPUTE the engine's sealed
    sha256 byte-exactly → seal → Ed25519-attest. Identical receipt re-presented ⇒
    the memo returns the SAME receipt (idempotent retry, materialize precedent).
    A receipt whose seal does not recompute is refused (422) — the spine never
    attests what it cannot verify."""
    req = ComputeRequest(
        kind="engine-seal", project=body.project, actor=body.actor,
        entitlement=body.entitlement,
        spec={"kind": body.kind, "engineReceipt": body.engineReceipt, "subject": body.subject})
    result = await engine.execute(req)
    if result.status in ("entitlement_required", "grant_required"):
        raise HTTPException(status_code=403, detail=result.message or result.status)
    if result.status != "ok" or result.receipt is None:
        raise HTTPException(status_code=422, detail=result.error or result.message or "engine-seal refused")
    return {
        "receiptId": result.receipt.id,
        "envelope": {"receipt": result.receipt.model_dump(), "attestation": result.attestation},
        "memoized": result.memoized,
    }


@app.get("/v1/engine-receipts/{receipt_id}/verify")
def engine_receipt_verify(receipt_id: str, project: str = "default",
                          _: None = Depends(require_token)) -> dict:
    """ONE verify() that walks an engine receipt end-to-end: chain position (every
    id-hash + prev-link from genesis) and gateway Ed25519 signature → engine
    sealed-hash recomputation → snapshot.seq binding.

    Once past auth this ALWAYS answers 200 with {valid, steps:[{step, status,
    detail}]} — the typed trace IS the result, so a missing receipt, a tampered
    chain and a broken seal are all valid:false at the step that owns the failure,
    never an HTTP error. Auth itself still refuses first: require_token raises 401
    (bad/absent token) or 503 (no GATEWAY_TOKEN configured — fail-closed)."""
    return engine_receipts.verify_walk(project, receipt_id)


class ConfigSetBody(BaseModel):
    name: str
    value: bool | int | float | str
    kind: str = "flag"          # "flag" | "model" (a per-model kill-switch)
    actor: str = "operator"
    app: str = "noetica"
    model: str | None = None
    org: str | None = None


@app.get("/v1/config")
def config_snapshot(app: str = "noetica", model: str | None = None,
                    org: str | None = None,
                    authorization: str = Header(default="")) -> dict:
    """The flag snapshot a client caches.

    The DEFAULT scope is deliberately unauthenticated: a client that cannot reach the plane
    falls back to its last cached snapshot, so gating the common read would only deepen an
    outage. But org/model SELECTORS are a different matter — leaving them open let any
    caller enumerate other tenants' snapshots by guessing identifiers (raised in review), so
    a scoped read requires the token. Open where openness helps, closed where it leaks.
    """
    if (model or org) and authorization.removeprefix("Bearer ").strip() != GATEWAY_TOKEN:
        raise HTTPException(status_code=401, detail="scoped config reads require a token")
    return config_plane.get_snapshot(app=app, model=model, org=org)


@app.post("/v1/config/set")
def config_set(body: ConfigSetBody, _: None = Depends(require_token)) -> dict:
    """Change a flag or per-model kill-switch. The change is SEALED as a receipt before it
    takes effect, so 'who turned this off, from what, and when' is provable rather than
    merely logged. Unknown flags are refused: the plane's authority is explicit."""
    try:
        return config_plane.set_flag(
            body.name, body.value, kind=body.kind, actor=body.actor,
            app=body.app, model=body.model, org=body.org)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/v1/config/history")
def config_history(limit: int = 50, _: None = Depends(require_token)) -> dict:
    """Current values with the receipt that set each one. The immutable change history is
    the receipt chain itself — not duplicated here, so the two can never drift."""
    return {"entries": config_plane.history(limit)}


@app.get("/v1/receipts")
def receipts_view(project: str = "default", _: None = Depends(require_token)) -> dict:
    ch = receipts.chain(project)
    return {"project": project, "count": len(ch), "receipts": [r.model_dump() for r in ch]}


@app.get("/v1/receipts/verify")
def receipts_verify(project: str = "default", _: None = Depends(require_token)) -> dict:
    return receipts.verify(project)
