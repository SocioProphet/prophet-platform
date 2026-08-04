"""receipt_id must be unique per emission, even for identical bodies.

The Watchdog alert fires with an effectively identical body every repeat_interval --
that is the whole point of it as a dead-man's switch. Pre-fix, receipt_id was derived
only from a hash of the body, so every Watchdog heartbeat produced the SAME
receipt_id. Anything downstream that treats receipt_id as an idempotency/dedup key
would then silently collapse repeated heartbeats into "already seen" -- exactly the
kind of silent delivery failure this sink exists to make loud. `hash` (the pure
content digest) is deliberately left unchanged; only receipt_id must vary per call.

Local-only (Actions are spend-capped). Requires: python3 (stdlib only).
"""
from __future__ import annotations

import importlib.util
import threading
from pathlib import Path

_SINK = Path(__file__).resolve().parents[1] / "base" / "sink.py"


def _load_sink():
    spec = importlib.util.spec_from_file_location("alert_sink_under_test_uniq", _SINK)
    assert spec and spec.loader, f"cannot build an import spec for {_SINK}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_identical_body_gets_distinct_receipt_ids_same_hash():
    sink = _load_sink()
    body = {"alertname": "Watchdog", "severity": "none", "status": "firing"}

    r1 = sink.receipt("alert-delivered", "accepted", "alert/-/Watchdog", body)
    r2 = sink.receipt("alert-delivered", "accepted", "alert/-/Watchdog", body)

    assert r1["hash"] == r2["hash"], "content hash must still reflect identical bodies"
    assert r1["receipt_id"] != r2["receipt_id"], (
        "receipt_id collided across two occurrences of the same body -- a downstream "
        "consumer that dedupes by receipt_id would drop the second Watchdog heartbeat"
    )


def test_receipt_id_unique_under_concurrent_calls():
    """next_seq() is called from many request threads at once in production; it must
    never hand out the same sequence number twice."""
    sink = _load_sink()
    body = {"alertname": "Watchdog", "severity": "none", "status": "firing"}
    n = 64
    ids: list[str] = [None] * n  # type: ignore[list-item]
    barrier = threading.Barrier(n)

    def one(i: int) -> None:
        barrier.wait()
        ids[i] = sink.receipt("alert-delivered", "accepted", "alert/-/Watchdog", body)["receipt_id"]

    threads = [threading.Thread(target=one, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(set(ids)) == n, f"expected {n} distinct receipt_ids, got {len(set(ids))} (sequence collision)"
