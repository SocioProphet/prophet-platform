"""Entity Resolution engine — similarity, blocking, clustering, proof-carrying decisions."""
from fastapi.testclient import TestClient

from entity_resolution.resolver import Record, jaro_winkler, jaccard, score_pair, resolve
from entity_resolution.server import app

client = TestClient(app)


def test_jaro_winkler_and_jaccard():
    assert jaro_winkler("martha", "marhta") > 0.9        # classic JW example
    assert jaro_winkler("acme corp", "acme corp") == 1.0
    assert jaro_winkler("acme", "zzzz") < 0.5
    assert jaccard({"city": "NYC"}, {"city": "nyc"}) == 1.0   # normalized
    assert jaccard({"city": "NYC"}, {"city": "LA"}) == 0.0


def test_merge_verified_on_high_similarity():
    a = Record("1", "Acme Corporation", {"city": "New York"})
    b = Record("2", "Acme Corporation", {"city": "New York"})
    d = score_pair(a, b)
    assert d.decision == "MERGE_VERIFIED" and d.score >= 0.9
    assert "city" in d.evidence["matched_attributes"]        # proof-carrying evidence


def test_review_queue_on_middling_similarity():
    a = Record("1", "Jon Smith", {})
    b = Record("2", "John Smyth", {})
    d = score_pair(a, b)
    assert d.decision in ("REQUIRES_REVIEW", "MERGE_VERIFIED")  # near-dup names surface for review/merge


def test_hard_conflict_blocks_merge():
    # identical names but conflicting email → MERGE_BLOCKED even at high name similarity
    a = Record("1", "Jane Doe", {"email": "jane@a.com"})
    b = Record("2", "Jane Doe", {"email": "jane@b.com"})
    d = score_pair(a, b)
    assert d.decision == "MERGE_BLOCKED"
    assert d.evidence["conflict_field"] == "email"


def test_resolve_clusters_transitively():
    # A~B and B~C (all "Acme Corp") → one entity of 3 via union-find; a distinct "Globex" stays separate
    recs = [
        Record("a", "Acme Corp", {"city": "NYC"}),
        Record("b", "Acme Corp", {"city": "NYC"}),
        Record("c", "Acme Corp", {"city": "NYC"}),
        Record("d", "Globex LLC", {"city": "LA"}),
    ]
    out = resolve(recs)
    sizes = sorted(e["size"] for e in out["entities"])
    assert sizes == [1, 3]                                    # {a,b,c} merged, {d} alone
    assert out["merged"] == 1
    assert any(x["decision"] == "MERGE_VERIFIED" for x in out["decision_ledger"])


def test_resolve_endpoint():
    r = client.post("/resolve", json={"records": [
        {"id": "1", "name": "Acme Corp", "attributes": {"city": "NYC"}},
        {"id": "2", "name": "Acme Corp", "attributes": {"city": "NYC"}},
    ]})
    assert r.status_code == 200
    b = r.json()
    assert b["records"] == 2 and b["merged"] == 1
    assert b["decision_ledger"][0]["decision"] == "MERGE_VERIFIED"


def test_healthz():
    assert client.get("/healthz").json()["ok"] is True
