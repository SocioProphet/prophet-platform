"""GRLPlus service HTTP smoke — healthz, rules, and the graph-backed evaluate loop (mocked graph)."""
from fastapi.testclient import TestClient

from grlplus_service.server import app, gather_evidence

client = TestClient(app)


def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json()["ok"] is True


def test_rules_catalog():
    r = client.get("/grlplus/rules")
    b = r.json()
    assert "CR_MIN_EVIDENCE_LINK_1" in b["closure"] and "ER_CRITICAL_IMMEDIATE" in b["escalation"]


def test_gather_evidence_buckets_incident_edges():
    triples = [
        {"s": "goal.x", "p": "SUPPORTS", "o": "arg1"},
        {"s": "arg2", "p": "ARGUES_FOR", "o": "goal.x"},
        {"s": "goal.x", "p": "GROUNDS", "o": "doc1"},
        {"s": "goal.x", "p": "rdf:type", "o": "Goal"},      # skipped (type triple)
        {"s": "other", "p": "SUPPORTS", "o": "unrelated"},  # not incident → skipped
    ]
    ev = gather_evidence("goal.x", triples)
    assert ev.found is True
    assert ev.direct_arguments == 2 and ev.evidence_links == 1
    assert len(ev.atom_ids) == 3


def test_evaluate_degrades_gracefully_when_graph_unreachable():
    # hellgraph unreachable in test → no evidence → items stay keep_open (fail-safe), response still 200
    r = client.post("/grlplus/evaluate", json={"items": [
        {"element_id": "goal.launch_viability", "closure_rule_code": "CR_MIN_EVIDENCE_LINK_1"},
    ]})
    assert r.status_code == 200
    b = r.json()
    assert b["evaluated"] == 1 and b["closable"] == 0
    assert b["graph_degraded"] is not None            # honestly flags no-graph
    assert b["results"][0]["decision"] == "keep_open" and b["results"][0]["grounded"] is False


def test_evaluate_closes_with_graph_evidence(monkeypatch):
    import grlplus_service.server as srv

    async def fake_triples():
        return [
            {"s": "goal.launch", "p": "GROUNDS", "o": "doc1"},
            {"s": "arg1", "p": "SUPPORTS", "o": "goal.launch"},
            {"s": "arg2", "p": "ARGUES_FOR", "o": "goal.launch"},
        ], None
    monkeypatch.setattr(srv, "_fetch_triples", fake_triples)

    r = client.post("/grlplus/evaluate", json={"items": [
        {"element_id": "goal.launch", "closure_rule_code": "CR_MIN_DIRECT_ARGUMENT_2",
         "escalation_rule_code": "ER_MISSING_DIRECT_ARGUMENT_BLOCKS_CLOSURE"},
    ]})
    b = r.json()
    res = b["results"][0]
    assert res["decision"] == "close" and res["grounded"] is True
    assert res["evidence"]["direct_arguments"] == 2
    assert res["atoms"]  # provenance carried into the decision
