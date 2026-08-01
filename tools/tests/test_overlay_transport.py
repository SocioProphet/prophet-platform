from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import overlay_transport as ov  # type: ignore

LANE = ROOT / "contracts" / "workspace-control-plane"
TOPIC_SCHEMA = json.loads((LANE / "schemas" / "topic-manifest.v0.schema.json").read_text())

NOW = "2026-08-01T00:00:00+00:00"
FUTURE = "2026-12-31T00:00:00+00:00"
PAST = "2025-01-01T00:00:00+00:00"


def manifest(topic="socioprophet/intel", transport="hypercore", revoked=False, expiry=FUTURE):
    return {
        "manifest_id": "topman-1", "kind": "data_topic", "topic": topic, "transport": transport,
        "discovery_key": "hc:abc", "expiry": expiry, "revocation": {"revoked": revoked},
        "signature": {"signer": "root", "algorithm": "ed25519", "signature": "s", "signed_at": NOW},
    }


# ---- append-only log (Hypercore semantics) ----

def test_append_log_chain_and_tamper():
    log = ov.AppendLog("w1")
    log.append("a", 1)
    log.append("b", 2)
    assert log.verify()
    # tamper with a committed entry -> chain breaks.
    log.entries[0].data = "evil"
    assert not log.verify()


def test_sparse_fetch_returns_only_requested():
    log = ov.AppendLog("w1")
    for i in range(5):
        log.append(f"d{i}", i)
    got = ov.sparse_fetch(log, [3, 1, 1, 99, -1])  # dedup, in order, ignore OOB
    assert [e.data for e in got] == ["d1", "d3"]


def test_linearize_multiwriter_is_causal_and_deterministic():
    a = ov.AppendLog("A")
    a.append("a1", 1)
    a.append("a2", 3)
    b = ov.AppendLog("B")
    b.append("b1", 2)
    view = ov.linearize([a, b])
    assert [e.data for e in view] == ["a1", "b1", "a2"]  # by (clock, writer, seq)
    # order is independent of the input order of logs.
    assert [e.data for e in ov.linearize([b, a])] == ["a1", "b1", "a2"]


# ---- broker: join-after-trust ----

def test_join_refused_without_trust_or_when_invalid():
    broker = ov.OverlayBroker()
    with pytest.raises(ov.OverlayRefused) as e:
        broker.join(manifest(), trusted=False, now=NOW)
    assert "untrusted" in e.value.reasons

    for bad, reason in [
        (manifest(transport="carrier-pigeon"), "unknown_transport"),
        (manifest(revoked=True), "revoked"),
        (manifest(expiry=PAST), "expired"),
    ]:
        with pytest.raises(ov.OverlayRefused) as e2:
            broker.join(bad, trusted=True, now=NOW)
        assert reason in e2.value.reasons


def test_join_then_append_fetch_linearize():
    broker = ov.OverlayBroker()
    topic = broker.join(manifest(), trusted=True, now=NOW).name
    broker.append(topic, "A", "a1", 1)
    broker.append(topic, "B", "b1", 2)
    broker.append(topic, "A", "a2", 3)
    assert [e.data for e in broker.linearized_view(topic)] == ["a1", "b1", "a2"]
    assert [e.data for e in broker.fetch(topic, "A", [0, 1])] == ["a1", "a2"]


def test_ops_on_unjoined_topic_refused():
    broker = ov.OverlayBroker()
    with pytest.raises(ov.OverlayRefused) as e:
        broker.append("never-joined", "A", "x", 1)
    assert "not_joined" in e.value.reasons


def test_join_manifest_conforms_to_frozen_schema():
    assert list(Draft202012Validator(TOPIC_SCHEMA).iter_errors(manifest())) == []
