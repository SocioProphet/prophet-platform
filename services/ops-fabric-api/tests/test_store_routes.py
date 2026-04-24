from fastapi.testclient import TestClient

from app.main import app
from app.store import store

client = TestClient(app)


def setup_function() -> None:
    store.events.clear()
    store.proposals.clear()


def sample_payload() -> dict[str, object]:
    return {
        "target": {"kind": "Workload", "id": "sample-workload", "namespace": "default", "cluster": "p0-lab", "zone": "local"},
        "observed_at": "2026-04-24T17:45:00Z",
        "cpu_request_millicores": 1000,
        "cpu_p95_millicores": 220,
        "memory_request_mib": 2048,
        "memory_p95_mib": 620,
        "monthly_cost_usd": 96.0,
        "evidence_refs": [
            {
                "evidence_id": "evidence.metric-window.0001",
                "kind": "METRIC_WINDOW",
                "source": "synthetic-v0",
                "uri": "memory://ops-fixtures/metric-window/0001",
                "observed_at": "2026-04-24T17:45:00Z"
            }
        ],
        "intelligence_refs": [
            {
                "intelligence_id": "gdi.profile.operational-exhaust-fusion.v0",
                "profile_ref": "profiles/operational-exhaust-fusion-profile.v0.yaml",
                "kind": "OPERATIONAL_EXHAUST_FUSION",
                "confidence": 0.7
            }
        ]
    }


def test_rightsize_route_stores_and_retrieves_proposal() -> None:
    response = client.post("/v1/ops/proposals/rightsize", json=sample_payload())
    assert response.status_code == 200
    proposal_id = response.json()["proposal_id"]

    list_response = client.get("/v1/ops/proposals")
    assert list_response.status_code == 200
    assert list_response.json()[0]["proposal_id"] == proposal_id

    get_response = client.get(f"/v1/ops/proposals/{proposal_id}")
    assert get_response.status_code == 200
    assert get_response.json()["autonomy_tier"] == "REPORT_ONLY"


def test_search_records_include_ops_fabric_proposal_record() -> None:
    client.post("/v1/ops/proposals/rightsize", json=sample_payload())
    response = client.get("/v1/ops/search-records")
    assert response.status_code == 200
    body = response.json()
    assert body[0]["source"] == "OPS_FABRIC"
    assert body[0]["entity_type"] == "ACTION_PROPOSAL"
    assert body[0]["intelligence_ref_ids"] == ["gdi.profile.operational-exhaust-fusion.v0"]
