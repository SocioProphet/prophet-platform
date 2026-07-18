"""IFM step 2: the SQL load sink — reconciled facts into the structured layer, with a
REAL SQLite write (sovereign, no creds). Closes the doc→SQL loop end to end."""
import importlib
import os
import pathlib

_DB = f"/tmp/test_ifm_{os.getpid()}.db"
os.environ["GATEWAY_TOKEN"] = "t"
os.environ["COMPUTE_ENTITLEMENTS"] = "demo"
os.environ["GATEWAY_WRITE_PROVENANCE"] = "false"
os.environ["SQL_LOAD_DSN"] = f"sqlite:///{_DB}"

from fastapi.testclient import TestClient  # noqa: E402

from compute_gateway import adapters, engine, receipts, server, zerotrust  # noqa: E402

importlib.reload(zerotrust)
importlib.reload(engine)
importlib.reload(adapters)
importlib.reload(server)
client = TestClient(server.app)
AUTH = {"Authorization": "Bearer t"}


def setup_function():
    os.environ["COMPUTE_ENTITLEMENTS"] = "demo"
    receipts._CHAINS.clear()
    engine._MEMO.clear()
    pathlib.Path(_DB).unlink(missing_ok=True)   # fresh DB per test

    async def ref(entity, field, period):
        return {"revenue": 100.0, "net_income": 20.0}.get(field)
    adapters.set_reference_resolver(ref)


def _compute(body):
    return client.post("/v1/compute", json={"project": "demo", **body}, headers=AUTH).json()


def _rows():
    import sqlite3
    con = sqlite3.connect(_DB)
    out = con.execute("SELECT entity, period, field, value, warrant FROM financials ORDER BY field").fetchall()
    con.close()
    return out


def test_load_writes_rows_and_upserts():
    body = {"kind": "load", "spec": {
        "table": "financials", "entity": {"cik": "320193"}, "period": "FY",
        "rows": [{"field": "revenue", "value": 100, "warrant": "verified"},
                 {"field": "net_income", "value": 20, "warrant": "derived"}]}}
    r = _compute(body)
    assert r["status"] == "ok" and r["kind"] == "load"
    d = r["outputs"][0]["data"]
    assert d["inserted"] == 2 and d["updated"] == 0 and d["table_total"] == 2
    assert len(_rows()) == 2
    # re-load with a changed value → upsert (update, not duplicate)
    body["spec"]["rows"][0]["value"] = 105
    d2 = _compute(body)["outputs"][0]["data"]
    assert d2["inserted"] == 0 and d2["updated"] == 2 and d2["table_total"] == 2
    assert dict((f, v) for _, _, f, v, _ in _rows())["revenue"] == "105"


def test_load_warrant_is_weakest_row():
    r = _compute({"kind": "load", "spec": {
        "table": "financials", "entity": {"cik": "1"}, "period": "FY",
        "rows": [{"field": "revenue", "value": 1, "warrant": "verified"},
                 {"field": "margin", "value": 0.2, "warrant": "derived"}]}})
    assert r["epistemic_status"] == "derived"   # weakest of {verified, derived}


def test_load_non_sqlite_dsn_degrades_honestly():
    r = _compute({"kind": "load", "spec": {
        "table": "financials", "entity": {"cik": "1"}, "period": "FY", "dsn": "postgres://prod/db",
        "rows": [{"field": "revenue", "value": 1, "warrant": "verified"}]}})
    assert r["status"] == "degraded" and "production driver" in r["degraded"]


def test_full_ifm_pipeline_extract_reconcile_load():
    r = _compute({"kind": "workflow", "spec": {"steps": [
        {"id": "extract", "kind": "extraction", "spec": {
            "target_schema": {"table": "financials"},
            "entity": {"cik": "320193"}, "period": "FY",
            "facts": [{"field": "revenue", "value": 100, "source_span": "p12"}]}},
        {"id": "reconcile", "kind": "reconcile", "from": "extract", "spec": {"tolerance": 0.01}},
        {"id": "load", "kind": "load", "from": "reconcile", "spec": {"table": "financials"}},
    ]}})
    assert r["status"] == "ok" and r["kind"] == "workflow"
    steps = {s["id"]: s for s in r["outputs"][0]["data"]["steps"]}
    assert [*steps] == ["extract", "reconcile", "load"]        # topological
    assert steps["reconcile"]["epistemic_status"] == "verified"
    assert steps["load"]["status"] == "ok"
    # the row landed in the SQL layer, tagged verified (it reconciled with open data)
    rows = _rows()
    assert len(rows) == 1 and rows[0][2] == "revenue" and rows[0][4] == "verified"
    # extract + reconcile + load + composite = 4 sealed receipts
    assert client.get("/v1/receipts", params={"project": "demo"}, headers=AUTH).json()["count"] == 4


def test_load_live_in_registry():
    ks = {k["kind"]: k for k in client.get("/v1/registry", params={"project": "demo"}, headers=AUTH).json()["kinds"]}
    assert ks["load"]["status"] == "live" and "upsert" in ks["load"]["capabilities"]
