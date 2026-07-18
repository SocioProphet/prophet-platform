"""IFM: document → typed facts (extraction) + reconcile vs open data, composed as a
governed pipeline. The extraction backend isn't needed when facts are pre-parsed; the
reference resolver is injected (prod = SEC EDGAR)."""
import importlib
import os

os.environ["GATEWAY_TOKEN"] = "t"
os.environ["COMPUTE_ENTITLEMENTS"] = "demo"
os.environ["GATEWAY_WRITE_PROVENANCE"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

from compute_gateway import adapters, engine, receipts, server, zerotrust  # noqa: E402

importlib.reload(zerotrust)
importlib.reload(engine)
importlib.reload(server)
client = TestClient(server.app)
AUTH = {"Authorization": "Bearer t"}


def setup_function():
    os.environ["COMPUTE_ENTITLEMENTS"] = "demo"
    receipts._CHAINS.clear()
    engine._MEMO.clear()

    async def ref(entity, field, period):
        # a deterministic open-data stand-in: revenue=100 for the demo entity/period
        return {"revenue": 100.0, "net_income": 20.0}.get(field)
    adapters.set_reference_resolver(ref)


def _compute(body):
    return client.post("/v1/compute", json={"project": "demo", **body}, headers=AUTH).json()


# ── extraction ──
def test_extraction_types_each_fact_and_weakest_warrant():
    r = _compute({"kind": "extraction", "spec": {
        "target_schema": {"table": "financials"},
        "entity": {"cik": "320193"}, "period": "FY",
        "facts": [
            {"field": "revenue", "value": 100, "source_span": "p12/tbl1"},   # verbatim → observed
            {"field": "margin", "value": 0.2},                               # computed → derived
        ]}})
    assert r["status"] == "ok" and r["kind"] == "extraction"
    rows = r["outputs"][0]["data"]["rows"]
    assert rows[0]["warrant"] == "observed" and rows[1]["warrant"] == "derived"
    assert r["epistemic_status"] == "observed"        # weakest-link across facts
    assert r["receipt"]["kind"] == "extraction"       # sealed like any compute


# ── reconcile vs open data ──
def test_reconcile_promotes_matching_fact_to_verified():
    r = _compute({"kind": "reconcile", "spec": {
        "entity": {"cik": "320193"}, "period": "FY", "tolerance": 0.01,
        "facts": [{"field": "revenue", "value": 100.5}]}})   # within 1% of ref 100
    rec = r["outputs"][0]["data"]["reconciliations"][0]
    assert rec["within_tol"] is True and rec["warrant"] == "verified" and rec["flagged"] is False
    assert r["outputs"][0]["data"]["all_verified"] is True
    assert r["epistemic_status"] == "verified"


def test_reconcile_flags_divergence_as_the_edge():
    r = _compute({"kind": "reconcile", "spec": {
        "entity": {"cik": "320193"}, "period": "FY",
        "facts": [{"field": "revenue", "value": 130}]}})     # pack says 130, ref says 100
    rec = r["outputs"][0]["data"]["reconciliations"][0]
    assert rec["within_tol"] is False and rec["flagged"] is True and rec["delta"] == 30.0
    assert r["epistemic_status"] == "derived"                # not verified — held for review


def test_reconcile_unresolved_reference_stays_unverified():
    r = _compute({"kind": "reconcile", "spec": {
        "entity": {"cik": "320193"}, "period": "FY",
        "facts": [{"field": "unknown_metric", "value": 5}]}})
    rec = r["outputs"][0]["data"]["reconciliations"][0]
    assert rec["reference"] is None and rec["within_tol"] is False and rec["flagged"] is False


# ── the IFM pipeline: extract → reconcile, threaded via `from`, one composite proof ──
def test_ifm_pipeline_extract_then_reconcile():
    r = _compute({"kind": "workflow", "spec": {"steps": [
        {"id": "extract", "kind": "extraction", "spec": {
            "target_schema": {"table": "financials"},
            "entity": {"cik": "320193"}, "period": "FY",
            "facts": [{"field": "revenue", "value": 100, "source_span": "p12"}]}},
        # reconcile pulls extract's output (rows/entity/period) via `from`
        {"id": "reconcile", "kind": "reconcile", "from": "extract", "spec": {"tolerance": 0.01}},
    ]}})
    assert r["status"] == "ok" and r["kind"] == "workflow"
    steps = {s["id"]: s for s in r["outputs"][0]["data"]["steps"]}
    assert [*steps] == ["extract", "reconcile"]           # topological order (from ⇒ dependency)
    assert steps["reconcile"]["epistemic_status"] == "verified"   # revenue reconciled → verified
    # extract(observed) + reconcile(verified) → workflow weakest-link = observed
    assert r["epistemic_status"] == "observed"
    # extract + reconcile + composite = 3 sealed receipts
    assert client.get("/v1/receipts", params={"project": "demo"}, headers=AUTH).json()["count"] == 3


def test_extraction_and_reconcile_live_in_registry():
    ks = {k["kind"]: k for k in client.get("/v1/registry", params={"project": "demo"}, headers=AUTH).json()["kinds"]}
    assert ks["extraction"]["status"] == "live" and ks["reconcile"]["status"] == "live"
    assert "sec-edgar" in ks["reconcile"]["capabilities"]
