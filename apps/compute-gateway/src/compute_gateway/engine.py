"""The compute execution engine — the one gate→grant→memo→route→seal→attest→
provenance pipeline behind /v1/compute.

Extracted from the endpoint so that COMPOSITE kinds can invoke governed
sub-computes through the EXACT same path. A `workflow` is a DAG of steps; every
step is itself a fully-gated, memoized, receipt-sealed, attested compute — so a
pipeline is heterogeneous compute bound by homogeneous, chained evidence (the
Flyte/Dagster/Nextflow answer, but proof-carrying + sovereign by construction).
The workflow seals a COMPOSITE receipt over its ordered step receipts, and its
epistemic warrant is the WEAKEST link — a pipeline is only as warranted as its
least-warranted step.
"""
from __future__ import annotations

import os

from . import adapters, artifacts, receipts, registry, zerotrust
from .contract import ComputeOutput, ComputeRequest, ComputeResult, GraphEdge

MEMOIZE = os.getenv("GATEWAY_MEMOIZE", "true").lower() == "true"
WRITE_PROVENANCE = os.getenv("GATEWAY_WRITE_PROVENANCE", "true").lower() == "true"
MAX_WORKFLOW_DEPTH = int(os.getenv("GATEWAY_MAX_WORKFLOW_DEPTH", "3"))

# content-addressed compute memo: sha(project|kind|backend|spec) → prior ComputeResult.
_MEMO: dict[str, ComputeResult] = {}
_MEMO_MAX = int(os.getenv("GATEWAY_MEMO_MAX", "2048"))

# the epistemic ladder, weakest → strongest (for the workflow weakest-link warrant)
_LADDER = ["unknown", "hypothesis", "simulated", "observed", "derived", "verified", "attested"]


def memo_key(project: str, kind: str, backend: str, spec: dict) -> str:
    return receipts.sha({"project": project, "kind": kind, "backend": backend, "spec": spec})


def _weakest(warrants: list[str]) -> str:
    if not warrants:
        return "unknown"
    return min(warrants, key=lambda w: _LADDER.index(w) if w in _LADDER else 0)


class WorkflowError(ValueError):
    pass


def _as_list(x) -> list[str]:
    return [] if x is None else ([x] if isinstance(x, str) else list(x))


def _deps(s: dict) -> list[str]:
    """A step depends on its explicit `needs` AND any `from` it threads data out of."""
    return list(dict.fromkeys((s.get("needs", []) or []) + _as_list(s.get("from"))))


def _topo_order(steps: list[dict]) -> list[dict]:
    """Kahn topological sort of steps by their `needs`/`from`. Raises on unknown dep or cycle."""
    by_id = {}
    for s in steps:
        sid = s.get("id")
        if not sid or sid in by_id:
            raise WorkflowError(f"each step needs a unique 'id' (offender: {sid!r})")
        by_id[sid] = s
    indeg = {sid: 0 for sid in by_id}
    for s in steps:
        for dep in _deps(s):
            if dep not in by_id:
                raise WorkflowError(f"step '{s['id']}' needs unknown step '{dep}'")
            indeg[s["id"]] += 1
    ready = [sid for sid, d in indeg.items() if d == 0]
    order: list[dict] = []
    while ready:
        sid = ready.pop(0)
        order.append(by_id[sid])
        for s in steps:
            if sid in _deps(s):
                indeg[s["id"]] -= 1
                if indeg[s["id"]] == 0:
                    ready.append(s["id"])
    if len(order) != len(steps):
        raise WorkflowError("workflow steps contain a cycle")
    return order


async def _orchestrate(req: ComputeRequest, depth: int) -> tuple[dict, list[dict], list[str]]:
    """Run the workflow DAG. Returns (raw-adapter-shaped result, step summaries,
    step receipt ids). Fail-fast: a non-ok step stops the run (dependents skipped)."""
    if depth >= MAX_WORKFLOW_DEPTH:
        return ({"outputs": [], "runtime": "workflow", "status": "error",
                 "error": f"workflow nesting exceeds max depth {MAX_WORKFLOW_DEPTH}", "degraded": None},
                [], [])
    steps = req.spec.get("steps")
    if not isinstance(steps, list) or not steps:
        return ({"outputs": [], "runtime": "workflow", "status": "error",
                 "error": "workflow spec needs a non-empty 'steps' list", "degraded": None}, [], [])
    try:
        ordered = _topo_order(steps)
    except WorkflowError as e:
        return ({"outputs": [], "runtime": "workflow", "status": "error",
                 "error": str(e), "degraded": None}, [], [])

    summaries: list[dict] = []
    receipt_ids: list[str] = []
    outputs_by_id: dict[str, dict] = {}   # step id → its primary output data (for `from` threading)
    status = "ok"
    for s in ordered:
        # data threading: a step pulls the output of the step(s) it declares `from`, so a
        # pipeline (extract → reconcile → load) passes real data, not just governance order.
        # Explicit spec fields win over threaded ones.
        spec = {}
        for src in _as_list(s.get("from")):
            spec.update(outputs_by_id.get(src, {}))
        spec.update(s.get("spec") or {})
        step_req = ComputeRequest(
            kind=s.get("kind", ""), spec=spec, backend=s.get("backend"),
            project=req.project, entitlement=req.entitlement, grant_id=req.grant_id,
            actor=req.actor, session=req.session, no_cache=req.no_cache)
        res = await execute(step_req, _depth=depth + 1)
        outputs_by_id[s["id"]] = (res.outputs[0].data if res.outputs and res.outputs[0].data else {})
        summaries.append({
            "id": s["id"], "kind": res.kind, "backend": res.backend, "status": res.status,
            "epistemic_status": res.epistemic_status,
            "receipt": res.receipt.id if res.receipt else None,
            "memoized": res.memoized,
        })
        if res.receipt:
            receipt_ids.append(res.receipt.id)
        if res.status not in ("ok",):
            status = "error" if res.status in ("error", "grant_required", "entitlement_required") else "degraded"
            break   # fail-fast: dependents are not run

    warrant = _weakest([x["epistemic_status"] for x in summaries]) if status == "ok" else "unknown"
    raw = {
        "outputs": [ComputeOutput(type="workflow", data={
            "steps": summaries, "ran": len(summaries), "total": len(ordered),
            "warrant": warrant})],
        "runtime": "workflow", "status": status,
        "error": None if status == "ok" else f"workflow halted at step {summaries[-1]['id']}",
        "degraded": None,
        "_warrant": warrant, "_receipt_ids": receipt_ids,
    }
    return raw, summaries, receipt_ids


async def execute(req: ComputeRequest, _depth: int = 0) -> ComputeResult:
    """The universal compute path: resolve → entitle → zero-trust grant → memo →
    route (or orchestrate) → seal → attest → provenance. One shape for a cell, a
    query, a spark job, or a whole workflow."""
    try:
        kind, _def, backend = registry.resolve(req.kind, req.backend)
    except registry.UnknownKind:
        return ComputeResult(status="error", kind=req.kind, backend=req.backend or "—",
                             epistemic_status="unknown", error=f"unknown compute kind: {req.kind}")
    except registry.UnknownBackend as e:
        return ComputeResult(status="error", kind=req.kind, backend=req.backend or "—",
                             epistemic_status="unknown", error=str(e))

    epistemic = registry.epistemic_for(kind)
    entitled = registry.entitled(req.project, kind, backend, req.entitlement)
    check, permitted = zerotrust.grant_check(
        project=req.project, kind=kind, backend=backend, actor=req.actor,
        grant_id=req.grant_id, entitled=entitled)
    if not permitted:
        return ComputeResult(
            status="entitlement_required" if not entitled else "grant_required",
            kind=kind, backend=backend, epistemic_status=epistemic,
            entitlement_required=not entitled, grant_check=check,
            message=check["result"]["reason"])

    key = memo_key(req.project, kind, backend, req.spec)
    if MEMOIZE and not req.no_cache and key in _MEMO:
        cached = _MEMO[key].model_copy(deep=True)
        cached.memoized = True
        cached.grant_check = check
        return cached

    # route: a workflow orchestrates governed sub-computes through THIS engine;
    # everything else dispatches to its backend adapter.
    if kind == "workflow":
        raw, _summaries, step_receipt_ids = await _orchestrate(req, _depth)
        epistemic = raw.get("_warrant", epistemic) if raw["status"] == "ok" else epistemic
    else:
        raw = await adapters.dispatch(kind, backend, req.spec, req.project, req.session)
        step_receipt_ids = []
    status = raw["status"]
    # an adapter may TYPE the warrant dynamically (extraction = weakest extracted fact;
    # reconcile → verified only when every fact reconciled). Falls back to the kind default.
    epistemic = raw.get("epistemic", epistemic)

    # ── exhaust accounting (W6.1) ──────────────────────────────────────────────
    # Every receipt carries what the stage consumed vs produced (bytes_out/bytes_in
    # is the v1 entropy proxy). An adapter that DISCARDS things reports them via
    # `_exhaust` (an ExhaustRecord, sourceos-spec: counts + hash-only item refs) —
    # content-addressed into the artifact store so the discard ledger is retrievable
    # at /v1/artifacts/{exhaust_sha}, and bound to the receipt via exhaust_sha.
    outputs_dump = [o.model_dump() for o in raw["outputs"]]
    exhaust = raw.get("_exhaust")
    exhaust_sha = artifacts.put(exhaust) if isinstance(exhaust, dict) else None

    receipt = receipts.seal(
        req.project, kind=kind, backend=backend, runtime=raw["runtime"],
        inputs=req.spec, outputs=outputs_dump,
        status=status, actor=req.actor, epistemic_status=epistemic,
        bytes_in=receipts.canonical_size(req.spec),
        bytes_out=receipts.canonical_size(outputs_dump),
        exhaust_sha=exhaust_sha)

    delta = adapters.build_delta(req.project, kind, backend, receipt.id, epistemic,
                                 inputs_sha=receipt.inputs_sha, outputs_sha=receipt.outputs_sha)
    # a workflow's provenance links its run to each step's run (lineage is emergent)
    if kind == "workflow" and step_receipt_ids:
        run_id = delta.nodes[0].id
        for rid in step_receipt_ids:
            short = rid.replace("sha256:", "")[:12]
            step_run = f"proj-{req.project}:compute:{short}"
            delta.edges.append(GraphEdge.model_validate({"label": "HAS_STEP", "from": run_id, "to": step_run}))
            delta.edges.append(GraphEdge.model_validate({"label": "prov:wasInformedBy", "from": step_run, "to": run_id}))
    # an adapter may veto the provenance write-back (`_no_provenance`): a materialize run's
    # provenance subgraph would land in the very graph whose log the materializer tails —
    # each receipt would emit new log events and feed itself forever. The receipt chain
    # still carries the run; only the graph write-back is suppressed.
    if WRITE_PROVENANCE and status == "ok" and not raw.get("_no_provenance"):
        delta.written = await adapters.write_provenance(delta)

    attestation = zerotrust.attestation_bundle(receipt)
    # content-address each output blob (dedup) → data-level lineage + diff
    art = artifacts.store_outputs(receipt.id, [o.model_dump() for o in raw["outputs"]]) if status == "ok" else []
    result = ComputeResult(
        status=status, kind=kind, backend=backend, epistemic_status=epistemic,
        outputs=raw["outputs"], receipt=receipt, graph_delta=delta,
        error=raw.get("error"), degraded=raw.get("degraded"),
        grant_check=check, attestation=attestation, memoized=False, artifacts=art)

    if MEMOIZE and not req.no_cache and status == "ok":
        if len(_MEMO) >= _MEMO_MAX:
            _MEMO.pop(next(iter(_MEMO)))
        _MEMO[key] = result
    return result
