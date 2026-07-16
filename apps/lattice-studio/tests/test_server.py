"""Studio BFF smoke: healthz + the studio bundle (live fabric services unreachable in test → graceful degrade)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from lattice_studio.server import app, proj_collection

client = TestClient(app)


def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json()["ok"] is True


def test_project_collection_matches_noetica():
    # Noetica projectCollectionId: proj-<12 hex, dashes stripped>
    assert proj_collection("a1b2-c3d4-e5f6-7890") == "proj-a1b2c3d4e5f6"


def test_studio_bundle_project_scoped_and_complete():
    r = client.get("/api/studio?project=my-proj-42")
    assert r.status_code == 200
    b = r.json()
    assert b["project"] == "my-proj-42"
    assert b["projectCollection"] == "proj-myproj42"
    # all ten sections present (workbench + knowledge engineering)
    for s in ["notebooks", "data", "models", "experiments", "extraction", "ontology", "graph", "retrieval", "generation"]:
        assert s in b and isinstance(b[s], list)
    # graceful degrade: live flags exist; services unreachable in test → False, response still 200
    assert set(b["live"]) == {"hellgraph", "tritfabric", "search_orchestrator"}
    # retrieval names the real engines
    engines = {r["engine"] for r in b["retrieval"]}
    assert {"fibered-retrieval", "hellgraph", "slash-topics"} <= engines


def test_extract_facts_deterministic():
    from lattice_studio.server import extract_facts
    ents, rels = extract_facts("HellGraph powers SocioProphet. Neo4j and Anzo compete with SocioProphet.")
    names = {e.lower() for e in ents}
    assert "hellgraph" in names and "socioprophet" in names and "neo4j" in names and "anzo" in names
    # co-occurrence within a sentence produces a relation (Neo4j ↔ Anzo, Neo4j ↔ SocioProphet)
    assert len(rels) >= 1


def test_extract_endpoint_writes_proof_carrying_facts():
    # hellgraph unreachable in test → written=0 but extraction + provenance still returned (graceful)
    r = client.post("/api/studio/extract", json={"project": "team-x", "text": "HellGraph beats Neo4j on provenance."})
    assert r.status_code == 200
    b = r.json()
    assert b["projectCollection"] == "proj-teamx"
    assert b["extracted"]["entities"] >= 2
    # the moat: every fact carries epistemic_mode + source + project
    assert b["provenance"]["epistemic_mode"] == "observed"
    assert b["provenance"]["project"] == "proj-teamx"
    assert b["provenance"]["extractor"].startswith("lattice-studio/")
