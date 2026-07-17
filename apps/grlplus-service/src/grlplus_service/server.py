"""GRLPlus service — the live, graph-integrated policy evaluator.

Makes GRLPlus a real service: it evaluates semantic-worklist items' closure/escalation rules against
the proof-carrying HellGraph (via the SPARQL surface on hellgraph-service), instead of the standards
repo's export shim which only copies rule codes. GRLPlus becomes the symbolic *shield* over the same
graph the Graph-RL loop learns on — argument/evidence coverage and divergence are checked as real
graph facts, and every decision carries the atoms it consulted (proof-carrying governance).

Endpoints:
  GET  /healthz
  GET  /grlplus/rules             the closure + escalation rule catalog this evaluator implements
  POST /grlplus/evaluate          { items: [...], project? } → per-item close/keep-open/escalate + evidence
"""
from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

from .evaluator import (
    CLOSURE_RULES, ESCALATION_RULES, DIVERGENCE_WARNING,
    GraphEvidence, decide,
)

HELLGRAPH_URL = os.getenv("HELLGRAPH_URL", "http://hellgraph-service:8090")
TIMEOUT = float(os.getenv("GRLPLUS_TIMEOUT", "5.0"))

app = FastAPI(title="grlplus-service", version="0.1.0")

# Edge-predicate → evidence-type. Generous, case-insensitive substring match, so the evaluator works
# across the graph's relation vocabularies without a brittle exact-label contract.
_ARG = ("argue", "argument", "support", "justif")
_EVID = ("evidence", "grounds", "cites", "attest", "proves", "provenance")
_TELE = ("telemetry", "metric", "monitor", "measure", "control")
_SKIP_PRED = {"rdf:type", "name", "epistemic_mode", "source", "extractor", "kko_type", "label"}


class EvaluateRequest(BaseModel):
    items: list[dict[str, Any]]
    project: str | None = None


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {"ok": True, "service": "grlplus-service", "hellgraph": HELLGRAPH_URL}


@app.get("/grlplus/rules")
def rules() -> dict[str, Any]:
    return {"closure": CLOSURE_RULES, "escalation": ESCALATION_RULES, "divergence_warning": DIVERGENCE_WARNING}


async def _fetch_triples() -> tuple[list[dict[str, Any]], str | None]:
    """Pull the graph's triples from hellgraph-service's SPARQL surface. Degrades (empty) if unreachable."""
    q = "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 5000"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.post(f"{HELLGRAPH_URL}/api/graph/sparql", json={"query": q})
            r.raise_for_status()
            data = r.json()
        return data.get("bindings", []) if isinstance(data, dict) else [], None
    except Exception as e:  # noqa: BLE001 — fail-open: governance degrades, never crashes
        return [], str(e)


def gather_evidence(element_id: str, triples: list[dict[str, Any]]) -> GraphEvidence:
    """Count an element's incident graph edges into evidence buckets (skipping type/property triples)."""
    ev = GraphEvidence()
    for t in triples:
        s, p, o = t.get("s"), t.get("p"), t.get("o")
        if s != element_id and o != element_id:
            continue
        pl = (p or "").lower()
        if not pl or pl in _SKIP_PRED:
            continue
        ev.found = True
        ev.atom_ids.append(f"{s} -{p}-> {o}")
        if any(k in pl for k in _ARG):
            ev.direct_arguments += 1
        elif any(k in pl for k in _EVID):
            ev.evidence_links += 1
        elif any(k in pl for k in _TELE):
            ev.telemetry_artifacts += 1
        elif "approv" in pl:
            ev.owner_approved = True
    ev.atom_ids = ev.atom_ids[:20]
    return ev


@app.post("/grlplus/evaluate")
async def evaluate(req: EvaluateRequest) -> dict[str, Any]:
    """Evaluate each worklist item's closure/escalation against the live graph. The GRLPlus engine."""
    triples, err = await _fetch_triples()
    results: list[dict[str, Any]] = []
    for item in req.items:
        ev = gather_evidence(item.get("element_id", ""), triples)
        d = decide(item, ev)
        results.append({
            "element_id": d.element_id,
            "decision": d.decision,
            "escalate": d.escalate,
            "grounded": d.grounded,  # was there a real graph node backing the check?
            "closure": {
                "rule": d.closure.rule, "satisfied": d.closure.satisfied,
                "needed": d.closure.needed, "observed": d.closure.observed, "reason": d.closure.reason,
            },
            "escalation": {"rule": d.escalation_rule, "reason": d.escalation_reason},
            "evidence": {
                "direct_arguments": ev.direct_arguments, "evidence_links": ev.evidence_links,
                "telemetry_artifacts": ev.telemetry_artifacts, "owner_approved": ev.owner_approved,
            },
            "atoms": d.atom_ids,  # provenance: the edges the decision consulted
        })
    closable = sum(1 for r in results if r["decision"] == "close")
    return {
        "project": req.project,
        "evaluated": len(results),
        "closable": closable,
        "escalations": sum(1 for r in results if r["escalate"]),
        "graph_degraded": err,  # non-null → decisions were made without graph evidence (fail-safe = keep open)
        "results": results,
    }
