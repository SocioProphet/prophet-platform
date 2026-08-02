#!/usr/bin/env python3
"""Alertmanager webhook sink: the estate's terminal receiver.

Until this existed, Alertmanager's only receiver was literally named "null".
Every alert in the estate -- including the ones that page for data loss --
was routed to a receiver that discards. The stack reported healthy the whole
time, because "delivered to null" and "delivered" are the same code path.

What this does
--------------
Accepts Alertmanager webhook POSTs and turns each one into an EvidenceReceipt
(contracts/EvidenceReceipt.v0.1.json) written as one JSON line to stdout.
Pod stdout is collected by fluentbit-gke and lands in Google Cloud Logging,
which is the estate's only working log sink -- Loki is deployed but has zero
ingested bytes and nothing ships to it.

Why this is not just another silent hop
---------------------------------------
Delivery is proven continuously, not asserted. kube-prometheus-stack ships a
`Watchdog` alert that fires permanently by design. It is routed here, so this
process receives a heartbeat every repeat_interval forever. The counter
`alert_sink_notifications_total` therefore MUST keep rising. If it stops, the
delivery path is broken, and `AlertDeliveryDead` fires on that absence.

That inverts the failure mode. A silent sink is not "no alerts today" -- it is
itself an alert.

Bounds
------
No unbounded state. Counters are integers; the /recent buffer is a fixed-size
ring (RING_MAX). Request bodies are capped at MAX_BODY bytes. Nothing is
retained on disk by this process; durability is Cloud Logging's job.

Refusals are loud
-----------------
A malformed payload is NOT swallowed. It increments alert_sink_errors_total,
emits a receipt with status="failed", and returns 400. An error the sink
absorbs quietly would reproduce the defect this exists to fix.
"""

from __future__ import annotations

import collections
import hashlib
import json
import os
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = "0.1"
SERVICE_REF = "infra/k8s/alert-delivery"
PORT = int(os.environ.get("PORT", "9095"))
MAX_BODY = int(os.environ.get("MAX_BODY_BYTES", str(2 * 1024 * 1024)))
RING_MAX = int(os.environ.get("RECENT_RING", "50"))
CLUSTER = os.environ.get("CLUSTER_NAME", "unknown")

_lock = threading.Lock()
# Dedicated stdout lock, separate from _lock (which guards the counters/ring). This
# server is a ThreadingHTTPServer, so multiple request threads reach emit() at once;
# an unguarded write+flush can interleave two receipts into one corrupt line and break
# the JSONL contract the whole sink exists to uphold. A separate lock keeps this off
# the counter critical section and cannot deadlock against it (emit() is never called
# while _lock is held).
_emit_lock = threading.Lock()
_counters = {
    "notifications_total": 0,
    "alerts_total": 0,
    "receipts_total": 0,
    "errors_total": 0,
    "bytes_total": 0,
}
_by_severity: dict[tuple[str, str], int] = collections.defaultdict(int)
_recent: collections.deque = collections.deque(maxlen=RING_MAX)
_started = time.time()
_last_notification = 0.0


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def canonical(payload) -> str:
    """Deterministic JSON. Sorted keys, no incidental whitespace."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(payload) -> str:
    return hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest()


def emit(obj: dict) -> None:
    """One JSON object per line to stdout -> fluentbit-gke -> Cloud Logging.

    The write+flush is atomic under _emit_lock: ThreadingHTTPServer can call emit()
    from several request threads at once, and an unguarded pair of writes interleaves
    two receipts into one unparseable line — the exact silent corruption a receipt
    stream must not have. Serialise the line first, hold the lock only for the I/O.
    """
    line = canonical(obj) + "\n"
    with _emit_lock:
        sys.stdout.write(line)
        sys.stdout.flush()


def receipt(action: str, status: str, subject_ref: str, body: dict, **extra) -> dict:
    """An EvidenceReceipt.v0.1. Fields and enum values come from the contract."""
    h = digest(body)
    r = {
        "version": VERSION,
        "receipt_id": "evr-%s-%s" % (action, h[:32]),
        "created_at": utc_now(),
        "service_ref": SERVICE_REF,
        "action": action,
        "status": status,
        "subject_ref": subject_ref,
        "hash": h,
        "hash_algo": "sha256",
    }
    r.update(extra)
    return r


def handle_notification(payload: dict) -> dict:
    """Turn one Alertmanager webhook into receipts. Returns a summary."""
    alerts = payload.get("alerts")
    if not isinstance(alerts, list):
        raise ValueError("payload has no 'alerts' list")

    group_key = str(payload.get("groupKey", ""))
    receiver = str(payload.get("receiver", ""))
    seen = []

    for a in alerts:
        if not isinstance(a, dict):
            raise ValueError("alert entry is not an object")
        labels = a.get("labels") or {}
        annotations = a.get("annotations") or {}
        name = str(labels.get("alertname", "<unnamed>"))
        severity = str(labels.get("severity", "none"))
        status = str(a.get("status", "unknown"))

        # firing -> the condition is live and was delivered here.
        # resolved -> Alertmanager observed it clear.
        ev_status = "accepted" if status == "firing" else "succeeded"

        body = {
            "alertname": name,
            "severity": severity,
            "status": status,
            "labels": labels,
            "annotations": annotations,
            "startsAt": a.get("startsAt"),
            "endsAt": a.get("endsAt"),
            "generatorURL": a.get("generatorURL"),
            "fingerprint": a.get("fingerprint"),
        }
        subject = "alert/%s/%s" % (labels.get("namespace", "-"), name)
        r = receipt(
            "alert-delivered",
            ev_status,
            subject,
            body,
            metrics={"severity": severity, "alert_status": status},
            evidence_refs=[x for x in [a.get("generatorURL")] if x],
            policy_refs=["alertmanager/receiver/%s" % receiver] if receiver else [],
        )
        r["alert"] = body
        r["group_key"] = group_key
        r["cluster"] = CLUSTER
        emit(r)

        with _lock:
            _counters["receipts_total"] += 1
            _counters["alerts_total"] += 1
            _by_severity[(severity, status)] += 1
            _recent.append(
                {"at": r["created_at"], "alertname": name, "severity": severity, "status": status}
            )
        seen.append((name, severity, status))

    return {"count": len(seen), "alerts": seen, "receiver": receiver}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # noqa: A003 - stdlib hook
        # Access logs go through the same structured stream as everything else.
        emit(
            {
                "stream": "access",
                "at": utc_now(),
                "service_ref": SERVICE_REF,
                "line": fmt % args,
            }
        )

    def _send(self, code: int, obj: dict) -> None:
        body = canonical(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, code: int, text: str) -> None:
        body = text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 - stdlib hook
        if self.path.startswith("/metrics"):
            return self._send_text(200, self._metrics())
        if self.path.startswith("/healthz"):
            return self._send(200, {"ok": True, "uptime_s": int(time.time() - _started)})
        if self.path.startswith("/recent"):
            with _lock:
                return self._send(200, {"recent": list(_recent)})
        return self._send(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802 - stdlib hook
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            with _lock:
                _counters["errors_total"] += 1
            emit(
                receipt(
                    "alert-delivered",
                    "denied",
                    "alert/-/<oversize>",
                    {"content_length": length, "limit": MAX_BODY},
                )
            )
            return self._send(413, {"error": "body too large", "limit": MAX_BODY})

        raw = self.rfile.read(length) if length else b""
        with _lock:
            _counters["bytes_total"] += len(raw)

        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
            if not isinstance(payload, dict):
                raise ValueError("payload is not a JSON object")
            summary = handle_notification(payload)
        except Exception as exc:  # noqa: BLE001 - deliberate: every failure is reported
            with _lock:
                _counters["errors_total"] += 1
            emit(
                receipt(
                    "alert-delivered",
                    "failed",
                    "alert/-/<malformed>",
                    {"error": str(exc), "bytes": len(raw)},
                    metrics={"error": type(exc).__name__},
                )
            )
            return self._send(400, {"error": str(exc)})

        global _last_notification
        with _lock:
            _counters["notifications_total"] += 1
            _last_notification = time.time()
        return self._send(200, {"ok": True, **summary})

    def _metrics(self) -> str:
        with _lock:
            c = dict(_counters)
            sev = dict(_by_severity)
            last = _last_notification
        out = [
            "# HELP alert_sink_notifications_total Alertmanager webhook notifications accepted.",
            "# TYPE alert_sink_notifications_total counter",
            "alert_sink_notifications_total %d" % c["notifications_total"],
            "# HELP alert_sink_alerts_total Individual alerts extracted from notifications.",
            "# TYPE alert_sink_alerts_total counter",
            "alert_sink_alerts_total %d" % c["alerts_total"],
            "# HELP alert_sink_receipts_total EvidenceReceipts emitted to the log stream.",
            "# TYPE alert_sink_receipts_total counter",
            "alert_sink_receipts_total %d" % c["receipts_total"],
            "# HELP alert_sink_errors_total Malformed or refused deliveries.",
            "# TYPE alert_sink_errors_total counter",
            "alert_sink_errors_total %d" % c["errors_total"],
            "# HELP alert_sink_last_notification_timestamp_seconds Unix time of the last accepted notification.",
            "# TYPE alert_sink_last_notification_timestamp_seconds gauge",
            "alert_sink_last_notification_timestamp_seconds %f" % last,
            "# HELP alert_sink_build_info Sink build metadata.",
            "# TYPE alert_sink_build_info gauge",
            'alert_sink_build_info{version="%s",cluster="%s"} 1' % (VERSION, CLUSTER),
            "# HELP alert_sink_alerts_by_severity_total Alerts by severity and firing status.",
            "# TYPE alert_sink_alerts_by_severity_total counter",
        ]
        for (severity, status), n in sorted(sev.items()):
            out.append(
                'alert_sink_alerts_by_severity_total{severity="%s",alert_status="%s"} %d'
                % (severity, status, n)
            )
        return "\n".join(out) + "\n"


def main() -> None:
    emit(
        {
            "stream": "lifecycle",
            "at": utc_now(),
            "service_ref": SERVICE_REF,
            "event": "start",
            "port": PORT,
            "cluster": CLUSTER,
        }
    )
    ThreadingHTTPServer(("", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
