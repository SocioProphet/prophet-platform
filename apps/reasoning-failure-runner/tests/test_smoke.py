"""Service smoke: healthz, suite listing, and an experiment over the HTTP surface."""
from __future__ import annotations

from fastapi.testclient import TestClient

from reasoning_failure_runner.server import app

client = TestClient(app)


def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "suite:tool-empty-200" in body["suites"]


def test_list_suites():
    r = client.get("/v1/suites")
    assert r.status_code == 200
    assert len(r.json()["suites"]) >= 3


def test_run_builtin_suite_over_http():
    r = client.post("/v1/experiments/run", json={"suite_id": "suite:tool-empty-200"})
    assert r.status_code == 200
    roll = r.json()
    assert roll["silent_failure_rate"] == 1.0
    assert roll["passed"] is False
    assert len(roll["receipts"]) == 3


def test_unknown_suite_404():
    r = client.post("/v1/experiments/run", json={"suite_id": "suite:nope"})
    assert r.status_code == 404


def test_oracles_invariant_names():
    from reasoning_failure_runner.oracles import ORACLES
    assert set(ORACLES) == {"exactString", "grounded", "non-fabricated", "revoked-not-served"}
