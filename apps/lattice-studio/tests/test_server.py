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


# ── WS#32: experiment tracking — runs as first-class proof-carrying graph facts ──

def test_experiment_create_is_write_gated():
    assert client.post("/api/studio/experiments", json={"project": "p", "name": "run-1"}).status_code == 503


def test_experiment_persists_run_as_graph_fact(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "w")
    captured = {}

    async def fake_req(client, method, url, json=None):
        captured["url"] = url; captured["json"] = json
        return ({"ok": True}, None)
    monkeypatch.setattr(srv, "_req", fake_req)

    r = client.post("/api/studio/experiments",
                    json={"project": "team-x", "name": "sweep-lr", "params": {"lr": 0.01}, "metrics": {"acc": 0.91}, "status": "finished"},
                    headers={"authorization": "Bearer w"})
    assert r.status_code == 200
    b = r.json()
    assert b["run_id"].startswith("proj-teamx:run:") and b["written"] is True
    # persisted to the GRAPH as a Run+Experiment fact carrying provenance
    assert captured["url"].endswith("/api/graph/node")
    node = captured["json"]
    assert node["labels"] == ["proj-teamx", "Run", "Experiment"]
    assert '"lr": 0.01' in node["properties"]["params_json"] and '"acc": 0.91' in node["properties"]["metrics_json"]
    assert node["properties"]["extractor"] == "studio/experiment-v0" and node["properties"]["epistemic_mode"] == "observed"


def test_experiments_list_reads_runs_with_epistemic(monkeypatch):
    import lattice_studio.server as srv

    async def fake_req(client, method, url, json=None):
        if "subgraph" in url:
            return ({"nodes": [
                {"id": "proj-teamx:run:abc", "labels": ["proj-teamx", "Run", "Experiment"],
                 "properties": {"name": "sweep-lr", "run_id": "proj-teamx:run:abc", "status": "finished",
                                "params_json": "{\"lr\": 0.01}", "metrics_json": "{\"acc\": 0.91}",
                                "created_at": "2026-07-17T12:00:00Z", "epistemic_mode": "observed", "extractor": "studio/experiment-v0"}},
                {"id": "proj-teamx:ent:x", "labels": ["proj-teamx", "Entity"], "properties": {"name": "not-a-run"}},
            ], "edgeList": []}, None)
        return (None, "unreachable")
    monkeypatch.setattr(srv, "_req", fake_req)

    b = client.get("/api/studio/experiments?project=team-x").json()
    assert b["count"] == 1   # the Entity node is filtered out
    run = b["runs"][0]
    assert run["name"] == "sweep-lr" and run["status"] == "finished"
    assert run["params"] == {"lr": 0.01} and run["metrics"] == {"acc": 0.91}
    assert run["epistemic_mode"] == "observed" and run["run_id"] == "proj-teamx:run:abc"


# ── WS#35: sovereign persistent IDs + citation (DataCite-compatible, resolves to a proof-carrying record) ──

def test_cite_is_write_gated():
    assert client.post("/api/studio/cite", json={"project": "p", "kind": "graph"}).status_code == 503


def test_cite_mints_pid_doi_and_persists_as_graph_fact(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "w")
    captured = {}

    async def fake_req(client, method, url, json=None):
        captured["url"] = url; captured["json"] = json
        return ({"ok": True}, None)
    monkeypatch.setattr(srv, "_req", fake_req)

    b = client.post("/api/studio/cite",
                    json={"project": "team-x", "kind": "dataset", "ref": "proj-teamx:ds:1", "title": "Apple 2024 corpus", "creators": ["M. Heller"]},
                    headers={"authorization": "Bearer w"}).json()
    # content-addressed, stable PID + DataCite DOI + a formatted citation + BibTeX + DataCite metadata
    assert b["pid"].startswith("sp:proj-teamx/dataset/") and b["doi"].startswith("10.82044/proj-teamx.dataset.")
    assert "Apple 2024 corpus" in b["citation"] and "M. Heller" in b["citation"] and b["pid"] in b["citation"]
    assert "@misc{" in b["bibtex"] and b["datacite"]["attributes"]["doi"] == b["doi"]
    # the BEAT: provenance rides in the DataCite metadata + the identifier is itself a proof-carrying graph fact
    assert "epistemic_mode=attested" in b["datacite"]["attributes"]["descriptions"][0]["description"]
    assert captured["url"].endswith("/api/graph/node")
    assert captured["json"]["labels"] == ["proj-teamx", "Citation", "Identifier"]
    assert captured["json"]["properties"]["epistemic_mode"] == "attested" and captured["json"]["properties"]["pid"] == b["pid"]


def test_cite_is_idempotent_content_addressed(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "w")

    async def fake_req(client, method, url, json=None):
        return ({"ok": True}, None)
    monkeypatch.setattr(srv, "_req", fake_req)
    a = client.post("/api/studio/cite", json={"project": "team-x", "kind": "graph", "ref": "x"}, headers={"authorization": "Bearer w"}).json()
    b = client.post("/api/studio/cite", json={"project": "team-x", "kind": "graph", "ref": "x"}, headers={"authorization": "Bearer w"}).json()
    assert a["pid"] == b["pid"] and a["doi"] == b["doi"]   # citing the same thing twice = same identifier


def test_resolve_returns_proof_carrying_record(monkeypatch):
    import lattice_studio.server as srv

    async def fake_req(client, method, url, json=None):
        if "subgraph" in url:
            return ({"nodes": [
                {"id": "proj-teamx:cite:abc", "labels": ["proj-teamx", "Citation", "Identifier"],
                 "properties": {"pid": "sp:proj-teamx/dataset/abc123", "doi": "10.82044/proj-teamx.dataset.abc",
                                "kind": "dataset", "target": "proj-teamx:ds:1", "title": "Apple 2024 corpus",
                                "creators_json": "[\"M. Heller\"]", "content_hash": "abc123def456",
                                "created_at": "2026-07-17T12:00:00Z", "epistemic_mode": "attested", "extractor": "studio/cite-v0"}},
            ], "edgeList": []}, None)
        return (None, "unreachable")
    monkeypatch.setattr(srv, "_req", fake_req)

    assert client.get("/api/studio/resolve").status_code == 422        # pid required
    assert client.get("/api/studio/resolve?pid=nonsense").status_code == 422  # malformed
    b = client.get("/api/studio/resolve?pid=sp:proj-teamx/dataset/abc123").json()
    assert b["found"] is True and b["title"] == "Apple 2024 corpus" and b["doi"] == "10.82044/proj-teamx.dataset.abc"
    # resolves to a VERIFIABLE record, not a landing page
    assert b["proof_carrying"] is True and b["content_hash"] == "abc123def456"
    assert b["provenance"]["epistemic_mode"] == "attested" and b["creators"] == ["M. Heller"]


# ── WS#36: immutable preservation + versioning (content-addressed, chained, tamper-evident) ──

def test_preserve_is_write_gated():
    assert client.post("/api/studio/preserve", json={"project": "p"}).status_code == 503


def test_preserve_seals_v1_snapshot(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "w")
    posts = []
    nodes = [
        {"id": "proj-teamx:ent:a", "labels": ["proj-teamx", "Entity"], "properties": {"name": "A", "epistemic_mode": "observed"}},
        {"id": "proj-teamx:ent:b", "labels": ["proj-teamx", "Entity"], "properties": {"name": "B", "epistemic_mode": "observed"}},
    ]

    async def fake_req(client, method, url, json=None):
        if "subgraph" in url:
            return ({"nodes": nodes, "edgeList": []}, None)
        posts.append((url, json)); return ({"ok": True}, None)
    monkeypatch.setattr(srv, "_req", fake_req)

    b = client.post("/api/studio/preserve", json={"project": "team-x", "note": "first seal"}, headers={"authorization": "Bearer w"}).json()
    assert b["version"] == 1 and b["content_hash"] == srv._state_hash(nodes, "") and b["unchanged"] is False and b["parent"] is None
    node_post = next(p for u, p in posts if u.endswith("/api/graph/node"))
    assert node_post["labels"] == ["proj-teamx", "Snapshot", "Preservation"]
    assert node_post["properties"]["version"] == 1 and node_post["properties"]["epistemic_mode"] == "attested"


def test_preserve_is_idempotent_on_unchanged_state(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "w")
    ents = [{"id": "proj-teamx:ent:a", "labels": ["proj-teamx", "Entity"], "properties": {"name": "A"}}]
    h = srv._state_hash(ents, "")
    snap = {"id": "proj-teamx:snap:x", "labels": ["proj-teamx", "Snapshot", "Preservation"],
            "properties": {"target": "proj-teamx", "version": 1, "content_hash": h, "sealed_at": "t0"}}
    created = []

    async def fake_req(client, method, url, json=None):
        if "subgraph" in url:
            return ({"nodes": ents + [snap], "edgeList": []}, None)
        created.append(url); return ({"ok": True}, None)
    monkeypatch.setattr(srv, "_req", fake_req)

    b = client.post("/api/studio/preserve", json={"project": "team-x"}, headers={"authorization": "Bearer w"}).json()
    assert b["unchanged"] is True and b["version"] == 1
    assert not any(u.endswith("/api/graph/node") for u in created)   # no duplicate snapshot written


def test_versions_lists_the_chain_newest_first(monkeypatch):
    import lattice_studio.server as srv

    async def fake_req(client, method, url, json=None):
        if "subgraph" in url:
            return ({"nodes": [
                {"id": "proj-teamx:snap:1", "labels": ["proj-teamx", "Snapshot"],
                 "properties": {"target": "proj-teamx", "version": 1, "content_hash": "h1", "sealed_at": "t1", "epistemic_mode": "attested"}},
                {"id": "proj-teamx:snap:2", "labels": ["proj-teamx", "Snapshot"],
                 "properties": {"target": "proj-teamx", "version": 2, "content_hash": "h2", "sealed_at": "t2", "parent": "proj-teamx:snap:1", "epistemic_mode": "attested"}},
            ], "edgeList": []}, None)
        return (None, "x")
    monkeypatch.setattr(srv, "_req", fake_req)

    b = client.get("/api/studio/versions?project=team-x").json()
    assert b["count"] == 2 and b["versions"][0]["version"] == 2   # newest first
    assert b["versions"][0]["parent"] == "proj-teamx:snap:1" and b["versions"][1]["content_hash"] == "h1"


def test_fair_full_record_scores_high_and_carries_provenance(monkeypatch):
    import lattice_studio.server as srv

    async def fake_req(client, method, url, json=None):
        if "subgraph" in url:
            return ({"nodes": [
                {"id": "proj-teamx:cite", "labels": ["proj-teamx", "Citation"],
                 "properties": {"target": "proj-teamx", "pid": "sp:proj-teamx/graph/abc123",
                                "doi": "10.82044/proj-teamx.graph.abc12345", "title": "Team X graph",
                                "resolve": "https://x/api/studio/resolve?pid=sp:proj-teamx/graph/abc123",
                                "epistemic_mode": "verified"}},
                {"id": "proj-teamx:snap:1", "labels": ["proj-teamx", "Snapshot"],
                 "properties": {"target": "proj-teamx", "version": 1, "content_hash": "seal1"}},
            ], "edgeList": []}, None)
        return (None, "x")
    monkeypatch.setattr(srv, "_req", fake_req)

    b = client.get("/api/studio/fair?project=team-x").json()
    assert b["fair"]["findable"] and b["fair"]["accessible"] and b["fair"]["reusable"]
    assert b["fair"]["score"] == 1.0
    assert b["schema_org"]["@type"] == "Dataset" and b["schema_org"]["sha256"] == "seal1"
    assert b["schema_org"]["identifier"] == "10.82044/proj-teamx.graph.abc12345"
    assert b["schema_org"]["provenance"]["epistemic_status"] == "verified"   # FAIR+
    assert b["fair_plus"]["provenance_chain"] and b["fair_plus"]["hash_sealed"]
    assert b["hint"] is None


def test_fair_without_citation_is_not_findable_and_hints(monkeypatch):
    import lattice_studio.server as srv

    async def fake_req(client, method, url, json=None):
        if "subgraph" in url:
            return ({"nodes": [], "edgeList": []}, None)   # nothing minted yet
        return (None, "x")
    monkeypatch.setattr(srv, "_req", fake_req)

    b = client.get("/api/studio/fair?project=team-x").json()
    assert not b["fair"]["findable"] and not b["fair"]["accessible"]
    assert b["fair"]["interoperable"]              # RDF/PROV-O always available
    assert b["fair"]["score"] == 0.25
    assert b["hint"] and "persistent identifier" in b["hint"]


def test_ecosystem_links_scholarly_and_emits_agent_manifest(monkeypatch):
    import lattice_studio.server as srv

    async def fake_req(client, method, url, json=None):
        if "subgraph" in url:
            return ({"nodes": [
                {"id": "proj-teamx:cite", "labels": ["proj-teamx", "Citation"],
                 "properties": {"target": "proj-teamx", "pid": "sp:proj-teamx/graph/abc123",
                                "doi": "10.82044/proj-teamx.graph.abc12345",
                                "contributors": [{"name": "A. Author", "orcid": "0000-0002-1825-0097"}]}},
                {"id": "proj-teamx:person:kim", "labels": ["proj-teamx", "Person"],
                 "properties": {"name": "Kim", "orcid": "0000-0001-0000-0001"}},
            ], "edgeList": []}, None)
        return (None, "x")
    monkeypatch.setattr(srv, "_req", fake_req)

    b = client.get("/api/studio/ecosystem?project=team-x").json()
    assert b["scholarly"]["doi_url"] == "https://doi.org/10.82044/proj-teamx.graph.abc12345"
    orcids = {c["orcid"] for c in b["scholarly"]["orcid_contributors"]}
    assert orcids == {"0000-0002-1825-0097", "0000-0001-0000-0001"}   # graph node + citation, deduped
    assert b["scholarly"]["openaire"]["harvestable"]
    m = b["agent_manifest"]
    assert m["proof_carrying"] and m["identifier"] == "sp:proj-teamx/graph/abc123"
    verbs = {v["name"]: v for v in m["access"]}
    assert verbs["resolve"]["endpoint"] and all(v["verifiable"] for v in m["access"])
    assert "receipts" in verbs and "query" in verbs


def test_commons_overview_counts_scale_and_epistemic_quality(monkeypatch):
    import lattice_studio.server as srv

    async def fake_req(client, method, url, json=None):
        if "subgraph" in url:
            return ({"nodes": [
                {"id": "proj-teamx:a", "labels": ["proj-teamx", "Entity"], "properties": {"epistemic_mode": "attested", "orcid": "0000-0001-0000-0001"}},
                {"id": "proj-teamx:b", "labels": ["proj-teamx", "Entity"], "properties": {"epistemic_mode": "hypothesis"}},
                {"id": "proj-teamx:cite", "labels": ["proj-teamx", "Citation"], "properties": {"target": "proj-teamx"}},
                {"id": "proj-teamx:snap:1", "labels": ["proj-teamx", "Snapshot"], "properties": {"target": "proj-teamx", "version": 1}},
                {"id": "proj-teamx:endorse:x", "labels": ["proj-teamx", "Endorsement"], "properties": {"target": "proj-teamx:a", "endorser": "kim"}},
            ], "edgeList": []}, None)
        return (None, "x")
    monkeypatch.setattr(srv, "_req", fake_req)

    b = client.get("/api/studio/commons?project=team-x").json()
    assert b["scale"] == {"facts": 2, "citations": 1, "preserved_versions": 1, "endorsements": 1, "contributors": 1}
    assert b["epistemic_distribution"] == {"attested": 1, "hypothesis": 1}
    assert b["epistemic_quality_index"] == round((1.0 + 0.25) / 2, 3)   # attested + hypothesis


def test_endorse_requires_write_token(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "")
    r = client.post("/api/studio/endorse", json={"project": "team-x", "target": "proj-teamx:a", "endorser": "kim"})
    assert r.status_code == 503   # fail-closed


def test_endorse_writes_governed_fact_and_curation_is_epistemic_weighted(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "T")
    writes = []

    async def fake_req(client, method, url, json=None):
        if "/api/graph/node" in url or "/api/graph/edge" in url:
            writes.append(json)
            return ({"ok": True}, None)
        if "subgraph" in url:
            return ({"nodes": [
                {"id": "proj-teamx:a", "labels": ["proj-teamx", "Entity"], "properties": {"epistemic_mode": "attested"}},
                {"id": "e1", "labels": ["proj-teamx", "Endorsement"], "properties": {"target": "proj-teamx:a", "endorser": "kim", "revoked": False, "at": "t"}},
                {"id": "e2", "labels": ["proj-teamx", "Endorsement"], "properties": {"target": "proj-teamx:a", "endorser": "sam", "revoked": True, "at": "t"}},
            ], "edgeList": []}, None)
        return (None, "x")
    monkeypatch.setattr(srv, "_req", fake_req)

    r = client.post("/api/studio/endorse", json={"project": "team-x", "target": "proj-teamx:a", "endorser": "kim"},
                    headers={"Authorization": "Bearer T"})
    assert r.status_code == 200 and r.json()["proof_carrying"]
    node = next(w for w in writes if "labels" in w)
    assert "Endorsement" in node["labels"] and "Curation" in node["labels"]

    c = client.get("/api/studio/curation?project=team-x&target=proj-teamx:a").json()
    assert c["count"] == 1                          # revoked endorsement excluded
    assert c["endorsements"][0]["endorser"] == "kim"
    assert c["curation_score"] == 1.0               # endorsing an attested fact = full weight
    assert c["epistemic_weighted"]


def test_connectors_registry_lists_live_and_declared(monkeypatch):
    b = client.get("/api/studio/connectors").json()
    by_type = {c["type"]: c for c in b["connectors"]}
    assert by_type["csv"]["status"] == "live" and by_type["json"]["status"] == "live"
    assert by_type["http"]["status"] == "declared"
    assert all(c["governed"] for c in b["connectors"])   # every connector is governed


def test_ingest_requires_write_token(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "")
    r = client.post("/api/studio/ingest", json={"project": "team-x", "connector": "csv", "data": "a,b\n1,2"})
    assert r.status_code == 503   # fail-closed


def test_ingest_csv_writes_one_governed_node_per_row(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "T")
    writes = []

    async def fake_req(client, method, url, json=None):
        if "/api/graph/node" in url:
            writes.append(json)
            return ({"ok": True}, None)
        return (None, "x")
    monkeypatch.setattr(srv, "_req", fake_req)

    r = client.post("/api/studio/ingest",
                    json={"project": "team-x", "connector": "csv", "key": "id",
                          "data": "id,name\n1,Ann\n2,Bo", "label": "Person", "epistemic_mode": "observed"},
                    headers={"Authorization": "Bearer T"})
    b = r.json()
    assert b["rows"] == 2 and b["written"] == 2
    labels = writes[0]["labels"]
    assert "Person" in labels and "Ingested" in labels
    assert writes[0]["properties"]["epistemic_mode"] == "observed"      # per-row provenance
    assert writes[0]["properties"]["connector"] == "csv"
    assert writes[0]["id"].endswith(":ingest:1")                         # keyed by the id column


def test_ingest_rejects_unwired_connector(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "T")
    r = client.post("/api/studio/ingest",
                    json={"project": "team-x", "connector": "s3", "data": "s3://bucket/key"},
                    headers={"Authorization": "Bearer T"})
    assert r.status_code == 422 and "not yet wired" in r.json()["detail"]


def test_perspective_requires_write_token(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "")
    r = client.post("/api/studio/perspective", json={"project": "team-x", "name": "verified-people"})
    assert r.status_code == 503   # fail-closed


def test_save_perspective_then_list_roundtrips_epistemic_filter(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "T")
    writes = []

    async def fake_req(client, method, url, json=None):
        if "/api/graph/node" in url:
            writes.append(json)
            return ({"ok": True}, None)
        if "subgraph" in url:
            return ({"nodes": [
                {"id": "proj-teamx:perspective:verified_people", "labels": ["proj-teamx", "Perspective", "Curation"],
                 "properties": {"name": "verified people", "label": "Person",
                                "epistemic": '["attested", "verified"]', "limit": 200, "layout": "radial",
                                "saved_at": "t1"}},
            ], "edgeList": []}, None)
        return (None, "x")
    monkeypatch.setattr(srv, "_req", fake_req)

    r = client.post("/api/studio/perspective",
                    json={"project": "team-x", "name": "verified people", "label": "Person",
                          "epistemic": ["attested", "verified"], "limit": 200, "layout": "radial"},
                    headers={"Authorization": "Bearer T"})
    assert r.status_code == 200 and r.json()["shared_to_team"]
    node = writes[0]
    assert "Perspective" in node["labels"] and node["properties"]["epistemic"] == '["attested", "verified"]'

    b = client.get("/api/studio/perspectives?project=team-x").json()
    assert b["count"] == 1
    p = b["perspectives"][0]
    assert p["name"] == "verified people" and p["epistemic"] == ["attested", "verified"]   # JSON round-trip
    assert p["label"] == "Person" and p["layout"] == "radial"


def test_pidgraph_assembles_typed_research_graph(monkeypatch):
    import lattice_studio.server as srv

    async def fake_req(client, method, url, json=None):
        if "subgraph" in url:
            return ({"nodes": [
                {"id": "proj-teamx:cite", "labels": ["proj-teamx", "Citation"],
                 "properties": {"target": "proj-teamx", "title": "Team X graph", "pid": "sp:proj-teamx/graph/abc",
                                "doi": "10.82044/proj-teamx.graph.abc12345", "epistemic_mode": "verified",
                                "contributors": [{"name": "A. Author", "orcid": "0000-0002-1825-0097", "affiliation": "SocioProphet"}]}},
                {"id": "proj-teamx:person:kim", "labels": ["proj-teamx", "Person"],
                 "properties": {"name": "Kim", "orcid": "0000-0001-0000-0001"}},
            ], "edgeList": []}, None)
        return (None, "x")
    monkeypatch.setattr(srv, "_req", fake_req)

    b = client.get("/api/studio/pidgraph?project=team-x").json()
    types = {n["id"]: n["type"] for n in b["nodes"]}
    assert types["proj-teamx"] == "Result"
    assert types["sp:proj-teamx/graph/abc"] == "Identifier"
    assert types["10.82044/proj-teamx.graph.abc12345"] == "Identifier"
    assert types["orcid:0000-0002-1825-0097"] == "Person"
    assert types["org:socioprophet"] == "Organization"
    assert types["orcid:0000-0001-0000-0001"] == "Person"          # standalone graph person joined
    labels = {(e["from"], e["to"], e["label"]) for e in b["edges"]}
    assert ("sp:proj-teamx/graph/abc", "proj-teamx", "identifies") in labels
    assert ("orcid:0000-0002-1825-0097", "proj-teamx", "authored") in labels
    assert ("orcid:0000-0002-1825-0097", "org:socioprophet", "affiliated") in labels
    assert b["stats"]["results"] == 1 and b["stats"]["persons"] == 2 and b["stats"]["identifiers"] == 2
    assert all(n["proof_carrying"] for n in b["nodes"])            # the beat


# ── WS#45–47: Databricks/Foundry parity — pipelines, catalog+lineage, model registry ──────────────────────────
def test_pipeline_write_gated_and_builds_dag(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "")
    assert client.post("/api/studio/pipeline", json={"project": "team-x", "name": "etl"}).status_code == 503

    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "T")
    writes = []

    async def fake_req(client, method, url, json=None):
        if "/api/graph/node" in url or "/api/graph/edge" in url:
            writes.append(json); return ({"ok": True}, None)
        return (None, "x")
    monkeypatch.setattr(srv, "_req", fake_req)

    r = client.post("/api/studio/pipeline",
                    json={"project": "team-x", "name": "ETL train",
                          "steps": [{"id": "load", "kind": "extract", "outputs": ["raw"]},
                                    {"id": "clean", "kind": "transform", "inputs": ["raw"], "outputs": ["tidy"]},
                                    {"id": "fit", "kind": "train", "inputs": ["tidy"]}]},
                    headers={"Authorization": "Bearer T"})
    b = r.json()
    assert b["pipeline_id"] == "proj-teamx:pipeline:etl_train" and b["steps"] == 3 and b["proof_carrying"]
    labels = {(w.get("label"), w.get("from"), w.get("to")) for w in writes if "label" in w}
    assert ("feeds", "proj-teamx:pipeline:etl_train:step:load", "proj-teamx:pipeline:etl_train:step:clean") in labels
    assert ("feeds", "proj-teamx:pipeline:etl_train:step:clean", "proj-teamx:pipeline:etl_train:step:fit") in labels
    assert any(w.get("label") == "step_of" for w in writes)


def test_pipeline_run_records_ledger(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "T")
    writes = []

    async def fake_req(client, method, url, json=None):
        if "/api/graph/node" in url or "/api/graph/edge" in url:
            writes.append(json); return ({"ok": True}, None)
        return (None, "x")
    monkeypatch.setattr(srv, "_req", fake_req)

    b = client.post("/api/studio/pipeline/run", json={"project": "team-x", "pipeline": "ETL train", "status": "finished"},
                    headers={"Authorization": "Bearer T"}).json()
    assert b["proof_carrying"] and b["status"] == "finished"
    node = next(w for w in writes if "labels" in w)
    assert "PipelineRun" in node["labels"] and "Run" in node["labels"]
    assert any(w.get("label") == "run_of" and w.get("to") == "proj-teamx:pipeline:etl_train" for w in writes)


def test_catalog_lists_governed_datasets(monkeypatch):
    import lattice_studio.server as srv

    async def fake_req(client, method, url, json=None):
        if "subgraph" in url:
            return ({"nodes": [
                {"id": "proj-teamx:ingest:1", "labels": ["proj-teamx", "Person", "Ingested"],
                 "properties": {"name": "row1", "id_col": "1", "age": "40", "connector": "csv",
                                "epistemic_mode": "observed", "source": "connector:csv:abc", "extractor": "x"}},
                {"id": "proj-teamx:ent:foo", "labels": ["proj-teamx", "Entity"], "properties": {"name": "foo"}},
            ], "edgeList": []}, None)
        return (None, "x")
    monkeypatch.setattr(srv, "_req", fake_req)

    b = client.get("/api/studio/catalog?project=team-x").json()
    assert b["count"] == 1                                    # only the Ingested node, not the plain Entity
    ds = b["datasets"][0]
    assert ds["connector"] == "csv" and ds["governed"] and ds["epistemic_mode"] == "observed"
    assert set(ds["columns"]) == {"id_col", "age"}           # provenance keys filtered out


def test_lineage_walks_the_flow_graph(monkeypatch):
    import lattice_studio.server as srv

    async def fake_req(client, method, url, json=None):
        if "subgraph" in url:
            return ({"nodes": [
                {"id": "ds", "labels": ["proj-teamx", "Dataset"], "properties": {"name": "tidy", "epistemic_mode": "observed"}},
                {"id": "run", "labels": ["proj-teamx", "Run", "Experiment"], "properties": {"name": "fit"}},
                {"id": "model", "labels": ["proj-teamx", "Model"], "properties": {"name": "clf", "epistemic_mode": "attested"}},
                {"id": "unrelated", "labels": ["proj-teamx", "Entity"], "properties": {"name": "x"}},
            ], "edgeList": [
                {"from": "run", "to": "ds", "label": "feeds"},
                {"from": "model", "to": "run", "label": "produced_by"},
                {"from": "unrelated", "to": "ds", "label": "co_occurs"},   # not a lineage edge → excluded
            ]}, None)
        return (None, "x")
    monkeypatch.setattr(srv, "_req", fake_req)

    b = client.get("/api/studio/lineage?project=team-x&target=model").json()
    ids = {n["id"] for n in b["nodes"]}
    assert ids == {"model", "run", "ds"}                      # walked model→run→ds; unrelated excluded
    labels = {(e["from"], e["to"], e["label"]) for e in b["edges"]}
    assert ("model", "run", "produced_by") in labels and ("run", "ds", "feeds") in labels
    assert next(n for n in b["nodes"] if n["id"] == "model")["type"] == "Model"


def test_model_register_promote_and_list(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "T")
    writes = []
    state = {"nodes": []}

    async def fake_req(client, method, url, json=None):
        if "/api/graph/node" in url:
            writes.append(json)
            state["nodes"] = [n for n in state["nodes"] if n["id"] != json["id"]] + [json]
            return ({"ok": True}, None)
        if "/api/graph/edge" in url:
            writes.append(json); return ({"ok": True}, None)
        if "subgraph" in url:
            return ({"nodes": state["nodes"], "edgeList": []}, None)
        return (None, "x")
    monkeypatch.setattr(srv, "_req", fake_req)

    reg = client.post("/api/studio/model",
                      json={"project": "team-x", "name": "classifier", "version": "2", "run": "proj-teamx:run:abc",
                            "stage": "staging", "metrics": {"acc": 0.93}},
                      headers={"Authorization": "Bearer T"}).json()
    assert reg["model_id"] == "proj-teamx:model:classifier:2" and reg["stage"] == "staging"
    assert any(w.get("label") == "produced_by" and w.get("to") == "proj-teamx:run:abc" for w in writes)

    prom = client.post("/api/studio/model/promote",
                       json={"project": "team-x", "name": "classifier", "version": "2", "stage": "production"},
                       headers={"Authorization": "Bearer T"}).json()
    assert prom["from_stage"] == "staging" and prom["stage"] == "production"

    lst = client.get("/api/studio/models?project=team-x").json()
    assert lst["count"] == 1
    v = lst["models"][0]["versions"][0]
    assert v["stage"] == "production" and v["metrics"] == {"acc": 0.93} and v["run"] == "proj-teamx:run:abc"


def test_model_register_rejects_bad_stage(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "T")
    r = client.post("/api/studio/model", json={"project": "team-x", "name": "m", "stage": "prod"},
                    headers={"Authorization": "Bearer T"})
    assert r.status_code == 422


def test_connectors_registry_names_open_connector_backbone():
    b = client.get("/api/studio/connectors").json()
    assert b["backbone"]["project"] == "oomol-lab/open-connector"
    assert b["backbone"]["license"] == "Apache-2.0" and "mcp" in b["backbone"]["interfaces"]


def test_connect_gated_and_registers_governed_connection(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "")
    assert client.post("/api/studio/connect", json={"project": "team-x", "provider": "github"}).status_code == 503

    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "T")
    writes = []

    async def fake_req(client, method, url, json=None):
        if "/api/graph/node" in url:
            writes.append(json); return ({"ok": True}, None)
        if "subgraph" in url:
            return ({"nodes": [
                {"id": "proj-teamx:connection:github:prod", "labels": ["proj-teamx", "Connection"],
                 "properties": {"provider": "github", "name": "prod", "status": "declared",
                                "owner": "mdheller", "backbone": "open-connector", "created_at": "t1"}},
            ], "edgeList": []}, None)
        return (None, "x")
    monkeypatch.setattr(srv, "_req", fake_req)

    r = client.post("/api/studio/connect",
                    json={"project": "team-x", "provider": "GitHub", "name": "prod", "owner": "mdheller"},
                    headers={"Authorization": "Bearer T"}).json()
    assert r["connection_id"] == "proj-teamx:connection:github:prod" and r["provider"] == "github"
    assert r["status"] == "declared" and r["backbone"] == "oomol-lab/open-connector" and r["proof_carrying"]
    node = writes[0]
    assert "Connection" in node["labels"] and node["properties"]["epistemic_mode"] == "attested"

    lst = client.get("/api/studio/connections?project=team-x").json()
    assert lst["count"] == 1 and lst["connections"][0]["provider"] == "github"
    assert lst["backbone"]["url"].endswith("open-connector")


def test_communities_label_propagation_finds_two_clusters(monkeypatch):
    import lattice_studio.server as srv

    async def fake_req(client, method, url, json=None):
        if "subgraph" in url:
            def n(i, mode="observed"):
                return {"id": i, "labels": ["proj-teamx", "Entity"], "properties": {"name": i, "epistemic_mode": mode}}
            def e(a, b):
                return {"from": a, "to": b, "label": "co_occurs", "properties": {"weight": 2}}
            return ({"nodes": [n("a1", "attested"), n("a2"), n("a3"), n("b1"), n("b2"), n("b3")],
                     "edgeList": [e("a1", "a2"), e("a2", "a3"), e("a3", "a1"),   # cluster A triangle
                                  e("b1", "b2"), e("b2", "b3"), e("b3", "b1"),   # cluster B triangle
                                  e("a1", "b1")]}, None)                          # one bridge
        return (None, "x")
    monkeypatch.setattr(srv, "_req", fake_req)

    b = client.get("/api/studio/communities?project=team-x").json()
    assert b["count"] == 2 and b["nodes"] == 6
    assert b["inter_community_edges"] == 1                       # only the bridge crosses communities
    # each community has 3 members and the two clusters are separated
    sizes = sorted(c["size"] for c in b["communities"])
    assert sizes == [3, 3]
    # epistemic profile rides on the community (a1 is attested)
    assert any("attested" in c["epistemic_distribution"] for c in b["communities"])
    assert b["algorithm"].startswith("louvain")


def test_communities_deterministic(monkeypatch):
    import lattice_studio.server as srv

    async def fake_req(client, method, url, json=None):
        if "subgraph" in url:
            return ({"nodes": [{"id": x, "labels": ["proj-teamx", "Entity"], "properties": {"name": x}} for x in ["a1", "a2", "b1", "b2"]],
                     "edgeList": [{"from": "a1", "to": "a2", "label": "co_occurs"},
                                  {"from": "b1", "to": "b2", "label": "co_occurs"}]}, None)
        return (None, "x")
    monkeypatch.setattr(srv, "_req", fake_req)

    a = client.get("/api/studio/communities?project=team-x").json()
    b = client.get("/api/studio/communities?project=team-x").json()
    assert [c["seed"] for c in a["communities"]] == [c["seed"] for c in b["communities"]]   # stable output


# ── WS#31 (reframed): pay-gated execution plane ──
def test_compute_backends_available_but_ungated_by_default(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_COMPUTE_ENTITLEMENTS", "")
    b = client.get("/api/studio/compute?project=team-x").json()
    ids = {x["id"] for x in b["backends"]}
    assert {"mesh-k8s", "spark", "databricks"} <= ids
    assert b["entitled_any"] is False and all(not x["entitled"] for x in b["backends"])   # available, not provisioned


def test_execute_fail_closed_on_token_then_entitlement(monkeypatch):
    import lattice_studio.server as srv
    # no write token → 503
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "")
    assert client.post("/api/studio/execute", json={"project": "team-x", "kind": "notebook-cell"}).status_code == 503
    # token but no entitlement → 402 (capability available, pay-gated)
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "T")
    monkeypatch.setattr(srv, "STUDIO_COMPUTE_ENTITLEMENTS", "")
    r = client.post("/api/studio/execute", json={"project": "team-x", "kind": "notebook-cell", "backend": "spark"},
                    headers={"Authorization": "Bearer T"})
    assert r.status_code == 402
    d = r.json()["detail"]
    assert d["status"] == "entitlement_required" and d["capability"] == "available" and d["backend"] == "spark"


def test_execute_when_entitled_records_run_and_emits_receipt(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "T")
    monkeypatch.setattr(srv, "STUDIO_COMPUTE_ENTITLEMENTS", "team-x:mesh-k8s")
    writes = []

    async def fake_req(client, method, url, json=None):
        if "/api/graph/node" in url or "/api/graph/edge" in url:
            writes.append(json); return ({"ok": True}, None)
        if "subgraph" in url:
            return ({"nodes": [
                {"id": "proj-teamx:execution:abc", "labels": ["proj-teamx", "Execution", "Run"],
                 "properties": {"kind": "notebook-cell", "backend": "mesh-k8s", "status": "dispatched",
                                "correlation_id": "exec-abc", "receipt_bundle": "/v1/receipts/lattice-studio/exec-abc",
                                "submitted_at": "t1"}},
            ], "edgeList": []}, None)
        return (None, "x")
    monkeypatch.setattr(srv, "_req", fake_req)

    r = client.post("/api/studio/execute",
                    json={"project": "team-x", "kind": "notebook-cell", "backend": "mesh-k8s",
                          "ref": "proj-teamx:notebook:1", "code": "df.show()"},
                    headers={"Authorization": "Bearer T"})
    b = r.json()
    assert r.status_code == 200 and b["status"] == "dispatched" and b["proof_carrying"]
    assert b["receipt"]["replayable"] and b["receipt"]["backend"] == "mesh-k8s"
    assert b["receipt"]["bundle_ref"].startswith("/v1/receipts/lattice-studio/")
    node = next(w for w in writes if "labels" in w)
    assert "Execution" in node["labels"] and node["properties"]["epistemic_mode"] == "attested"
    assert any(w.get("label") == "executed" and w.get("to") == "proj-teamx:notebook:1" for w in writes)

    # wildcard entitlement also works
    monkeypatch.setattr(srv, "STUDIO_COMPUTE_ENTITLEMENTS", "*")
    assert client.get("/api/studio/compute?project=anything").json()["entitled_any"] is True

    lst = client.get("/api/studio/executions?project=team-x").json()
    assert lst["count"] == 1 and lst["executions"][0]["backend"] == "mesh-k8s"


# ── WS#49: ontology actions + writeback (the Foundry crown jewel, beaten) ──
def _stateful_graph(seed=None):
    state = {"nodes": dict(seed or {}), "edges": []}

    async def fake_req(client, method, url, json=None):
        if "/api/graph/node" in url:
            state["nodes"][json["id"]] = json
            return ({"ok": True}, None)
        if "/api/graph/edge" in url:
            state["edges"].append(json)
            return ({"ok": True}, None)
        if "subgraph" in url:
            return ({"nodes": list(state["nodes"].values()), "edgeList": state["edges"]}, None)
        return (None, "x")
    return state, fake_req


def test_action_define_requires_token_and_effects(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "")
    assert client.post("/api/studio/action", json={"project": "team-x", "name": "approve", "target_type": "Order",
                                                    "effects": [{"op": "set_status", "value": "approved"}]}).status_code == 503
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "T")
    # no effects → 422
    assert client.post("/api/studio/action", json={"project": "team-x", "name": "x", "target_type": "Order"},
                       headers={"Authorization": "Bearer T"}).status_code == 422


def test_ontology_serves_real_classes_not_a_mock():
    b = client.get("/api/studio/ontology").json()
    assert b["counts"]["classes"] == 827                    # the real Ontogenesis corpus (+10 health classes, #936)
    assert b["base_iri"].endswith("ontogenesis#")
    assert any(c["iri"] == "upper:Entity" for c in b["classes"])           # upper ontology by default
    one = client.get("/api/studio/ontology?cls=ACSETAttr").json()
    props = {p["iri"] for p in one["class"]["inherited_properties"]}
    assert "acsetAttrName" in props and "attrType" in props                # real declared properties


def test_ontology_prefixes_expand_to_full_iris():
    """REGRESSION — the silent-wrong that disarmed SHACL: the generated index carried no prefix map, so
    expand() returned curies unexpanded and pyshacl targeted nothing (every writeback vacuously conformed).
    expand() must yield a real IRI for shape-constrained prefixes, whatever the index version."""
    from lattice_studio import ontology
    assert ontology.prefixes(), "prefix map must never be empty"
    expanded = ontology.expand("sp:Surface")
    assert expanded.startswith("http") and expanded.endswith("#Surface")


def test_action_define_rejects_non_ontology_class(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "T")
    r = client.post("/api/studio/action",
                    json={"project": "team-x", "name": "bogus", "target_type": "Order",
                          "effects": [{"op": "set_property", "property": "whatever", "value": "x"}]},
                    headers={"Authorization": "Bearer T"})
    assert r.status_code == 422
    assert "not an Ontogenesis class" in r.json()["detail"]["violations"][0]


def test_action_define_rejects_undeclared_property(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "T")
    r = client.post("/api/studio/action",
                    json={"project": "team-x", "name": "bad", "target_type": "ACSETAttr",
                          "effects": [{"op": "set_property", "property": "not_a_real_prop", "value": "x"}]},
                    headers={"Authorization": "Bearer T"})
    assert r.status_code == 422
    assert "not declared" in r.json()["detail"]["violations"][0]


def test_action_full_lifecycle_ontology_typed(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "T")
    # a target typed as the real ontology class ACSETAttr
    state, fake_req = _stateful_graph({
        "proj-teamx:attr:1": {"id": "proj-teamx:attr:1", "labels": ["proj-teamx", "ACSETAttr"],
                              "properties": {"acsetAttrName": "old", "status": "draft"}},
    })
    monkeypatch.setattr(srv, "_req", fake_req)

    # define — typed against ACSETAttr, effects use its REAL declared properties/relations
    d = client.post("/api/studio/action",
                    json={"project": "team-x", "name": "Rename attr", "target_type": "ACSETAttr",
                          "params": [{"name": "newname"}, {"name": "type_id"}],
                          "effects": [{"op": "set_property", "property": "acsetAttrName", "value_from": "newname"},
                                      {"op": "add_edge", "label": "attrType", "value_from": "type_id"},
                                      {"op": "set_status", "value": "reviewed"}]},
                    headers={"Authorization": "Bearer T"}).json()
    assert d["action_id"] == "proj-teamx:action:rename_attr" and d["ontology_typed"]
    assert d["class_iri"] == "ACSETAttr"

    # missing required arg → 422
    assert client.post("/api/studio/action/invoke",
                       json={"project": "team-x", "action": "Rename attr", "target": "proj-teamx:attr:1", "args": {}},
                       headers={"Authorization": "Bearer T"}).status_code == 422

    # invoke → governed writeback + receipt
    inv = client.post("/api/studio/action/invoke",
                      json={"project": "team-x", "action": "Rename attr", "target": "proj-teamx:attr:1",
                            "args": {"newname": "width", "type_id": "proj-teamx:acsettype:int"}},
                      headers={"Authorization": "Bearer T"}).json()
    assert inv["reversible"] and inv["receipt"]["replayable"]
    tgt = state["nodes"]["proj-teamx:attr:1"]["properties"]
    assert tgt["acsetAttrName"] == "width" and tgt["status"] == "reviewed"        # writeback applied
    assert tgt["epistemic_mode"] == "attested"                                    # proof-carrying
    assert any(e.get("label") == "attrType" and e.get("to") == "proj-teamx:acsettype:int" for e in state["edges"])

    aud = client.get("/api/studio/action/invocations?project=team-x").json()
    assert aud["count"] == 1 and aud["invocations"][0]["revoked"] is False

    # governed revoke → restores before-state
    rev = client.post("/api/studio/action/revoke", json={"project": "team-x", "invocation": inv["invocation_id"]},
                      headers={"Authorization": "Bearer T"}).json()
    assert rev["revoked"] and rev["restored_state"]
    tgt2 = state["nodes"]["proj-teamx:attr:1"]["properties"]
    assert tgt2["acsetAttrName"] == "old" and tgt2["status"] == "draft"           # fully restored
    aud2 = client.get("/api/studio/action/invocations?project=team-x").json()
    assert aud2["invocations"][0]["revoked"] is True


def test_action_invoke_shacl_rejects_nonconformant_writeback(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "T")
    # a target typed as sp:Surface — a class the real Ontogenesis shapes constrain (required props)
    state, fake_req = _stateful_graph({
        "proj-teamx:surface:1": {"id": "proj-teamx:surface:1", "labels": ["proj-teamx", "sp:Surface"],
                                 "properties": {}},   # missing every required property
    })
    monkeypatch.setattr(srv, "_req", fake_req)

    # define an action typed against sp:Surface (sp:homepageVisible is a real declared property)
    d = client.post("/api/studio/action",
                    json={"project": "team-x", "name": "Publish surface", "target_type": "sp:Surface",
                          "params": [{"name": "vis"}],
                          "effects": [{"op": "set_property", "property": "sp:homepageVisible", "value_from": "vis"}]},
                    headers={"Authorization": "Bearer T"}).json()
    assert d["ontology_typed"] and d["class_iri"] == "sp:Surface"

    # invoke → resulting node still misses required props → SHACL rejects the writeback (422), nothing committed
    r = client.post("/api/studio/action/invoke",
                    json={"project": "team-x", "action": "Publish surface", "target": "proj-teamx:surface:1",
                          "args": {"vis": "true"}},
                    headers={"Authorization": "Bearer T"})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert "SHACL" in detail["message"] and detail["class"] == "sp:Surface" and len(detail["violations"]) >= 1
    # fail-closed: the target was NOT mutated
    assert state["nodes"]["proj-teamx:surface:1"]["properties"] == {}


# ── WS#50: GAIA stewardship writeback + the epistemic invariant ──
def test_steward_human_decision_is_attested(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "T")
    state, fake_req = _stateful_graph({
        "proj-teamx:entity:1": {"id": "proj-teamx:entity:1", "labels": ["proj-teamx", "LIVING_ENTITY"],
                                "properties": {}},
    })
    monkeypatch.setattr(srv, "_req", fake_req)

    r = client.post("/api/studio/steward",
                    json={"project": "team-x", "target": "proj-teamx:entity:1", "keeper": "kim",
                          "phase": "maturity", "resolve_signals": ["stale_evidence"], "actor_kind": "human"},
                    headers={"Authorization": "Bearer T"}).json()
    assert r["proof_carrying"] and r["reversible"]
    assert r["epistemic_mode"] == "attested" and r["invariant_applied"] is None      # human → canonical
    assert r["state"]["keeper"] == "kim" and r["state"]["phase_override"] == "maturity"
    tgt = state["nodes"]["proj-teamx:entity:1"]["properties"]
    assert tgt["gaia_keeper"] == "kim" and tgt["gaia_phase_override"] == "maturity"
    assert tgt["gaia_phase_epistemic"] == "attested" and tgt["gaia_resolved_signals"] == "stale_evidence"


def test_steward_model_phase_is_derived_not_canonical(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "T")
    state, fake_req = _stateful_graph({
        "proj-teamx:entity:2": {"id": "proj-teamx:entity:2", "labels": ["proj-teamx", "LIVING_ENTITY"], "properties": {}},
    })
    monkeypatch.setattr(srv, "_req", fake_req)

    r = client.post("/api/studio/steward",
                    json={"project": "team-x", "target": "proj-teamx:entity:2", "phase": "decline", "actor_kind": "model"},
                    headers={"Authorization": "Bearer T"}).json()
    # GAIA invariant #2: a model may OBSERVE the phase but not PROMOTE it to canonical truth → derived
    assert r["epistemic_mode"] == "derived"
    assert r["invariant_applied"] and "GAIA-2" in r["invariant_applied"]
    assert state["nodes"]["proj-teamx:entity:2"]["properties"]["gaia_phase_epistemic"] == "derived"


def test_steward_validates_phase_and_signals(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "T")
    assert client.post("/api/studio/steward", json={"project": "team-x", "target": "x", "phase": "bogus"},
                       headers={"Authorization": "Bearer T"}).status_code == 422
    assert client.post("/api/studio/steward", json={"project": "team-x", "target": "x", "resolve_signals": ["nope"]},
                       headers={"Authorization": "Bearer T"}).status_code == 422


def test_steward_state_reads_back_and_derives_orphan(monkeypatch):
    import lattice_studio.server as srv

    async def fake_req(client, method, url, json=None):
        if "subgraph" in url:
            return ({"nodes": [
                {"id": "proj-teamx:entity:3", "labels": ["proj-teamx", "LIVING_ENTITY"],
                 "properties": {"gaia_keeper": "sam", "gaia_phase_override": "growth", "gaia_phase_epistemic": "attested"}},
            ], "edgeList": []}, None)   # no edges → orphaned
        return (None, "x")
    monkeypatch.setattr(srv, "_req", fake_req)

    b = client.get("/api/studio/steward?project=team-x&target=proj-teamx:entity:3").json()
    assert b["stewardship"]["keeper"] == "sam" and b["stewardship"]["phase_override"] == "growth"
    assert b["derived_signals"] == ["orphaned_artifact"] and b["degree"] == 0
    assert "maturity" in b["phases"]


# ── WS#51: GAIA World Model — world-signals + the promotion membrane as epistemic status ──
def test_worldsignal_submit_is_evidence_only_and_epistemic_maps(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "T")
    writes = []
    async def fake_req(client, method, url, json=None):
        if "/api/graph/node" in url or "/api/graph/edge" in url:
            writes.append(json); return ({"ok": True}, None)
        return (None, "x")
    monkeypatch.setattr(srv, "_req", fake_req)

    # human submit → observed (not canonical)
    h = client.post("/api/studio/worldsignal",
                    json={"project": "team-x", "feature_id": "foot-traffic-poi-42", "signal_type": "feature_registry",
                          "actor_kind": "human"}, headers={"Authorization": "Bearer T"}).json()
    assert h["promotion_state"] == "EvidenceOnly" and h["epistemic_mode"] == "observed"
    assert h["admissible_for_promotion"] is False                       # no evidence yet
    node = next(w for w in writes if "labels" in w)
    assert "WorldSignal" in node["labels"] and node["properties"]["gaia:hasPromotionState"] == "EvidenceOnly"

    # model submit → derived (a model observes, doesn't canonize)
    m = client.post("/api/studio/worldsignal",
                    json={"project": "team-x", "feature_id": "weather-x", "signal_type": "weather", "actor_kind": "model"},
                    headers={"Authorization": "Bearer T"}).json()
    assert m["epistemic_mode"] == "derived"


def test_worldsignal_shacl_rejects_incomplete_energy_ledger(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "T")
    async def fake_req(client, method, url, json=None):
        if "/api/graph/node" in url or "/api/graph/edge" in url: return ({"ok": True}, None)
        return (None, "x")
    monkeypatch.setattr(srv, "_req", fake_req)
    # energy_ledger requires gaia:hasMarginDelta + gaia:hasPerturbationFlipRate — we don't supply them → SHACL 422
    r = client.post("/api/studio/worldsignal",
                    json={"project": "team-x", "feature_id": "e1", "signal_type": "energy_ledger"},
                    headers={"Authorization": "Bearer T"})
    assert r.status_code == 422 and "GAIA shapes" in r.json()["detail"]["message"]


def test_worldsignal_model_cannot_promote_to_canonical(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "T")
    r = client.post("/api/studio/worldsignal/promote",
                    json={"project": "team-x", "signal": "s1", "to_state": "Promoted", "actor_kind": "model"},
                    headers={"Authorization": "Bearer T"})
    assert r.status_code == 403 and "invariant #2" in r.json()["detail"]["message"]


def test_worldsignal_promotion_admissibility_and_canonical(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "T")

    # a signal with NO evidence → cannot be Promoted
    state, fake_req = _stateful_graph({
        "proj-teamx:worldsignal:noev": {"id": "proj-teamx:worldsignal:noev", "labels": ["proj-teamx", "WorldSignal"],
                                        "properties": {"promotion_state": "EvidenceOnly", "evidence_refs": "[]", "actor_kind": "human"}},
        "proj-teamx:worldsignal:ok": {"id": "proj-teamx:worldsignal:ok", "labels": ["proj-teamx", "WorldSignal"],
                                     "properties": {"promotion_state": "EvidenceOnly",
                                                    "evidence_refs": "[\"proj-teamx:evidence:1\"]", "actor_kind": "human"}},
    })
    monkeypatch.setattr(srv, "_req", fake_req)

    r = client.post("/api/studio/worldsignal/promote",
                    json={"project": "team-x", "signal": "proj-teamx:worldsignal:noev", "to_state": "Promoted", "actor_kind": "human"},
                    headers={"Authorization": "Bearer T"})
    assert r.status_code == 422 and "source evidence" in r.json()["detail"]

    # a signal WITH evidence, promoted by a human → Promoted + attested + a DecisionLedgerEntry
    ok = client.post("/api/studio/worldsignal/promote",
                     json={"project": "team-x", "signal": "proj-teamx:worldsignal:ok", "to_state": "Promoted",
                           "policy_id": "policy/geo-v1", "actor_kind": "human"},
                     headers={"Authorization": "Bearer T"}).json()
    assert ok["to_state"] == "Promoted" and ok["epistemic_mode"] == "attested" and ok["canonical"]
    assert ok["receipt"]["replayable"]
    signal = state["nodes"]["proj-teamx:worldsignal:ok"]["properties"]
    assert signal["promotion_state"] == "Promoted" and signal["epistemic_mode"] == "attested"
    dec = next(w for w in state["nodes"].values() if "DecisionLedgerEntry" in (w.get("labels") or []))
    assert dec["properties"]["to_state"] == "Promoted"


def test_gaia_ontology_serves_the_three_twin_membrane():
    b = client.get("/api/studio/gaia/ontology").json()
    assert b["promotion_states"] == ["EvidenceOnly", "ReviewRequired", "Rejected", "Promoted"]
    prom = next(m for m in b["promotion_epistemic_membrane"] if m["state"] == "Promoted")
    assert prom["epistemic_human"] == "attested" and prom["canonical"]
    assert set(b["three_twins"]) >= {"knowledge", "human", "earth"}


def test_execute_spark_dispatches_to_runner_and_chains_receipt(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "T")
    monkeypatch.setattr(srv, "STUDIO_COMPUTE_ENTITLEMENTS", "team-x:spark")
    async def fake_req(client, method, url, json=None):
        if "/api/graph/node" in url or "/api/graph/edge" in url: return ({"ok": True}, None)
        return (None, "x")
    monkeypatch.setattr(srv, "_req", fake_req)

    async def fake_spark(sql, data, correlation):
        assert "select" in sql.lower() and len(data) == 3
        return {"rows": [{"n": 3}], "receipt": {"correlation_id": "spark-abc", "engine": "apache-spark"}}
    monkeypatch.setattr(srv, "_spark_submit", fake_spark)

    r = client.post("/api/studio/execute",
                    json={"project": "team-x", "kind": "query", "backend": "spark",
                          "code": "select count(*) n from t", "data": [{"x": 1}, {"x": 2}, {"x": 3}]},
                    headers={"Authorization": "Bearer T"}).json()
    assert r["status"] == "completed" and r["rows"] == [{"n": 3}]        # it actually ran on Spark
    assert r["spark_receipt"]["engine"] == "apache-spark"
    assert r["receipt"]["chained"] == "spark-abc"                        # receipt chained studio→spark-runner


def test_execute_spark_degrades_to_ledger_when_runner_absent(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "T")
    monkeypatch.setattr(srv, "STUDIO_COMPUTE_ENTITLEMENTS", "*")
    async def fake_req(client, method, url, json=None):
        if "/api/graph/node" in url: return ({"ok": True}, None)
        return (None, "x")
    monkeypatch.setattr(srv, "_req", fake_req)
    async def no_spark(sql, data, correlation): return None            # runner unreachable / no token
    monkeypatch.setattr(srv, "_spark_submit", no_spark)

    r = client.post("/api/studio/execute",
                    json={"project": "team-x", "kind": "query", "backend": "spark", "code": "select 1"},
                    headers={"Authorization": "Bearer T"}).json()
    assert r["status"] == "dispatched" and r["rows"] is None            # honest degrade to the governed ledger


# ── WS#52: HDT — the human twin (closes the triangle) ──
def test_hdt_observation_seeded_and_epistemic_maps(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "T")
    writes = []
    async def fake_req(client, method, url, json=None):
        if "/api/graph/node" in url or "/api/graph/edge" in url: writes.append(json); return ({"ok": True}, None)
        return (None, "x")
    monkeypatch.setattr(srv, "_req", fake_req)

    h = client.post("/api/studio/hdt/observation",
                    json={"project": "team-x", "subject": "proj-teamx:person:kim", "code": "8867-4",
                          "value": "72", "m_cbd": 0.8, "actor_kind": "human"},
                    headers={"Authorization": "Bearer T"}).json()
    assert h["omega_state"] == "SEEDED" and h["epistemic_mode"] == "observed"
    node = next(w for w in writes if "labels" in w)
    assert "HdtObservation" in node["labels"] and node["properties"]["hdt:hasOmegaState"] == "SEEDED"


def test_hdt_model_cannot_deliver_to_canonical(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "T")
    r = client.post("/api/studio/hdt/promote",
                    json={"project": "team-x", "observation": "o1", "to_state": "DELIVERED", "actor_kind": "model"},
                    headers={"Authorization": "Bearer T"})
    assert r.status_code == 403 and "DELIVER" in r.json()["detail"]["message"]


def test_hdt_promote_to_delivered_is_attested(monkeypatch):
    import lattice_studio.server as srv
    monkeypatch.setattr(srv, "STUDIO_WRITE_TOKEN", "T")
    state, fake_req = _stateful_graph({
        "proj-teamx:hdtobs:1": {"id": "proj-teamx:hdtobs:1", "labels": ["proj-teamx", "HdtObservation"],
                                "properties": {"omega_state": "TRUSTED", "actor_kind": "human", "subject": "p"}},
    })
    monkeypatch.setattr(srv, "_req", fake_req)
    r = client.post("/api/studio/hdt/promote",
                    json={"project": "team-x", "observation": "proj-teamx:hdtobs:1", "to_state": "DELIVERED", "actor_kind": "clinician"},
                    headers={"Authorization": "Bearer T"}).json()
    assert r["to_state"] == "DELIVERED" and r["epistemic_mode"] == "attested" and r["canonical"]
    obs = state["nodes"]["proj-teamx:hdtobs:1"]["properties"]
    assert obs["omega_state"] == "DELIVERED" and obs["epistemic_mode"] == "attested"
    ev = next(w for w in state["nodes"].values() if "EvaluationEvent" in (w.get("labels") or []))
    assert ev["properties"]["hdt:promotedToState"] == "DELIVERED"


def test_hdt_ontology_closes_the_three_twin_triangle():
    b = client.get("/api/studio/hdt/ontology").json()
    assert b["omega_states"] == ["ABSENT", "SEEDED", "NORMALIZED", "LINKED", "TRUSTED", "ACTIONABLE", "DELIVERED"]
    deliv = next(s for s in b["omega_epistemic_lattice"] if s["state"] == "DELIVERED")
    assert deliv["epistemic_human"] == "attested" and deliv["canonical"]
    assert set(b["three_twins_closed"]) >= {"knowledge", "human", "earth"}
    assert set(b["kfs_triad"]) == {"CBD", "CGT", "NHY"}
