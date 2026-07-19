import { fetchT } from './http';
// Live markets adapter — flips the crypto asset class off FIXTURE using CoinGecko's
// public simple-price endpoint (no key, CORS-enabled). Returns a map of our symbol
// → live USD price + 24h change, which MarketMonitor overlays onto the fixture
// instruments. Fails closed (returns null) so we fall back to fixture on
// offline / rate-limit (429) / block.

// Our instrument symbol → CoinGecko coin id.
const IDS: Record<string, string> = {
  BTCUSD: 'bitcoin',
  ETHUSD: 'ethereum',
  SOLUSD: 'solana',
  XRPUSD: 'ripple',
  AVAXUSD: 'avalanche-2',
  DOGEUSD: 'dogecoin',
};

export interface CryptoQuote { price: number; changePct: number }

export async function fetchCryptoLive(): Promise<Map<string, CryptoQuote> | null> {
  try {
    const ids = Object.values(IDS).join(',');
    const url = `https://api.coingecko.com/api/v3/simple/price?ids=${ids}&vs_currencies=usd&include_24hr_change=true`;
    const res = await fetchT(url, { headers: { accept: 'application/json' } });
    if (!res.ok) return null; // 429 rate-limit / offline → fixture
    const j = (await res.json()) as Record<string, { usd?: number; usd_24h_change?: number }>;
    const out = new Map<string, CryptoQuote>();
    for (const [sym, id] of Object.entries(IDS)) {
      const q = j[id];
      if (q && typeof q.usd === 'number') {
        out.set(sym, {
          price: +q.usd.toFixed(q.usd < 10 ? 4 : 2),
          changePct: +Number(q.usd_24h_change ?? 0).toFixed(2),
        });
      }
    }
    return out.size ? out : null;
  } catch {
    return null;
  }
}

// FX via Frankfurter (frankfurter.dev, ECB data, no key, CORS). Handles the mixed
// quote conventions: EURUSD/GBPUSD/AUDUSD are USD-per-foreign (invert USD-base
// rate); USDJPY/USDCHF/USDCAD are foreign-per-USD (direct). Change is best-effort
// vs ~a week prior. Same Map<symbol, quote> shape as crypto so it merges cleanly.
function fxQuote(sym: string, r: Record<string, number>): number {
  switch (sym) {
    case 'USDJPY': return r.JPY ?? 0;
    case 'USDCHF': return r.CHF ?? 0;
    case 'USDCAD': return r.CAD ?? 0;
    case 'EURUSD': return r.EUR ? 1 / r.EUR : 0;
    case 'GBPUSD': return r.GBP ? 1 / r.GBP : 0;
    case 'AUDUSD': return r.AUD ? 1 / r.AUD : 0;
    default: return 0;
  }
}

export async function fetchFxLive(): Promise<Map<string, CryptoQuote> | null> {
  try {
    const q = 'base=USD&symbols=EUR,JPY,GBP,CHF,AUD,CAD';
    const latest = await fetchT(`https://api.frankfurter.dev/v1/latest?${q}`, { headers: { accept: 'application/json' } });
    if (!latest.ok) return null;
    const lj = (await latest.json()) as { date?: string; rates?: Record<string, number> };
    const r = lj.rates;
    if (!r) return null;
    let prior: Record<string, number> = {};
    try {
      const d = new Date(lj.date ?? Date.now());
      d.setDate(d.getDate() - 7);
      const p = await fetchT(`https://api.frankfurter.dev/v1/${d.toISOString().slice(0, 10)}?${q}`, { headers: { accept: 'application/json' } });
      if (p.ok) prior = ((await p.json()) as { rates?: Record<string, number> }).rates ?? {};
    } catch { /* change is best-effort */ }
    const out = new Map<string, CryptoQuote>();
    for (const sym of ['EURUSD', 'USDJPY', 'GBPUSD', 'USDCHF', 'AUDUSD', 'USDCAD']) {
      const now = fxQuote(sym, r);
      if (!now) continue;
      const before = Object.keys(prior).length ? fxQuote(sym, prior) : now;
      const changePct = before ? +(((now - before) / before) * 100).toFixed(2) : 0;
      out.set(sym, { price: +now.toFixed(now < 10 ? 4 : 2), changePct });
    }
    return out.size ? out : null;
  } catch {
    return null;
  }
}
