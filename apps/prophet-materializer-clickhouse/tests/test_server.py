"""/healthz truthfulness + run_step state folding (loop disabled — units drive steps)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ["MATERIALIZER_LOOP"] = "off"   # no background thread under test

from fastapi.testclient import TestClient  # noqa: E402

from prophet_materializer_clickhouse import server  # noqa: E402
from prophet_materializer_clickhouse.materializer import Materializer  # noqa: E402
from test_materializer import FakeClickHouse, FakeGateway, FakeHellGraph, THREE_EVENTS  # noqa: E402

client = TestClient(server.app)


def setup_function():
    server.STATE.update({
        "last_cursor": 0, "version": 0, "lag": 0, "batches_ok": 0, "events_written": 0,
        "receipts": 0, "last_receipt_id": None, "last_batch_at": None,
        "last_error": None, "last_error_at": None, "loop_running": False,
    })


def test_healthz_reports_cursor_and_lag_after_a_batch():
    m = Materializer(hellgraph=FakeHellGraph(THREE_EVENTS), clickhouse=FakeClickHouse(),
                     gateway=FakeGateway(), batch_limit=2)
    assert server.run_step(m) is True                  # first page (2 events) landed

    h = client.get("/healthz").json()
    assert h["ok"] is True and h["service"] == "prophet-materializer-clickhouse"
    assert h["last_cursor"] == 9 and h["version"] == 12 and h["lag"] == 3
    assert h["batches_ok"] == 1 and h["events_written"] == 2 and h["receipts"] == 1
    assert h["last_receipt_id"] and h["last_error"] is None

    assert server.run_step(m) is True                  # drain the rest
    assert server.run_step(m) is False                 # caught up → empty step
    h = client.get("/healthz").json()
    assert h["last_cursor"] == 12 and h["lag"] == 0 and h["receipts"] == 2


def test_healthz_reports_failure_without_advancing_the_cursor():
    gw = FakeGateway()
    gw.down = True
    m = Materializer(hellgraph=FakeHellGraph(THREE_EVENTS), clickhouse=FakeClickHouse(),
                     gateway=gw, batch_limit=500)
    assert server.run_step(m) is False                 # swallowed, recorded, not checkpointed

    h = client.get("/healthz").json()
    assert h["ok"] is True                             # liveness stays truthful-200
    assert "GatewayError" in h["last_error"]
    assert h["last_cursor"] == 0 and h["receipts"] == 0 and h["batches_ok"] == 0
