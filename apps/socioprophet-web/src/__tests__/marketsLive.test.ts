import { describe, it, expect, vi, afterEach } from 'vitest';
import { fetchCryptoLive, fetchFxLive } from '../data/adapters/marketsLive';

const sample = {
  bitcoin: { usd: 63125.4, usd_24h_change: 2.31 },
  ethereum: { usd: 3410.88, usd_24h_change: -1.12 },
  solana: { usd: 151.2, usd_24h_change: 4.9 },
  ripple: { usd: 0.4921, usd_24h_change: 0.4 },
  'avalanche-2': { usd: 28.44, usd_24h_change: -3.1 },
  dogecoin: { usd: 0.1256, usd_24h_change: 1.8 },
};
const mockFetch = (ok: boolean, body: unknown) => vi.fn().mockResolvedValue({ ok, json: () => Promise.resolve(body) });
afterEach(() => vi.restoreAllMocks());

describe('markets live (crypto) adapter', () => {
  it('maps CoinGecko ids back to our symbols with price + 24h change', async () => {
    vi.stubGlobal('fetch', mockFetch(true, sample));
    const m = await fetchCryptoLive();
    expect(m).not.toBeNull();
    expect(m!.get('BTCUSD')).toEqual({ price: 63125.4, changePct: 2.31 });
    expect(m!.get('ETHUSD')!.changePct).toBe(-1.12);
    // sub-$10 assets keep 4 decimals
    expect(m!.get('XRPUSD')!.price).toBe(0.4921);
    expect(m!.get('DOGEUSD')!.price).toBe(0.1256);
    expect(m!.size).toBe(6);
  });

  it('fails closed on non-200 (e.g. 429 rate-limit), throw, and empty', async () => {
    vi.stubGlobal('fetch', mockFetch(false, sample));
    expect(await fetchCryptoLive()).toBeNull();
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
    expect(await fetchCryptoLive()).toBeNull();
    vi.stubGlobal('fetch', mockFetch(true, {}));
    expect(await fetchCryptoLive()).toBeNull();
  });

  it('FX handles mixed quote conventions (invert USD-base for EURUSD, direct for USDJPY)', async () => {
    // USD-base rates: 1 USD = 0.92 EUR, 161 JPY, 0.79 GBP, ...
    const latest = { date: '2026-07-08', rates: { EUR: 0.92, JPY: 161.0, GBP: 0.79, CHF: 0.90, AUD: 1.50, CAD: 1.37 } };
    const prior = { rates: { EUR: 0.90, JPY: 160.0, GBP: 0.80, CHF: 0.90, AUD: 1.50, CAD: 1.37 } };
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(latest) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(prior) }));
    const m = await fetchFxLive();
    expect(m).not.toBeNull();
    // EURUSD = 1 / 0.92 ≈ 1.087 (inverted)
    expect(m!.get('EURUSD')!.price).toBeCloseTo(1.087, 2);
    // USDJPY = 161.0 direct
    expect(m!.get('USDJPY')!.price).toBe(161);
    // EUR strengthened vs USD (0.90→0.92 per USD means USD stronger → EURUSD fell)
    expect(m!.get('EURUSD')!.changePct).toBeLessThan(0);
  });

  it('FX fails closed when latest is not ok', async () => {
    vi.stubGlobal('fetch', mockFetch(false, {}));
    expect(await fetchFxLive()).toBeNull();
  });
});
