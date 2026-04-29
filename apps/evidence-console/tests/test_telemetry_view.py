from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app.telemetry_view as telemetry_view  # type: ignore


def test_get_recent_telemetry_view(monkeypatch):
    expected_items = [
        {
            "service": "telemetry-runtime",
            "correlation_id": "corr-123",
            "event_type": "reliability.conversation.stream.completed",
            "status": "recorded",
        }
    ]
    monkeypatch.setattr(telemetry_view.client, "get_recent_receipts", lambda service, limit=25: expected_items)
    payload = telemetry_view.get_recent_telemetry_view(service="telemetry-runtime", limit=7)
    assert payload["service"] == "telemetry-runtime"
    assert payload["items"] == expected_items
