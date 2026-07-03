"""Smoke tests for the Regis/ACR API service — the deployable runtime for regis-entity-graph."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from regis_acr_api.main import app  # noqa: E402

client = TestClient(app)


def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body.get("service") == "regis-acr-api"


def test_source_record_ingest_emits_receipt():
    r = client.post(
        "/v1/source-records",
        json={
            "source_record_id": "sr-001",
            "source_system": "test",
            "raw_payload": {"name": "Example Org"},
        },
    )
    assert r.status_code == 200
    body = r.json()
    # every material op emits a platform-conformant receipt (correlation + receipt_ref)
    assert "receipt_ref" in body or "receipt" in body or "correlation_id" in body


def test_promotion_evaluate():
    r = client.post(
        "/v1/promotion/evaluate",
        json={"candidate_id": "c-1", "top_score": 0.9, "runnerup_score": 0.2},
    )
    assert r.status_code == 200
