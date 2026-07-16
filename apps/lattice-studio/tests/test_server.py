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


def test_extract_filters_pronouns_and_strips_articles():
    from lattice_studio.server import extract_facts
    ents, _ = extract_facts("It powers The Lattice Studio. They compete with Neo4j.")
    names = {e.lower() for e in ents}
    assert "it" not in names and "they" not in names          # pronouns filtered
    assert "the lattice studio" not in names                   # leading article stripped
    assert "lattice studio" in names and "neo4j" in names      # real entities kept


def test_graph_endpoint_returns_provenance_shape():
    # hellgraph unreachable in test → graceful empty, but the KE-2 shape (provenance + epistemic distribution) holds
    r = client.get("/api/studio/graph?project=team-x")
    assert r.status_code == 200
    b = r.json()
    assert b["projectCollection"] == "proj-teamx"
    # nodes AND edges (topology for the force-directed explorer) + provenance distribution
    assert "nodes" in b and "count" in b and "epistemic_distribution" in b
    assert "edges" in b and "edge_count" in b and isinstance(b["edges"], list)


def test_subgraph_maps_induced_edges(monkeypatch):
    # the BFF must map the kernel's induced-subgraph edgeList (from/to) → explorer edges (source/target)
    import lattice_studio.server as srv

    async def fake_req(client, method, url, json=None):
        if "subgraph" in url:
            return ({
                "nodes": [
                    {"id": "proj-teamx:ent:a", "labels": ["proj-teamx", "Entity"],
                     "properties": {"name": "A", "epistemic_mode": "observed", "kko_type": "Particulars"}},
                    {"id": "proj-teamx:ent:b", "labels": ["proj-teamx", "Entity"],
                     "properties": {"name": "B", "epistemic_mode": "observed"}},
                ],
                "edgeList": [
                    {"id": "h:1", "label": "CO_OCCURS", "from": "proj-teamx:ent:a",
                     "to": "proj-teamx:ent:b", "properties": {"n": 3}},
                ],
            }, None)
        return (None, "unreachable")
    monkeypatch.setattr(srv, "_req", fake_req)

    r = client.get("/api/studio/graph?project=team-x")
    assert r.status_code == 200
    b = r.json()
    assert b["count"] == 2 and b["edge_count"] == 1
    e = b["edges"][0]
    assert e["source"] == "proj-teamx:ent:a" and e["target"] == "proj-teamx:ent:b"
    assert e["label"] == "CO_OCCURS" and e["weight"] == 3


def test_rdf_export_carries_provenance(monkeypatch):
    # KE-3: the RDF/Turtle export must carry epistemic_mode + provenance as standard triples (PROV-O / DCT).
    import lattice_studio.server as srv

    async def fake_nodes(coll, limit=200):
        return [{"id": f"{coll}:ent:hellgraph", "name": "HellGraph", "epistemic_mode": "observed",
                 "source": "doc:kg", "extractor": "lattice-studio/deterministic-v0",
                 "kko_type": "Particulars", "labels": [coll, "Entity"]}], None
    monkeypatch.setattr(srv, "_fetch_nodes", fake_nodes)

    r = client.get("/api/studio/graph.ttl?project=team-x")
    assert r.status_code == 200
    assert "text/turtle" in r.headers["content-type"]
    ttl = r.text
    # KKO upper ontology: the node types INTO KKO (Peircean Particulars) — standards-grounded, not ad-hoc
    assert "kko:" in ttl and "kko:Particulars" in ttl
    assert "http://kbpedia.org/ontologies/kko#" in ttl
    # provenance survives export: epistemic mode + source + generator ride the RDF (the moat, on export)
    assert "sp:epistemicMode" in ttl and '"observed"' in ttl
    assert "dct:source" in ttl and "prov:wasGeneratedBy" in ttl
    assert 'rdfs:label "HellGraph"' in ttl
    # and it's valid Turtle a semantic-web tool can parse
    from rdflib import Graph as RDFGraph
    assert len(RDFGraph().parse(data=ttl, format="turtle")) >= 4
