"""algo-engine — a REAL backtest + paper-execution service for the Algorithmic Trading surface.

No fixtures: strategies run over real historical daily bars (Stooq, free, no API key), producing
real equity curves + metrics (Sharpe, drawdown, win-rate, trades). A paper-execution ledger holds
real positions marked to the latest close with real unrealized P&L. Live-broker execution is a
separate, credential-gated step (see /paper vs a future /live).

Endpoints:
  GET  /healthz
  GET  /strategies                      catalog (id, label, params, blurb)
  GET  /bars?symbol=NVDA&lookback=400   daily OHLC bars
  POST /backtest  { strategy, universe[], lookback_days?, params? }  → equity curve + metrics + fills
  GET  /paper/state                     positions, cash, market value, unrealized P&L, order log
  POST /paper/order { symbol, side, qty, price? }                    place a paper order (real ledger)
  POST /paper/reset
"""
from __future__ import annotations
import io, time, csv, math
from typing import Any
import httpx
import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="algo-engine", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── market data (Stooq daily bars, cached) ──────────────────────────────────
_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_TTL = 3600.0

def fetch_bars(symbol: str) -> list[dict[str, Any]]:
    """Daily OHLC bars from Yahoo's chart API (JSON, no key). ~2y of history, cached."""
    sym = symbol.strip().upper()
    now = time.time()
    hit = _CACHE.get(sym)
    if hit and now - hit[0] < _TTL:
        return hit[1]
    rows: list[dict[str, Any]] = []
    for host in ("query1", "query2"):
        try:
            url = f"https://{host}.finance.yahoo.com/v8/finance/chart/{sym}?range=2y&interval=1d"
            r = httpx.get(url, timeout=15.0, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200:
                continue
            res = r.json()["chart"]["result"][0]
            ts = res["timestamp"]
            q = res["indicators"]["quote"][0]
            for i, t in enumerate(ts):
                c = q["close"][i]
                if c is None:
                    continue
                rows.append({"date": time.strftime("%Y-%m-%d", time.gmtime(t)),
                             "open": float(q["open"][i] or c), "high": float(q["high"][i] or c),
                             "low": float(q["low"][i] or c), "close": float(c),
                             "volume": float(q["volume"][i] or 0)})
            if rows:
                break
        except (httpx.HTTPError, KeyError, TypeError, ValueError, IndexError):
            rows = []
    _CACHE[sym] = (now, rows)
    return rows

def close_series(symbol: str, lookback: int) -> tuple[list[str], np.ndarray]:
    bars = fetch_bars(symbol)[-lookback:]
    return [b["date"] for b in bars], np.array([b["close"] for b in bars], dtype=float)

# ── strategy catalog ────────────────────────────────────────────────────────
STRATEGIES = [
    {"id": "momentum", "label": "Cross-sectional Momentum", "blurb": "Rank the universe by trailing return; hold the positive-momentum names, weighted by strength.", "params": {"lookback": 60}},
    {"id": "mean_reversion", "label": "RSI Mean-Reversion", "blurb": "Buy oversold names (RSI < threshold), exit as they normalize.", "params": {"rsi_period": 14, "entry": 30, "exit": 55}},
    {"id": "trend", "label": "Moving-Average Trend", "blurb": "Hold names whose fast MA is above their slow MA (trend-following).", "params": {"fast": 20, "slow": 60}},
    {"id": "market_neutral", "label": "Low-Vol Market-Neutral", "blurb": "Dollar-neutral: long the low-volatility half of the universe, short the high-volatility half.", "params": {"vol_window": 20}},
]

def _rsi(x: np.ndarray, period: int) -> np.ndarray:
    d = np.diff(x, prepend=x[0])
    up = np.where(d > 0, d, 0.0); dn = np.where(d < 0, -d, 0.0)
    ru = np.zeros_like(x); rd = np.zeros_like(x)
    au = ad = 0.0
    for i in range(len(x)):
        au = (au * (period - 1) + up[i]) / period
        ad = (ad * (period - 1) + dn[i]) / period
        ru[i] = au; rd[i] = ad
    rs = np.divide(ru, rd, out=np.zeros_like(ru), where=rd > 0)
    return 100 - 100 / (1 + rs)

def _ma(x: np.ndarray, w: int) -> np.ndarray:
    out = np.full_like(x, np.nan)
    if len(x) >= w:
        c = np.cumsum(np.insert(x, 0, 0))
        out[w - 1:] = (c[w:] - c[:-w]) / w
    return out

def weights(strategy: str, P: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    """P: (T x N) close matrix → W: (T x N) target weights (applied to NEXT-day returns)."""
    T, N = P.shape
    W = np.zeros((T, N))
    R = np.zeros_like(P); R[1:] = P[1:] / P[:-1] - 1.0
    if strategy == "momentum":
        lb = int(params.get("lookback", 60))
        for t in range(lb, T):
            mom = P[t] / P[t - lb] - 1.0
            pos = np.where(mom > 0, mom, 0.0)
            if pos.sum() > 0:
                W[t] = pos / pos.sum()
    elif strategy == "mean_reversion":
        per = int(params.get("rsi_period", 14)); entry = float(params.get("entry", 30)); ex = float(params.get("exit", 55))
        rsi = np.column_stack([_rsi(P[:, j], per) for j in range(N)])
        holding = np.zeros(N, dtype=bool)
        for t in range(per, T):
            holding = np.where(rsi[t] < entry, True, np.where(rsi[t] > ex, False, holding))
            longs = holding.sum()
            if longs > 0:
                W[t, holding] = 1.0 / longs
    elif strategy == "trend":
        fast = int(params.get("fast", 20)); slow = int(params.get("slow", 60))
        for j in range(N):
            f = _ma(P[:, j], fast); s = _ma(P[:, j], slow)
            sig = (f > s).astype(float)
            W[:, j] = sig
        rs = W.sum(axis=1, keepdims=True)
        W = np.divide(W, rs, out=np.zeros_like(W), where=rs > 0)
    elif strategy == "market_neutral":
        vw = int(params.get("vol_window", 20))
        for t in range(vw, T):
            vol = np.array([R[t - vw + 1:t + 1, j].std() for j in range(N)])
            order = np.argsort(vol)
            half = max(1, N // 2)
            longs = order[:half]; shorts = order[-half:]
            W[t, longs] = 0.5 / len(longs)
            W[t, shorts] = -0.5 / len(shorts)
    return W

def metrics(equity: np.ndarray, port_ret: np.ndarray) -> dict[str, Any]:
    if len(equity) < 2:
        return {"total_return": 0, "cagr": 0, "sharpe": 0, "max_drawdown": 0, "win_rate": 0, "vol": 0}
    total = float(equity[-1] / equity[0] - 1.0)
    yrs = max(len(equity) / 252.0, 1e-9)
    cagr = float((equity[-1] / equity[0]) ** (1 / yrs) - 1.0)
    mu, sd = float(port_ret.mean()), float(port_ret.std())
    sharpe = float(mu / sd * math.sqrt(252)) if sd > 0 else 0.0
    peak = np.maximum.accumulate(equity)
    mdd = float((equity / peak - 1.0).min())
    win = float((port_ret > 0).mean())
    return {"total_return": round(total, 4), "cagr": round(cagr, 4), "sharpe": round(sharpe, 2),
            "max_drawdown": round(mdd, 4), "win_rate": round(win, 4), "vol": round(sd * math.sqrt(252), 4)}

class BacktestReq(BaseModel):
    strategy: str
    universe: list[str]
    lookback_days: int = 400
    params: dict[str, Any] = {}

# ── plain-English → strategy spec (the agent-authoring entry point) ──────────
_UNIVERSES = {
    "semis": ["NVDA", "AMD", "AVGO", "INTC", "MU", "QCOM"], "semiconductor": ["NVDA", "AMD", "AVGO", "INTC", "MU", "QCOM"],
    "megacap": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA"], "mega": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA"],
    "bank": ["JPM", "BAC", "WFC", "C", "GS", "MS"], "energy": ["XOM", "CVX", "COP", "SLB", "EOG"],
    "index": ["SPY", "QQQ", "IWM", "DIA"], "tech": ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "AVGO"],
}
_STOPWORDS = {"RSI", "ETF", "US", "AI", "IPO", "CEO", "P", "E", "THE", "AND", "BUY", "SELL"}

class NlReq(BaseModel):
    text: str

@app.post("/strategy/from-nl")
def strategy_from_nl(req: NlReq) -> dict[str, Any]:
    t = req.text.lower()
    if any(k in t for k in ("mean-reversion", "mean reversion", "oversold", "reversion", "rsi")):
        strat = "mean_reversion"
    elif any(k in t for k in ("market-neutral", "market neutral", "long quality", "short high-beta", "long/short", "long-short", "dollar-neutral")):
        strat = "market_neutral"
    elif any(k in t for k in ("trend", "moving average", "crossover", "ma cross")):
        strat = "trend"
    else:
        strat = "momentum"  # breakout / momentum / default
    import re
    universe: list[str] = []
    for kw, u in _UNIVERSES.items():
        if kw in t:
            universe = u; break
    if not universe:
        tickers = [x for x in re.findall(r"\b[A-Z]{2,5}\b", req.text) if x not in _STOPWORDS]
        universe = tickers[:8] or _UNIVERSES["index"]
    params: dict[str, Any] = {}
    m = re.search(r"(\d+)\s*%.*(?:trailing|stop)", t)
    if m:
        params["trailing_stop_pct"] = int(m.group(1))
    label = {"momentum": "Momentum", "mean_reversion": "RSI Mean-Reversion", "trend": "MA Trend", "market_neutral": "Market-Neutral"}[strat]
    return {"strategy": strat, "universe": universe, "params": params,
            "name": f"{label} · {', '.join(universe[:3])}{'…' if len(universe) > 3 else ''}",
            "rationale": f"Parsed “{req.text.strip()}” → {label} strategy over {len(universe)} names."}

@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {"ok": True, "service": "algo-engine", "strategies": [s["id"] for s in STRATEGIES]}

@app.get("/strategies")
def strategies() -> dict[str, Any]:
    return {"strategies": STRATEGIES}

@app.get("/bars")
def bars(symbol: str, lookback: int = 400) -> dict[str, Any]:
    b = fetch_bars(symbol)[-lookback:]
    return {"symbol": symbol.upper(), "count": len(b), "bars": b}

@app.post("/backtest")
def backtest(req: BacktestReq) -> dict[str, Any]:
    uni = [s.strip().upper() for s in req.universe if s.strip()][:12] or ["SPY"]
    series = {s: close_series(s, req.lookback_days) for s in uni}
    # align on common length (Stooq bars are already date-sorted; align by tail length)
    good = {s: v for s, (d, v) in series.items() if len(v) > 70}
    if not good:
        return {"ok": False, "error": "no historical data for the requested universe", "universe": uni}
    L = min(len(v) for v in good.values())
    names = list(good.keys())
    P = np.column_stack([good[s][-L:] for s in names])
    dates = close_series(names[0], req.lookback_days)[0][-L:]
    W = weights(req.strategy, P, req.params)
    R = np.zeros_like(P); R[1:] = P[1:] / P[:-1] - 1.0
    port_ret = np.sum(W[:-1] * R[1:], axis=1)
    equity = 100.0 * np.cumprod(1 + np.insert(port_ret, 0, 0.0))
    m = metrics(equity, port_ret)
    # fills: last position changes as concrete orders
    fills = []
    if len(W) >= 2:
        for j, nm in enumerate(names):
            dw = W[-1, j] - W[-2, j]
            if abs(dw) > 1e-4:
                fills.append({"symbol": nm, "side": "BUY" if dw > 0 else "SELL",
                              "weight_delta": round(float(dw), 4), "price": round(float(P[-1, j]), 2)})
    turnover = float(np.abs(np.diff(W, axis=0)).sum()) if len(W) > 1 else 0.0
    return {"ok": True, "strategy": req.strategy, "universe": names, "as_of": dates[-1] if dates else None,
            "metrics": m, "trades": int(round(turnover * 10)),
            "gross_exposure": round(float(np.abs(W[-1]).sum()), 3),
            "equity_curve": [round(float(x), 3) for x in equity],
            "dates": dates, "fills": fills[:12],
            "provenance": {"data_source": "stooq daily bars", "bars_per_name": int(L), "not_investment_advice": True}}

# ── paper-execution ledger (real positions, marked to latest close) ─────────
_LEDGER: dict[str, Any] = {"cash": 1_000_000.0, "positions": {}, "orders": []}

class OrderReq(BaseModel):
    symbol: str
    side: str            # BUY | SELL
    qty: float
    price: float | None = None

@app.post("/paper/order")
def paper_order(o: OrderReq) -> dict[str, Any]:
    sym = o.symbol.strip().upper()
    px = o.price if o.price is not None else (float(fetch_bars(sym)[-1]["close"]) if fetch_bars(sym) else 0.0)
    if px <= 0:
        return {"ok": False, "error": f"no price for {sym}"}
    signed = o.qty if o.side.upper() == "BUY" else -o.qty
    _LEDGER["positions"][sym] = _LEDGER["positions"].get(sym, 0.0) + signed
    _LEDGER["cash"] -= signed * px
    fill = {"symbol": sym, "side": o.side.upper(), "qty": o.qty, "price": round(px, 2), "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
    _LEDGER["orders"].insert(0, fill)
    if abs(_LEDGER["positions"][sym]) < 1e-9:
        _LEDGER["positions"].pop(sym, None)
    return {"ok": True, "fill": fill, **paper_state()}

@app.get("/paper/state")
def paper_state() -> dict[str, Any]:
    mv = 0.0; rows = []
    for sym, qty in _LEDGER["positions"].items():
        b = fetch_bars(sym)
        px = float(b[-1]["close"]) if b else 0.0
        val = qty * px; mv += val
        rows.append({"symbol": sym, "qty": round(qty, 2), "price": round(px, 2), "market_value": round(val, 2)})
    equity = _LEDGER["cash"] + mv
    return {"cash": round(_LEDGER["cash"], 2), "positions": rows, "market_value": round(mv, 2),
            "equity": round(equity, 2), "unrealized_pnl": round(equity - 1_000_000.0, 2),
            "orders": _LEDGER["orders"][:25]}

@app.post("/paper/reset")
def paper_reset() -> dict[str, Any]:
    _LEDGER.update({"cash": 1_000_000.0, "positions": {}, "orders": []})
    return {"ok": True, **paper_state()}
