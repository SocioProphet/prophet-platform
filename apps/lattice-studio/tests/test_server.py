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
    assert set(b["live"]) == {"hellgraph", "tritfabric", "search_orchestrator", "evidence"}
    # the MOAT header rides above every section
    assert "moat" in b and set(b["moat"]) >= {"epistemic_distribution", "provenance_coverage", "verified_compute", "governed_writes"}
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


def test_extract_write_gate(monkeypatch):
    # fail-closed: no token configured → writes refused (503), never anonymous graph writes
    r = client.post("/api/studio/extract", json={"project": "team-x", "text": "HellGraph beats Neo4j."})
    assert r.status_code == 503
    # token configured but wrong bearer → 401
    monkeypatch.setattr("lattice_studio.server.STUDIO_WRITE_TOKEN", "secret")
    r = client.post("/api/studio/extract", json={"project": "team-x", "text": "x"}, headers={"authorization": "Bearer nope"})
    assert r.status_code == 401


def test_extract_endpoint_writes_proof_carrying_facts(monkeypatch):
    # hellgraph unreachable in test → written=0 but extraction + provenance still returned (graceful)
    monkeypatch.setattr("lattice_studio.server.STUDIO_WRITE_TOKEN", "secret")
    r = client.post("/api/studio/extract", json={"project": "team-x", "text": "HellGraph beats Neo4j on provenance."},
                    headers={"authorization": "Bearer secret"})
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


def test_rdf_export_carries_provenance_AND_edges(monkeypatch):
    # KE-3: the RDF/Turtle export must carry epistemic_mode + provenance AND the RELATIONS (edges) — without
    # edges the exported graph is a bag of typed nodes a reasoner can't reason over (the compounding bug).
    import lattice_studio.server as srv

    async def fake_subgraph(coll, limit=200):
        nodes = [
            {"id": f"{coll}:ent:hellgraph", "name": "HellGraph", "epistemic_mode": "observed",
             "source": "doc:kg", "extractor": "lattice-studio/deterministic-v0", "kko_type": "Particulars"},
            {"id": f"{coll}:ent:atomspace", "name": "AtomSpace", "epistemic_mode": "observed", "kko_type": "Particulars"},
        ]
        edges = [{"id": "e1", "source": f"{coll}:ent:hellgraph", "target": f"{coll}:ent:atomspace",
                  "label": "co_occurs", "weight": 3}]
        return nodes, edges, None
    monkeypatch.setattr(srv, "_fetch_subgraph", fake_subgraph)

    r = client.get("/api/studio/graph.ttl?project=team-x")
    assert r.status_code == 200 and "text/turtle" in r.headers["content-type"]
    ttl = r.text
    assert "kko:Particulars" in ttl and "http://kbpedia.org/ontologies/kko#" in ttl
    assert "sp:epistemicMode" in ttl and '"observed"' in ttl
    assert "dct:source" in ttl and "prov:wasGeneratedBy" in ttl and 'rdfs:label "HellGraph"' in ttl
    # PROV-O correctness: wasGeneratedBy points at a prov:Activity RESOURCE, not a bare literal
    assert "prov:Activity" in ttl
    # THE FIX: the co_occurs RELATION is exported as a real predicate triple between the two entities
    from rdflib import Graph as RDFGraph, Namespace
    rg = RDFGraph().parse(data=ttl, format="turtle")
    SP = Namespace("https://socioprophet.ai/kg#")
    rels = [(s, o) for s, p, o in rg if p == SP["co_occurs"]]
    assert len(rels) == 1, "the co_occurs edge must be exported as an RDF relation"
    assert "hellgraph" in str(rels[0][0]) and "atomspace" in str(rels[0][1])


# ── WRITE workbench: manual add-node / add-edge (same fail-closed gate as /extract) ──

def test_workbench_write_gate():
    # fail-closed: no token → node + edge writes both refused (503)
    assert client.post("/api/studio/node", json={"project": "team-x", "name": "HellGraph"}).status_code == 503
    assert client.post("/api/studio/edge", json={"project": "team-x", "from_name": "A", "to_name": "B"}).status_code == 503


def test_workbench_wrong_token_401(monkeypatch):
    monkeypatch.setattr("lattice_studio.server.STUDIO_WRITE_TOKEN", "secret")
    r = client.post("/api/studio/node", json={"project": "team-x", "name": "HellGraph"},
                    headers={"authorization": "Bearer nope"})
    assert r.status_code == 401


def test_add_node_writes_proof_carrying(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "secret")
    captured = {}

    async def fake_req(client, method, url, json=None):
        captured["url"] = url; captured["json"] = json
        return ({"ok": True}, None)
    monkeypatch.setattr(srv, "_req", fake_req)

    r = client.post("/api/studio/node",
                    json={"project": "team-x", "name": "Custom Fact", "epistemic_mode": "attested", "labels": ["Claim"]},
                    headers={"authorization": "Bearer secret"})
    assert r.status_code == 200
    b = r.json()
    # project-scoped id matches /extract's scheme; provenance carries the user's epistemic mode + workbench origin
    assert b["id"] == "proj-teamx:ent:custom_fact" and b["written"] is True
    assert b["provenance"]["epistemic_mode"] == "attested"
    assert b["provenance"]["extractor"] == "lattice-studio/workbench-v0"
    assert "Claim" in b["labels"] and "proj-teamx" in b["labels"] and "Entity" in b["labels"]
    # it actually POSTed to the hellgraph node endpoint with the mapped id
    assert captured["url"].endswith("/api/graph/node") and captured["json"]["id"] == "proj-teamx:ent:custom_fact"


def test_add_node_requires_name(monkeypatch):
    monkeypatch.setattr("lattice_studio.server.STUDIO_WRITE_TOKEN", "secret")
    r = client.post("/api/studio/node", json={"project": "team-x", "name": "   "},
                    headers={"authorization": "Bearer secret"})
    assert r.status_code == 422


def test_add_edge_upserts_endpoints_then_relation(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "secret")
    calls: list[tuple[str, dict]] = []

    async def fake_req(client, method, url, json=None):
        calls.append((url, json))
        return ({"ok": True}, None)
    monkeypatch.setattr(srv, "_req", fake_req)

    r = client.post("/api/studio/edge",
                    json={"project": "team-x", "from_name": "HellGraph", "to_name": "Neo4j", "label": "beats"},
                    headers={"authorization": "Bearer secret"})
    assert r.status_code == 200
    b = r.json()
    assert b["from"] == "proj-teamx:ent:hellgraph" and b["to"] == "proj-teamx:ent:neo4j"
    assert b["label"] == "beats" and b["written"] is True
    # both endpoint nodes upserted FIRST, then the edge (3 calls, edge last)
    assert len(calls) == 3
    assert all(u.endswith("/api/graph/node") for u, _ in calls[:2])
    assert calls[2][0].endswith("/api/graph/edge")
    assert calls[2][1]["from"] == "proj-teamx:ent:hellgraph" and calls[2][1]["to"] == "proj-teamx:ent:neo4j"


def test_add_edge_graph_failure_is_502(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "secret")

    async def fake_req(client, method, url, json=None):
        return (None, "connection refused")
    monkeypatch.setattr(srv, "_req", fake_req)

    r = client.post("/api/studio/edge", json={"project": "team-x", "from_name": "A", "to_name": "B"},
                    headers={"authorization": "Bearer secret"})
    assert r.status_code == 502


# ── KE-5 "How derived?": proof-carrying provenance/lineage for one fact ──

def test_provenance_requires_id():
    assert client.get("/api/studio/provenance?project=team-x").status_code == 422


def test_provenance_not_found_is_graceful(monkeypatch):
    import lattice_studio.server as srv

    async def fake_req(client, method, url, json=None):
        return ({"nodes": [], "edgeList": []}, None)
    monkeypatch.setattr(srv, "_req", fake_req)
    b = client.get("/api/studio/provenance?project=team-x&id=proj-teamx:ent:ghost").json()
    assert b["found"] is False and b["id"] == "proj-teamx:ent:ghost"


def test_provenance_returns_derivation_and_summary(monkeypatch):
    import lattice_studio.server as srv

    async def fake_req(client, method, url, json=None):
        if "subgraph" in url:
            return ({
                "nodes": [
                    {"id": "proj-teamx:ent:hellgraph", "labels": ["proj-teamx", "Entity"],
                     "properties": {"name": "HellGraph", "epistemic_mode": "verified", "source": "doc:spec",
                                    "extractor": "lattice-studio/workbench-v0", "kko_type": "Particulars"}},
                    {"id": "proj-teamx:ent:neo4j", "labels": ["proj-teamx", "Entity"],
                     "properties": {"name": "Neo4j", "epistemic_mode": "observed"}},
                ],
                "edgeList": [
                    {"id": "h:1", "label": "beats", "from": "proj-teamx:ent:hellgraph",
                     "to": "proj-teamx:ent:neo4j", "properties": {"n": 4}},
                ],
            }, None)
        return (None, "unreachable")
    monkeypatch.setattr(srv, "_req", fake_req)

    b = client.get("/api/studio/provenance?project=team-x&id=proj-teamx:ent:hellgraph").json()
    assert b["found"] is True and b["name"] == "HellGraph"
    assert b["epistemic_mode"] == "verified" and b["extractor"] == "lattice-studio/workbench-v0"
    assert b["kko_type"] == "Particulars" and b["source"] == "doc:spec"
    assert b["derivation_count"] == 1
    d = b["derivations"][0]
    assert d["relation"] == "beats" and d["direction"] == "out" and d["weight"] == 4
    assert d["with"]["name"] == "Neo4j" and d["with"]["epistemic_mode"] == "observed"
    assert "verified" in b["summary"] and "HellGraph" in b["summary"]


# ── Read-auth: opt-in, tied to the sovereign identity plane (socbase HS256 JWT) ──

def test_reads_open_when_jwt_secret_unset():
    assert client.get("/api/studio?project=team-x").status_code == 200
    assert client.get("/api/studio/graph?project=team-x").status_code == 200


def test_reads_require_token_when_secret_set(monkeypatch):
    monkeypatch.setattr("lattice_studio.server.STUDIO_JWT_SECRET", "sovereign-secret")
    assert client.get("/api/studio?project=team-x").status_code == 401
    assert client.get("/api/studio/graph?project=team-x").status_code == 401
    assert client.get("/api/studio?project=team-x", headers={"authorization": "Bearer nope"}).status_code == 401


def test_reads_accept_valid_socbase_jwt(monkeypatch):
    import jwt
    monkeypatch.setattr("lattice_studio.server.STUDIO_JWT_SECRET", "sovereign-secret")
    token = jwt.encode({"sub": "user-1", "role": "authenticated"}, "sovereign-secret", algorithm="HS256")
    r = client.get("/api/studio?project=team-x", headers={"authorization": f"Bearer {token}"})
    assert r.status_code == 200 and r.json()["project"] == "team-x"
    bad = jwt.encode({"sub": "x"}, "other-secret", algorithm="HS256")
    assert client.get("/api/studio?project=team-x", headers={"authorization": f"Bearer {bad}"}).status_code == 401


# ── WS#29 surface-the-moat: verified-compute receipts + epistemic status on every load ──

def test_moat_header_computes_epistemic_and_verified(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "w")  # governed_writes → True

    async def fake_req(client, method, url, json=None):
        if "subgraph" in url:
            return ({"nodes": [
                {"id": "proj-x:ent:a", "labels": ["proj-x", "Entity"], "properties": {"name": "A", "epistemic_mode": "verified", "source": "doc:1"}},
                {"id": "proj-x:ent:b", "labels": ["proj-x", "Entity"], "properties": {"name": "B", "epistemic_mode": "observed", "source": "doc:2"}},
                {"id": "proj-x:ent:c", "labels": ["proj-x", "Entity"], "properties": {"name": "C", "epistemic_mode": "observed"}},
            ], "edgeList": []}, None)
        if "receipts/recent" in url:
            return ({"items": [{"correlation_id": "c1"}, {"correlation_id": "c2"}]}, None)
        return (None, "unreachable")
    monkeypatch.setattr(srv, "_req", fake_req)

    m = client.get("/api/studio?project=x").json()["moat"]
    assert m["fact_count"] == 3
    assert m["epistemic_distribution"] == {"verified": 1, "observed": 2}
    assert m["provenance_coverage"] == round(2 / 3, 3)   # 2 of 3 carry a source
    assert m["verified_compute"] is True and m["receipts_recent"] == 2
    assert m["governed_writes"] is True


def test_receipts_aggregate_across_the_evidence_fabric(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "RECEIPT_SERVICES", ["hellgraph-service", "owl-reasoner", "down-svc"])

    async def fake_req(client, method, url, json=None):
        if "service=hellgraph-service" in url:
            return ({"items": [{"correlation_id": "hg-1", "received_at": "2026-07-17T10:00:00Z", "verdict": "ok"}]}, None)
        if "service=owl-reasoner" in url:
            return ({"items": [{"correlation_id": "owl-1", "received_at": "2026-07-17T11:00:00Z", "receipt": {"verdict": "sound"}}]}, None)
        return (None, "connection refused")   # down-svc degrades only itself
    monkeypatch.setattr(srv, "_req", fake_req)

    b = client.get("/api/studio/receipts").json()
    assert b["count"] == 2 and b["services_reachable"] == 2
    assert b["services"] == {"hellgraph-service": True, "owl-reasoner": True, "down-svc": False}
    # newest first + nested verdict extracted + a replayable bundle ref
    assert b["receipts"][0]["correlation_id"] == "owl-1" and b["receipts"][0]["verdict"] == "sound"
    assert b["receipts"][0]["bundle_ref"] == "/v1/receipts/owl-reasoner/owl-1"
    assert b["receipts"][1]["correlation_id"] == "hg-1" and b["receipts"][1]["verdict"] == "ok"


# ── WS#30: proof-carrying query IDE (SPARQL/Cypher/Gremlin) ──

def test_query_validates_lang_and_query():
    assert client.post("/api/studio/query", json={"lang": "gql", "query": "x"}).status_code == 422
    assert client.post("/api/studio/query", json={"lang": "sparql", "query": "  "}).status_code == 422


def test_query_bad_syntax_surfaces_400(monkeypatch):
    import lattice_studio.server as srv

    async def fake_req(client, method, url, json=None):
        if url.endswith("/api/graph/sparql"):
            return (None, "HTTP 400")   # kernel rejects bad syntax
        return ({"nodes": []}, None)
    monkeypatch.setattr(srv, "_req", fake_req)
    r = client.post("/api/studio/query", json={"project": "team-x", "lang": "sparql", "query": "SELEKT *"})
    assert r.status_code == 400


def test_query_is_proof_carrying_and_epistemically_enriched(monkeypatch):
    import lattice_studio.server as srv

    async def fake_req(client, method, url, json=None):
        if url.endswith("/api/graph/sparql"):
            return ({
                "ok": True, "queryHash": "qh-abc", "evaluatedAtSeq": 42,
                "head": {"vars": ["s", "name"]},
                "results": {"bindings": [
                    {"s": {"value": "proj-teamx:ent:hellgraph"}, "name": {"value": "HellGraph"}},
                ]},
            }, None)
        if "subgraph" in url:
            return ({"nodes": [
                {"id": "proj-teamx:ent:hellgraph", "labels": ["proj-teamx", "Entity"],
                 "properties": {"name": "HellGraph", "epistemic_mode": "verified"}},
            ], "edgeList": []}, None)
        return (None, "unreachable")
    monkeypatch.setattr(srv, "_req", fake_req)

    b = client.post("/api/studio/query", json={"project": "team-x", "lang": "sparql", "query": "SELECT ?s ?name WHERE {}"}).json()
    # rows/columns normalised from SPARQL JSON
    assert b["columns"] == ["s", "name"] and b["row_count"] == 1
    assert b["rows"][0]["s"] == "proj-teamx:ent:hellgraph" and b["rows"][0]["name"] == "HellGraph"
    # THE BEAT #1: the result is REPLAYABLE — carries the kernel's proof
    assert b["proof"]["query_hash"] == "qh-abc" and b["proof"]["evaluated_at_seq"] == 42 and b["proof"]["replayable"] is True
    # THE BEAT #2: the referenced fact carries its epistemic status
    assert b["epistemic"] == {"proj-teamx:ent:hellgraph": "verified"}
