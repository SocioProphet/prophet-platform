"""Unit tests for the OTLP->EventEnvelope producer transform + round-trip with
the Loki projection (both halves speak one contract)."""
import os, importlib.util
from transform import otlp_log_to_envelope, _stable_id

# load the consumer-side projection under a distinct name (both files are transform.py)
_p = os.path.join(os.path.dirname(__file__), "..", "mlog-projection-loki", "transform.py")
_spec = importlib.util.spec_from_file_location("proj_transform", _p)
_proj = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_proj)
envelope_to_loki_stream = _proj.envelope_to_loki_stream

REC = {
    "timeUnixNano": "1785520800000000000",
    "severityText": "INFO",
    "body": "hello world",
    "attributes": {"http.method": "GET"},
    "resource": {"service.name": "search-gateway", "k8s.pod.name": "sg-1", "k8s.namespace.name": "socioprophet"},
}


def test_wraps_otlp_into_envelope():
    env = otlp_log_to_envelope(REC)
    assert env["type"] == "telemetry.log"
    assert env["source"] == "search-gateway"
    assert env["topic"] == "telemetry.logs"
    assert env["time"] == "2026-07-31T18:00:00Z"
    assert env["payload"]["body"] == "hello world"
    assert env["id"].startswith("ev-")


def test_id_is_deterministic():
    assert _stable_id(REC, "telemetry.logs") == _stable_id(REC, "telemetry.logs")


def test_pair_is_contract_compatible():
    # producer output must be consumable by the Loki projection unchanged
    env = otlp_log_to_envelope(REC)
    stream = envelope_to_loki_stream(env)
    s = stream["streams"][0]
    assert s["stream"]["type"] == "telemetry.log"
    assert s["stream"]["source"] == "search-gateway"
    assert s["values"][0][0] == "1785520800000000000"
