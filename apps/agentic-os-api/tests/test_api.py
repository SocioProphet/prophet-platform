"""Tests for the Agentic OS coordination API."""
from fastapi.testclient import TestClient

from app.data import READINESS_DIMS
from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_opportunities_conform_to_contract():
    r = client.get("/opportunities")
    assert r.status_code == 200
    opps = r.json()["opportunities"]
    assert len(opps) >= 2
    for o in opps:
        assert o["type"] == "Opportunity"
        assert o["id"].startswith("urn:srcos:opportunity:")
        # Composes over workspace + carries the Telos.
        assert o["workroomRef"].startswith("workroom://")
        assert set(o["telos"]) == {"objective", "constraints"}


def test_opportunity_detail_has_readiness_and_cadence():
    r = client.get("/opportunities/health-devsecops")
    assert r.status_code == 200
    body = r.json()
    rd = body["readiness"]
    assert rd["type"] == "ReadinessScore"
    assert set(rd["dimensions"]) == set(READINESS_DIMS)
    assert rd["total"] == 18 and rd["readinessPct"] == 50 and rd["rag"] == "Amber"
    assert body["cadence"]["currentWeek"] == 4


def test_pods_align_to_choir():
    pods = client.get("/pods").json()["pods"]
    assert all(p["id"].startswith("urn:srcos:agent-pod:") for p in pods)
    assert any(p["choirRole"] == "governance-sentinel" for p in pods)


def test_missing_opportunity_404():
    assert client.get("/opportunities/nope").status_code == 404
