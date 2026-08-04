"""HTTP shell: /healthz (last cursor + lag, honest) + the log-tail poll loop on a daemon thread +
POST /percolate (the exchange-envelope.v0 webhook — the api_webhook ingress the envelope schema names).

The loop never dies: any batch error is recorded in state and retried after the poll interval (a batch
that failed was, by construction, not checkpointed — see percolator.run_once). /healthz always answers
200 with the truth; liveness is "the process and loop are up", not "every dependency is green".

Config (env):
  HELLGRAPH_URL           reads (log/subgraph) AND writes (node/edge)  (default http://hellgraph-service:8090)
  GRAPH_TOKEN             graph:write bearer via secretEnv — only needed when hellgraph AUTH_ENFORCE=on
  COMPUTE_GATEWAY_URL     the receipt spine                            (default http://compute-gateway:8080)
  GATEWAY_TOKEN           via secretEnv (compute-gateway-token)
  PERCOLATOR_PROJECT      receipt chain/project                        (default "default")
  POLL_INTERVAL_SECONDS   (default 5)
  BATCH_LIMIT             (default 500, server caps at 1000)
  SUBGRAPH_LIMIT          live-catalog read cap                        (default 2000)
  PERCOLATOR_LOOP=off     disables the background loop (tests / envelope-only / one-shot debugging)
"""
from __future__ import annotations

import os
import threading
import time
from contextlib import asynccontextmanager

from fastapi import Body, FastAPI
from fastapi.responses import JSONResponse

from tools.hellgraph_percolation.writer_hellgraph import HellgraphServiceWriter

from .clients import GatewayClient, GraphClient
from .percolator import GatewayError, Percolator

POLL_INTERVAL = float(os.getenv("POLL_INTERVAL_SECONDS", "5"))
BATCH_LIMIT = int(os.getenv("BATCH_LIMIT", "500"))
SUBGRAPH_LIMIT = int(os.getenv("SUBGRAPH_LIMIT", "2000"))

STATE: dict = {
    "last_cursor": 0, "version": 0, "lag": 0,
    "batches_ok": 0, "materialized": 0, "receipts": 0,
    "last_receipt_id": None, "last_batch_at": None,
    "envelopes_ok": 0, "last_envelope_at": None,
    "last_error": None, "last_error_at": None,
    "loop_running": False,
}
_STATE_LOCK = threading.Lock()
_PERCOLATOR: Percolator | None = None


def build_percolator() -> Percolator:
    hellgraph_url = os.getenv("HELLGRAPH_URL", "http://hellgraph-service:8090")
    return Percolator(
        graph=GraphClient(hellgraph_url, subgraph_limit=SUBGRAPH_LIMIT),
        writer=HellgraphServiceWriter(base_url=hellgraph_url,
                                      token=os.getenv("GRAPH_TOKEN") or None, validate=True),
        gateway=GatewayClient(os.getenv("COMPUTE_GATEWAY_URL", "http://compute-gateway:8080"),
                              token=os.getenv("GATEWAY_TOKEN", ""),
                              project=os.getenv("PERCOLATOR_PROJECT", "default")),
        batch_limit=BATCH_LIMIT,
    )


def run_step(p: Percolator) -> bool:
    """One loop step: run a log-tail batch, fold the outcome into STATE. Returns True when a non-empty
    batch landed (the loop then polls again immediately to drain a backlog faster than one per interval)."""
    try:
        result = p.run_once(now=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        with _STATE_LOCK:
            STATE["version"] = result.version
            STATE["lag"] = result.lag
            STATE["last_error"] = None
            if result.checkpointed:
                STATE["last_cursor"] = result.to_cursor
                STATE["batches_ok"] += 1
                STATE["materialized"] += result.materialized
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


def _loop(p: Percolator) -> None:
    with _STATE_LOCK:
        STATE["loop_running"] = True
    while True:
        if not run_step(p):
            time.sleep(POLL_INTERVAL)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    global _PERCOLATOR
    _PERCOLATOR = build_percolator()
    if os.getenv("PERCOLATOR_LOOP", "on").lower() != "off":
        threading.Thread(target=_loop, args=(_PERCOLATOR,), name="percolator-loop", daemon=True).start()
    yield


app = FastAPI(title="hellgraph-percolator", version="0.1.0", lifespan=_lifespan)


@app.get("/healthz")
def healthz() -> dict:
    with _STATE_LOCK:
        snapshot = dict(STATE)
    return {"ok": True, "service": "hellgraph-percolator", **snapshot}


@app.post("/percolate")
def percolate_envelope(envelope: dict = Body(...)) -> JSONResponse:
    """The exchange-envelope.v0 ingress: an exchange announces the assets it touched, and we percolate
    that change (tenant-scoped) then seal a receipt. Fail-closed — a receipt failure returns 502 and the
    caller safely re-POSTs (the write is idempotent). A tokenless/absent percolator returns 503."""
    if _PERCOLATOR is None:
        return JSONResponse(status_code=503, content={"ok": False, "error": "percolator not ready"})
    if not envelope.get("tenant_id"):
        return JSONResponse(status_code=400, content={"ok": False, "error": "exchange-envelope.v0 requires tenant_id"})
    try:
        result = _PERCOLATOR.on_envelope(envelope, now=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    except GatewayError as e:
        return JSONResponse(status_code=502, content={"ok": False, "error": f"receipt refused: {e}"})
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"ok": False, "error": f"{type(e).__name__}: {e}"})
    with _STATE_LOCK:
        STATE["envelopes_ok"] += 1
        STATE["receipts"] += 1
        STATE["materialized"] += result.materialized
        STATE["last_receipt_id"] = result.receipt_id
        STATE["last_envelope_at"] = time.time()
    return JSONResponse(status_code=200, content={
        "ok": True, "trigger": "exchange-envelope", "materialized": result.materialized,
        "receipt_id": result.receipt_id, "batch_hash": result.batch_hash})
