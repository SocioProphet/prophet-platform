"""HTTP shell: /healthz (last cursor + lag, honest) + the poll loop on a daemon thread.

The loop never dies: any batch error is recorded in state and retried after the poll
interval (a batch that failed was, by construction, not checkpointed — see
materializer.run_once). /healthz always answers 200 with the truth; liveness is "the
process and loop are up", not "every dependency is green" — a poller has no traffic to
gate, and restarting it cannot fix a down ClickHouse.

Config (env):
  HELLGRAPH_URL           the log surface                (default http://hellgraph-service:8090)
  CLICKHOUSE_URL          ClickHouse HTTP interface      (default http://clickhouse:8123)
  CLICKHOUSE_USER         (default "default")
  CLICKHOUSE_PASSWORD     via secretEnv — never in values/config
  COMPUTE_GATEWAY_URL     the receipt spine              (default http://compute-gateway:8080)
  GATEWAY_TOKEN           via secretEnv (compute-gateway-token)
  MATERIALIZER_PROJECT    receipt chain/project          (default "default")
  POLL_INTERVAL_SECONDS   (default 5)
  BATCH_LIMIT             (default 500, server caps at 1000)
  MATERIALIZER_LOOP=off   disables the background loop (tests / one-shot debugging)
"""
from __future__ import annotations

import os
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .clients import ClickHouseClient, GatewayClient, HellGraphClient
from .materializer import MATERIALIZER_NAME, Materializer


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    if os.getenv("MATERIALIZER_LOOP", "on").lower() != "off":
        threading.Thread(target=_loop, name="materializer-loop", daemon=True).start()
    yield


app = FastAPI(title="prophet-materializer-clickhouse", version="0.1.0", lifespan=_lifespan)

POLL_INTERVAL = float(os.getenv("POLL_INTERVAL_SECONDS", "5"))
BATCH_LIMIT = int(os.getenv("BATCH_LIMIT", "500"))

STATE: dict = {
    "last_cursor": 0, "version": 0, "lag": 0,
    "batches_ok": 0, "events_written": 0, "receipts": 0,
    "last_receipt_id": None, "last_batch_at": None,
    "last_error": None, "last_error_at": None,
    "loop_running": False,
}
_STATE_LOCK = threading.Lock()


def build_materializer() -> Materializer:
    return Materializer(
        hellgraph=HellGraphClient(os.getenv("HELLGRAPH_URL", "http://hellgraph-service:8090")),
        clickhouse=ClickHouseClient(
            os.getenv("CLICKHOUSE_URL", "http://clickhouse:8123"),
            user=os.getenv("CLICKHOUSE_USER", "default"),
            password=os.getenv("CLICKHOUSE_PASSWORD", "")),
        gateway=GatewayClient(
            os.getenv("COMPUTE_GATEWAY_URL", "http://compute-gateway:8080"),
            token=os.getenv("GATEWAY_TOKEN", ""),
            project=os.getenv("MATERIALIZER_PROJECT", "default")),
        batch_limit=BATCH_LIMIT,
    )


def run_step(m: Materializer) -> bool:
    """One loop step: run a batch, fold the outcome into STATE. Returns True when a
    non-empty batch landed (the loop then polls again immediately to drain a backlog
    faster than one batch per interval)."""
    try:
        result = m.run_once()
        with _STATE_LOCK:
            STATE["version"] = result.version
            STATE["lag"] = result.lag
            STATE["last_error"] = None
            if result.checkpointed:
                STATE["last_cursor"] = result.to_cursor
                STATE["batches_ok"] += 1
                STATE["events_written"] += result.events
                STATE["receipts"] += 1
                STATE["last_receipt_id"] = result.receipt_id
                STATE["last_batch_at"] = time.time()
            else:
                STATE["last_cursor"] = result.from_cursor
        return result.checkpointed
    except Exception as e:  # noqa: BLE001 — the loop must survive any dependency outage
        with _STATE_LOCK:
            STATE["last_error"] = f"{type(e).__name__}: {e}"
            STATE["last_error_at"] = time.time()
        return False


def _loop() -> None:
    m = build_materializer()
    with _STATE_LOCK:
        STATE["loop_running"] = True
    while True:
        drained_more = run_step(m)
        if not drained_more:
            time.sleep(POLL_INTERVAL)


@app.get("/healthz")
def healthz() -> dict:
    with _STATE_LOCK:
        snapshot = dict(STATE)
    return {"ok": True, "service": "prophet-materializer-clickhouse",
            "materializer": MATERIALIZER_NAME, **snapshot}
