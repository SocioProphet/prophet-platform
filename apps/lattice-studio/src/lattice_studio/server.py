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
from fastapi import FastAPI
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

_STOP = {"The", "This", "That", "These", "Those", "There", "Then", "When", "Where", "What", "Which", "While", "And", "But", "For", "With", "From", "Into"}
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
            name = m.group(1).strip()
            if name in _STOP or len(name) < 2:
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
    prov = {"epistemic_mode": "observed", "source": src, "extractor": "lattice-studio/deterministic-v0", "project": coll}

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
