"""telemetry-producer — OTLP -> EventEnvelope adapter (the Kappa producer).

Consumes OTLP-json the OTel collector's kafka exporter writes to
`telemetry.logs.raw`, flattens each log record, wraps it as a CDM EventEnvelope
(deterministic id => a redelivered record maps to the same id, so a reader can
dedupe on replay -- Kafka production itself is still at-least-once, not
idempotent), and produces to `telemetry.logs` (the Map-Log stream
mlog-projection-loki consumes). Serves /healthz + /metrics.
"""
import json, os, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from confluent_kafka import Consumer, Producer, KafkaError

from transform import otlp_log_to_envelope

BOOTSTRAP = os.environ["MESH_BOOTSTRAP"]
IN_TOPIC = os.environ.get("SOURCE_TOPIC", "telemetry.logs.raw")
OUT_TOPIC = os.environ.get("TARGET_TOPIC", "telemetry.logs")
GROUP = os.environ.get("CONSUMER_GROUP", "telemetry-producer")
HEALTH_PORT = int(os.environ.get("HEALTH_PORT", "9110"))

_m = {"produced": 0, "errors": 0, "started": 0}
_lock = threading.Lock()


def _attr_val(v: dict):
    return list(v.values())[0] if isinstance(v, dict) and v else v


def flatten_otlp_logs(doc: dict) -> list[dict]:
    """OTLP LogsData json -> flat records for otlp_log_to_envelope()."""
    out = []
    for rl in doc.get("resourceLogs", []):
        res = {a.get("key"): _attr_val(a.get("value", {})) for a in rl.get("resource", {}).get("attributes", [])}
        for sl in rl.get("scopeLogs", []):
            for lr in sl.get("logRecords", []):
                out.append({
                    "timeUnixNano": lr.get("timeUnixNano"),
                    "severityText": lr.get("severityText"),
                    "body": _attr_val(lr.get("body", {})),
                    "attributes": {a.get("key"): _attr_val(a.get("value", {})) for a in lr.get("attributes", [])},
                    "resource": res,
                    "traceId": lr.get("traceId"),
                })
    return out


def _serve_health() -> None:
    def metrics() -> bytes:
        with _lock:
            m = dict(_m)
        return (
            f"# TYPE telemetry_producer_up gauge\ntelemetry_producer_up {1 if m['started'] else 0}\n"
            f"# TYPE telemetry_producer_events_total counter\ntelemetry_producer_events_total {m['produced']}\n"
            f"# TYPE telemetry_producer_errors_total counter\ntelemetry_producer_errors_total {m['errors']}\n"
        ).encode()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            if self.path == "/healthz":
                self.send_response(200 if _m["started"] else 503); self.end_headers(); self.wfile.write(b"ok")
            elif self.path == "/metrics":
                self.send_response(200); self.send_header("Content-Type", "text/plain"); self.end_headers(); self.wfile.write(metrics())
            else:
                self.send_response(404); self.end_headers()

    ThreadingHTTPServer(("0.0.0.0", HEALTH_PORT), H).serve_forever()


def main() -> None:
    threading.Thread(target=_serve_health, daemon=True).start()
    c = Consumer({"bootstrap.servers": BOOTSTRAP, "group.id": GROUP,
                  "auto.offset.reset": "earliest", "enable.auto.commit": False})
    c.subscribe([IN_TOPIC])
    p = Producer({"bootstrap.servers": BOOTSTRAP})
    with _lock:
        _m["started"] = int(time.time())
    print(f"telemetry-producer {IN_TOPIC} -> EventEnvelope -> {OUT_TOPIC} @ {BOOTSTRAP}", file=sys.stderr)
    while True:
        msg = c.poll(1.0)
        if msg is None:
            continue
        if msg.error():
            if msg.error().code() != KafkaError._PARTITION_EOF:
                print("consume error:", msg.error(), file=sys.stderr)
            continue
        try:
            n = 0
            for rec in flatten_otlp_logs(json.loads(msg.value())):
                env = otlp_log_to_envelope(rec, OUT_TOPIC)
                p.produce(OUT_TOPIC, key=env["id"].encode(), value=json.dumps(env).encode())
                n += 1
            pending = p.flush(5)
            if pending:
                # flush() returns the still-undelivered count on timeout rather than
                # raising; committing the source offset anyway would drop those
                # messages for good. Skip the commit so this batch redelivers.
                with _lock:
                    _m["errors"] += 1
                print(f"produce error: flush timed out with {pending} message(s) undelivered, not committing offset", file=sys.stderr)
                continue
            c.commit(msg)  # at-least-once; deterministic ids let a reader dedupe on redelivery
            with _lock:
                _m["produced"] += n
        except Exception as e:
            with _lock:
                _m["errors"] += 1
            print("produce error:", e, file=sys.stderr)


if __name__ == "__main__":
    main()
