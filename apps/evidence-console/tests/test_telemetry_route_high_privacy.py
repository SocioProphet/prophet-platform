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


def _emit_high_privacy_bundle(tmp_path: Path) -> None:
    script = f'''
import sys
sys.path.insert(0, {str(EVIDENCE_RECEIPTS_ROOT)!r})
from app.telemetry_runtime import emit_event_bundle

emit_event_bundle(
    "telemetry-runtime",
    "analytics.citations.rendered.summary",
    {{
        "local_turn_id": "turn-high-privacy-route-001",
        "citations_rendered_count": 4,
        "enhanced_citations_present": True,
        "sources_footer_present": True,
        "subject_ref": "turn://turn-high-privacy-route-001",
        "created_at": "2026-04-25T14:30:00+00:00",
    }},
    control_snapshot={{"product_analytics": "high_privacy"}},
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
        event_path = event_dir / f"{correlation_id}.event.json"
        event = json.loads(event_path.read_text(encoding="utf-8")) if event_path.exists() else {}
        payload_path = payload_dir / f"{correlation_id}.payload.json"
        items.append({
            "service": service,
            "correlation_id": correlation_id,
            "created_at": receipt.get("created_at") or event.get("created_at"),
            "status": receipt.get("status"),
            "action": receipt.get("action"),
            "event_type": event.get("event_type"),
            "subject_ref": receipt.get("subject_ref") or event.get("subject_ref"),
            "receipt_ref": f"file://{receipt_path.resolve()}",
            "event_ref": f"file://{event_path.resolve()}" if event_path.exists() else None,
            "payload_ref": f"file://{payload_path.resolve()}" if payload_path.exists() else None,
        })
    items.sort(key=lambda item: datetime.fromisoformat(str(item["created_at"]).replace("Z", "+00:00")), reverse=True)
    return items[:limit]


def test_telemetry_route_reflects_high_privacy_block(monkeypatch, tmp_path):
    _emit_high_privacy_bundle(tmp_path)

    def recent(service: str, limit: int = 25):
        return _read_recent_from_state(tmp_path, service=service, limit=limit)

    monkeypatch.setattr(main.service.telemetry_view.client, "get_recent_receipts", recent)
    monkeypatch.setattr(main.service.client, "get_recent_receipts", recent)

    resp = client.get("/v1/console/telemetry?service_name=telemetry-runtime&limit=10")
    assert resp.status_code == 200
    payload = resp.json()
    items = payload["items"]
    assert len(items) == 1
    item = items[0]
    assert item["event_type"] == "analytics.citations.rendered.summary"
    assert item["status"] == "blocked"
    assert item["action"] == "BLOCK"
