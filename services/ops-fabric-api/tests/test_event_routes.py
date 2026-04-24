from fastapi.testclient import TestClient

from app.main import app
from app.store import store

client = TestClient(app)


def setup_function() -> None:
    store.events.clear()
    store.proposals.clear()


def event_payload() -> dict[str, object]:
    return {
        "event_id": "ops.event.0001",
        "event_type": "WORKLOAD_RESOURCE_SAMPLE",
        "observed_at": "2026-04-24T17:45:00Z",
        "subject": {"kind": "Workload", "id": "sample-workload", "namespace": "default", "cluster": "p0-lab", "zone": "local"},
        "source": {"system": "synthetic-v0", "adapter": "ops-fabric-test"},
        "measurements": {"cpu_request_millicores": 1000, "cpu_p95_millicores": 220},
        "evidence_refs": [
            {
                "evidence_id": "evidence.event.0001",
                "kind": "METRIC_WINDOW",
                "source": "synthetic-v0",
                "uri": "memory://ops-fixtures/event/0001",
                "observed_at": "2026-04-24T17:45:00Z"
            }
        ],
        "intelligence_refs": []
    }


def test_event_route_stores_and_lists_event() -> None:
    response = client.post("/v1/ops/events", json=event_payload())
    assert response.status_code == 200
    assert response.json()["event_id"] == "ops.event.0001"

    list_response = client.get("/v1/ops/events")
    assert list_response.status_code == 200
    assert list_response.json()[0]["event_type"] == "WORKLOAD_RESOURCE_SAMPLE"


def test_search_records_include_event_record() -> None:
    client.post("/v1/ops/events", json=event_payload())
    response = client.get("/v1/ops/search-records")
    assert response.status_code == 200
    body = response.json()
    assert body[0]["source"] == "OPS_FABRIC"
    assert body[0]["entity_type"] == "TELEMETRY_EVENT"
    assert body[0]["evidence_ref_ids"] == ["evidence.event.0001"]
