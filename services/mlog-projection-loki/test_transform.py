"""Unit tests for the Loki projection rule — deterministic, no Kafka/Loki."""
import json
import os
import importlib.util

# telemetry-producer has a same-named transform.py; a bare `from transform
# import ...` collides via sys.modules if both test_transform.py files get
# collected in one pytest process. Load this service's own module by path
# under a distinct name instead of relying on the ambient sys.path.
_p = os.path.join(os.path.dirname(__file__), "transform.py")
_spec = importlib.util.spec_from_file_location("projection_transform", _p)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
envelope_to_loki_stream, _to_ns = _mod.envelope_to_loki_stream, _mod._to_ns


def test_maps_envelope_to_loki_stream():
    env = {
        "id": "01J-abc", "type": "telemetry.log", "source": "promtail",
        "topic": "telemetry.logs", "namespace": "socioprophet",
        "time": "2026-07-31T18:00:00Z", "subject": "pod/x",
        "payload": {"msg": "hello"},
    }
    out = envelope_to_loki_stream(env)
    s = out["streams"][0]
    assert s["stream"]["type"] == "telemetry.log"
    assert s["stream"]["topic"] == "telemetry.logs"
    assert s["stream"]["namespace"] == "socioprophet"
    ns, line = s["values"][0]
    assert ns == "1785520800000000000"          # deterministic ns for the RFC3339 ts
    assert json.loads(line)["id"] == "01J-abc"   # id in the line => replay-idempotent


def test_replay_is_byte_identical():
    env = {"id": "x", "type": "t", "topic": "telemetry.logs", "time": "2026-07-31T18:00:00Z", "payload": {"a": 1}}
    assert envelope_to_loki_stream(env) == envelope_to_loki_stream(env)


def test_rejects_non_envelope():
    try:
        envelope_to_loki_stream({"foo": "bar"})
        assert False, "should reject non-envelope"
    except ValueError:
        pass


def test_epoch_seconds_and_ns():
    assert _to_ns(1785520800) == "1785520800000000000"
    assert _to_ns(1785520800000000000) == "1785520800000000000"
