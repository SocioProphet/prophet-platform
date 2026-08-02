from fastapi.testclient import TestClient

from app.backends import reset_academy_records
from app.metrics import reset
from app.main import app

client = TestClient(app)


def setup_function() -> None:
    reset_academy_records()


def academy_record() -> dict[str, object]:
    return {
        "header": {
            "object_id": "lsr_metrics_0001",
            "object_type": "LearningSearchRecord",
            "policy_tags": ["learning-loop", "search"],
        },
        "source": "ALEXANDRIAN_ACADEMY",
        "entity_type": "LEARNING_ACTION_EXPLANATION",
        "title": "Why recommended",
        "text": "Metrics smoke evidence explanation.",
        "target_ref": "llr_metrics_0001",
        "final_score": 1.0,
    }


def test_debug_metrics_reports_counters_without_sensitive_values() -> None:
    reset()
    assert client.post("/v1/search/ingest/academy", json=academy_record()).status_code == 200
    query_response = client.post(
        "/v0/search/query",
        json={
            "query_id": "q-metrics",
            "actor_id": "user-1",
            "text": "evidence",
            "mode": "HYBRID",
            "limit": 10,
            "scope": {"cloud_workspace": True, "local_desktop": False, "memory": False},
        },
    )
    assert query_response.status_code == 200

    response = client.get("/v1/search/debug/metrics")
    assert response.status_code == 200
    payload = response.json()
    metrics = payload["metrics"]
    assert metrics["academy_ingest_total"] == 1
    assert metrics["search_query_total"] == 1
    assert metrics["academy_result_total"] >= 1
    text = str(payload)
    assert "user-1" not in text
    assert "q-metrics" not in text
    assert "http://" not in text
    assert "https://" not in text
    assert "/tmp/" not in text


def restricted_academy_record() -> dict[str, object]:
    return {
        "header": {
            "object_id": "lsr_policy_gate_0001",
            "object_type": "LearningSearchRecord",
            "policy_tags": ["learning-loop", "search"],
        },
        "source": "ALEXANDRIAN_ACADEMY",
        "entity_type": "LEARNING_ACTION_EXPLANATION",
        "title": "Policy gate regression fixture",
        "text": "Policy gate deny-path evidence explanation.",
        "target_ref": "llr_policy_gate_0001",
        "visibility": {
            "allowed_actor_ids": ["allowed-user"],
            "allowed_workspace_ids": [],
            "allowed_jurisdiction_ids": [],
        },
        "final_score": 1.0,
    }


def _query(actor_id: str, query_id: str) -> None:
    response = client.post(
        "/v0/search/query",
        json={
            "query_id": query_id,
            "actor_id": actor_id,
            "text": "policy gate deny",
            "mode": "HYBRID",
            "limit": 10,
        },
    )
    assert response.status_code == 200


def test_policy_gate_fires_on_the_request_path_both_ways() -> None:
    # KMASS baseline (2026-08-01): all five policy_decision_* counters read 0
    # before AND after 30 real queries. The evaluator code (app/policy.py) was
    # correct and unit-tested in isolation, but nothing in the request path ever
    # reached it -- query_academy_records() returned [] before its internal
    # academy_record_visible() call (the one that actually invokes
    # academy_policy_evaluator.decide()) because SearchRequest.scope defaulted
    # to a value that disabled retrieval entirely. Fixing the scope default
    # (test_query_endpoint_omitting_scope_is_not_silently_disabled in
    # test_service_smoke.py) is what lets this evaluator run at all; this test
    # is the "prove teeth both ways" proof that it now does, for both verdicts.
    reset()
    assert client.post("/v1/search/ingest/academy", json=restricted_academy_record()).status_code == 200

    _query(actor_id="allowed-user", query_id="q-allow")
    allowed_metrics = client.get("/v1/search/debug/metrics").json()["metrics"]
    assert allowed_metrics["policy_decision_allow_total"] == 1
    assert allowed_metrics["policy_decision_deny_total"] == 0
    assert allowed_metrics["policy_decision_local_total"] == 1

    _query(actor_id="other-user", query_id="q-deny")
    denied_metrics = client.get("/v1/search/debug/metrics").json()["metrics"]
    assert denied_metrics["policy_decision_allow_total"] == 1
    assert denied_metrics["policy_decision_deny_total"] == 1
    assert denied_metrics["policy_decision_local_total"] == 2
