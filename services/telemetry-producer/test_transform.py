"""Unit tests for the OTLP->EventEnvelope producer transform + round-trip with
the Loki projection (both halves speak one contract)."""
import os, importlib.util


def _load(name: str, rel_path: str):
    # both this service and mlog-projection-loki have a same-named transform.py;
    # a bare `from transform import ...` in each test file collides via
    # sys.modules when both get collected in one pytest process (the SUT here
    # AND the cross-service round-trip import both need a distinct name).
    p = os.path.join(os.path.dirname(__file__), rel_path)
    spec = importlib.util.spec_from_file_location(name, p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_own = _load("producer_transform", "transform.py")
otlp_log_to_envelope, _stable_id = _own.otlp_log_to_envelope, _own._stable_id

_proj = _load("proj_transform", os.path.join("..", "mlog-projection-loki", "transform.py"))
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
