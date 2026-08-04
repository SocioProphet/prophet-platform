"""HTTP-surface tests for the identity-twin service — prove the endpoints wire the vendored twin
correctly: attest→verify roundtrip, forged/malformed proofs rejected (fail-closed), recall
fidelity, the medium fingerprint moving on every write, the interferometric diff, and the
'fringes not scores' read."""
from __future__ import annotations

import pytest

pytest.importorskip("numpy")
pytest.importorskip("cryptography")
pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from app.core import TwinService
from app.main import app, get_service


@pytest.fixture()
def client():
    # A fresh sealed sovereign core per test → isolated, order-independent state.
    svc = TwinService(seed=bytes(range(32)))
    app.dependency_overrides[get_service] = lambda: svc
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["records"] == 0


def test_attest_then_verify_roundtrips(client):
    r = client.post("/attest", json={"context": "alice#reputation", "value": "score=0.9"})
    assert r.status_code == 200
    ref = r.json()
    assert ref["records"] == 1 and ref["proof"] and ref["context"] == "alice#reputation"
    v = client.post("/verify", json={
        "context": ref["context"], "proof": ref["proof"], "verify_key": ref["verify_key"]})
    assert v.status_code == 200 and v.json()["verified"] is True


def test_forged_proof_is_rejected(client):
    ref = client.post("/attest", json={"context": "bob#endorsement", "value": "ok"}).json()
    forged = "00" * (len(ref["proof"]) // 2)
    v = client.post("/verify", json={
        "context": ref["context"], "proof": forged, "verify_key": ref["verify_key"]})
    assert v.status_code == 200 and v.json()["verified"] is False


def test_malformed_proof_fails_closed(client):
    ref = client.post("/attest", json={"context": "c", "value": "v"}).json()
    v = client.post("/verify", json={
        "context": "c", "proof": "zznothex", "verify_key": ref["verify_key"]})
    assert v.status_code == 200 and v.json()["verified"] is False


def test_recall_fidelity_high_for_true_value_low_for_wrong(client):
    client.post("/attest", json={"context": "carol#claim", "value": "the-true-value"})
    good = client.post("/recall", json={"context": "carol#claim", "value": "the-true-value"}).json()
    bad = client.post("/recall", json={"context": "carol#claim", "value": "a-different-value"}).json()
    assert good["matches"] is True and good["fidelity"] > 0.9
    assert bad["matches"] is False and bad["fidelity"] < 0.5


def test_recall_unknown_context_is_404(client):
    r = client.post("/recall", json={"context": "nobody", "value": "x"})
    assert r.status_code == 404


def test_medium_digest_moves_on_every_write(client):
    empty = client.get("/medium").json()
    assert empty["records"] == 0
    d1 = client.post("/attest", json={"context": "k1", "value": "v1"}).json()["medium_digest"]
    d2 = client.post("/attest", json={"context": "k2", "value": "v2"}).json()["medium_digest"]
    assert d1 != d2  # holographic: every write perturbs the global fingerprint
    assert client.get("/medium").json()["digest"] == d2


def test_diff_detects_movement_between_snapshots(client):
    d1 = client.post("/attest", json={"context": "k1", "value": "v1"}).json()["medium_digest"]
    client.post("/attest", json={"context": "k2", "value": "v2"})
    diff = client.post("/diff", json={"from_digest": d1}).json()
    assert diff["changed"] is True
    assert diff["moved_components"] > 0 and diff["phase_energy"] > 0.0


def test_diff_unknown_snapshot_is_404(client):
    client.post("/attest", json={"context": "k1", "value": "v1"})
    r = client.post("/diff", json={"from_digest": "ab" * 32})
    assert r.status_code == 404


def test_interfere_is_score_blind_but_fringe_visible(client):
    r = client.post("/interfere", json={
        "value": "same-value", "context_a": "prov-A", "context_b": "prov-B"}).json()
    # Same value, two provenances: a scalar score can't tell them apart; the fringe can.
    assert r["score_blind"] is True and r["magnitude_similarity"] > 0.999
    assert r["fringe_visible"] is True and r["provenance_moved"] is True and r["phase_energy"] > 0.0
