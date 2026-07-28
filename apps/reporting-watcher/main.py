"""reporting-watcher — the IFM design's cadence trigger, running on the calendar.

Polls the ASX announcements API for the watched tickers' reporting-event documents
(results packs, statutory Appendix 4D/4E, annual reports). When a new one lands it
downloads the PDF and runs the governed doc→SQL workflow on the compute gateway:
ingest → parse → extract → reconcile → load, receipts and all.

Deliberately STATELESS: the poller keeps only in-memory seen-keys, because safety
lives downstream — packs are content-addressed and requests memoized at the gateway,
so reprocessing after a restart re-seals nothing and costs nothing. Statutory forms
are processed FIRST within a poll: the Appendix 4E lands in the reference table, so
the glossy pack that follows reconciles against it (the AU cross-document design).
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import time
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException

app = FastAPI(title="reporting-watcher", version="0.1.0")

ASX_API = os.getenv("ASX_API", "https://asx.api.markitdigital.com/asx-research/1.0").rstrip("/")
ASX_FILE = os.getenv("ASX_FILE", "https://cdn-api.markitdigital.com/apiman-gateway/ASX/asx-research/1.0/file").rstrip("/")
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://compute-gateway:8080").rstrip("/")
GATEWAY_TOKEN = os.getenv("GATEWAY_TOKEN", "")
WATCH_TICKERS = [t.strip().lower() for t in os.getenv("WATCH_TICKERS", "gyg").split(",") if t.strip()]
POLL_SECONDS = int(os.getenv("POLL_SECONDS", "1800"))
PROJECT = os.getenv("WATCH_PROJECT", "gyg-reporting")
REPORT_PERIOD = os.getenv("REPORT_PERIOD", "FY26")
TIMEOUT = float(os.getenv("WATCHER_TIMEOUT", "120"))

# What a results pack must yield. Override with TARGET_SCHEMA_JSON for other desks.
_DEFAULT_SCHEMA = {
    "table": "financials",
    "fields": [
        {"name": "revenue", "type": "number", "unit": "AUD_k", "labels": ["total revenue", "revenue"]},
        {"name": "net_profit", "type": "number", "unit": "AUD_k",
         "labels": ["net profit", "net profit after tax", "profit for the period", "npat"]},
        {"name": "ebitda", "type": "number", "unit": "AUD_k", "labels": ["ebitda", "underlying ebitda"]},
        {"name": "eps_diluted", "type": "number", "labels": ["diluted earnings per share", "diluted"]},
    ],
}
TARGET_SCHEMA = json.loads(os.getenv("TARGET_SCHEMA_JSON", "null")) or _DEFAULT_SCHEMA

_RELEVANT = re.compile(r"appendix 4[de]|full year|half year|results|annual report|trading update", re.I)

# Scheduling / heads-up releases that NAME a reporting event but carry none of its
# numbers. These lodge under announcementType "PERIODIC REPORTS" (so the type check
# alone waves them through) and often echo the results wording ("...Full Year
# Results..."), yet firing the pipeline on them yields an empty extraction — and the
# real GYG "Advance Notice - 2026 Full Year Results and Briefing" is one, live in the
# feed now. Excluded before anything else. (Verified against the live ASX feed
# 2026-07-28; the keyless index also caps at the 5 most recent, itemsPerPage notwithstanding.)
_EXCLUDE = re.compile(
    r"advance notice|notice of (meeting|agm|annual general)"
    r"|date (of|for) .*(results|release|report|announcement)"
    r"|(results|investor) briefing details", re.I)

STATE: dict[str, Any] = {"seen": set(), "runs": [], "last_poll": None, "polls": 0, "errors": 0}


def relevant(item: dict) -> bool:
    headline = item.get("headline", "")
    if _EXCLUDE.search(headline):           # scheduling notice — no numbers to extract
        return False
    return item.get("announcementType") == "PERIODIC REPORTS" or bool(_RELEVANT.search(headline))


def statutory_first(items: list[dict]) -> list[dict]:
    """Appendix 4D/4E before everything else: the statutory form is the AU reference —
    it must be IN the reference table before the investor pack reconciles."""
    return sorted(items, key=lambda i: 0 if re.search(r"appendix 4[de]", i.get("headline", ""), re.I) else 1)


def _workflow_spec(ticker: str, item: dict, doc_b64: str) -> dict:
    is_statutory = bool(re.search(r"appendix 4[de]", item.get("headline", ""), re.I))
    table = "reference_facts" if is_statutory else TARGET_SCHEMA.get("table", "financials")
    entity = {"asx": ticker.upper(), "name": item.get("displayName") or ticker.upper()}
    return {"steps": [
        {"id": "ingest", "kind": "ingest",
         "spec": {"document_b64": doc_b64, "filename": f"{ticker}-{item.get('documentKey', 'doc')}.pdf"}},
        {"id": "parse", "kind": "parse", "from": "ingest"},
        {"id": "extract", "kind": "extraction", "from": "parse",
         "spec": {"target_schema": {**TARGET_SCHEMA, "table": table}, "entity": entity,
                  "period": REPORT_PERIOD, "column_convention": "current-last"}},
        {"id": "reconcile", "kind": "reconcile", "from": "extract", "spec": {"tolerance": 0.01}},
        {"id": "load", "kind": "load", "from": "reconcile",
         "spec": {"table": table, "source": "asx-appendix-4e" if is_statutory else "investor-pack"}},
    ]}


async def process_item(client: httpx.AsyncClient, ticker: str, item: dict) -> dict:
    key = item.get("documentKey", "")
    r = await client.get(f"{ASX_FILE}/{key}")
    r.raise_for_status()
    doc_b64 = base64.b64encode(r.content).decode()
    res = await client.post(
        f"{GATEWAY_URL}/v1/compute",
        headers={"Authorization": f"Bearer {GATEWAY_TOKEN}"},
        json={"project": PROJECT, "kind": "workflow", "spec": _workflow_spec(ticker, item, doc_b64)})
    body = res.json() if res.status_code == 200 else {"status": f"HTTP {res.status_code}"}
    run = {
        "ticker": ticker, "documentKey": key, "headline": item.get("headline"),
        "date": item.get("date"), "status": body.get("status"),
        "receipt": (body.get("receipt") or {}).get("id"),
        "warrant": ((body.get("outputs") or [{}])[0].get("data") or {}).get("warrant"),
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    STATE["runs"] = (STATE["runs"] + [run])[-50:]
    STATE["seen"].add(key)
    return run


async def poll_once() -> list[dict]:
    """One pass over every watched ticker. Never raises — a dead API must not kill the loop."""
    processed: list[dict] = []
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for ticker in WATCH_TICKERS:
            try:
                r = await client.get(f"{ASX_API}/companies/{ticker}/announcements",
                                     params={"page": 0, "itemsPerPage": 20})
                items = (r.json().get("data") or {}).get("items") or []
            except Exception:  # noqa: BLE001
                STATE["errors"] += 1
                continue
            fresh = [i for i in items if relevant(i) and i.get("documentKey")
                     and i["documentKey"] not in STATE["seen"]]
            for item in statutory_first(fresh):
                try:
                    processed.append(await process_item(client, ticker, item))
                except Exception:  # noqa: BLE001
                    STATE["errors"] += 1
    STATE["last_poll"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    STATE["polls"] += 1
    return processed


async def _loop() -> None:
    while True:
        await poll_once()
        await asyncio.sleep(POLL_SECONDS)


@app.on_event("startup")
async def _start() -> None:
    if os.getenv("WATCHER_DISABLE_LOOP") != "1":   # tests drive poll_once directly
        asyncio.get_event_loop().create_task(_loop())


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {"ok": True, "service": "reporting-watcher", "tickers": WATCH_TICKERS}


@app.get("/status")
def status() -> dict[str, Any]:
    return {"tickers": WATCH_TICKERS, "poll_seconds": POLL_SECONDS, "project": PROJECT,
            "period": REPORT_PERIOD, "last_poll": STATE["last_poll"], "polls": STATE["polls"],
            "errors": STATE["errors"], "seen": len(STATE["seen"]), "runs": STATE["runs"][-10:]}


@app.post("/poke")
async def poke(authorization: str = Header(default="")) -> dict[str, Any]:
    """Manual trigger (the demo button). Same bearer the gateway takes — no second secret."""
    if not GATEWAY_TOKEN or authorization.removeprefix("Bearer ").strip() != GATEWAY_TOKEN:
        raise HTTPException(status_code=401, detail="bearer must match the gateway token")
    return {"processed": await poll_once()}
