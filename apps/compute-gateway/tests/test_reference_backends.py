"""Dual-jurisdiction reference backends for reconcile (IFM stage 04).

US: SEC EDGAR company-facts (one cached call per CIK). AU: cross-document — the statutory
Appendix 4E, itself run through the governed pipeline, becomes the reference the glossy
investor pack reconciles against. Routing is by entity: cik → EDGAR, asx → appendix.
"""
import asyncio
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
    adapters.set_reference_resolver(None)   # exercise REAL routing, not an injected stub
    adapters._EDGAR_CACHE.clear()


def teardown_function():
    adapters.set_reference_resolver(None)


def _compute(body):
    return client.post("/v1/compute", json={"project": "demo", **body}, headers=AUTH).json()


# ── jurisdiction routing ──
def test_routing_by_entity_and_explicit_source():
    assert adapters._pick_reference(None, {"cik": "320193"})[0] == "sec-edgar"
    assert adapters._pick_reference(None, {"asx": "GYG"})[0] == "asx-appendix"
    # explicit source always wins
    assert adapters._pick_reference("asx-appendix", {"cik": "320193"})[0] == "asx-appendix"
    # dual-listed (both ids) defaults to the structured feed
    assert adapters._pick_reference(None, {"cik": "1", "asx": "X"})[0] == "sec-edgar"


# ── US: EDGAR company-facts ──
def test_edgar_companyfacts_parsing_and_concept_map(monkeypatch):
    async def fake_companyfacts(cik):
        return {"facts": {"us-gaap": {
            "RevenueFromContractWithCustomerExcludingAssessedTax": {
                "units": {"USD": [{"fy": 2026, "fp": "FY", "val": 9876000000}]}},
            "NetIncomeLoss": {"units": {"USD": [{"fy": 2026, "fp": "FY", "val": 1234000000}]}},
        }}}
    monkeypatch.setattr(adapters, "_edgar_companyfacts", fake_companyfacts)

    ent = {"cik": "1058090"}
    assert asyncio.run(adapters._sec_edgar_reference(ent, "revenue", "FY")) == 9876000000.0
    # npat maps onto the same GAAP concept as net_income (widened concept map)
    assert asyncio.run(adapters._sec_edgar_reference(ent, "npat", "FY")) == 1234000000.0
    # unmapped field resolves to None — never a guess
    assert asyncio.run(adapters._sec_edgar_reference(ent, "same_store_sales", "FY")) is None


def test_edgar_cache_one_call_per_cik(monkeypatch):
    fetches = []

    class FakeResp:
        status_code = 200
        def json(self):
            return {"facts": {"us-gaap": {}}}

    class FakeClient:
        def __init__(self, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url):
            fetches.append(url)
            return FakeResp()
    monkeypatch.setattr(adapters.httpx, "AsyncClient", FakeClient)

    asyncio.run(adapters._edgar_companyfacts("0001058090"))
    asyncio.run(adapters._edgar_companyfacts("0001058090"))
    assert len(fetches) == 1                     # second hit served from cache


# ── AU: cross-document reconciliation against the statutory appendix ──
def test_au_pack_reconciles_against_prior_appendix_extraction(tmp_path, monkeypatch):
    monkeypatch.setattr(adapters, "SQL_LOAD_DSN", f"sqlite:///{tmp_path}/ifm.db")

    # 1) the statutory Appendix 4E goes through the pipeline first → reference_facts table
    r1 = _compute({"kind": "workflow", "spec": {"steps": [
        {"id": "extract", "kind": "extraction", "spec": {
            "target_schema": {"table": "reference_facts"},
            "entity": {"asx": "GYG"}, "period": "FY26",
            "facts": [{"field": "revenue", "value": 1204.0, "source_span": "4E/p2"},
                      {"field": "net_profit", "value": -14.0, "source_span": "4E/p3"}]}},
        {"id": "load", "kind": "load", "from": "extract",
         "spec": {"table": "reference_facts", "source": "asx-appendix-4e"}},
    ]}})
    assert r1["status"] == "ok"

    # 2) the glossy investor pack reconciles against those rows — agreement promotes
    r2 = _compute({"kind": "reconcile", "spec": {
        "entity": {"asx": "GYG"}, "period": "FY26", "tolerance": 0.01,
        "facts": [{"field": "revenue", "value": 1204.0},        # agrees with the appendix
                  {"field": "net_profit", "value": -20.0}]}})   # pack diverges — the signal
    assert r2["status"] == "ok"
    d = r2["outputs"][0]["data"]
    assert d["source"] == "asx-appendix"                        # routed by the asx ticker
    recs = {x["field"]: x for x in d["reconciliations"]}
    assert recs["revenue"]["within_tol"] and recs["revenue"]["warrant"] == "verified"
    assert recs["net_profit"]["flagged"] and recs["net_profit"]["delta"] == -6.0
    assert d["all_verified"] is False                           # divergence surfaced, not buried


def test_au_reference_missing_row_cannot_reach_verified(tmp_path, monkeypatch):
    monkeypatch.setattr(adapters, "SQL_LOAD_DSN", f"sqlite:///{tmp_path}/empty.db")
    r = _compute({"kind": "reconcile", "spec": {
        "entity": {"asx": "GYG"}, "period": "FY26",
        "facts": [{"field": "revenue", "value": 1204.0, "warrant": "observed"}]}})
    rec = r["outputs"][0]["data"]["reconciliations"][0]
    assert rec["reference"] is None and rec["within_tol"] is False
    assert rec["warrant"] == "observed"                         # keeps its warrant, no promotion
