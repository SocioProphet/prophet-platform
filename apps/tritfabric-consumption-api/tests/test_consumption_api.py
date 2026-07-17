"""tritfabric-consumption-api smoke — the readiness surfaces load their contract and stay non-mutating."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # import main.py
from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app)


def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json()["ok"] is True
    assert r.json()["mutation_authorized"] is False


def test_summary_lists_all_four_surfaces_non_mutating():
    r = client.get("/tritfabric")
    assert r.status_code == 200
    body = r.json()
    assert body["mutation_authorized"] is False and body["runtime_execution_authorized"] is False
    ids = {s["surface"]["id"] for s in body["surfaces"]}
    assert {"community-learning-intake", "network-atlas-framework-catalog",
            "model-card-promotion-evidence", "serve-readiness"} <= ids


def test_serve_readiness_does_not_claim_production():
    r = client.get("/tritfabric/serve-readiness")
    assert r.status_code == 200 and r.json()["serve_deployment"] is False
