#!/usr/bin/env python3
"""emit_company_financials — free, no-key public fundamentals for ANY listed company,
so Value Driver Studio can auto-build a VDT profile for any exchange:ticker.

Source: Yahoo Finance's public quoteSummary, reached via the cookie+crumb handshake
(unofficial, best-effort, $0). Global coverage incl. ASX (e.g. GYG.AX). Stdlib only
(urllib + http.cookiejar) so the dashboard-bff gains no new dependency. If the handshake
fails, the endpoint returns available=false and the Studio falls back to manual entry.
Never presents estimates as audited figures — the caller labels provenance.
"""
from __future__ import annotations

import json
import http.cookiejar
import urllib.request
import urllib.error

_UA = "Mozilla/5.0 (compatible; SocioProphet/1.0)"
_MODULES = "price,summaryDetail,defaultKeyStatistics,financialData"


def _raw(node) -> float | None:
    if isinstance(node, dict):
        return node.get("raw")
    return node if isinstance(node, (int, float)) else None


def fetch(ticker: str) -> dict:
    """Pull public fundamentals for a ticker (e.g. 'GYG.AX', 'AAPL'). Returns a normalized
    dict with available=True/False and provenance. Never raises to the caller."""
    t = (ticker or "").strip().upper()
    if not t:
        return {"ticker": ticker, "available": False, "error": "no ticker"}
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.addheaders = [("User-Agent", _UA)]
    try:
        opener.open("https://fc.yahoo.com", timeout=12).read()
    except Exception:
        pass  # cookie may still be set / not required
    try:
        crumb = opener.open("https://query1.finance.yahoo.com/v1/test/getcrumb", timeout=12).read().decode().strip()
        url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{urllib.parse.quote(t)}?modules={_MODULES}&crumb={urllib.parse.quote(crumb)}"
        body = json.loads(opener.open(url, timeout=15).read().decode())
        r = (body.get("quoteSummary") or {}).get("result")
        if not r:
            return {"ticker": t, "available": False, "error": "no data (bad ticker or blocked)"}
        q = r[0]
        price, dks, fd = q.get("price", {}), q.get("defaultKeyStatistics", {}), q.get("financialData", {})
        return {
            "ticker": t,
            "available": True,
            "name": price.get("longName") or price.get("shortName") or t,
            "currency": price.get("currency"),
            "exchange": price.get("exchangeName"),
            "market_cap": _raw(price.get("marketCap")),
            "enterprise_value": _raw(dks.get("enterpriseValue")),
            "revenue_ttm": _raw(fd.get("totalRevenue")),
            "gross_margin": _raw(fd.get("grossMargins")),
            "ebitda_margin": _raw(fd.get("ebitdaMargins")),
            "operating_margin": _raw(fd.get("operatingMargins")),
            "profit_margin": _raw(dks.get("profitMargins")),
            "provenance": {
                "source": "Yahoo Finance public quoteSummary (unofficial, no-key)",
                "basis": "public_market_data",
                "note": "Best-effort free data; verify before use. Manual entry available as override.",
            },
        }
    except urllib.error.HTTPError as e:
        return {"ticker": t, "available": False, "error": f"http {e.code}"}
    except Exception as e:  # noqa: BLE001
        return {"ticker": t, "available": False, "error": str(e)[:120]}


if __name__ == "__main__":
    import sys
    print(json.dumps(fetch(sys.argv[1] if len(sys.argv) > 1 else "GYG.AX"), indent=2))
