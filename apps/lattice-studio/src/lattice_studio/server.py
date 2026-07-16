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
from fastapi import FastAPI, Response
from pydantic import BaseModel

from lattice_studio import product_spine

SERVICE_VERSION = "0.2.0"
HELLGRAPH_URL = os.getenv("HELLGRAPH_URL", "http://hellgraph-service:8090")
TRITFABRIC_URL = os.getenv("TRITFABRIC_URL", "http://tritfabric:8750")
SEARCH_ORCH_URL = os.getenv("SEARCH_ORCH_URL", "http://search-orchestrator:8080")
TIMEOUT = float(os.getenv("STUDIO_TIMEOUT", "5"))

app = FastAPI(title="Lattice Studio BFF", version=SERVICE_VERSION)


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
async def studio(project: str = "default") -> dict[str, Any]:
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


class ExtractRequest(BaseModel):
    project: str = "default"
    text: str
    source: str | None = None


@app.post("/api/studio/extract")
async def extract(req: ExtractRequest) -> dict[str, Any]:
    coll = proj_collection(req.project)
    src = req.source or ("text:" + hashlib.sha256(req.text.encode()).hexdigest()[:16])
    entities, relations = extract_facts(req.text)
    ent_id = lambda name: f"{coll}:ent:{_norm(name).replace(' ', '_')}"  # noqa: E731
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


async def _fetch_nodes(coll: str, limit: int = 200) -> tuple[list[dict[str, Any]], str | None]:
    """Read the project's atoms (by collection label) from the live HellGraph, each with its provenance."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        res, err = await _req(client, "GET", f"{HELLGRAPH_URL}/api/graph/query?label={coll}")
    raw = (res.get("nodes", res) if isinstance(res, dict) else res) if res else []
    nodes: list[dict[str, Any]] = []
    for n in (raw if isinstance(raw, list) else [])[:limit]:
        props = n.get("properties", n) if isinstance(n, dict) else {}
        nid = n.get("id", "") if isinstance(n, dict) else str(n)
        nodes.append({
            "id": nid, "name": props.get("name", nid),
            "epistemic_mode": props.get("epistemic_mode", "unknown"),
            "source": props.get("source"), "extractor": props.get("extractor"),
            "kko_type": props.get("kko_type", "Particulars"),  # KKO upper-ontology type
            "labels": n.get("labels", []) if isinstance(n, dict) else [],
        })
    return nodes, err


@app.get("/api/studio/graph")
async def graph(project: str = "default", limit: int = 100) -> dict[str, Any]:
    """KE-2: the project sub-graph with PROVENANCE PER NODE — the differentiator, read from the live kernel.

    Not just the node, but its epistemic status + source + extractor, in one governed project scope — what a
    Neo4j/Bloom explorer can't show natively.
    """
    coll = proj_collection(project)
    nodes, err = await _fetch_nodes(coll, limit)
    dist: dict[str, int] = {}
    for x in nodes:
        dist[x["epistemic_mode"]] = dist.get(x["epistemic_mode"], 0) + 1
    return {"project": project, "projectCollection": coll, "nodes": nodes, "count": len(nodes),
            "epistemic_distribution": dist, "degraded": (err if err else None)}


@app.get("/api/studio/graph.ttl")
async def graph_ttl(project: str = "default", limit: int = 500) -> Response:
    """KE-3: RDF/Turtle export — standards interop (Protégé / GraphDB / Anzo / Stardog) that CARRIES provenance.

    Every node exports as a PROV-O-annotated resource: rdf:type sp:Entity, rdfs:label, sp:epistemicMode,
    dct:source, prov:wasGeneratedBy. Their RDF exports drop provenance; ours doesn't — epistemic status + origin
    ride the standard triples, so a proof-carrying graph stays proof-carrying when it leaves us.
    """
    from rdflib import Graph as RDFGraph, Literal, Namespace
    from rdflib.namespace import DCTERMS, PROV, RDF, RDFS

    coll = proj_collection(project)
    nodes, _ = await _fetch_nodes(coll, limit)
    g = RDFGraph()
    # KKO (KBpedia Knowledge Ontology) is the estate's upper ontology — the export types INTO it, so the graph
    # is grounded in a formal, open (CC-BY-4.0), Peircean upper ontology that Protégé/GraphDB/Anzo/Stardog already
    # understand. Meet them on standards (KKO/RDF/PROV) AND carry the provenance moat they drop on export.
    KKO = Namespace("http://kbpedia.org/ontologies/kko#")
    SP = Namespace("https://socioprophet.ai/kg#")
    PROJ = Namespace(f"https://socioprophet.ai/kg/{coll}/")
    g.bind("kko", KKO); g.bind("sp", SP); g.bind("proj", PROJ); g.bind("prov", PROV); g.bind("dct", DCTERMS)
    for n in nodes:
        u = PROJ[(n["id"].split(":")[-1] or "node")]
        g.add((u, RDF.type, KKO[n.get("kko_type", "Particulars")]))  # KKO upper-ontology type (Peircean)
        g.add((u, RDFS.label, Literal(n["name"])))
        # epistemic_mode is a Peircean inference status (KKO kko:Methodeutic) — provenance grounded in the standard.
        g.add((u, SP.epistemicMode, Literal(n["epistemic_mode"])))
        if n.get("source"): g.add((u, DCTERMS.source, Literal(n["source"])))
        if n.get("extractor"): g.add((u, PROV.wasGeneratedBy, Literal(n["extractor"])))
    return Response(content=g.serialize(format="turtle"), media_type="text/turtle")
