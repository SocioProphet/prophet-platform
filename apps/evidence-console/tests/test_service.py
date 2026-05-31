from __future__ import annotations

import app.service as service


def test_frontier_view_selects_latest_frontier_and_provenance(monkeypatch):
    items = [
        {"service": "eval-fabric-api", "correlation_id": "c1", "event_type": "eval.fabric.frontier.provenance.read", "created_at": "2026-04-14T00:00:00+00:00"},
        {"service": "eval-fabric-api", "correlation_id": "c2", "event_type": "eval.fabric.frontier.read", "created_at": "2026-04-14T00:01:00+00:00"},
    ]
    bundles = {
        "c1": {"event": {"event_type": "eval.fabric.frontier.provenance.read"}},
        "c2": {"event": {"event_type": "eval.fabric.frontier.read"}},
    }
    monkeypatch.setattr(service.client, "get_recent_receipts", lambda service, limit=20: items)
    monkeypatch.setattr(service.client, "get_bundle", lambda service, correlation_id: bundles[correlation_id])
    view = service.get_frontier_view(limit=10)
    assert view["frontier"]["event"]["event_type"] == "eval.fabric.frontier.read"
    assert view["provenance"]["event"]["event_type"] == "eval.fabric.frontier.provenance.read"
    assert len(view["recent"]) == 2


def test_model_view_filters_by_subject(monkeypatch):
    items = [
        {"service": "eval-fabric-api", "correlation_id": "d1", "event_type": "eval.fabric.dossier.read", "subject_ref": "model://model.semantic-stack.2026-04-05", "created_at": "2026-04-14T00:01:00+00:00"},
        {"service": "eval-fabric-api", "correlation_id": "a1", "event_type": "eval.fabric.attribution.read", "subject_ref": "model://model.semantic-stack.2026-04-05", "created_at": "2026-04-14T00:00:00+00:00"},
        {"service": "eval-fabric-api", "correlation_id": "x1", "event_type": "eval.fabric.dossier.read", "subject_ref": "model://other", "created_at": "2026-04-13T00:00:00+00:00"},
    ]
    monkeypatch.setattr(service.client, "get_recent_receipts", lambda service, limit=20: items)
    monkeypatch.setattr(service.client, "get_bundle", lambda service, correlation_id: {"correlation_id": correlation_id})
    view = service.get_model_view("model.semantic-stack.2026-04-05", limit=10)
    assert view["dossier"]["correlation_id"] == "d1"
    assert view["attribution"]["correlation_id"] == "a1"
    assert len(view["recent"]) == 2


def test_fogstack_validation_view_groups_latest_by_bundle(monkeypatch):
    items = [
        {"service": "fogstack-validation", "correlation_id": "a-new", "event_type": "fogstack.validation.record.emitted", "subject_ref": "bundle://fogstack.access@0.1.0", "created_at": "2026-04-14T00:02:00+00:00"},
        {"service": "fogstack-validation", "correlation_id": "a-old", "event_type": "fogstack.validation.record.emitted", "subject_ref": "bundle://fogstack.access@0.1.0", "created_at": "2026-04-14T00:01:00+00:00"},
        {"service": "fogstack-validation", "correlation_id": "k1", "event_type": "fogstack.validation.record.emitted", "subject_ref": "bundle://fogstack.knowledge@0.1.0", "created_at": "2026-04-14T00:00:00+00:00"},
    ]
    monkeypatch.setattr(service.client, "get_recent_receipts", lambda service, limit=20: items)
    monkeypatch.setattr(service.client, "get_bundle", lambda service, correlation_id: {"correlation_id": correlation_id})
    view = service.get_fogstack_validation_view(limit=10)
    assert [item["correlation_id"] for item in view["latest_by_bundle"]] == ["a-new", "k1"]
    assert [item["correlation_id"] for item in view["recent"]] == ["a-new", "a-old", "k1"]


def test_recent_events_merges_and_sorts(monkeypatch):
    monkeypatch.setattr(service.client, "get_services", lambda: ["eval-fabric-api", "lampstand"])
    monkeypatch.setattr(service.client, "get_recent_receipts", lambda service, limit=15: [
        {"service": service, "correlation_id": service + "-1", "created_at": "2026-04-14T00:01:00+00:00" if service == "eval-fabric-api" else "2026-04-14T00:00:00+00:00"}
    ])
    view = service.get_recent_events_view(limit=10, per_service_limit=5)
    assert view["services"] == ["eval-fabric-api", "lampstand"]
    assert view["items"][0]["service"] == "eval-fabric-api"
