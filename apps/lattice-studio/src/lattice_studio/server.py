"""server.py — the Lattice Studio BFF.

Wraps lattice-studio's existing ``product_spine`` (pure functions) into a real HTTP service and AGGREGATES LIVE
data from the running fabric, project-scoped to Noetica ``proj-`` collections. This is the "make it live" service.

Design (production-grade):
  * CONCURRENT fan-out — all upstream calls run under a single ``asyncio.gather`` (not sequential awaits), so
    ``/api/studio`` latency is max(upstream) not sum(upstream).
  * GRACEFUL — every upstream is wrapped; a down/slow service degrades only its own section, never the response.
  * HONEST — the ``live`` map reports exactly which upstreams answered; ``degraded`` carries the reason.

Upstreams (real, in-cluster):
  * hellgraph-service  GET  /api/graph/stats          → Graph section (live stats)
  * search-orchestrator POST /v0/search/query          → Extraction/Sherlock (live federated results)
  * tritfabric         GET  /v1/registry              → Model catalog (live) — degrades until tritfabric is deployed
"""
from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, Response
from pydantic import BaseModel

from lattice_studio import product_spine

SERVICE_VERSION = "0.2.0"
HELLGRAPH_URL = os.getenv("HELLGRAPH_URL", "http://hellgraph-service:8090")
TRITFABRIC_URL = os.getenv("TRITFABRIC_URL", "http://tritfabric:8750")
SEARCH_ORCH_URL = os.getenv("SEARCH_ORCH_URL", "http://search-orchestrator:8080")
TIMEOUT = float(os.getenv("STUDIO_TIMEOUT", "5"))
# Write gate for /api/studio/extract (mutates the graph). Fail-closed: unset → writes refused.
STUDIO_WRITE_TOKEN = os.getenv("STUDIO_WRITE_TOKEN", "")
# Read gate tied to the SOVEREIGN identity plane: the HS256 secret socbase (GoTrue) signs its JWTs with.
# OPT-IN — unset → reads stay open (backward compatible); set → every read requires a valid socbase-issued
# bearer token. Governance without a bolt-on: Studio reads are gated by the same identity that runs the estate.
STUDIO_JWT_SECRET = os.getenv("STUDIO_JWT_SECRET", "")
# Evidence fabric — verified-compute RECEIPTS. Studio surfaces the replayable proof-of-work behind its services:
# not "the job ran" (a TEE attestation), but a sealed record of exactly WHAT ran and its verdict, per correlation.
EVIDENCE_RECEIPTS_URL = os.getenv("EVIDENCE_RECEIPTS_URL", "http://evidence-receipts:8080")
RECEIPT_SERVICES = [s.strip() for s in os.getenv(
    "STUDIO_RECEIPT_SERVICES",
    "hellgraph-service,lattice-studio,search-orchestrator,owl-reasoner,entity-resolution,eval-fabric-api",
).split(",") if s.strip()]

app = FastAPI(title="Lattice Studio BFF", version=SERVICE_VERSION)


def require_read(authorization: str = Header(default="")) -> dict[str, Any] | None:
    """FastAPI dependency for READ endpoints. If STUDIO_JWT_SECRET is unset, returns None (reads open). When set,
    verifies the Bearer JWT (HS256) with that secret and returns its claims (the caller identity); a missing,
    invalid, or expired token is a 401. Reads are thereby gated by sovereign identity, not an ad-hoc password."""
    if not STUDIO_JWT_SECRET:
        return None
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="read requires a bearer token (STUDIO_JWT_SECRET is set)")
    try:
        return jwt.decode(token, STUDIO_JWT_SECRET, algorithms=["HS256"], options={"verify_aud": False})
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail=f"invalid token: {exc}") from exc


def proj_collection(project: str) -> str:
    """Mirror Noetica projectCollectionId — proj-<12 hex of the project id, dashes stripped>."""
    return "proj-" + re.sub(r"-", "", project)[:12]


def _first(d: dict[str, Any], *keys: str, default: str = "—") -> Any:
    for k in keys:
        if d.get(k):
            return d[k]
    return default


async def _req(client: httpx.AsyncClient, method: str, url: str, json: Any | None = None) -> tuple[Any, str | None]:
    """One resilient upstream call. Returns (json_or_None, error_or_None). Never raises."""
    try:
        r = await client.request(method, url, json=json)
        if r.status_code == 200:
            return r.json(), None
        return None, f"HTTP {r.status_code}"
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


def _sherlock_request(project: str) -> dict[str, Any]:
    """A schema-valid sherlock_search_request (see schemas/search/sherlock_search_request.schema.json)."""
    return {
        "query_id": f"studio-{proj_collection(project)}",
        "actor_id": "lattice-studio-bff",
        "text": project,
        "mode": "HYBRID",
        "scope": {"local_desktop": False, "cloud_workspace": True, "memory": True},
        "limit": 10,
    }


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {"ok": True, "service": "lattice-studio", "version": SERVICE_VERSION}


@app.get("/api/studio")
async def studio(project: str = "default", _auth: dict[str, Any] | None = Depends(require_read)) -> dict[str, Any]:
    coll = proj_collection(project)
    spine = product_spine.demo_product_spine()  # the real integration object model

    # ── CONCURRENT live fan-out to the running fabric ──
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        (gstats, gerr), (reg, rerr), (sher, serr), (subg, _suberr), (rec, _recerr) = await asyncio.gather(
            _req(client, "GET", f"{HELLGRAPH_URL}/api/graph/stats"),
            _req(client, "GET", f"{TRITFABRIC_URL}/v1/registry"),
            _req(client, "POST", f"{SEARCH_ORCH_URL}/v0/search/query", json=_sherlock_request(project)),
            _req(client, "GET", f"{HELLGRAPH_URL}/api/graph/subgraph?label={coll}&limit=300"),
            _req(client, "GET", f"{EVIDENCE_RECEIPTS_URL}/v1/receipts/recent?service=hellgraph-service&limit=10"),
        )
    degraded = {k: v for k, v in {"graph": gerr, "models": rerr, "extraction": serr}.items() if v}

    # ── The MOAT header, computed live on every load: epistemic distribution + provenance coverage across the
    # project's facts, plus whether the verified-compute evidence fabric is answering. This governance readout
    # rides ABOVE every section — the proof-carrying identity of the whole workspace, not just the graph panel.
    epi_nodes = [_map_node(n) for n in ((subg.get("nodes") if isinstance(subg, dict) else None) or [])]
    epi_dist: dict[str, int] = {}
    prov_have = 0
    for n in epi_nodes:
        epi_dist[n["epistemic_mode"]] = epi_dist.get(n["epistemic_mode"], 0) + 1
        if n.get("source"):
            prov_have += 1
    moat = {
        "epistemic_distribution": epi_dist,
        "fact_count": len(epi_nodes),
        "provenance_coverage": round(prov_have / len(epi_nodes), 3) if epi_nodes else 0.0,
        "verified_compute": rec is not None,
        "receipts_recent": len((rec.get("items") if isinstance(rec, dict) else None) or []),
        "governed_writes": bool(STUDIO_WRITE_TOKEN),
        "read_auth": bool(STUDIO_JWT_SECRET),
    }

    # ── Workbench: product_spine object model, bound to the Noetica project ──
    session = dict(spine.get("notebookSession", {}))
    session["projectId"] = project
    notebooks = [{
        "id": _first(session, "notebookSessionId", "id", default="nb-session"),
        "name": _first(session, "name", "title", default="Notebook session"),
        "runtime": _first(spine.get("runtimeAsset", {}), "runtimeAssetId", "name", default="prophet-python-ml"),
        "kernel": "python3", "status": "idle", "updatedAt": _first(session, "createdAt", default=""),
        "cells": 0, "collaborators": ["you"], "projectCollection": coll,
    }]
    data = [
        {"id": _first(d, "catalogAssetId", "id"), "name": _first(d, "name", "title"), "kind": "dataset",
         "catalog": "prophet-core-catalog", "governed": True,
         "lineage": [_first(d, "reproduceCommand", "reproduce_command", default="lineage")]}
        for d in (spine.get("catalogAsset", {}), spine.get("dataProduct", {})) if d
    ]
    models: list[dict[str, Any]] = []
    if reg:
        arts = reg.get("artifacts", reg) if isinstance(reg, dict) else reg
        for a in (arts if isinstance(arts, list) else []):
            models.append({"id": _first(a, "id", "artifact_id", default="m"), "name": _first(a, "name", "id"),
                           "task": _first(a, "task", default="model"), "stage": _first(a, "stage", "state", default="candidate"),
                           "servable": True, "metrics": []})
    if not models:
        for m in (spine.get("factsheet", {}), spine.get("promotionCandidate", {})):
            if m:
                models.append({"id": _first(m, "id", "candidateId"), "name": _first(m, "id", "candidateId"),
                               "task": "governed", "stage": "staged", "lineage": m.get("lineageRefs", [])})
    experiments = [
        {"id": _first(e, "id"), "title": _first(e, "title", "id"), "reproducible": True,
         "provenance": "in-toto + lockfile", "createdAt": "", "rerunnable": True}
        for e in (spine.get("evaluationBundle", {}), spine.get("publicationArtifact", {})) if e
    ]

    # ── Graph: LIVE hellgraph stats ──
    graph: list[dict[str, Any]] = []
    if isinstance(gstats, dict):
        for k, v in gstats.items():
            if isinstance(v, (int, float, str)):
                graph.append({"id": f"g-{k}", "label": k, "value": v})
    graph.append({"id": "g-engine", "label": "Engine", "value": "HellGraph", "hint": f"live · {HELLGRAPH_URL}"})

    # ── Knowledge engineering — LIVE where a service exists, honest lib/spec status otherwise ──
    sher_hits = len(sher.get("results", sher) if isinstance(sher, dict) else (sher or [])) if sher else 0
    extraction = [
        {"id": "x-holmes", "name": "Holmes — entities & relations", "engine": "holmes",
         "kind": "claim reasoning (Propose→Explain→Verify)", "status": "idle", "target": coll},
        {"id": "x-sherlock", "name": "Sherlock — federated search", "engine": "sherlock", "kind": "federated retrieval",
         "status": ("done" if sher is not None else "idle"), "extracted": sher_hits, "target": coll},
    ]
    ontology = [
        {"id": "o-1", "name": "Ontogenesis modules (RDF/OWL + SHACL)", "kind": "class", "engine": "ontogenesis", "aligned": True},
        {"id": "o-epi", "name": "Epistemology (epi.ttl / epistemic_mode)", "kind": "axiom", "engine": "ontogenesis", "aligned": True},
    ]
    retrieval = [
        {"id": "r-fiber", "name": "Fibered retrieval (PageIndex ⊕ HellGraph)", "method": "fiber", "engine": "fibered-retrieval", "scope": "project", "ready": True},
        {"id": "r-grag", "name": "Graph-RAG", "method": "graph-rag", "engine": "hellgraph", "scope": "project", "ready": gstats is not None},
        {"id": "r-topic", "name": "Topic packs (/topic)", "method": "topic", "engine": "slash-topics", "scope": "project", "ready": True},
        {"id": "r-sem", "name": "Semantic + lexical (sheaf)", "method": "vector", "engine": "noetica", "scope": "chat + project", "ready": True},
    ]
    generation = [
        {"id": "gn-1", "name": "New-Hope grounded synthesis", "engine": "new-hope", "kind": "synthesis", "status": "idle", "grounded": True},
    ]

    return {
        "project": project, "projectCollection": coll,
        "moat": moat,
        "notebooks": notebooks, "data": data, "models": models, "tuning": [], "experiments": experiments,
        "extraction": extraction, "ontology": ontology, "graph": graph, "retrieval": retrieval, "generation": generation,
        "live": {"hellgraph": gstats is not None, "tritfabric": reg is not None,
                 "search_orchestrator": sher is not None, "evidence": rec is not None},
        "degraded": (degraded or None),
    }


def _receipt_verdict(item: dict[str, Any]) -> Any:
    rc = item.get("receipt") if isinstance(item.get("receipt"), dict) else {}
    return item.get("verdict") or rc.get("verdict")


@app.get("/api/studio/receipts")
async def receipts(limit: int = 12, _auth: dict[str, Any] | None = Depends(require_read)) -> dict[str, Any]:
    """Verified-compute RECEIPTS from the evidence fabric — the replayable proof-of-work behind Studio's services,
    aggregated across the estate. Each is a sealed record (fetch the full bundle at /v1/receipts/{service}/{cid}):
    not a TEE's 'it ran privately', but 'here is exactly WHAT ran and its verdict'. No incumbent studio has this.
    Graceful: a down evidence fabric or service degrades only its own slice."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        results = await asyncio.gather(*[
            _req(client, "GET", f"{EVIDENCE_RECEIPTS_URL}/v1/receipts/recent?service={s}&limit={limit}")
            for s in RECEIPT_SERVICES
        ])
    out: list[dict[str, Any]] = []
    live: dict[str, bool] = {}
    for svc, (res, err) in zip(RECEIPT_SERVICES, results):
        live[svc] = err is None
        items = (res.get("items") if isinstance(res, dict) else None) or []
        for it in (items if isinstance(items, list) else [])[:limit]:
            it = it if isinstance(it, dict) else {}
            cid = str(it.get("correlation_id") or it.get("id") or "")
            out.append({
                "service": svc, "correlation_id": cid,
                "received_at": it.get("received_at") or it.get("timestamp") or it.get("created_at"),
                "verdict": _receipt_verdict(it),
                "kind": it.get("kind") or it.get("type"),
                "bundle_ref": f"/v1/receipts/{svc}/{cid}" if cid else None,
            })
    out.sort(key=lambda r: str(r.get("received_at") or ""), reverse=True)
    return {
        "receipts": out[: max(limit, 20)], "count": len(out),
        "services": live, "services_reachable": sum(1 for v in live.values() if v),
        "detail_endpoint": f"{EVIDENCE_RECEIPTS_URL}/v1/receipts/{{service}}/{{correlation_id}}",
    }


_QUERY_LANGS = {"sparql", "cypher", "gremlin"}


class QueryRequest(BaseModel):
    project: str = "default"
    lang: str = "sparql"
    query: str
    params: dict[str, str] | None = None


def _scan_ids(obj: Any, epi: dict[str, str], found: dict[str, str]) -> None:
    """Recursively find any value in a query result that is a known project-entity id, so results can carry the
    fact's epistemic status regardless of the (SPARQL/Cypher/Gremlin) result shape."""
    if isinstance(obj, str):
        if obj in epi:
            found[obj] = epi[obj]
    elif isinstance(obj, dict):
        for v in obj.values():
            _scan_ids(v, epi, found)
    elif isinstance(obj, list):
        for v in obj:
            _scan_ids(v, epi, found)


def _rows_columns(res: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """Best-effort normalise a kernel query result into rows + columns for a grid, defensively across shapes."""
    results = res.get("results")
    if isinstance(results, dict) and isinstance(results.get("bindings"), list):  # SPARQL 1.1 JSON
        cols = list(res.get("head", {}).get("vars", []))
        rows = [{c: (b.get(c, {}) or {}).get("value") for c in cols} for b in results["bindings"]]
        return rows, cols
    rws = res.get("rows")
    if isinstance(rws, list):  # Cypher/Gremlin {columns, rows}
        cols = res.get("columns") or (list(rws[0].keys()) if rws and isinstance(rws[0], dict) else [])
        return rws, list(cols)
    return [], []


@app.post("/api/studio/query")
async def query(req: QueryRequest, _auth: dict[str, Any] | None = Depends(require_read)) -> dict[str, Any]:
    """Proof-carrying query IDE (WS#30). Runs SPARQL / Cypher / Gremlin against the live kernel and returns the
    result WITH its replay proof (query_hash + evaluated_at_seq) AND per-fact epistemic enrichment: every value
    that is a known project entity is tagged with how well it's known. Stardog/Bloom return rows; we return rows
    you can REPLAY and whose facts carry their epistemic status. Bad syntax is a 400, not a silently-empty result."""
    lang = req.lang.lower()
    if lang not in _QUERY_LANGS:
        raise HTTPException(status_code=422, detail=f"lang must be one of {sorted(_QUERY_LANGS)}")
    if not req.query.strip():
        raise HTTPException(status_code=422, detail="query required")
    coll = proj_collection(req.project)
    body: dict[str, Any] = {"query": req.query}
    if lang == "cypher" and req.params:
        body["params"] = req.params
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        (res, err), (subg, _s) = await asyncio.gather(
            _req(client, "POST", f"{HELLGRAPH_URL}/api/graph/{lang}", json=body),
            _req(client, "GET", f"{HELLGRAPH_URL}/api/graph/subgraph?label={coll}&limit=500"),
        )
    if not isinstance(res, dict):
        raise HTTPException(status_code=400, detail=f"query failed: {err or 'no result from kernel'}")
    epi = {n["id"]: n["epistemic_mode"] for n in [_map_node(x) for x in ((subg.get("nodes") if isinstance(subg, dict) else None) or [])]}
    epistemic: dict[str, str] = {}
    _scan_ids(res, epi, epistemic)
    rows, columns = _rows_columns(res)
    proof = {
        "query_hash": res.get("queryHash") or res.get("query_hash"),
        "evaluated_at_seq": res.get("evaluatedAtSeq") or res.get("evaluated_at_seq"),
        "replayable": bool(res.get("queryHash") or res.get("query_hash")),
    }
    return {
        "project": req.project, "lang": lang, "columns": columns, "rows": rows, "row_count": len(rows),
        "epistemic": epistemic, "proof": proof,
        "raw": {k: v for k, v in res.items() if k not in ("queryHash", "evaluatedAtSeq", "ok")},
    }


# ── WS#32: experiment tracking — runs persisted as FIRST-CLASS proof-carrying graph facts (not a side DB) ──────────
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_json(s: Any) -> Any:
    if isinstance(s, (dict, list)):
        return s
    try:
        return json.loads(s) if s else {}
    except (ValueError, TypeError):
        return {}


async def _fetch_raw_nodes(coll: str, limit: int = 500) -> tuple[list[dict[str, Any]], str | None]:
    """Raw project nodes (properties preserved — unlike _map_node, which projects to a fixed field set)."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        res, err = await _req(client, "GET", f"{HELLGRAPH_URL}/api/graph/subgraph?label={coll}&limit={limit}")
    raw = (res.get("nodes") if isinstance(res, dict) else None) or []
    return (raw if isinstance(raw, list) else []), err


class ExperimentRun(BaseModel):
    project: str = "default"
    name: str
    params: dict[str, Any] = {}
    metrics: dict[str, float] = {}
    status: str = "finished"   # running | finished | failed
    source: str | None = None


@app.post("/api/studio/experiments")
async def create_experiment(req: ExperimentRun, authorization: str = Header(default="")) -> dict[str, Any]:
    """Track an experiment RUN. MEET MLflow/W&B: params + metrics + status per run. BEAT: the run is persisted as
    a node in the PROOF-CARRYING graph (labels Run+Experiment), so it isn't a row in a side database — it's a FACT
    carrying epistemic status + provenance, queryable via the query IDE and linkable to the data/models it touched.
    Token-gated (it writes the graph)."""
    _require_write_token(authorization)
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="name required")
    coll = proj_collection(req.project)
    run_id = f"{coll}:run:{uuid.uuid4().hex[:12]}"
    prov = _workbench_prov(coll, "observed", req.source or "studio/experiment")
    prov["extractor"] = "studio/experiment-v0"
    props = {
        "name": name, "run_id": run_id, "status": req.status,
        "params_json": json.dumps(req.params, default=str), "metrics_json": json.dumps(req.metrics, default=str),
        "created_at": _now_iso(), **prov,
    }
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        _, err = await _req(client, "POST", f"{HELLGRAPH_URL}/api/graph/node",
                            json={"id": run_id, "labels": [coll, "Run", "Experiment"], "properties": props})
    if err:
        raise HTTPException(status_code=502, detail=f"graph write failed: {err}")
    return {"run_id": run_id, "project": req.project, "name": name, "status": req.status,
            "params": req.params, "metrics": req.metrics, "provenance": prov, "written": True}


@app.get("/api/studio/experiments")
async def list_experiments(project: str = "default", limit: int = 200,
                           _auth: dict[str, Any] | None = Depends(require_read)) -> dict[str, Any]:
    """List the project's experiment runs — read back from the graph, params/metrics parsed, each run carrying its
    epistemic status + provenance. These are graph facts you can also query in the IDE (SPARQL/Cypher over runs)."""
    coll = proj_collection(project)
    raw, err = await _fetch_raw_nodes(coll, limit)
    runs: list[dict[str, Any]] = []
    for n in raw:
        if "Run" not in (n.get("labels") or []):
            continue
        p = n.get("properties") or {}
        runs.append({
            "run_id": p.get("run_id") or n.get("id"), "name": p.get("name"), "status": p.get("status", "unknown"),
            "params": _safe_json(p.get("params_json")), "metrics": _safe_json(p.get("metrics_json")),
            "created_at": p.get("created_at"), "epistemic_mode": p.get("epistemic_mode", "observed"),
            "source": p.get("source"), "extractor": p.get("extractor"),
        })
    runs.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
    return {"project": project, "projectCollection": coll, "runs": runs, "count": len(runs), "degraded": err}


# ── WS#35: sovereign persistent IDs + citation. A citable, resolvable identifier for a knowledge artifact —
# DataCite-compatible so it bridges to the scholarly ecosystem — that resolves to a PROOF-CARRYING record
# (provenance + epistemic + content hash), not a bare landing page. The identifier is itself a graph fact. ──
SP_PID_PREFIX = os.getenv("STUDIO_PID_PREFIX", "sp")
STUDIO_DOI_PREFIX = os.getenv("STUDIO_DOI_PREFIX", "10.82044")          # DataCite-style prefix (placeholder until registered)
STUDIO_RESOLVE_BASE = os.getenv("STUDIO_RESOLVE_BASE", "https://studio.socioprophet.ai/resolve")


class CiteRequest(BaseModel):
    project: str = "default"
    kind: str = "graph"        # graph | run | dataset | fact | document
    ref: str = ""              # target id (run_id / node id / dataset id); "" = the whole-project graph snapshot
    title: str | None = None
    creators: list[str] = []


def _mint_pid(coll: str, kind: str, ref: str) -> tuple[str, str]:
    """Content-addressed sovereign PID: stable per (project, kind, target) so citing the same thing is idempotent."""
    h = hashlib.sha256(f"{coll}:{kind}:{ref}".encode()).hexdigest()[:16]
    return f"{SP_PID_PREFIX}:{coll}/{kind}/{h[:12]}", h


@app.post("/api/studio/cite")
async def cite(req: CiteRequest, authorization: str = Header(default="")) -> dict[str, Any]:
    """Mint a persistent, citable identifier for a knowledge artifact. MEET Zenodo/DataCite: a DOI + a formatted
    citation + BibTeX + DataCite metadata. BEAT: the PID resolves to a PROOF-CARRYING record (the identifier is
    persisted as a Citation graph fact carrying epistemic status + content hash + provenance), and that
    provenance rides inside the DataCite metadata (nanopublication-style) — not a bare landing page."""
    _require_write_token(authorization)
    coll = proj_collection(req.project)
    pid, h = _mint_pid(coll, req.kind, req.ref)
    doi = f"{STUDIO_DOI_PREFIX}/{coll}.{req.kind}.{h[:8]}"
    title = (req.title or f"{req.kind} · {req.ref or coll}").strip()
    creators = req.creators or ["SocioProphet Knowledge Commons"]
    year = datetime.now(timezone.utc).year
    created = _now_iso()
    resolve_url = f"{STUDIO_RESOLVE_BASE}?pid={pid}"
    prov = _workbench_prov(coll, "attested", "studio/cite")   # a minted, hash-sealed identifier is 'attested'
    prov["extractor"] = "studio/cite-v0"
    node_id = f"{coll}:cite:{h[:12]}"
    props = {"pid": pid, "doi": doi, "kind": req.kind, "target": req.ref or coll, "title": title,
             "creators_json": json.dumps(creators), "resolve": resolve_url, "content_hash": h,
             "created_at": created, **prov}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        _, err = await _req(client, "POST", f"{HELLGRAPH_URL}/api/graph/node",
                            json={"id": node_id, "labels": [coll, "Citation", "Identifier"], "properties": props})
    if err:
        raise HTTPException(status_code=502, detail=f"graph write failed: {err}")
    citation = f"{', '.join(creators)} ({year}). {title}. SocioProphet Knowledge Commons. {pid} (DOI: {doi})."
    bibtex = ("@misc{" + h[:8] + ",\n  author = {" + " and ".join(creators) + "},\n  title = {" + title
              + "},\n  year = {" + str(year) + "},\n  howpublished = {SocioProphet Knowledge Commons},\n  note = {"
              + pid + "},\n  doi = {" + doi + "}\n}")
    datacite = {
        "id": doi, "type": "dois",
        "attributes": {
            "doi": doi, "titles": [{"title": title}], "creators": [{"name": c} for c in creators],
            "publisher": "SocioProphet Knowledge Commons", "publicationYear": year,
            "types": {"resourceTypeGeneral": "Dataset" if req.kind in ("dataset", "graph") else "Other"},
            "url": resolve_url,
            # the BEAT: provenance + epistemic status ride inside the standard metadata (FAIR+)
            "descriptions": [{"descriptionType": "Other",
                              "description": f"Proof-carrying record. epistemic_mode={prov['epistemic_mode']}; content_hash={h}; provenance={prov['extractor']}."}],
        },
    }
    return {"pid": pid, "doi": doi, "resolve": resolve_url, "content_hash": h, "created_at": created,
            "citation": citation, "bibtex": bibtex, "datacite": datacite, "proof_carrying": True, "node_id": node_id}


@app.get("/api/studio/resolve")
async def resolve(pid: str = "", _auth: dict[str, Any] | None = Depends(require_read)) -> dict[str, Any]:
    """Resolve a sovereign PID to its PROOF-CARRYING record — not a landing page. Reads the Citation fact back
    from the graph and returns the target + provenance + epistemic status + content hash, so the identifier
    resolves to something you can VERIFY (the beat over a DOI landing page)."""
    if not pid:
        raise HTTPException(status_code=422, detail="pid required")
    m = re.match(r"^[^:]+:([^/]+)/", pid)
    if not m:
        raise HTTPException(status_code=422, detail="malformed pid")
    coll = m.group(1)
    raw, err = await _fetch_raw_nodes(coll, 500)
    for n in raw:
        p = n.get("properties") or {}
        if "Citation" in (n.get("labels") or []) and p.get("pid") == pid:
            return {"pid": pid, "found": True, "doi": p.get("doi"), "kind": p.get("kind"), "target": p.get("target"),
                    "title": p.get("title"), "creators": _safe_json(p.get("creators_json")),
                    "created_at": p.get("created_at"), "content_hash": p.get("content_hash"),
                    "provenance": {"epistemic_mode": p.get("epistemic_mode"), "extractor": p.get("extractor"), "source": p.get("source")},
                    "proof_carrying": True}
    return {"pid": pid, "found": False, "degraded": err}


# ── WS#36: immutable preservation + versioning. A tamper-evident, content-addressed snapshot of a knowledge
# artifact, versioned in a chain (each links to its predecessor). Idempotent: re-preserving unchanged state
# returns the existing version. The snapshot carries the provenance chain — an archived fact stays proof-carrying. ──
class PreserveRequest(BaseModel):
    project: str = "default"
    target: str = ""        # "" = the whole-project graph; else a label/id to scope the snapshot
    note: str | None = None


def _state_hash(raw: list[dict[str, Any]], target: str) -> str:
    """A stable content hash over the CURRENT state of the target — the sorted (id, content_hash-of-props) of the
    nodes in scope. Deterministic, so identical state → identical hash (tamper-evidence + idempotent versioning)."""
    def in_scope(n: dict[str, Any]) -> bool:
        if not target:
            return "Snapshot" not in (n.get("labels") or [])   # don't hash prior snapshots into the state
        return target in (n.get("labels") or []) or n.get("id") == target
    parts = []
    for n in sorted((x for x in raw if in_scope(x)), key=lambda n: str(n.get("id", ""))):
        props = json.dumps(n.get("properties") or {}, sort_keys=True, default=str)
        parts.append(f"{n.get('id','')}={hashlib.sha256(props.encode()).hexdigest()[:16]}")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


@app.post("/api/studio/preserve")
async def preserve(req: PreserveRequest, authorization: str = Header(default="")) -> dict[str, Any]:
    """Seal an immutable, versioned snapshot of a knowledge artifact. MEET Zenodo/OSF versioning. BEAT: the
    snapshot is content-addressed + tamper-evident (re-hash to verify), chained to its predecessor, and carries
    the provenance chain (epistemic=attested) so an archived fact stays proof-carrying. Idempotent — preserving
    unchanged state returns the existing version, never a duplicate."""
    _require_write_token(authorization)
    coll = proj_collection(req.project)
    target = req.target or coll
    raw, err = await _fetch_raw_nodes(coll, 1000)
    if err:
        raise HTTPException(status_code=502, detail=f"graph read failed: {err}")
    content_hash = _state_hash(raw, req.target)
    snaps = [n for n in raw if "Snapshot" in (n.get("labels") or []) and (n.get("properties") or {}).get("target") == target]
    snaps.sort(key=lambda n: (n.get("properties") or {}).get("version", 0))
    # idempotent: unchanged state → return the existing head version
    if snaps and (snaps[-1].get("properties") or {}).get("content_hash") == content_hash:
        p = snaps[-1]["properties"]
        return {"snapshot_id": snaps[-1].get("id"), "version": p.get("version"), "content_hash": content_hash,
                "target": target, "sealed_at": p.get("sealed_at"), "unchanged": True, "proof_carrying": True}
    version = len(snaps) + 1
    parent = snaps[-1].get("id") if snaps else None
    sealed_at = _now_iso()
    snap_id = f"{coll}:snap:{content_hash[:12]}"
    prov = _workbench_prov(coll, "attested", "studio/preserve")
    prov["extractor"] = "studio/preserve-v0"
    props = {"target": target, "version": version, "content_hash": content_hash, "sealed_at": sealed_at,
             "parent": parent or "", "note": req.note or "", **prov}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        _, werr = await _req(client, "POST", f"{HELLGRAPH_URL}/api/graph/node",
                             json={"id": snap_id, "labels": [coll, "Snapshot", "Preservation"], "properties": props})
        if werr:
            raise HTTPException(status_code=502, detail=f"graph write failed: {werr}")
        if parent:  # chain to predecessor (version lineage)
            await _req(client, "POST", f"{HELLGRAPH_URL}/api/graph/edge",
                       json={"label": "supersedes", "from": snap_id, "to": parent, "properties": prov})
    return {"snapshot_id": snap_id, "version": version, "content_hash": content_hash, "target": target,
            "sealed_at": sealed_at, "parent": parent, "unchanged": False, "proof_carrying": True}


@app.get("/api/studio/versions")
async def versions(project: str = "default", target: str = "",
                   _auth: dict[str, Any] | None = Depends(require_read)) -> dict[str, Any]:
    """The version history of a preserved artifact — the immutable chain, newest first, each sealed with its
    content hash + timestamp. Verify integrity by re-hashing the state against a version's content_hash."""
    coll = proj_collection(project)
    tgt = target or coll
    raw, err = await _fetch_raw_nodes(coll, 1000)
    snaps = []
    for n in raw:
        if "Snapshot" not in (n.get("labels") or []):
            continue
        p = n.get("properties") or {}
        if p.get("target") != tgt:
            continue
        snaps.append({"snapshot_id": n.get("id"), "version": p.get("version"), "content_hash": p.get("content_hash"),
                      "sealed_at": p.get("sealed_at"), "parent": p.get("parent") or None, "note": p.get("note") or None,
                      "epistemic_mode": p.get("epistemic_mode", "attested")})
    snaps.sort(key=lambda s: s.get("version") or 0, reverse=True)
    return {"project": project, "target": tgt, "versions": snaps, "count": len(snaps), "degraded": err}


# ── WS#37: FAIR metadata + interoperability. Assembles a FAIR record (Findable/Accessible/Interoperable/
# Reusable) from the artifact's citation + preservation, emits schema.org/Dataset JSON-LD (Google Dataset
# Search) alongside DataCite + the PROV-O Turtle export, and scores FAIR. The BEAT is FAIR+: epistemic status
# and a verifiable provenance chain ride inside the metadata (nanopublication-style), which FAIR alone omits. ──
@app.get("/api/studio/fair")
async def fair(project: str = "default", target: str = "",
               _auth: dict[str, Any] | None = Depends(require_read)) -> dict[str, Any]:
    """FAIR metadata + self-assessment for a knowledge artifact. MEET Zenodo/OpenAIRE: schema.org/Dataset JSON-LD +
    DataCite + PROV-O Turtle + an F/A/I/R score. BEAT (FAIR+): epistemic status + a verifiable provenance chain
    ride inside the record — Interoperability is real (RDF/PROV-O export), not just 'a metadata blob exists'."""
    coll = proj_collection(project)
    tgt = target or coll
    raw, err = await _fetch_raw_nodes(coll, 1000)
    cite = next((n.get("properties") or {} for n in raw
                 if "Citation" in (n.get("labels") or []) and (n.get("properties") or {}).get("target") == tgt), {})
    snaps = [n.get("properties") or {} for n in raw
             if "Snapshot" in (n.get("labels") or []) and (n.get("properties") or {}).get("target") == tgt]
    snaps.sort(key=lambda p: p.get("version", 0))
    pid, doi = cite.get("pid"), cite.get("doi")
    title = cite.get("title") or f"{project} — knowledge graph"
    resolve = cite.get("resolve")
    version = snaps[-1].get("version") if snaps else None
    content_hash = (snaps[-1].get("content_hash") if snaps else None) or cite.get("content_hash")
    turtle_export = f"/api/studio/graph.ttl?project={project}"
    schema_org = {
        "@context": "https://schema.org/", "@type": "Dataset", "name": title,
        "identifier": doi or pid, "url": resolve,
        "creator": {"@type": "Organization", "name": "SocioProphet Knowledge Commons"},
        "distribution": {"@type": "DataDownload", "encodingFormat": "text/turtle", "contentUrl": turtle_export},
        "version": version, "sha256": content_hash,
        # FAIR+: provenance + epistemic status ride in the record
        "provenance": {"epistemic_status": cite.get("epistemic_mode", "observed"), "hashSealed": bool(content_hash)},
    }
    findable, accessible = bool(pid or doi), bool(resolve)
    interoperable = True                      # RDF/Turtle + PROV-O + schema.org always available
    reusable = bool(cite)                     # provenance present (+ license, implicit)
    score = round(sum([findable, accessible, interoperable, reusable]) / 4, 2)
    return {
        "project": project, "target": tgt, "title": title, "pid": pid, "doi": doi,
        "version": version, "content_hash": content_hash,
        "schema_org": schema_org, "datacite_doi": doi, "turtle_export": turtle_export,
        "fair": {"findable": findable, "accessible": accessible, "interoperable": interoperable, "reusable": reusable, "score": score},
        "fair_plus": {"epistemic": True, "provenance_chain": bool(snaps), "hash_sealed": bool(content_hash)},
        "hint": None if findable else "mint a persistent identifier (Cite) to make this Findable",
        "degraded": err,
    }


# ── WS#38: scholarly + agent ecosystem hooks. MEET Zenodo/OpenAIRE: ORCID contributor links, DOI resolution,
# an OpenAIRE/DataCite-harvestable metadata pointer. BEAT (agent-native): a machine-readable capability manifest
# so an AGENT — not just a human — can discover the proof-carrying record and consume it, each access verb flagged
# verifiable. Scholarly repos expose discovery to people; we expose it to autonomous agents. ────────────────────
@app.get("/api/studio/ecosystem")
async def ecosystem(project: str = "default", target: str = "",
                    _auth: dict[str, Any] | None = Depends(require_read)) -> dict[str, Any]:
    """Scholarly + agent ecosystem hooks for a knowledge artifact: ORCID contributors, DOI resolution, an
    OpenAIRE-harvestable pointer, and an agent-native capability manifest of verifiable access verbs."""
    coll = proj_collection(project)
    tgt = target or coll
    raw, err = await _fetch_raw_nodes(coll, 1000)
    cite = next((n.get("properties") or {} for n in raw
                 if "Citation" in (n.get("labels") or []) and (n.get("properties") or {}).get("target") == tgt), {})
    contributors: list[dict[str, Any]] = []
    seen: set[str] = set()
    for n in raw:                                   # harvest ORCID from any graph node that carries one
        p = n.get("properties") or {}
        orcid = p.get("orcid")
        if orcid and orcid not in seen:
            seen.add(orcid)
            contributors.append({"name": p.get("name") or p.get("label") or n.get("id"),
                                 "orcid": orcid, "orcid_url": f"https://orcid.org/{orcid}"})
    for c in (cite.get("contributors") or []):      # plus any the citation declared
        oc = c.get("orcid") if isinstance(c, dict) else None
        if oc and oc not in seen:
            seen.add(oc)
            contributors.append({"name": c.get("name"), "orcid": oc, "orcid_url": f"https://orcid.org/{oc}"})
    doi, pid = cite.get("doi"), cite.get("pid")
    scholarly = {
        "doi": doi, "doi_url": f"https://doi.org/{doi}" if doi else None,
        "orcid_contributors": contributors,
        "openaire": {"harvestable": bool(doi), "datacite_doi": doi,
                     "metadata": f"/api/studio/fair?project={project}&target={tgt}"},
    }

    def _verb(name: str, endpoint: str | None) -> dict[str, Any]:
        return {"name": name, "endpoint": endpoint, "verifiable": True}

    agent_manifest = {
        "@type": "AgentCapabilityManifest", "commons": "SocioProphet Knowledge Commons",
        "project": project, "identifier": pid or doi,
        "proof_carrying": True, "epistemic_status": True, "sovereign": True,
        "access": [
            _verb("resolve", f"/api/studio/resolve?pid={pid}" if pid else None),
            _verb("query", "/api/studio/query"),
            _verb("provenance", "/api/studio/provenance"),
            _verb("receipts", "/api/studio/receipts"),
            _verb("rdf", f"/api/studio/graph.ttl?project={project}"),
            _verb("fair", f"/api/studio/fair?project={project}&target={tgt}"),
        ],
        "consume_note": "every result carries a queryHash + epistemic status; verify via the receipts/provenance verbs",
    }
    return {"project": project, "target": tgt, "scholarly": scholarly,
            "agent_manifest": agent_manifest, "degraded": err}


# ── WS#39: commons at scale + community curation. MEET Zenodo/Wikidata: a commons overview (scale + community
# stats) and community endorsement of records. BEAT (epistemic curation): endorsements are governed, proof-
# carrying facts (identified endorser, revocable), and the curation score is EPISTEMIC-WEIGHTED — trust follows
# the epistemic status of the underlying facts (attested > verified > observed …), not raw popularity. ──────────
# epistemic ladder → curation weight (higher = more trustworthy grounding). Mirrors studioApi EPISTEMIC_ORDER.
EPISTEMIC_WEIGHT = {"attested": 1.0, "verified": 0.85, "observed": 0.6,
                    "derived": 0.45, "hypothesis": 0.25, "simulated": 0.1}


@app.get("/api/studio/commons")
async def commons(project: str = "default",
                  _auth: dict[str, Any] | None = Depends(require_read)) -> dict[str, Any]:
    """Commons-at-scale overview for a project: node/edge counts, the epistemic-status distribution, and the
    community signals (citations, preserved versions, endorsements, contributors). The scale + health story —
    every count is grounded in the graph, and the epistemic distribution is the quality signal repos lack."""
    coll = proj_collection(project)
    raw, err = await _fetch_raw_nodes(coll, 2000)
    epistemic: dict[str, int] = {}
    citations = versions = endorsements = 0
    contributors: set[str] = set()
    facts = 0
    for n in raw:
        labels = n.get("labels") or []
        p = n.get("properties") or {}
        if "Citation" in labels:
            citations += 1
        elif "Snapshot" in labels:
            versions += 1
        elif "Endorsement" in labels:
            endorsements += 1
        else:
            facts += 1
            mode = p.get("epistemic_mode")
            if mode:
                epistemic[mode] = epistemic.get(mode, 0) + 1
        if p.get("orcid"):
            contributors.add(p["orcid"])
    # a single epistemic-weighted quality index over the project's facts (0..1)
    graded = sum(EPISTEMIC_WEIGHT.get(m, 0.3) * c for m, c in epistemic.items())
    total_graded = sum(epistemic.values())
    quality_index = round(graded / total_graded, 3) if total_graded else None
    return {
        "project": project, "collection": coll,
        "scale": {"facts": facts, "citations": citations, "preserved_versions": versions,
                  "endorsements": endorsements, "contributors": len(contributors)},
        "epistemic_distribution": epistemic,
        "epistemic_quality_index": quality_index,   # the beat: quality, not just volume
        "degraded": err,
    }


class EndorseRequest(BaseModel):
    project: str = "default"
    target: str            # node id (or label) being endorsed
    endorser: str          # identified endorser (orcid / sovereign id / handle) — no anonymous curation
    note: str | None = None
    revoke: bool = False    # governed: an endorsement can be withdrawn


@app.post("/api/studio/endorse")
async def endorse(req: EndorseRequest, authorization: str = Header(default="")) -> dict[str, Any]:
    """Community curation: an identified endorser endorses (or revokes) a record. BEAT: the endorsement is a
    governed, proof-carrying graph fact — identified endorser, timestamped, revocable — not an anonymous vote.
    Idempotent per (target, endorser): re-endorsing updates; revoke marks it withdrawn."""
    _require_write_token(authorization)
    if not req.target.strip() or not req.endorser.strip():
        raise HTTPException(status_code=422, detail="target and endorser required")
    coll = proj_collection(req.project)
    endorser_key = hashlib.sha256(req.endorser.encode()).hexdigest()[:12]
    end_id = f"{coll}:endorse:{hashlib.sha256(req.target.encode()).hexdigest()[:8]}:{endorser_key}"
    prov = _workbench_prov(coll, "attested", "studio/endorse")
    prov["extractor"] = "lattice-studio/endorse-v0"
    props = {"target": req.target, "endorser": req.endorser, "note": req.note or "",
             "revoked": req.revoke, "at": _now_iso(), **prov}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        _, werr = await _req(client, "POST", f"{HELLGRAPH_URL}/api/graph/node",
                             json={"id": end_id, "labels": [coll, "Endorsement", "Curation"], "properties": props})
        if werr:
            raise HTTPException(status_code=502, detail=f"graph write failed: {werr}")
        if not req.revoke:      # link the endorsement to what it endorses (revoked ones stay as tombstones)
            await _req(client, "POST", f"{HELLGRAPH_URL}/api/graph/edge",
                       json={"label": "endorses", "from": end_id, "to": req.target, "properties": prov})
    return {"endorsement_id": end_id, "target": req.target, "endorser": req.endorser,
            "revoked": req.revoke, "proof_carrying": True}


@app.get("/api/studio/curation")
async def curation(project: str = "default", target: str = "",
                   _auth: dict[str, Any] | None = Depends(require_read)) -> dict[str, Any]:
    """The curation signals for a target: the identified, non-revoked endorsements and an epistemic-weighted
    curation score. BEAT: the score weights each endorsement by the epistemic status of the endorsed fact —
    an endorsement of an attested fact counts more than one of a hypothesis. Governance is read-enforced:
    revoked endorsements never contribute."""
    coll = proj_collection(project)
    raw, err = await _fetch_raw_nodes(coll, 2000)
    by_id = {n.get("id"): (n.get("properties") or {}) for n in raw}
    fact_mode = {nid: p.get("epistemic_mode") for nid, p in by_id.items()}
    endorsements = []
    seen: set[str] = set()
    for n in raw:
        if "Endorsement" not in (n.get("labels") or []):
            continue
        p = n.get("properties") or {}
        if target and p.get("target") != target:
            continue
        if p.get("revoked"):        # governance: withdrawn curation never counts
            continue
        key = f"{p.get('target')}|{p.get('endorser')}"
        if key in seen:
            continue
        seen.add(key)
        endorsements.append({"target": p.get("target"), "endorser": p.get("endorser"),
                             "note": p.get("note") or None, "at": p.get("at")})
    # epistemic-weighted curation score: each endorsement scaled by the grounding of the fact it endorses
    score = 0.0
    for e in endorsements:
        mode = fact_mode.get(e["target"]) or "observed"
        score += EPISTEMIC_WEIGHT.get(mode, 0.3)
    return {"project": project, "target": target or None, "endorsements": endorsements,
            "count": len(endorsements), "curation_score": round(score, 3),
            "epistemic_weighted": True, "degraded": err}


# ── WS#33: data connectors framework (governed ingest). MEET DS studios: connectors that pull structured data
# into the workspace. BEAT: ingest is GOVERNED — fail-closed write gate, per-row provenance, epistemic status,
# and a source connector id — so every ingested row lands as a proof-carrying fact, not an untracked blob. Inline
# CSV/JSON is fully live here; fetch-based connectors (http/s3/postgres) are declared + gated, not yet wired. ──
INGEST_ROW_CAP = 5000

CONNECTORS = [
    {"type": "csv", "status": "live", "governed": True, "note": "inline CSV → one proof-carrying node per row"},
    {"type": "json", "status": "live", "governed": True, "note": "inline JSON array of objects → node per element"},
    {"type": "http", "status": "declared", "governed": True, "note": "URL fetch — membrane-gated egress, not yet wired"},
    {"type": "s3", "status": "declared", "governed": True, "note": "object store — sovereign creds required, not yet wired"},
    {"type": "postgres", "status": "declared", "governed": True, "note": "SQL source — governed pull, not yet wired"},
]


@app.get("/api/studio/connectors")
async def connectors(_auth: dict[str, Any] | None = Depends(require_read)) -> dict[str, Any]:
    """The connector registry: supported source types and each one's governance posture. Every connector is
    governed (fail-closed writes + per-row provenance); inline csv/json are live, fetch-based ones are declared."""
    return {"connectors": CONNECTORS, "row_cap": INGEST_ROW_CAP,
            "governance": "fail-closed write token + per-row provenance + epistemic status on every ingested fact"}


class IngestRequest(BaseModel):
    project: str = "default"
    connector: str = "csv"          # csv | json (live); others rejected until wired
    data: str = ""                  # inline CSV text, or a JSON array-of-objects string
    key: str | None = None          # column/field to use as the node key (dedup); else row index
    label: str = "Record"           # graph label for ingested rows
    epistemic_mode: str = "observed"
    source: str | None = None


def _parse_rows(connector: str, data: str) -> list[dict[str, Any]]:
    """Parse inline CSV or JSON-array-of-objects into a list of flat row dicts. Deterministic + real — no
    external I/O. Raises HTTPException(422) on an unusable payload or an unsupported (declared-only) connector."""
    if connector == "csv":
        rows = list(csv.DictReader(io.StringIO(data)))
        if not rows:
            raise HTTPException(status_code=422, detail="csv payload has no data rows")
        return [dict(r) for r in rows]
    if connector == "json":
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=422, detail=f"invalid json: {e}") from e
        if not isinstance(parsed, list) or not all(isinstance(x, dict) for x in parsed):
            raise HTTPException(status_code=422, detail="json connector expects an array of objects")
        if not parsed:
            raise HTTPException(status_code=422, detail="json payload is empty")
        return parsed
    raise HTTPException(status_code=422, detail=f"connector '{connector}' is declared but not yet wired for ingest")


@app.post("/api/studio/ingest")
async def ingest(req: IngestRequest, authorization: str = Header(default="")) -> dict[str, Any]:
    """Governed ingest of inline structured data (csv/json) into the project graph. Each row becomes a proof-
    carrying node: per-row provenance (source connector + epistemic status), fail-closed write gate, row cap,
    dedup by the key column. The BEAT over a plain DS connector: every ingested fact is governed + attributable."""
    _require_write_token(authorization)
    rows = _parse_rows(req.connector, req.data)
    if len(rows) > INGEST_ROW_CAP:
        raise HTTPException(status_code=413, detail=f"ingest exceeds row cap ({len(rows)} > {INGEST_ROW_CAP})")
    coll = proj_collection(req.project)
    src = req.source or f"connector:{req.connector}:{hashlib.sha256(req.data.encode()).hexdigest()[:12]}"
    prov = _workbench_prov(coll, req.epistemic_mode, src)
    prov["extractor"] = f"lattice-studio/connector-{req.connector}-v0"
    prov["connector"] = req.connector

    written = 0
    errors: list[str] = []
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        calls = []
        for i, row in enumerate(rows):
            key_val = str(row.get(req.key)) if req.key and row.get(req.key) is not None else f"row{i}"
            nid = f"{coll}:ingest:{_norm(key_val).replace(' ', '_')}"
            props = {**{str(k): v for k, v in row.items()}, **prov, "ingest_key": key_val}
            calls.append(_req(client, "POST", f"{HELLGRAPH_URL}/api/graph/node",
                              json={"id": nid, "labels": [coll, req.label, "Ingested"], "properties": props}))
        for _, err in await asyncio.gather(*calls):
            if err:
                errors.append(err)
            else:
                written += 1
    return {"project": req.project, "connector": req.connector, "source": src,
            "rows": len(rows), "written": written, "label": req.label,
            "provenance": {"epistemic_mode": req.epistemic_mode, "connector": req.connector, "source": src},
            "errors": errors[:5] or None}


# ── WS#34: explorer UX parity+ — saved perspectives. MEET the studios: named, reusable explorer views (a saved
# label/epistemic filter + layout). BEAT: a perspective is a proof-carrying graph fact — it's shared to the agent
# team the moment it's saved (lives in the project collection), governed (fail-closed write), and can filter the
# explorer BY EPISTEMIC STATUS — the moat, made a first-class lens over the graph. ──────────────────────────────
class PerspectiveRequest(BaseModel):
    project: str = "default"
    name: str
    label: str | None = None            # graph label to focus (e.g. "Person")
    epistemic: list[str] | None = None  # epistemic modes to include (the beat: filter by grounding)
    limit: int = 300
    layout: str = "force"               # force | radial | hierarchy (explorer layout)
    note: str | None = None


@app.post("/api/studio/perspective")
async def save_perspective(req: PerspectiveRequest, authorization: str = Header(default="")) -> dict[str, Any]:
    """Save a named explorer perspective (label + epistemic filter + layout) as a proof-carrying graph fact —
    shared to the agent team on save, governed, and re-openable. Idempotent per (project, name)."""
    _require_write_token(authorization)
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="name required")
    coll = proj_collection(req.project)
    pid = f"{coll}:perspective:{_norm(name).replace(' ', '_')}"
    prov = _workbench_prov(coll, "attested", "studio/perspective")
    prov["extractor"] = "lattice-studio/perspective-v0"
    props = {"name": name, "label": req.label or "", "epistemic": json.dumps(req.epistemic or []),
             "limit": req.limit, "layout": req.layout, "note": req.note or "", "saved_at": _now_iso(), **prov}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        _, werr = await _req(client, "POST", f"{HELLGRAPH_URL}/api/graph/node",
                             json={"id": pid, "labels": [coll, "Perspective", "Curation"], "properties": props})
        if werr:
            raise HTTPException(status_code=502, detail=f"graph write failed: {werr}")
    return {"perspective_id": pid, "name": name, "shared_to_team": True, "proof_carrying": True}


@app.get("/api/studio/perspectives")
async def perspectives(project: str = "default",
                       _auth: dict[str, Any] | None = Depends(require_read)) -> dict[str, Any]:
    """The saved explorer perspectives for a project — each a proof-carrying, team-shared view with its label +
    epistemic filter + layout, ready to re-open in the graph explorer."""
    coll = proj_collection(project)
    raw, err = await _fetch_raw_nodes(coll, 1000)
    out = []
    for n in raw:
        if "Perspective" not in (n.get("labels") or []):
            continue
        p = n.get("properties") or {}
        try:
            epi = json.loads(p.get("epistemic") or "[]")
        except (ValueError, TypeError):
            epi = []
        out.append({"perspective_id": n.get("id"), "name": p.get("name"), "label": p.get("label") or None,
                    "epistemic": epi, "limit": p.get("limit", 300), "layout": p.get("layout", "force"),
                    "note": p.get("note") or None, "saved_at": p.get("saved_at")})
    out.sort(key=lambda x: x.get("saved_at") or "", reverse=True)
    return {"project": project, "perspectives": out, "count": len(out), "degraded": err}


# ── KE-1: the real extraction → HellGraph loop (proof-carrying, project-scoped) ──────────────────────────────────
# Deterministic entity + co-occurrence extraction (honest: not LLM). Every fact is written as a HellGraph atom with
# epistemic_mode="observed" + source provenance + the project label — the moat made real: not "entity X", but
# "entity X, observed, from source S, in project P, by extractor E". Neo4j stores the node; we store the node with
# its epistemic status and provenance, in one governed project scope.

# KE-1.1: stop-words (pronouns, determiners, conjunctions, common sentence-openers) that a capitalized-phrase
# extractor otherwise mistakes for entities. LEADING determiners are also stripped from phrases ("The Lattice
# Studio" → "Lattice Studio") so the entity is the noun, not the article.
_STOP = {
    "The", "This", "That", "These", "Those", "There", "Then", "When", "Where", "What", "Which", "While",
    "And", "But", "For", "With", "From", "Into", "It", "He", "She", "They", "We", "You", "I", "A", "An",
    "As", "At", "By", "Of", "On", "Or", "So", "To", "Its", "Our", "Their", "His", "Her", "Your", "My",
    "If", "In", "Is", "Are", "Was", "Were", "Be", "Has", "Have", "Had", "Not", "No", "Yes", "Also", "However",
}
_LEADING_DET = re.compile(r"^(The|This|That|These|Those|A|An|Its|Our|Their|His|Her|Your|My)\s+")
_PROPER = re.compile(r"\b([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)*)\b")
_ACRONYM = re.compile(r"\b([A-Z]{2,}[A-Za-z0-9]*)\b")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def extract_facts(text: str, limit: int = 60) -> tuple[list[str], list[tuple[str, str]]]:
    """Deterministic entities (proper-noun phrases + acronyms) + co-occurrence relations (same sentence)."""
    entities: list[str] = []
    seen: set[str] = set()
    sentences = re.split(r"(?<=[.!?])\s+", text)
    relations: list[tuple[str, str]] = []
    rel_seen: set[tuple[str, str]] = set()
    for sent in sentences:
        local: list[str] = []
        for m in (*_PROPER.finditer(sent), *_ACRONYM.finditer(sent)):
            name = _LEADING_DET.sub("", m.group(1).strip()).strip()  # strip leading determiner
            if not name or name in _STOP or len(name) < 2:
                continue
            key = _norm(name)
            if key not in seen and len(entities) < limit:
                seen.add(key); entities.append(name)
            if key not in {_norm(x) for x in local}:
                local.append(name)
        # co-occurrence edges within a sentence (undirected, deduped)
        for i in range(len(local)):
            for j in range(i + 1, len(local)):
                a, b = sorted((_norm(local[i]), _norm(local[j])))
                if (a, b) not in rel_seen:
                    rel_seen.add((a, b)); relations.append((local[i], local[j]))
    return entities, relations[: limit * 2]


def _require_write_token(authorization: str) -> None:
    """Shared WRITE gate for every endpoint that mutates the shared HellGraph (extract + the node/edge
    workbench). Fail-CLOSED: if STUDIO_WRITE_TOKEN is unset, writes are refused (reads stay open), so a
    public ingress can never accept anonymous graph writes. Token provisioned out-of-band (Secret)."""
    if not STUDIO_WRITE_TOKEN:
        raise HTTPException(status_code=503, detail="studio writes disabled: STUDIO_WRITE_TOKEN unset (fail-closed)")
    if authorization.removeprefix("Bearer ").strip() != STUDIO_WRITE_TOKEN:
        raise HTTPException(status_code=401, detail="invalid write token")


def _ent_id(coll: str, name: str) -> str:
    """Project-scoped entity id — must match /extract's scheme so a hand-authored node and an extracted one
    with the same name are the SAME node (the workbench edits the same graph, not a parallel one)."""
    return f"{coll}:ent:{_norm(name).replace(' ', '_')}"


class ExtractRequest(BaseModel):
    project: str = "default"
    text: str
    source: str | None = None


@app.post("/api/studio/extract")
async def extract(req: ExtractRequest, authorization: str = Header(default="")) -> dict[str, Any]:
    _require_write_token(authorization)
    coll = proj_collection(req.project)
    src = req.source or ("text:" + hashlib.sha256(req.text.encode()).hexdigest()[:16])
    entities, relations = extract_facts(req.text)
    ent_id = lambda name: _ent_id(coll, name)  # noqa: E731
    # KKO (KBpedia Knowledge Ontology) is the estate's UPPER ONTOLOGY. Extracted named entities are Peircean
    # Particulars (Secondness). epistemic_mode="observed" is itself Peircean (KKO formalizes the inference
    # trichotomy induced/deduced/abduced as kko:Methodeutic) — so the provenance is standards-grounded, not ad-hoc.
    prov = {"epistemic_mode": "observed", "source": src, "extractor": "lattice-studio/deterministic-v0",
            "project": coll, "kko_type": "Particulars"}

    written_nodes = written_edges = 0
    errors: list[str] = []
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # nodes first (concurrently), then edges (concurrently)
        node_calls = [
            _req(client, "POST", f"{HELLGRAPH_URL}/api/graph/node",
                 json={"id": ent_id(n), "labels": [coll, "Entity"], "properties": {"name": n, **prov}})
            for n in entities
        ]
        for _, err in await asyncio.gather(*node_calls):
            if err: errors.append(err)
            else: written_nodes += 1
        edge_calls = [
            _req(client, "POST", f"{HELLGRAPH_URL}/api/graph/edge",
                 json={"label": "co_occurs", "from": ent_id(a), "to": ent_id(b), "properties": prov})
            for a, b in relations
        ]
        for _, err in await asyncio.gather(*edge_calls):
            if err: errors.append(err)
            else: written_edges += 1

    return {
        "project": req.project, "projectCollection": coll, "source": src,
        "extracted": {"entities": len(entities), "relations": len(relations)},
        "written": {"nodes": written_nodes, "edges": written_edges},
        "provenance": prov,
        "sample": entities[:10],
        "errors": errors[:5] or None,
    }


class NodeRequest(BaseModel):
    project: str = "default"
    name: str
    labels: list[str] | None = None
    epistemic_mode: str = "observed"
    source: str | None = None


class EdgeRequest(BaseModel):
    project: str = "default"
    from_name: str
    to_name: str
    label: str = "relates_to"
    epistemic_mode: str = "observed"
    source: str | None = None


def _workbench_prov(coll: str, mode: str, source: str | None) -> dict[str, Any]:
    """Provenance for a HAND-AUTHORED fact — same shape /extract stamps, so a manual node is as proof-carrying
    as an extracted one. extractor marks it as workbench-authored; epistemic_mode is the user's assertion."""
    return {"epistemic_mode": mode, "source": source or "workbench",
            "extractor": "lattice-studio/workbench-v0", "project": coll, "kko_type": "Particulars"}


@app.post("/api/studio/node")
async def add_node(req: NodeRequest, authorization: str = Header(default="")) -> dict[str, Any]:
    """WRITE workbench: add ONE node to the project graph by hand. Same fail-closed token, project scope, and
    provenance as /extract — a hand-authored entity lands in the same graph, carrying its epistemic status."""
    _require_write_token(authorization)
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="name required")
    coll = proj_collection(req.project)
    nid = _ent_id(coll, name)
    prov = _workbench_prov(coll, req.epistemic_mode, req.source)
    # keep the project + Entity labels canonical; append any extra user labels (deduped)
    labels = [coll, "Entity"] + [l for l in (req.labels or []) if l not in (coll, "Entity")]
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        _, err = await _req(client, "POST", f"{HELLGRAPH_URL}/api/graph/node",
                            json={"id": nid, "labels": labels, "properties": {"name": name, **prov}})
    if err:
        raise HTTPException(status_code=502, detail=f"graph write failed: {err}")
    return {"id": nid, "name": name, "project": req.project, "projectCollection": coll,
            "labels": labels, "provenance": prov, "written": True}


@app.post("/api/studio/edge")
async def add_edge(req: EdgeRequest, authorization: str = Header(default="")) -> dict[str, Any]:
    """WRITE workbench: add ONE edge to the project graph by hand. Upserts both endpoints first (idempotent),
    so an edge between new names just works; then writes the relation. Same token/scope/provenance as /extract."""
    _require_write_token(authorization)
    a, b = req.from_name.strip(), req.to_name.strip()
    if not a or not b:
        raise HTTPException(status_code=422, detail="from_name and to_name required")
    coll = proj_collection(req.project)
    fid, tid = _ent_id(coll, a), _ent_id(coll, b)
    label = _norm(req.label).replace(" ", "_") or "relates_to"
    prov = _workbench_prov(coll, req.epistemic_mode, req.source)
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # endpoints first (idempotent upsert), then the edge — mirrors /extract's nodes-before-edges order.
        for nm, nid in ((a, fid), (b, tid)):
            _, err = await _req(client, "POST", f"{HELLGRAPH_URL}/api/graph/node",
                                json={"id": nid, "labels": [coll, "Entity"], "properties": {"name": nm, **prov}})
            if err:
                raise HTTPException(status_code=502, detail=f"graph write failed (node {nm}): {err}")
        _, err = await _req(client, "POST", f"{HELLGRAPH_URL}/api/graph/edge",
                            json={"label": label, "from": fid, "to": tid, "properties": prov})
    if err:
        raise HTTPException(status_code=502, detail=f"graph write failed (edge): {err}")
    return {"from": fid, "to": tid, "label": label, "project": req.project,
            "projectCollection": coll, "provenance": prov, "written": True}


def _map_node(n: Any) -> dict[str, Any]:
    props = n.get("properties", n) if isinstance(n, dict) else {}
    nid = n.get("id", "") if isinstance(n, dict) else str(n)
    return {
        "id": nid, "name": props.get("name", nid),
        "epistemic_mode": props.get("epistemic_mode", "unknown"),
        "source": props.get("source"), "extractor": props.get("extractor"),
        "kko_type": props.get("kko_type", "Particulars"),  # KKO upper-ontology type
        "labels": n.get("labels", []) if isinstance(n, dict) else [],
    }


async def _fetch_subgraph(coll: str, limit: int = 200) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str | None]:
    """Read the project's INDUCED SUBGRAPH (nodes + internal edges) from the live HellGraph kernel.

    The kernel returns an induced subgraph (edges only where both endpoints are in the node set), so the
    explorer draws real topology — not a chip-cloud — and every node still carries its provenance.
    """
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        res, err = await _req(client, "GET", f"{HELLGRAPH_URL}/api/graph/subgraph?label={coll}&limit={limit}")
    raw_nodes = res.get("nodes", []) if isinstance(res, dict) else []
    raw_edges = res.get("edgeList", []) if isinstance(res, dict) else []
    nodes = [_map_node(n) for n in (raw_nodes if isinstance(raw_nodes, list) else [])[:limit]]
    edges = [
        {"id": e.get("id", ""), "source": e.get("from", ""), "target": e.get("to", ""),
         "label": e.get("label", ""), "weight": (e.get("properties") or {}).get("n", 1)}
        for e in (raw_edges if isinstance(raw_edges, list) else [])
        if isinstance(e, dict) and e.get("from") and e.get("to")
    ]
    return nodes, edges, err


async def _fetch_nodes(coll: str, limit: int = 200) -> tuple[list[dict[str, Any]], str | None]:
    """Node-only read (RDF export path) — delegates to the subgraph fetch and drops edges."""
    nodes, _edges, err = await _fetch_subgraph(coll, limit)
    return nodes, err


@app.get("/api/studio/graph")
async def graph(project: str = "default", limit: int = 100, _auth: dict[str, Any] | None = Depends(require_read)) -> dict[str, Any]:
    """KE-2: the project sub-graph with PROVENANCE PER NODE — the differentiator, read from the live kernel.

    Not just the node, but its epistemic status + source + extractor, in one governed project scope — what a
    Neo4j/Bloom explorer can't show natively.
    """
    coll = proj_collection(project)
    nodes, edges, err = await _fetch_subgraph(coll, limit)
    dist: dict[str, int] = {}
    for x in nodes:
        dist[x["epistemic_mode"]] = dist.get(x["epistemic_mode"], 0) + 1
    return {"project": project, "projectCollection": coll, "nodes": nodes, "edges": edges,
            "count": len(nodes), "edge_count": len(edges),
            "epistemic_distribution": dist, "degraded": (err if err else None)}


def _derivation_summary(node: dict[str, Any], derivations: list[dict[str, Any]]) -> str:
    """One human sentence: how this fact came to be known — its epistemic status, who/what produced it, and how
    many other facts it's connected to. The 'How derived?' answer a Bloom/Stardog node inspector can't give."""
    mode = node.get("epistemic_mode", "unknown")
    by = node.get("extractor") or "an unknown process"
    src = node.get("source")
    origin = f" from {src}" if src else ""
    n = len(derivations)
    rel = "no other facts yet" if n == 0 else f"{n} related fact{'s' if n != 1 else ''}"
    return f"‘{node.get('name', node['id'])}’ is held as {mode}, produced by {by}{origin}, and connected to {rel}."


@app.get("/api/studio/provenance")
async def provenance(project: str = "default", id: str = "", _auth: dict[str, Any] | None = Depends(require_read)) -> dict[str, Any]:
    """KE-5: 'How derived?' — the derivation of ONE fact. Its provenance (epistemic status + source + extractor +
    KKO upper-ontology type) plus the edges that connect it (what it was co-observed / reasoned with), read from
    the live project subgraph. This is the proof-carrying lineage a Neo4j Bloom / Stardog node inspector can't
    show: not just properties, but where the fact came from and how well it's known."""
    if not id:
        raise HTTPException(status_code=422, detail="id required")
    coll = proj_collection(project)
    nodes, edges, err = await _fetch_subgraph(coll, 500)
    node = next((n for n in nodes if n["id"] == id), None)
    if node is None:
        return {"id": id, "project": project, "projectCollection": coll, "found": False, "degraded": err}
    by_id = {n["id"]: n for n in nodes}
    derivations = []
    for e in edges:
        if e["source"] != id and e["target"] != id:
            continue
        out = e["source"] == id
        other = by_id.get(e["target"] if out else e["source"], {})
        derivations.append({
            "relation": e["label"], "direction": "out" if out else "in",
            "with": {"id": other.get("id", ""), "name": other.get("name", ""),
                     "epistemic_mode": other.get("epistemic_mode", "unknown"), "source": other.get("source")},
            "weight": e.get("weight", 1),
        })
    derivations.sort(key=lambda d: d["weight"], reverse=True)
    return {
        "id": id, "project": project, "projectCollection": coll, "found": True, "name": node["name"],
        "epistemic_mode": node["epistemic_mode"], "source": node.get("source"),
        "extractor": node.get("extractor"), "kko_type": node.get("kko_type", "Particulars"),
        "labels": node.get("labels", []),
        "derivations": derivations, "derivation_count": len(derivations),
        "summary": _derivation_summary(node, derivations),
        "degraded": err,
    }


@app.get("/api/studio/graph.ttl")
async def graph_ttl(project: str = "default", limit: int = 500, _auth: dict[str, Any] | None = Depends(require_read)) -> Response:
    """KE-3: RDF/Turtle export — standards interop (Protégé / GraphDB / Anzo / Stardog) that CARRIES provenance.

    Every node exports as a PROV-O-annotated resource: rdf:type sp:Entity, rdfs:label, sp:epistemicMode,
    dct:source, prov:wasGeneratedBy. Their RDF exports drop provenance; ours doesn't — epistemic status + origin
    ride the standard triples, so a proof-carrying graph stays proof-carrying when it leaves us.
    """
    from rdflib import Graph as RDFGraph, Literal, Namespace, URIRef
    from rdflib.namespace import DCTERMS, PROV, RDF, RDFS

    coll = proj_collection(project)
    nodes, edges, _ = await _fetch_subgraph(coll, limit)   # nodes AND edges — the reasoner needs relations
    g = RDFGraph()
    # KKO (KBpedia Knowledge Ontology) is the estate's upper ontology — the export types INTO it, so the graph
    # is grounded in a formal, open (CC-BY-4.0), Peircean upper ontology that Protégé/GraphDB/Anzo/Stardog already
    # understand. Meet them on standards (KKO/RDF/PROV) AND carry the provenance moat they drop on export.
    KKO = Namespace("http://kbpedia.org/ontologies/kko#")
    SP = Namespace("https://socioprophet.ai/kg#")
    PROJ = Namespace(f"https://socioprophet.ai/kg/{coll}/")
    g.bind("kko", KKO); g.bind("sp", SP); g.bind("proj", PROJ); g.bind("prov", PROV); g.bind("dct", DCTERMS)

    def _local(node_id: str) -> URIRef:
        return PROJ[(node_id.split(":")[-1] or "node")]

    for n in nodes:
        u = _local(n["id"])
        g.add((u, RDF.type, KKO[n.get("kko_type", "Particulars")]))  # KKO upper-ontology type (Peircean)
        g.add((u, RDFS.label, Literal(n["name"])))
        # epistemic_mode is a Peircean inference status (KKO kko:Methodeutic) — provenance grounded in the standard.
        g.add((u, SP.epistemicMode, Literal(n["epistemic_mode"])))
        if n.get("source"): g.add((u, DCTERMS.source, Literal(n["source"])))
        # PROV-O: wasGeneratedBy must reference a prov:Activity RESOURCE, not a bare literal.
        if n.get("extractor"):
            act = SP[f"activity/{str(n['extractor']).replace(' ', '_')}"]
            g.add((act, RDF.type, PROV.Activity))
            g.add((u, PROV.wasGeneratedBy, act))
    # Edges — WITHOUT these the exported graph is a bag of typed nodes with NO relations, and a reasoner
    # pulling graph.ttl has nothing to reason over. Each edge becomes a real predicate triple; the label
    # (e.g. co_occurs) is minted under the sp: vocabulary so it is a dereferenceable property.
    for e in edges:
        src, tgt, label = e.get("source"), e.get("target"), e.get("label") or "relatedTo"
        if not src or not tgt:
            continue
        g.add((_local(src), SP[str(label)], _local(tgt)))
    return Response(content=g.serialize(format="turtle"), media_type="text/turtle")
