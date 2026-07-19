import { describe, it, expect, vi, afterEach } from 'vitest';
import { fetchWorldBankIndicators } from '../data/adapters/worldBankLive';

// World Bank returns [meta, rows] with rows newest-first.
const wbRows = (vals: Array<[string, number | null]>) => [{ page: 1 }, vals.map(([date, value]) => ({ date, value }))];
afterEach(() => vi.restoreAllMocks());

describe('worldBankLive', () => {
  it('maps a WB series (newest-first) to an Indicator oldest→newest with change', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(JSON.stringify(
      wbRows([['2024', 2.8], ['2023', 2.5], ['2022', null], ['2021', 5.9]]),
    ), { status: 200 }))));
    const r = await fetchWorldBankIndicators('USA');
    expect(r).not.toBeNull();
    const gdp = r!.find((i) => i.id === 'wb-gdp')!;
    expect(gdp.series).toEqual([5.9, 2.5, 2.8]); // nulls dropped, reversed to oldest→newest
    expect(gdp.value).toBe(2.8);
    expect(gdp.changeAbs).toBe(0.3); // 2.8 − 2.5
    expect(gdp.unit).toBe('%');
  });

  it('fails closed when every series is unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response('', { status: 500 }))));
    expect(await fetchWorldBankIndicators('USA')).toBeNull();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('net'))));
    expect(await fetchWorldBankIndicators('USA')).toBeNull();
  });

  it('drops series with <2 points but keeps the rest', async () => {
    let n = 0;
    vi.stubGlobal('fetch', vi.fn(() => { n += 1; return Promise.resolve(new Response(JSON.stringify(
      n === 1 ? wbRows([['2024', 3.1], ['2023', 2.9]]) : wbRows([['2024', null]]),
    ), { status: 200 })); }));
    const r = await fetchWorldBankIndicators('USA');
    expect(r).toHaveLength(1);
  });
});
