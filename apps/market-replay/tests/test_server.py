"""/healthz truthfulness + run_step state folding (loop disabled — units drive steps)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ["REPLAY_ENABLED"] = "off"   # no background thread under test

from fastapi.testclient import TestClient  # noqa: E402

from market_replay import server  # noqa: E402
from market_replay.emitter import ReplayEmitter  # noqa: E402
from market_replay.generator import TickGenerator  # noqa: E402
from test_emitter import WALL, FakeWriter  # noqa: E402

client = TestClient(server.app)


def make(writer: FakeWriter) -> ReplayEmitter:
    return ReplayEmitter(generator=TickGenerator(["SP:AAA", "SP:BBB", "SP:CCC"], seed=42),
                         writer=writer, clock=lambda: WALL)


def setup_function():
    server.STATE.update({
        "ticks_generated": 0, "emitted": 0, "last_seq": 0, "validation_failures": 0,
        "pending": 0, "hellgraph_ok": None, "last_emit_at": None,
        "last_error": None, "last_error_at": None, "loop_running": False,
    })


def test_healthz_reports_emission_truth_after_batches():
    em = make(FakeWriter())
    server.run_step(em)

    h = client.get("/healthz").json()
    assert h["ok"] is True and h["service"] == "market-replay"
    assert h["enabled"] is False                       # REPLAY_ENABLED=off — the truth
    assert h["emitted"] == 3 and h["ticks_generated"] == 3 and h["last_seq"] == 1
    assert h["validation_failures"] == 0               # the steady-state MUST-be-0 gauge
    assert h["hellgraph_ok"] is True and h["pending"] == 0
    assert h["last_emit_at"] and h["last_error"] is None

    server.run_step(em)
    h = client.get("/healthz").json()
    assert h["emitted"] == 6 and h["last_seq"] == 2


def test_healthz_reports_outage_without_lying_or_crashing():
    w = FakeWriter()
    w.down = True
    em = make(w)
    server.run_step(em)                                # swallowed, recorded, no crash

    h = client.get("/healthz").json()
    assert h["ok"] is True                             # liveness stays truthful-200
    assert h["hellgraph_ok"] is False and h["emitted"] == 0
    assert h["last_emit_at"] is None

    w.down = False                                     # heal → the SAME emitter drains
    server.run_step(em)
    h = client.get("/healthz").json()
    assert h["hellgraph_ok"] is True and h["emitted"] == 3 and h["pending"] == 0


def test_healthz_surfaces_validation_failures(monkeypatch):
    from market_replay import contract, emitter as emitter_mod

    real = contract.build_event

    def corrupting(tick, wall_time):
        ev = real(tick, wall_time)
        ev["eventKind"] = "vibes"                      # schema-invalid for every tick
        return ev

    monkeypatch.setattr(emitter_mod, "build_event", corrupting)
    em = make(FakeWriter())
    server.run_step(em)

    h = client.get("/healthz").json()
    assert h["validation_failures"] == 3               # counted loudly...
    assert h["emitted"] == 0 and h["pending"] == 0     # ...and NOTHING was emitted
