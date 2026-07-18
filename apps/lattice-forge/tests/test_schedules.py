"""lattice-forge scheduling tests — governed recurring jobs, no live kernel needed.

Covers the pure store (schedules.py) and the token-gated HTTP surface, including
the /v1/run-due tick a Kubernetes CronJob fires: it must execute only due jobs,
seal a receipt per run, and advance next_run. Executor is injected (no kernel).
"""
import importlib
import os

os.environ["FORGE_TOKEN"] = "test-token"  # set before server import (fail-closed gate)

from fastapi.testclient import TestClient  # noqa: E402

from lattice_forge import execn, schedules, server  # noqa: E402

importlib.reload(server)
client = TestClient(server.app)
AUTH = {"Authorization": "Bearer test-token"}


def setup_function():
    # deterministic fake executor (same shape as test_forge) + clean schedule store
    # so runs are isolated across tests (the store is pod-local, module-level state).
    def fake(code, lang, to, session_id):
        return {"status": "ok",
                "outputs": [{"type": "stream", "name": "stdout", "text": f"ran:{code}|sid={session_id}"}],
                "error": None}
    execn.set_executor(fake)
    schedules._SCHEDULES.clear()


# ── pure store ───────────────────────────────────────────────────────────────

def test_create_sets_next_run_and_defaults():
    s = schedules.create("p", "nightly", "print(1)", 60, now=1000.0)
    assert s["enabled"] is True
    assert s["next_run"] == 1060.0 and s["last_run"] is None and s["last_status"] is None
    assert s["session_id"].startswith("p:sched:")   # isolated from interactive session


def test_due_returns_only_past_due_and_enabled():
    past = schedules.create("p", "a", "x", 30, now=100.0)      # next_run = 130
    future = schedules.create("p", "b", "y", 300, now=100.0)   # next_run = 400
    off = schedules.create("p", "c", "z", 30, now=100.0)       # next_run = 130
    schedules.get(off["id"])["enabled"] = False
    due_ids = {s["id"] for s in schedules.due(now=200.0)}
    assert due_ids == {past["id"]}                              # future not yet, off disabled
    assert future["id"] not in due_ids


def test_mark_ran_advances_and_records():
    s = schedules.create("p", "a", "x", 60, now=100.0)         # next_run = 160
    schedules.mark_ran(s["id"], "ok", now=165.0)
    got = schedules.get(s["id"])
    assert got["last_run"] == 165.0 and got["last_status"] == "ok"
    assert got["next_run"] == 220.0                            # 160 + 60, still ahead of 165


def test_mark_ran_snaps_past_now_when_badly_behind():
    s = schedules.create("p", "a", "x", 60, now=100.0)         # next_run = 160
    schedules.mark_ran(s["id"], "ok", now=500.0)               # very late tick
    assert schedules.get(s["id"])["next_run"] > 500.0          # no thundering catch-up


def test_delete_removes():
    s = schedules.create("p", "a", "x", 30, now=0.0)
    assert schedules.delete(s["id"]) is True
    assert schedules.get(s["id"]) is None
    assert schedules.delete(s["id"]) is False                  # idempotent


# ── HTTP surface ─────────────────────────────────────────────────────────────

def test_schedule_endpoints_token_gated():
    assert client.post("/v1/schedule", json={}).status_code == 401
    assert client.get("/v1/schedules", params={"project": "p"}).status_code == 401
    assert client.post("/v1/run-due").status_code == 401


def test_create_validates_interval():
    r = client.post("/v1/schedule", json={
        "project": "p", "name": "too-hot", "code": "x", "interval_seconds": 5,
    }, headers=AUTH)
    assert r.status_code == 422                                 # below MIN_INTERVAL_SECONDS


def test_create_rejects_unknown_adapter():
    r = client.post("/v1/schedule", json={
        "project": "p", "name": "n", "code": "x", "interval_seconds": 60, "adapter": "excel",
    }, headers=AUTH)
    assert r.status_code == 422


def test_create_list_delete_roundtrip():
    c = client.post("/v1/schedule", json={
        "project": "p1", "name": "nightly", "code": "print(1)", "interval_seconds": 60,
    }, headers=AUTH).json()
    assert c["name"] == "nightly" and c["interval_seconds"] == 60
    lst = client.get("/v1/schedules", params={"project": "p1"}, headers=AUTH).json()
    assert lst["count"] == 1 and lst["schedules"][0]["id"] == c["id"]
    # a different project is isolated
    assert client.get("/v1/schedules", params={"project": "other"}, headers=AUTH).json()["count"] == 0
    client.delete(f"/v1/schedule/{c['id']}", params={"project": "p1"}, headers=AUTH)
    assert client.get("/v1/schedules", params={"project": "p1"}, headers=AUTH).json()["count"] == 0


def test_run_due_executes_seals_and_advances():
    # create a schedule already past-due by backdating next_run, then tick /v1/run-due.
    c = client.post("/v1/schedule", json={
        "project": "sched", "name": "job", "code": "1+1", "interval_seconds": 60,
    }, headers=AUTH).json()
    schedules.get(c["id"])["next_run"] = 0.0                   # force due now

    out = client.post("/v1/run-due", headers=AUTH).json()
    assert out["count"] == 1 and out["ran"] == [c["id"]]
    assert out["runs"][0]["status"] == "ok" and out["runs"][0]["receipt"].startswith("sha256:")

    # a receipt was sealed on the schedule's project chain (proof-carrying)
    ch = client.get("/v1/receipts", params={"project": "sched"}, headers=AUTH).json()
    assert ch["count"] == 1
    # next_run advanced past 0 → no longer due on the next tick
    assert schedules.get(c["id"])["next_run"] > 0.0
    assert schedules.get(c["id"])["last_status"] == "ok"
    assert client.post("/v1/run-due", headers=AUTH).json()["count"] == 0


def test_run_due_seals_degraded_when_kernel_unavailable():
    def boom(code, lang, to):
        raise execn.ForgeUnavailable("no kernel")
    execn.set_executor(boom)
    c = client.post("/v1/schedule", json={
        "project": "degr", "name": "job", "code": "x", "interval_seconds": 60,
    }, headers=AUTH).json()
    schedules.get(c["id"])["next_run"] = 0.0

    out = client.post("/v1/run-due", headers=AUTH).json()
    assert out["runs"][0]["status"] == "degraded"              # honest, not faked
    ch = client.get("/v1/receipts", params={"project": "degr"}, headers=AUTH).json()
    assert ch["count"] == 1 and ch["receipts"][0]["status"] == "degraded"
    assert schedules.get(c["id"])["last_status"] == "degraded"
