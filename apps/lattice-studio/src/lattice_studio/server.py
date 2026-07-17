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
import hashlib
import os
import re
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
        (gstats, gerr), (reg, rerr), (sher, serr) = await asyncio.gather(
            _req(client, "GET", f"{HELLGRAPH_URL}/api/graph/stats"),
            _req(client, "GET", f"{TRITFABRIC_URL}/v1/registry"),
            _req(client, "POST", f"{SEARCH_ORCH_URL}/v0/search/query", json=_sherlock_request(project)),
        )
    degraded = {k: v for k, v in {"graph": gerr, "models": rerr, "extraction": serr}.items() if v}

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
        "notebooks": notebooks, "data": data, "models": models, "tuning": [], "experiments": experiments,
        "extraction": extraction, "ontology": ontology, "graph": graph, "retrieval": retrieval, "generation": generation,
        "live": {"hellgraph": gstats is not None, "tritfabric": reg is not None, "search_orchestrator": sher is not None},
        "degraded": (degraded or None),
    }


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
