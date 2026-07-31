"""mlog-projection-loki — rebuilds the Loki projection from the Map Log.

Consumes CDM EventEnvelopes from the mesh (Kafka topics /telemetry/*) and writes
them to Loki. At-least-once: the offset is committed only after Loki accepts the
push; the transform is deterministic so reprocessing is idempotent (replay-safe).
Exposes /healthz + /metrics on :$HEALTH_PORT for probes + mesh liveness.
"""
import json, os, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests
from confluent_kafka import Consumer, KafkaError

from transform import envelope_to_loki_stream

BOOTSTRAP = os.environ["MESH_BOOTSTRAP"]
TOPICS = [t for t in os.environ.get("MESH_TOPICS_CONSUME", "telemetry.logs").split(",") if t]
LOKI_URL = os.environ.get("LOKI_URL", "http://loki.observability.svc.cluster.local:3100/loki/api/v1/push")
TENANT = os.environ.get("LOKI_TENANT", "fake")
GROUP = os.environ.get("CONSUMER_GROUP", "mlog-projection-loki")
HEALTH_PORT = int(os.environ.get("HEALTH_PORT", "9109"))

_m = {"projected": 0, "errors": 0, "started": 0}
_lock = threading.Lock()


def _push(body: dict) -> None:
    r = requests.post(LOKI_URL, json=body, headers={"X-Scope-OrgID": TENANT}, timeout=10)
    r.raise_for_status()


def _serve_health() -> None:
    def metrics() -> bytes:
        with _lock:
            m = dict(_m)
        return (
            f"# TYPE mlog_projection_up gauge\nmlog_projection_up {1 if m['started'] else 0}\n"
            f"# TYPE mlog_projection_records_total counter\nmlog_projection_records_total {m['projected']}\n"
            f"# TYPE mlog_projection_errors_total counter\nmlog_projection_errors_total {m['errors']}\n"
        ).encode()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            if self.path == "/healthz":
                self.send_response(200 if _m["started"] else 503); self.end_headers()
                self.wfile.write(b'{"status":"ok"}')
            elif self.path == "/metrics":
                self.send_response(200); self.send_header("Content-Type", "text/plain"); self.end_headers()
                self.wfile.write(metrics())
            else:
                self.send_response(404); self.end_headers()

    ThreadingHTTPServer(("0.0.0.0", HEALTH_PORT), H).serve_forever()


def main() -> None:
    threading.Thread(target=_serve_health, daemon=True).start()
    c = Consumer({"bootstrap.servers": BOOTSTRAP, "group.id": GROUP,
                  "auto.offset.reset": "earliest", "enable.auto.commit": False})
    c.subscribe(TOPICS)
    with _lock:
        _m["started"] = int(time.time())
    print(f"mlog-projection-loki consuming {TOPICS} from {BOOTSTRAP} -> {LOKI_URL}", file=sys.stderr)
    while True:
        msg = c.poll(1.0)
        if msg is None:
            continue
        if msg.error():
            if msg.error().code() != KafkaError._PARTITION_EOF:
                print("consume error:", msg.error(), file=sys.stderr)
            continue
        try:
            _push(envelope_to_loki_stream(json.loads(msg.value())))
            c.commit(msg)  # at-least-once: commit only after Loki accepts
            with _lock:
                _m["projected"] += 1
        except Exception as e:  # don't commit -> reprocess (idempotent)
            with _lock:
                _m["errors"] += 1
            print("projection error:", e, file=sys.stderr)


if __name__ == "__main__":
    main()
