"""emit() must write one intact JSON line per call, even under ThreadingHTTPServer.

The sink is a ThreadingHTTPServer, so several request threads reach emit() at once.
Pre-fix, emit() did an unguarded `sys.stdout.write(...) ; flush()`, so two receipts
could interleave into a single unparseable line — the exact silent corruption a
receipt stream (its whole reason to exist) must never produce. This test drives the
race deterministically: a fake stdout whose write() is deliberately NON-atomic (it
emits the line in two halves with a yield between). Without emit()'s lock the halves
of concurrent lines interleave and json.loads() fails; with it every line is intact.

Local-only (Actions are spend-capped). Requires: python3 (stdlib only).
"""
from __future__ import annotations

import importlib.util
import json
import sys
import threading
import time
from pathlib import Path

_SINK = Path(__file__).resolve().parents[1] / "base" / "sink.py"


def _load_sink():
    spec = importlib.util.spec_from_file_location("alert_sink_under_test", _SINK)
    assert spec and spec.loader, f"cannot build an import spec for {_SINK}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class SplittingStdout:
    """A stdout whose write() is intentionally non-atomic: it appends the line in two
    pieces with a scheduler yield between them. Any code that does not serialise its
    write() calls will interleave concurrent lines; correctly-locked code will not."""

    def __init__(self) -> None:
        self.parts: list[str] = []

    def write(self, s: str) -> int:
        half = len(s) // 2
        self.parts.append(s[:half])
        time.sleep(0)  # yield: invite another thread to interleave here
        self.parts.append(s[half:])
        return len(s)

    def flush(self) -> None:  # noqa: D401 - stdlib file protocol
        pass

    def value(self) -> str:
        return "".join(self.parts)


def _run_concurrent_emits(sink, n: int = 64) -> str:
    fake = SplittingStdout()
    real = sys.stdout
    sys.stdout = fake  # sink.emit() calls sys.stdout.write at call time
    try:
        barrier = threading.Barrier(n)

        def one(i: int) -> None:
            barrier.wait()  # maximise the race window
            sink.emit({"receipt_id": "evr-%04d" % i, "seq": i, "kind": "test"})

        threads = [threading.Thread(target=one, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    finally:
        sys.stdout = real
    return fake.value()


def test_concurrent_emit_produces_only_intact_json_lines():
    """THE regression. 64 threads race emit() through a write-splitting stdout. Every
    non-empty line must be valid JSON and exactly N lines must appear — pre-fix the
    unguarded write+flush interleaved halves and this failed with a JSONDecodeError."""
    sink = _load_sink()
    out = _run_concurrent_emits(sink, n=64)

    lines = [ln for ln in out.split("\n") if ln]
    assert len(lines) == 64, f"expected 64 intact lines, got {len(lines)} (interleaving splits/merges lines)"
    seqs = set()
    for ln in lines:
        obj = json.loads(ln)  # raises JSONDecodeError on an interleaved line
        seqs.add(obj["seq"])
    assert seqs == set(range(64)), "every receipt must survive exactly once and intact"
