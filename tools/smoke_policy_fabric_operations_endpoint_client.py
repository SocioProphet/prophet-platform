#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

RECOMMENDATION = {
    "recommendation_id": "oprec-live-endpoint-smoke",
    "risk_level": "low",
    "requested_outcome": "allow",
    "subject": {"id": "service-1", "type": "service", "name": "service-1"},
    "action": {"type": "restart", "intent": "restore health", "description": "restart service"},
    "policy_refs": ["policy://operations/default-action-gates/v1"],
}


class Handler(BaseHTTPRequestHandler):
    requests: list[dict[str, Any]] = []

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/operations/action-decision":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length).decode("utf-8"))
        Handler.requests.append(body)
        rec = body["recommendation"]
        decision = {
            "kind": "ProphetOperationsActionDecision",
            "schema_version": "v1",
            "decision_id": "opdec-live-endpoint-smoke",
            "decided_at": "2026-04-26T00:00:00+00:00",
            "recommendation_ref": rec["recommendation_id"],
            "subject": rec["subject"],
            "proposed_action": rec["action"],
            "decision": {"outcome": "manual_review", "reason": "mock_endpoint_report_only", "risk_level": rec["risk_level"], "expires_at": None},
            "basis": {"policy_refs": rec["policy_refs"], "signal_refs": [], "evidence_refs": []},
            "controls": {"requires_human_approval": True, "requires_change_window": False, "rollback_required": False},
            "audit": {"actor": "mock-policy-fabric", "mode": "automated", "notes": "smoke"},
        }
        payload = json.dumps(decision, sort_keys=True).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        recommendation_path = tmp / "recommendation.json"
        output_path = tmp / "decision.json"
        recommendation_path.write_text(json.dumps(RECOMMENDATION, indent=2) + "\n", encoding="utf-8")

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base_url = f"http://127.0.0.1:{server.server_port}"
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "request_policy_fabric_operations_decision.py"),
                    "--endpoint",
                    base_url,
                    "--recommendation",
                    str(recommendation_path),
                    "--mode",
                    "report_only",
                    "--output",
                    str(output_path),
                ],
                cwd=ROOT,
                check=True,
            )
        finally:
            server.shutdown()
            thread.join(timeout=5)

        decision = json.loads(output_path.read_text(encoding="utf-8"))
        request = Handler.requests[0] if Handler.requests else {}
        checks = {
            "request_seen": len(Handler.requests) == 1,
            "request_mode_report_only": request.get("mode") == "report_only",
            "request_recommendation_preserved": request.get("recommendation", {}).get("recommendation_id") == RECOMMENDATION["recommendation_id"],
            "decision_kind": decision.get("kind") == "ProphetOperationsActionDecision",
            "recommendation_ref": decision.get("recommendation_ref") == RECOMMENDATION["recommendation_id"],
            "manual_review": decision.get("decision", {}).get("outcome") == "manual_review",
            "requires_human": decision.get("controls", {}).get("requires_human_approval") is True,
        }
        ok = all(checks.values())
        print(json.dumps({"ok": ok, "checks": checks, "decision": decision}, indent=2, sort_keys=True))
        return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
