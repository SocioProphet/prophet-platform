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
BUNDLE = ROOT / "examples" / "operations" / "prophet_operations_evidence_bundle_with_policy_decision_links_0001.json"


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
            "decision_id": "opdec-guarded-workflow-smoke",
            "decided_at": "2026-04-26T00:00:00+00:00",
            "recommendation_ref": rec["recommendation_id"],
            "subject": rec["subject"],
            "proposed_action": rec["action"],
            "decision": {"outcome": "manual_review", "reason": "mock_endpoint_report_only", "risk_level": "high", "expires_at": None},
            "basis": {"policy_refs": ["policy://operations/default-action-gates/v1"], "signal_refs": [], "evidence_refs": []},
            "controls": {"requires_human_approval": True, "requires_change_window": False, "rollback_required": False},
            "audit": {"actor": "mock-policy-fabric", "mode": "automated", "notes": "guarded smoke"},
        }
        payload = json.dumps(decision, sort_keys=True).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        workdir = Path(td)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base_url = f"http://127.0.0.1:{server.server_port}"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "run_policy_fabric_guarded_operations_validation.py"),
                    "--endpoint",
                    base_url,
                    "--bundle",
                    str(BUNDLE),
                    "--mode",
                    "report_only",
                    "--workdir",
                    str(workdir),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=True,
            )
        finally:
            server.shutdown()
            thread.join(timeout=5)

        output = json.loads(result.stdout)
        decision_path = Path(output["decision_path"])
        report_path = Path(output["report_path"])
        report = json.loads(report_path.read_text(encoding="utf-8"))
        checks = {
            "request_seen": len(Handler.requests) == 1,
            "request_mode_report_only": Handler.requests[0].get("mode") == "report_only",
            "ok": output.get("ok") is True,
            "no_remediation_execution": output.get("executed_remediation") is False,
            "decision_path_exists": decision_path.exists(),
            "report_path_exists": report_path.exists(),
            "blocked_count_one": report.get("summary", {}).get("blocked_count") == 1,
            "executable_count_zero": report.get("summary", {}).get("executable_count") == 0,
            "manual_review_blocked": report.get("blocked_recommendations") == [{"recommendation_id": "oprec-worker-1-isolate", "outcome": "manual_review"}],
        }
        ok = all(checks.values())
        print(json.dumps({"ok": ok, "checks": checks, "output": output}, indent=2, sort_keys=True))
        return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
