"""owl-reasoner service — RDFS/OWL-RL reasoning + SHACL validation over the estate's graph.

Bridges Ontogenesis-class inference (rdflib/pyshacl/owlrl) onto HellGraph: reason over raw Turtle, or
pull a project's KKO-typed graph straight from lattice-studio's /api/studio/graph.ttl and entail over
it. Protégé/Stardog parity — proof-carrying (entailments are derivations, not assertions).

  GET  /healthz
  POST /reason            { turtle, shapes?, inference? } → entailments (+ SHACL report)
  POST /reason/project?project=&inference=   pull the project graph.ttl → reason
"""
from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

from .ontology_graph import tbox_graph
from .reasoner import reason

LATTICE_STUDIO_URL = os.getenv("LATTICE_STUDIO_URL", "http://lattice-studio:8080")
TIMEOUT = float(os.getenv("OWL_TIMEOUT", "8"))

app = FastAPI(title="owl-reasoner", version="0.1.0")


class ReasonRequest(BaseModel):
    turtle: str
    shapes: str | None = None
    inference: str = "rdfs"


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {"ok": True, "service": "owl-reasoner"}


@app.post("/reason")
def reason_endpoint(req: ReasonRequest) -> dict[str, Any]:
    return reason(req.turtle, req.shapes, req.inference)


@app.post("/reason/project")
async def reason_project(project: str = "default", inference: str = "rdfs") -> dict[str, Any]:
    """Pull the project's KKO-typed graph (lattice-studio graph.ttl) and compute its entailments."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(f"{LATTICE_STUDIO_URL}/api/studio/graph.ttl", params={"project": project})
            r.raise_for_status()
            ttl = r.text
    except Exception as e:  # noqa: BLE001 — degrade honestly, never crash
        return {"project": project, "error": f"graph pull failed: {e}", "entailed_triples": 0, "entailments": []}
    out = reason(ttl, None, inference)
    out["project"] = project
    return out


class OntologyGraphRequest(BaseModel):
    turtle: str
    limit: int = 1000


@app.post("/ontology/graph")
def ontology_graph_endpoint(req: OntologyGraphRequest) -> dict[str, Any]:
    """TBox → renderable graph (classes + subClassOf + object-property edges) — WebVOWL-style ontology viz."""
    return tbox_graph(req.turtle, req.limit)
