import { describe, it, expect, vi, afterEach } from 'vitest';
import { fetchAirQuality } from '../data/adapters/airLive';

const ok = (body: unknown) => Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
afterEach(() => vi.restoreAllMocks());

describe('airLive (Open-Meteo air quality)', () => {
  const pts: Array<[number, number]> = [[-73.98, 40.75], [-73.95, 40.72]];

  it('maps a multi-location response to AirPoints aligned by index', async () => {
    vi.stubGlobal('fetch', vi.fn(() => ok([{ current: { us_aqi: 42 } }, { current: { us_aqi: 88 } }])));
    const r = await fetchAirQuality(pts);
    expect(r).toEqual([{ lon: -73.98, lat: 40.75, aqi: 42 }, { lon: -73.95, lat: 40.72, aqi: 88 }]);
  });

  it('handles a single-location object response', async () => {
    vi.stubGlobal('fetch', vi.fn(() => ok({ current: { us_aqi: 55 } })));
    const r = await fetchAirQuality([[-73.98, 40.75]]);
    expect(r).toEqual([{ lon: -73.98, lat: 40.75, aqi: 55 }]);
  });

  it('drops points with missing/invalid aqi', async () => {
    vi.stubGlobal('fetch', vi.fn(() => ok([{ current: { us_aqi: 42 } }, { current: {} }])));
    const r = await fetchAirQuality(pts);
    expect(r).toHaveLength(1);
  });

  it('returns null on empty input, non-200, and thrown fetch (fails closed)', async () => {
    expect(await fetchAirQuality([])).toBeNull();
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response('', { status: 500 }))));
    expect(await fetchAirQuality(pts)).toBeNull();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('net'))));
    expect(await fetchAirQuality(pts)).toBeNull();
  });
});
