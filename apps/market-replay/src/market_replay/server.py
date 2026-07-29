"""HTTP shell: /healthz (emitted count, last seq, validation failures, hellgraph
reachability — the truth) + the replay loop on a daemon thread.

The loop never dies: hellgraph outages leave the batch pending and retried next
interval (see emitter.run_once — no crash-loop, no gap in the seq stream); validation
failures are counted and surfaced, never emitted. /healthz always answers 200 with the
truth; liveness is "the process and loop are up", not "every dependency is green" — a
producer has no traffic to gate, and restarting it cannot fix a down hellgraph.

Config (env):
  HELLGRAPH_URL             the graph/log surface       (default http://hellgraph-service:8090)
  REPLAY_ENABLED            "on"/"off" — the loop gate  (default on; off = serve /healthz only)
  REPLAY_INTERVAL_SECONDS   seconds between batches     (default 5)
  REPLAY_SYMBOLS            comma-separated symbol set  (default SP:AAA,SP:BBB,SP:CCC)
  REPLAY_SEED               random-walk seed            (default 42 — deterministic by default)
"""
from __future__ import annotations

import os
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .emitter import HellGraphWriter, ReplayEmitter
from .generator import TickGenerator

REPLAY_ENABLED = os.getenv("REPLAY_ENABLED", "on").lower() != "off"
REPLAY_INTERVAL = float(os.getenv("REPLAY_INTERVAL_SECONDS", "5"))
SYMBOLS = [s.strip() for s in
           os.getenv("REPLAY_SYMBOLS", "SP:AAA,SP:BBB,SP:CCC").split(",") if s.strip()]
SEED = int(os.getenv("REPLAY_SEED", "42"))


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    if REPLAY_ENABLED:
        em = build_emitter()
        # Fail-closed boot gate IN THE MAIN THREAD: contract drift (schema hash is
        # already asserted at import; this validates a probe event) aborts uvicorn
        # startup — a visible crash, never a silently dead loop behind a green pod.
        em.startup_check()
        threading.Thread(target=_loop, args=(em,), name="replay-loop", daemon=True).start()
    yield


app = FastAPI(title="market-replay", version="0.1.0", lifespan=_lifespan)

STATE: dict = {
    "enabled": REPLAY_ENABLED, "symbols": SYMBOLS, "seed": SEED,
    "interval_seconds": REPLAY_INTERVAL,
    "ticks_generated": 0, "emitted": 0, "last_seq": 0,
    "validation_failures": 0,          # steady-state MUST be 0 — nonzero is the alarm
    "pending": 0, "hellgraph_ok": None,
    "last_emit_at": None, "last_error": None, "last_error_at": None,
    "loop_running": False,
}
_STATE_LOCK = threading.Lock()


def build_emitter() -> ReplayEmitter:
    return ReplayEmitter(
        generator=TickGenerator(SYMBOLS, seed=SEED),
        writer=HellGraphWriter(os.getenv("HELLGRAPH_URL", "http://hellgraph-service:8090")))


def run_step(em: ReplayEmitter) -> None:
    """One loop step: run a batch, fold the outcome into STATE."""
    try:
        result = em.run_once()
        with _STATE_LOCK:
            STATE["ticks_generated"] += result.generated
            STATE["emitted"] += result.emitted
            STATE["validation_failures"] += result.validation_failures
            STATE["pending"] = result.pending
            STATE["last_seq"] = result.last_seq
            STATE["hellgraph_ok"] = result.hellgraph_ok
            STATE["last_error"] = None
            if result.emitted:
                STATE["last_emit_at"] = time.time()
    except Exception as e:  # noqa: BLE001 — the loop must survive any dependency outage
        with _STATE_LOCK:
            STATE["hellgraph_ok"] = False
            STATE["last_error"] = f"{type(e).__name__}: {e}"
            STATE["last_error_at"] = time.time()


def _loop(em: ReplayEmitter) -> None:
    with _STATE_LOCK:
        STATE["loop_running"] = True
    while True:
        run_step(em)
        time.sleep(REPLAY_INTERVAL)


@app.get("/healthz")
def healthz() -> dict:
    with _STATE_LOCK:
        snapshot = dict(STATE)
    return {"ok": True, "service": "market-replay", **snapshot}
