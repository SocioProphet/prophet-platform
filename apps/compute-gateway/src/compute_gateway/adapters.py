"""Backend adapters — the thin shims that make a heterogeneous backend speak the
one contract. Each returns raw `(outputs, runtime, status, error, degraded)`;
the gateway seals the receipt and types the warrant. New compute kind = new
adapter here + a registry row.

Adapters are injectable (`set_backend`) so tests never need a live forge/graph.
"""
from __future__ import annotations

import os
from typing import Any, Awaitable, Callable

import httpx

from .contract import ComputeOutput, GraphDelta, GraphEdge, GraphNode

FORGE_URL = os.getenv("FORGE_URL", "http://lattice-forge.sovereign-runtime.svc.cluster.local:8870").rstrip("/")
FORGE_TOKEN = os.getenv("FORGE_TOKEN", "")
HELLGRAPH_URL = os.getenv("HELLGRAPH_URL", "http://hellgraph-service:8090").rstrip("/")
SPARK_RUNNER_URL = os.getenv("SPARK_RUNNER_URL", "http://spark-runner:8080").rstrip("/")
SPARK_RUNNER_TOKEN = os.getenv("SPARK_RUNNER_TOKEN", "")
MODEL_SERVER_URL = os.getenv("MODEL_SERVER_URL", "http://embeddings:8080").rstrip("/")
MODEL_SERVER_TOKEN = os.getenv("MODEL_SERVER_TOKEN", "")
# document extraction (Holmes/Sherlock via the Studio BFF) + the open-data reference source.
EXTRACT_URL = os.getenv("EXTRACT_URL", "http://lattice-studio:8080").rstrip("/")
EXTRACT_TOKEN = os.getenv("EXTRACT_TOKEN", "")
# SEC EDGAR XBRL company-facts — public, keyless; the FactSet stand-in for reconciliation.
SEC_EDGAR_URL = os.getenv("SEC_EDGAR_URL", "https://data.sec.gov").rstrip("/")
SEC_EDGAR_UA = os.getenv("SEC_EDGAR_UA", "SocioProphet compute-gateway compliance@socioprophet.dev")
TIMEOUT = float(os.getenv("GATEWAY_TIMEOUT", "90"))

# adapter result shape: dict(outputs=[ComputeOutput], runtime, status, error, degraded)
AdapterResult = dict[str, Any]


async def _forge(req_spec: dict, project: str, session: str | None) -> AdapterResult:
    body = {"project": project, "code": req_spec.get("code", ""),
            "language": req_spec.get("language", "python"),
            "adapter": req_spec.get("adapter"), "session_id": session}
    headers = {"Authorization": f"Bearer {FORGE_TOKEN}"} if FORGE_TOKEN else {}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, headers=headers) as c:
            r = await c.post(f"{FORGE_URL}/v1/execute", json=body)
            if r.status_code != 200:
                return {"outputs": [], "runtime": "python3", "status": "error",
                        "error": f"forge HTTP {r.status_code}", "degraded": None}
            d = r.json()
            outs = [ComputeOutput(**o) if not isinstance(o, ComputeOutput) else o
                    for o in _shape_forge(d.get("outputs", []))]
            return {"outputs": outs, "runtime": d.get("runtime", "python3"),
                    "status": d.get("status", "ok"), "error": d.get("error"),
                    "degraded": d.get("degraded")}
    except Exception as e:  # noqa: BLE001
        return {"outputs": [], "runtime": "python3", "status": "degraded",
                "error": None, "degraded": f"forge unreachable: {e}"}


def _shape_forge(outputs: list[dict]) -> list[dict]:
    shaped = []
    for o in outputs:
        shaped.append({"type": o.get("type", "result"), "text": o.get("text"),
                       "data": {k: o[k] for k in ("png", "svg", "html", "mime") if o.get(k)} or None,
                       "mime": o.get("mime")})
    return shaped


async def _hellgraph_query(req_spec: dict, project: str) -> AdapterResult:
    label = req_spec.get("label") or project
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            r = await c.get(f"{HELLGRAPH_URL}/api/graph/query", params={"label": label})
            if r.status_code != 200:
                return {"outputs": [], "runtime": "hellgraph", "status": "error",
                        "error": f"hellgraph HTTP {r.status_code}", "degraded": None}
            data = r.json()
            nodes = data.get("nodes", data if isinstance(data, list) else [])
            return {"outputs": [ComputeOutput(type="graph", data={"nodes": nodes, "count": len(nodes)})],
                    "runtime": "hellgraph", "status": "ok", "error": None, "degraded": None}
    except Exception as e:  # noqa: BLE001
        return {"outputs": [], "runtime": "hellgraph", "status": "degraded",
                "error": None, "degraded": f"hellgraph unreachable: {e}"}


async def _hellgraph_stats(req_spec: dict, project: str) -> AdapterResult:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            r = await c.get(f"{HELLGRAPH_URL}/api/graph/stats")
            if r.status_code != 200:
                return {"outputs": [], "runtime": "hellgraph", "status": "error",
                        "error": f"hellgraph HTTP {r.status_code}", "degraded": None}
            return {"outputs": [ComputeOutput(type="table", data=r.json())],
                    "runtime": "hellgraph", "status": "ok", "error": None, "degraded": None}
    except Exception as e:  # noqa: BLE001
        return {"outputs": [], "runtime": "hellgraph", "status": "degraded",
                "error": None, "degraded": f"hellgraph unreachable: {e}"}


async def _spark(req_spec: dict, project: str, session: str | None) -> AdapterResult:
    """Sovereign Spark: submit SQL/DataFrame code to spark-runner (the same runtime
    lattice-studio dispatches to). Databricks' one paradigm, here as one backend
    among many behind the uniform contract — entitlement-gated, receipt-sealed."""
    body = {"sql": req_spec.get("sql", ""), "data": req_spec.get("data", []),
            "table": req_spec.get("table", "t"), "job_id": session}
    headers = {"Authorization": f"Bearer {SPARK_RUNNER_TOKEN}"} if SPARK_RUNNER_TOKEN else {}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, headers=headers) as c:
            r = await c.post(f"{SPARK_RUNNER_URL}/v1/submit", json=body)
            if r.status_code != 200:
                return {"outputs": [], "runtime": "spark", "status": "error",
                        "error": f"spark-runner HTTP {r.status_code}: {r.text[:200]}", "degraded": None}
            d = r.json()
            return {"outputs": [ComputeOutput(type="table", data={
                        "rows": d.get("rows", []), "row_count": d.get("row_count"),
                        "backend_receipt": d.get("receipt")})],
                    "runtime": "spark", "status": "ok", "error": None, "degraded": None}
    except Exception as e:  # noqa: BLE001
        return {"outputs": [], "runtime": "spark", "status": "degraded",
                "error": None, "degraded": f"spark-runner unreachable: {e}"}


async def _inference(req_spec: dict, project: str, session: str | None) -> AdapterResult:
    """Model inference (embed | chat) via the sovereign model server. Output warrant
    is `derived` — a model produces it, it is not observed from the graph."""
    task = req_spec.get("task", "embed")
    if task == "embed":
        payload = {"input": req_spec.get("input") or req_spec.get("texts") or []}
        path = "/embed"
    else:
        payload = {"messages": req_spec.get("messages", []), "model": req_spec.get("model")}
        path = "/v1/chat/completions"
    headers = {"Authorization": f"Bearer {MODEL_SERVER_TOKEN}"} if MODEL_SERVER_TOKEN else {}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, headers=headers) as c:
            r = await c.post(f"{MODEL_SERVER_URL}{path}", json=payload)
            if r.status_code != 200:
                return {"outputs": [], "runtime": "model-server", "status": "error",
                        "error": f"model-server HTTP {r.status_code}", "degraded": None}
            return {"outputs": [ComputeOutput(type="result", data=r.json())],
                    "runtime": "model-server", "status": "ok", "error": None, "degraded": None}
    except Exception as e:  # noqa: BLE001
        return {"outputs": [], "runtime": "model-server", "status": "degraded",
                "error": None, "degraded": f"model-server unreachable: {e}"}


# ── IFM: document → structured facts (extraction) + reconcile vs open data ──
# Each extracted fact carries its lineage AND an epistemic warrant, so the desk can
# gate what it trades on. observed = verbatim on the page; derived = computed.
_WARRANT_ORDER = ["unknown", "hypothesis", "simulated", "observed", "derived", "verified", "attested"]


def _norm_fact(f: dict) -> dict:
    """Normalise an extracted fact into the ExtractedFact shape + default warrant."""
    warrant = f.get("warrant")
    if warrant not in _WARRANT_ORDER:
        # verbatim-with-a-source-span is `observed`; anything computed is `derived`
        warrant = "observed" if (f.get("verbatim") or f.get("source_span")) else "derived"
    return {"field": f.get("field"), "value": f.get("value"), "unit": f.get("unit"),
            "page": f.get("page"), "source_span": f.get("source_span"),
            "confidence": f.get("confidence"), "warrant": warrant}


async def _extraction(req_spec: dict, project: str, session: str | None) -> AdapterResult:
    """Extract a document into typed rows against a target schema (Holmes/Sherlock via
    the Studio extract path). Output warrant = the WEAKEST fact's warrant. If the spec
    already carries `facts` (pre-parsed), extract is a no-op typing pass — useful for a
    demo pack whose blocks were parsed upstream."""
    schema = req_spec.get("target_schema", {})
    facts = req_spec.get("facts")
    if facts is None:
        headers = {"Authorization": f"Bearer {EXTRACT_TOKEN}"} if EXTRACT_TOKEN else {}
        body = {"project": project, "document": req_spec.get("document"),
                "blocks": req_spec.get("blocks"), "target_schema": schema}
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT, headers=headers) as c:
                r = await c.post(f"{EXTRACT_URL}/api/studio/extract", json=body)
                if r.status_code != 200:
                    return {"outputs": [], "runtime": "holmes", "status": "error",
                            "error": f"extract HTTP {r.status_code}", "degraded": None}
                facts = r.json().get("facts", [])
        except Exception as e:  # noqa: BLE001
            return {"outputs": [], "runtime": "holmes", "status": "degraded", "error": None,
                    "degraded": f"extractor unreachable: {e}"}
    rows = [_norm_fact(f) for f in facts]
    warrant = min((r["warrant"] for r in rows),
                  key=lambda w: _WARRANT_ORDER.index(w)) if rows else "unknown"
    return {"outputs": [ComputeOutput(type="table", data={
                "table": schema.get("table"), "rows": rows,
                "entity": req_spec.get("entity"), "period": req_spec.get("period")})],
            "runtime": "holmes", "status": "ok", "error": None, "degraded": None,
            "epistemic": warrant}


# field → us-gaap XBRL concept (extend as the schema grows)
_XBRL_CONCEPT = {
    "revenue": "RevenueFromContractWithCustomerExcludingAssessedTax",
    "revenues": "Revenues", "net_income": "NetIncomeLoss", "net_profit": "NetIncomeLoss",
    "assets": "Assets", "liabilities": "Liabilities",
}


async def _sec_edgar_reference(entity: dict, field: str, period: str) -> float | None:
    """Reference value from SEC EDGAR XBRL company-facts (public, keyless). `entity`
    carries a zero-padded 10-digit `cik`. Returns the value whose fiscal period matches,
    else None (unresolved → the fact simply can't reach `verified`)."""
    cik = str(entity.get("cik", "")).zfill(10)
    concept = _XBRL_CONCEPT.get(field.lower())
    if not cik.strip("0") or concept is None:
        return None
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, headers={"User-Agent": SEC_EDGAR_UA}) as c:
            r = await c.get(f"{SEC_EDGAR_URL}/api/xbrl/companyconcept/CIK{cik}/us-gaap/{concept}.json")
            if r.status_code != 200:
                return None
            for unit_rows in r.json().get("units", {}).values():
                for row in unit_rows:
                    if period and (row.get("fp") == period or row.get("frame", "").find(period) >= 0
                                   or str(row.get("fy")) == period):
                        return float(row["val"])
    except Exception:  # noqa: BLE001
        return None
    return None


# the reference resolver is injectable (tests supply a deterministic source; prod = SEC EDGAR)
_REFERENCE = _sec_edgar_reference


def set_reference_resolver(fn) -> None:
    global _REFERENCE
    _REFERENCE = fn


async def _reconcile(req_spec: dict, project: str, session: str | None) -> AdapterResult:
    """Reconcile extracted facts against a structured reference source (SEC EDGAR open
    data now; FactSet on a key later — the logic is identical). Agreement within tolerance
    PROMOTES a fact to `verified`; divergence is FLAGGED (the tradable edge). The step's
    warrant is `verified` iff every fact reconciled, else `derived`."""
    # `rows` is what the extraction step emits — accept it so a workflow can thread
    # extraction → reconcile via `from` without a rename.
    facts = req_spec.get("facts") or req_spec.get("rows") or []
    entity = req_spec.get("entity", {})
    period = req_spec.get("period", "")
    tol = float(req_spec.get("tolerance", 0.01))   # 1% default
    source = req_spec.get("source", "sec-edgar")
    recs, all_ok = [], True
    for f in facts:
        field, val = f.get("field"), f.get("value")
        ref = await _REFERENCE(entity, field, period)
        within = ref is not None and val is not None and abs(float(val) - ref) <= abs(ref) * tol
        delta = (float(val) - ref) if (ref is not None and val is not None) else None
        warrant = "verified" if within else (f.get("warrant") or "derived")
        all_ok = all_ok and within
        recs.append({"field": field, "extracted": val, "reference": ref, "delta": delta,
                     "within_tol": within, "warrant": warrant, "flagged": ref is not None and not within})
    return {"outputs": [ComputeOutput(type="table", data={
                "entity": entity, "period": period, "source": source,
                "reconciliations": recs, "all_verified": all_ok and bool(recs)})],
            "runtime": source, "status": "ok", "error": None, "degraded": None,
            "epistemic": "verified" if (all_ok and recs) else "derived"}


# kind → adapter coroutine. Overridable in tests.
_BACKENDS: dict[str, Callable[..., Awaitable[AdapterResult]]] = {
    "forge": lambda spec, project, session: _forge(spec, project, session),
    "hellgraph:graph-query": lambda spec, project, session: _hellgraph_query(spec, project),
    "hellgraph:graph-stats": lambda spec, project, session: _hellgraph_stats(spec, project),
    "spark-runner": lambda spec, project, session: _spark(spec, project, session),
    "model-server": lambda spec, project, session: _inference(spec, project, session),
    "holmes": lambda spec, project, session: _extraction(spec, project, session),
    "open-data": lambda spec, project, session: _reconcile(spec, project, session),
}


def set_backend(key: str, fn: Callable[..., Awaitable[AdapterResult]]) -> None:
    _BACKENDS[key] = fn


async def dispatch(kind: str, backend: str, spec: dict, project: str, session: str | None) -> AdapterResult:
    fn = _BACKENDS.get(f"{backend}:{kind}") or _BACKENDS.get(backend)
    if fn is None:
        return {"outputs": [], "runtime": backend, "status": "degraded", "error": None,
                "degraded": f"backend '{backend}' for kind '{kind}' not wired yet"}
    return await fn(spec, project, session)


# ── provenance write-back: every run becomes nodes+edges in the graph ──
async def write_provenance(delta: GraphDelta) -> bool:
    """Best-effort: persist the run's subgraph to hellgraph. Never fails the compute."""
    if not delta.nodes:
        return False
    try:
        async with httpx.AsyncClient(timeout=15.0) as c:
            for n in delta.nodes:
                await c.post(f"{HELLGRAPH_URL}/api/graph/node",
                             json={"id": n.id, "labels": n.labels, "properties": n.properties})
            for e in delta.edges:
                await c.post(f"{HELLGRAPH_URL}/api/graph/edge",
                             json={"label": e.label, "from": e.from_, "to": e.to, "properties": e.properties})
        return True
    except Exception:  # noqa: BLE001 — provenance write is best-effort
        return False


def build_delta(project: str, kind: str, backend: str, receipt_id: str, epistemic: str,
                inputs_sha: str | None = None, outputs_sha: str | None = None) -> GraphDelta:
    """The run's provenance subgraph, dual-labelled: OUR native labels (ComputeRun,
    Receipt, …) AND W3C PROV-O terms so it federates with any PROV-aware store —
    the run is a `prov:Activity`, the receipt/output/input are `prov:Entity`, and
    the edges are `prov:wasGeneratedBy` / `prov:used` / `prov:wasDerivedFrom`.
    """
    short = receipt_id.replace("sha256:", "")[:12]
    run_id = f"proj-{project}:compute:{short}"
    rc_id = f"proj-{project}:receipt:{short}"
    out_id = f"proj-{project}:output:{short}"
    in_id = f"proj-{project}:input:{short}"
    nodes = [
        GraphNode(id=run_id, labels=[project, "ComputeRun", kind, "prov:Activity"],
                  properties={"kind": kind, "backend": backend, "epistemic_mode": epistemic}),
        GraphNode(id=rc_id, labels=[project, "Receipt", "prov:Entity"],
                  properties={"receipt": receipt_id}),
        GraphNode(id=out_id, labels=[project, "ComputeOutput", "prov:Entity"],
                  properties={"outputs_sha": outputs_sha, "epistemic_mode": epistemic}),
        GraphNode(id=in_id, labels=[project, "ComputeInput", "prov:Entity"],
                  properties={"inputs_sha": inputs_sha}),
    ]
    edges = [
        # native label kept AND its PROV-O counterpart, side by side
        GraphEdge.model_validate({"label": "HAS_RECEIPT", "from": run_id, "to": rc_id}),
        GraphEdge.model_validate({"label": "prov:wasGeneratedBy", "from": rc_id, "to": run_id}),
        GraphEdge.model_validate({"label": "prov:wasGeneratedBy", "from": out_id, "to": run_id}),
        GraphEdge.model_validate({"label": "prov:used", "from": run_id, "to": in_id}),
        GraphEdge.model_validate({"label": "prov:wasDerivedFrom", "from": out_id, "to": in_id}),
    ]
    return GraphDelta(nodes=nodes, edges=edges)
