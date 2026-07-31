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

from . import adapters, artifacts, masking, receipts, registry, zerotrust
from .contract import ComputeOutput, ComputeRequest, ComputeResult, GraphEdge

MEMOIZE = os.getenv("GATEWAY_MEMOIZE", "true").lower() == "true"
WRITE_PROVENANCE = os.getenv("GATEWAY_WRITE_PROVENANCE", "true").lower() == "true"
MAX_WORKFLOW_DEPTH = int(os.getenv("GATEWAY_MAX_WORKFLOW_DEPTH", "3"))

# content-addressed compute memo: sha(project|kind|backend|spec) → prior ComputeResult.
_MEMO: dict[str, ComputeResult] = {}
_MEMO_MAX = int(os.getenv("GATEWAY_MEMO_MAX", "2048"))

# the epistemic ladder, weakest → strongest (for the workflow weakest-link warrant)
_LADDER = ["unknown", "hypothesis", "simulated", "observed", "derived", "verified", "attested"]


# ─── #1006 exhaust-shape guard ─────────────────────────────────────────────
# ExhaustRecord is counts + hash-only item refs, not raw payloads. An adapter
# that packs verbatim text/bytes into `_exhaust` would make
# /v1/artifacts/{exhaust_sha} an exfil channel: the endpoint is token-gated
# but any token holder becomes a consumer. Enforce the shape here so an
# adapter cannot smuggle raw content through the discard ledger.
#
# Shape matches the ExhaustRecord already in use across compute-gateway (see
# tests/test_exhaust_accounting.py:28 for the canonical example).

import json as _json
import re as _re

_EXHAUST_TOP_KEYS = frozenset({
    "type", "specVersion", "source", "counts", "bytesIn", "bytesOut", "items",
    # Short-label metadata; bounded lengths enforced below.
    "reason", "policy", "policy_ref", "adapter", "stage",
})
_EXHAUST_ITEM_KEYS = frozenset({"kind", "sha256", "size", "ref"})
_DIGEST_HEX_RE = _re.compile(r"^[a-f0-9]{64}$")
_DIGEST_OR_URN_RE = _re.compile(r"^(sha256:[a-f0-9]{64}|urn:[A-Za-z0-9._~:/-]+)$")
# Cap ref-string length so an adapter cannot smuggle payload as a huge URN.
# 512 chars comfortably covers real digest and URN shapes; longer inputs are
# not references — they are content. Copilot round-1 caught this bypass.
_MAX_REF_LEN = 512
_MAX_LABEL_LEN = 256          # kind, source, adapter, etc. — labels, not blobs
_MAX_REASON_LEN = 512         # bounded free-text
_MAX_ITEMS = 10_000           # DoS safeguard on the ledger
_MAX_SPEC_VERSION_LEN = 64    # a version string ("2.0", "2026-07-29"), not a field
_MAX_COUNT_KEYS = 256         # a counts map is a tally, not a key-value store
# Upper bound on any non-negative integer field. Python ints are arbitrary
# precision, so "must be a non-negative int" is not by itself a bound at all — a
# 1.9-million-digit int passes `isinstance(v, int)` just fine and only trips the
# aggregate-serialisation cap on the way out. That means the per-field check
# was declarative, not enforcing: exactly the "dimension nobody enumerated"
# shape #1071 warned about. int64 max (~9.22e18) sits above any real byte count
# (this exceeds exabyte-scale) and above any conceivable count of events, but
# refuses to store a digit-encoded blob as a "number".
_MAX_NONNEG_INT = 2**63 - 1

# Aggregate backstop. Every bound above is per-field, and per-field bounds only
# close the dimensions someone remembered to enumerate — `specVersion` and the
# *number* of `counts` keys were both unbounded on earlier passes of this very
# guard, each good for >10 MB of verbatim smuggled text. A total-size cap is the
# one check that also closes the dimensions nobody thought of, so it is
# deliberately consulted last and deliberately NOT derived from the per-field
# limits (deriving it would make it re-state the same assumptions it exists to
# catch).
#
# Sized by measurement, not guess: the largest LEGITIMATE record the per-field
# bounds permit is a full 10 000-entry bare-digest discard ledger, which
# serialises to 0.93 MiB. The largest record that is legal in every individual
# field but is plainly payload — 10 000 items x two 512-char URN refs — is
# 10.05 MiB. 2 MiB sits between them: ~2x headroom over the real ceiling, and
# still refuses the per-field-legal blob.
_MAX_EXHAUST_BYTES = 2 * 1024 * 1024


def _bad_ref(v) -> bool:
    if not isinstance(v, str):
        return True
    if len(v) > _MAX_REF_LEN:
        return True
    return not (_DIGEST_HEX_RE.match(v) or _DIGEST_OR_URN_RE.match(v))


def _bad_nonneg_int(v) -> bool:
    # bool subclasses int; excluded first so True/False are rejected as types.
    # The upper bound is what makes this a real gate: without it, an adapter can
    # smuggle a 1.9-MB decimal blob as a "count" and only the aggregate
    # backstop catches it — see the module docstring for the exhaust guard.
    if isinstance(v, bool) or not isinstance(v, int) or v < 0:
        return True
    return v > _MAX_NONNEG_INT


def _validate_exhaust(exhaust) -> str | None:
    """Return None if `exhaust` matches ExhaustRecord shape; else a short reason."""
    if not isinstance(exhaust, dict):
        return f"not a mapping: {type(exhaust).__name__}"
    for k in exhaust:
        if k not in _EXHAUST_TOP_KEYS:
            return f"unknown top-level key {k!r}"
    if "type" in exhaust and exhaust["type"] != "ExhaustRecord":
        return f"type must be 'ExhaustRecord', got {exhaust['type']!r}"
    for lbl in ("source", "adapter", "stage", "policy", "policy_ref"):
        if lbl in exhaust and not (isinstance(exhaust[lbl], str) and 0 < len(exhaust[lbl]) <= _MAX_LABEL_LEN):
            return f"{lbl} must be a short label string (<= {_MAX_LABEL_LEN} chars)"
    if "reason" in exhaust and not (isinstance(exhaust["reason"], str) and len(exhaust["reason"]) <= _MAX_REASON_LEN):
        return f"reason must be a bounded string (<= {_MAX_REASON_LEN} chars)"
    if "specVersion" in exhaust and not (
        isinstance(exhaust["specVersion"], str) and len(exhaust["specVersion"]) <= _MAX_SPEC_VERSION_LEN
    ):
        return f"specVersion must be a version string (<= {_MAX_SPEC_VERSION_LEN} chars)"
    for count_key in ("bytesIn", "bytesOut"):
        if count_key in exhaust and _bad_nonneg_int(exhaust[count_key]):
            return f"{count_key} must be a bounded non-negative int (<= {_MAX_NONNEG_INT})"
    if "counts" in exhaust:
        c = exhaust["counts"]
        if not isinstance(c, dict):
            return "counts must be a mapping"
        if len(c) > _MAX_COUNT_KEYS:
            return f"counts has {len(c)} entries (max {_MAX_COUNT_KEYS}) — a tally, not a payload"
        for k, v in c.items():
            if not isinstance(k, str) or len(k) > _MAX_LABEL_LEN:
                return f"counts.{k!r} label out of range"
            if _bad_nonneg_int(v):
                return f"counts.{k} must be a bounded non-negative int (<= {_MAX_NONNEG_INT})"
    if "items" in exhaust:
        items = exhaust["items"]
        if not isinstance(items, list):
            return "items must be a list"
        if len(items) > _MAX_ITEMS:
            return f"items length {len(items)} > {_MAX_ITEMS}"
        for i, it in enumerate(items):
            if not isinstance(it, dict):
                return f"items[{i}] not a mapping"
            for k in it:
                if k not in _EXHAUST_ITEM_KEYS:
                    return f"items[{i}] unknown key {k!r}"
            if "kind" in it and not (isinstance(it["kind"], str) and 0 < len(it["kind"]) <= _MAX_LABEL_LEN):
                return f"items[{i}].kind must be a short label"
            if "sha256" in it and _bad_ref(it["sha256"]):
                return f"items[{i}].sha256 must be a 64-hex digest or sha256:/urn: ref"
            if "size" in it and _bad_nonneg_int(it["size"]):
                return f"items[{i}].size must be a bounded non-negative int (<= {_MAX_NONNEG_INT})"
            if "ref" in it and _bad_ref(it["ref"]):
                return f"items[{i}].ref must be a digest/URN reference"
    # Aggregate backstop — last, so it catches whatever the per-field checks
    # above did not think to bound. Everything reaching here is JSON-safe
    # (str/int/dict/list only), but fail closed if serialisation surprises us.
    #
    # Deliberately WITHOUT default=str, even though artifacts.digest uses it. A
    # default= handler is the opposite of failing closed: it stops json.dumps
    # raising on an unknown type by silently stringifying it, so the except branch
    # below could never fire and an object the per-field checks never anticipated
    # would be measured, accepted, and stored. Since nothing that reaches here
    # should be anything but str/int/dict/list, a TypeError is exactly the signal
    # wanted — it means the validation above regressed.
    try:
        total = len(_json.dumps(exhaust, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    except (TypeError, ValueError) as exc:
        return f"exhaust is not serialisable ({type(exc).__name__}: {exc}) — refusing to store it"
    if total > _MAX_EXHAUST_BYTES:
        return f"exhaust serialises to {total} bytes > {_MAX_EXHAUST_BYTES} — a ledger, not a payload"
    return None


def _guard_exhaust(exhaust):
    """Return the exhaust dict if it passes the ExhaustRecord shape check.

    Three outcomes, because callers branch on them:

    * passes            -> the dict itself, unchanged
    * a dict that fails -> a stripped-safe dict recording ONLY that the exhaust
                           was rejected and why. The offending content never
                           reaches the artifact store.
    * None, or anything  -> ``None``. There is nothing to annotate: the caller
      that is not a dict     stores exhaust only ``if isinstance(exhaust, dict)``,
                             so a string or list simply produces no exhaust
                             record rather than an empty one.

    Never raises — a shape violation is a receipt annotation, not a run-time
    failure. Copilot flagged the earlier docstring for promising the second
    outcome in all failing cases; the third was already the behaviour and is the
    right one, so the docstring moved rather than the code."""
    if exhaust is None:
        return None
    why = _validate_exhaust(exhaust)
    if why is None:
        return exhaust
    if not isinstance(exhaust, dict):
        return None
    return {
        "type": "ExhaustRecord",
        "source": "compute-gateway",
        "adapter": "compute-gateway",
        "stage": "engine._guard_exhaust",
        "reason": f"exhaust rejected: {why[:_MAX_REASON_LEN - 32]}",
        "counts": {"rejectedFields": 1},
    }




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

    # ── masking PDP (read-path) ────────────────────────────────────────────────
    # For governed read kinds, apply the field-level masking policy to the outputs
    # BEFORE they are sealed, so the receipt attests exactly what the caller received
    # and the masking decision rides the same Ed25519 attestation. No policy
    # configured → exact passthrough (zero behaviour change on a live gateway).
    if status == "ok" and kind in masking.READ_KINDS:
        raw["outputs"] = masking.apply(
            raw["outputs"], kind=kind, project=req.project,
            actor=req.actor, entitlement=req.entitlement)

    # ── exhaust accounting (W6.1) ──────────────────────────────────────────────
    # Every receipt carries what the stage consumed vs produced (bytes_out/bytes_in
    # is the v1 entropy proxy). An adapter that DISCARDS things reports them via
    # `_exhaust` (an ExhaustRecord, sourceos-spec: counts + hash-only item refs) —
    # content-addressed into the artifact store so the discard ledger is retrievable
    # at /v1/artifacts/{exhaust_sha}, and bound to the receipt via exhaust_sha.
    outputs_dump = [o.model_dump() for o in raw["outputs"]]
    exhaust = _guard_exhaust(raw.get("_exhaust"))
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
