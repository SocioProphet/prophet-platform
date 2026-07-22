"""The cadence trigger: relevance filter, statutory-first ordering, and one full poll
against faked ASX + gateway — asserting the Appendix 4E hits the reference table BEFORE
the investor pack reconciles (the AU cross-document contract)."""
import asyncio
import os

os.environ["WATCHER_DISABLE_LOOP"] = "1"
os.environ["GATEWAY_TOKEN"] = "t"

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)


def setup_function():
    main.STATE["seen"] = set()
    main.STATE["runs"] = []
    main.STATE["errors"] = 0


def test_relevance_filter():
    assert main.relevant({"announcementType": "PERIODIC REPORTS", "headline": "x"})
    assert main.relevant({"announcementType": "OTHER", "headline": "Appendix 4E and Annual Report"})
    assert main.relevant({"announcementType": "OTHER", "headline": "2026 Full Year Results Briefing"})
    assert not main.relevant({"announcementType": "SECURITY HOLDER DETAILS",
                              "headline": "Ceasing to be a substantial holder"})


def test_statutory_forms_process_first():
    items = [{"headline": "FY26 Results Investor Presentation"},
             {"headline": "Appendix 4E and Full Year Statutory Accounts"}]
    assert "Appendix 4E" in main.statutory_first(items)[0]["headline"]


def test_workflow_spec_routes_statutory_to_reference_table():
    spec = main._workflow_spec("gyg", {"headline": "Appendix 4E", "documentKey": "k1"}, "QQ==")
    load = next(s for s in spec["steps"] if s["id"] == "load")
    assert load["spec"]["table"] == "reference_facts"
    assert load["spec"]["source"] == "asx-appendix-4e"
    spec2 = main._workflow_spec("gyg", {"headline": "FY26 Results Presentation", "documentKey": "k2"}, "QQ==")
    load2 = next(s for s in spec2["steps"] if s["id"] == "load")
    assert load2["spec"]["table"] == "financials"
    ex = next(s for s in spec2["steps"] if s["id"] == "extract")
    assert ex["spec"]["entity"] == {"asx": "GYG", "name": "GYG"}


def test_poll_processes_new_docs_once_statutory_first(monkeypatch):
    calls = {"gets": [], "computes": []}

    class FakeResp:
        def __init__(self, js=None, content=b"%PDF-fake"):
            self.status_code, self._js, self.content = 200, js, content
        def json(self):
            return self._js
        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url, params=None):
            calls["gets"].append(url)
            if "/announcements" in url:
                return FakeResp(js={"data": {"items": [
                    {"announcementType": "PERIODIC REPORTS", "documentKey": "pack-1",
                     "headline": "FY26 Full Year Results Presentation", "date": "2026-08-28",
                     "displayName": "GUZMAN Y GOMEZ"},
                    {"announcementType": "PERIODIC REPORTS", "documentKey": "app4e-1",
                     "headline": "Appendix 4E and Statutory Accounts", "date": "2026-08-28",
                     "displayName": "GUZMAN Y GOMEZ"},
                    {"announcementType": "SECURITY HOLDER DETAILS", "documentKey": "noise-1",
                     "headline": "Ceasing to be a substantial holder"},
                ]}})
            return FakeResp()  # the PDF download
        async def post(self, url, headers=None, json=None):
            calls["computes"].append(json)
            return FakeResp(js={"status": "ok", "receipt": {"id": f"sha256:{len(calls['computes'])}"},
                                "outputs": [{"data": {"warrant": "verified"}}]})
    monkeypatch.setattr(main.httpx, "AsyncClient", FakeClient)

    processed = asyncio.run(main.poll_once())
    assert [p["documentKey"] for p in processed] == ["app4e-1", "pack-1"]   # statutory FIRST, noise skipped
    tables = [next(s for s in c["spec"]["steps"] if s["id"] == "load")["spec"]["table"]
              for c in calls["computes"]]
    assert tables == ["reference_facts", "financials"]

    # second poll: nothing new → nothing reprocessed (and gateway memoization guards restarts anyway)
    assert asyncio.run(main.poll_once()) == []


def test_status_and_poke_auth():
    r = client.get("/status")
    assert r.status_code == 200 and r.json()["tickers"] == ["gyg"]
    assert client.post("/poke").status_code == 401
    assert client.post("/poke", headers={"Authorization": "Bearer wrong"}).status_code == 401
