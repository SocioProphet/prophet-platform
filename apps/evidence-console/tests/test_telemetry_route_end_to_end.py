from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parents[1]
EVIDENCE_RECEIPTS_ROOT = REPO_ROOT / "apps" / "evidence-receipts"
sys.path.insert(0, str(ROOT))

import app.main as main  # type: ignore

client = TestClient(main.app)


def _emit_reference_bundles(tmp_path: Path) -> None:
    script = f'''
import sys
sys.path.insert(0, {str(EVIDENCE_RECEIPTS_ROOT)!r})
from app.telemetry_runtime import emit_event_bundle

emit_event_bundle(
    "telemetry-runtime",
    "analytics.turn.rendered.summary",
    {{
        "local_turn_id": "turn-analytics-001",
        "turn_has_citations": True,
        "citations_rendered_count": 2,
        "source_footer_seen": True,
        "citation_panel_opened_during_turn": False,
        "subject_ref": "turn://turn-analytics-001",
        "created_at": "2026-04-25T14:10:00+00:00",
    }},
    control_snapshot={{"product_analytics": "disabled"}},
)

emit_event_bundle(
    "telemetry-runtime",
    "reliability.conversation.stream.completed",
    {{
        "request_id": "req-reliability-001",
        "local_turn_id": "turn-reliability-001",
        "duration_ms_bucket": 4200,
        "stream_transport": "sse_like",
        "completion_status": "clean_final_message",
        "subject_ref": "turn://turn-reliability-001",
        "created_at": "2026-04-25T14:11:00+00:00",
    }},
    control_snapshot={{"product_analytics": "disabled"}},
)
'''
    env = os.environ.copy()
    env["SOCIOPROFIT_STATE_HOME"] = str(tmp_path)
    subprocess.run([sys.executable, "-c", script], cwd=REPO_ROOT, check=True, env=env)


def _read_recent_from_state(tmp_path: Path, service: str, limit: int = 25) -> list[dict]:
    base = tmp_path / "prophet-platform"
    receipt_dir = base / "receipts" / service
    event_dir = base / "events" / service
    payload_dir = base / "payloads" / service
    items: list[dict] = []
    if not receipt_dir.exists():
        return items
    for receipt_path in receipt_dir.glob("*.receipt.json"):
        correlation_id = receipt_path.name[: -len(".receipt.json")]
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        event_path = event_dir / f"{{correlation_id}}.event.json"
        event = json.loads(event_path.read_text(encoding="utf-8")) if event_path.exists() else {{}}
        payload_path = payload_dir / f"{{correlation_id}}.payload.json"
        items.append({{
            "service": service,
            "correlation_id": correlation_id,
            "created_at": receipt.get("created_at") or event.get("created_at"),
            "status": receipt.get("status"),
            "action": receipt.get("action"),
            "event_type": event.get("event_type"),
            "subject_ref": receipt.get("subject_ref") or event.get("subject_ref"),
            "receipt_ref": f"file://{{receipt_path.resolve()}}",
            "event_ref": f"file://{{event_path.resolve()}}" if event_path.exists() else None,
            "payload_ref": f"file://{{payload_path.resolve()}}" if payload_path.exists() else None,
        }})
    items.sort(key=lambda item: datetime.fromisoformat(str(item["created_at"]).replace("Z", "+00:00")), reverse=True)
    return items[:limit]


def test_telemetry_route_reflects_blocked_optional_analytics_and_allowed_reliability(monkeypatch, tmp_path):
    _emit_reference_bundles(tmp_path)

    def recent(service: str, limit: int = 25):
        return _read_recent_from_state(tmp_path, service=service, limit=limit)

    monkeypatch.setattr(main.service.telemetry_view.client, "get_recent_receipts", recent)
    monkeypatch.setattr(main.service.client, "get_recent_receipts", recent)

    resp = client.get("/v1/console/telemetry?service_name=telemetry-runtime&limit=10")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["service"] == "telemetry-runtime"
    items = payload["items"]
    assert len(items) == 2

    by_event = {{item["event_type"]: item for item in items}}
    assert by_event["analytics.turn.rendered.summary"]["status"] == "blocked"
    assert by_event["analytics.turn.rendered.summary"]["action"] == "BLOCK"
    assert by_event["reliability.conversation.stream.completed"]["status"] == "recorded"
    assert by_event["reliability.conversation.stream.completed"]["action"] == "TRANSFORM_ALLOW"
