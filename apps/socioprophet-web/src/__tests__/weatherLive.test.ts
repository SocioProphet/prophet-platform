import { describe, it, expect, vi, afterEach } from 'vitest';
import { fetchWeatherLive, wmoToCond } from '../data/adapters/weatherLive';

// 9 regions expected (order-aligned); build a valid batched Open-Meteo response.
function loc(code: number, tmax: number) {
  return {
    current: { temperature_2m: tmax, relative_humidity_2m: 60, weather_code: code, wind_speed_10m: 8 },
    daily: {
      time: ['2026-07-07', '2026-07-08', '2026-07-09', '2026-07-10', '2026-07-11', '2026-07-12', '2026-07-13'],
      temperature_2m_max: [tmax - 4, tmax, tmax + 1, tmax, tmax - 2, tmax, tmax + 3],
      temperature_2m_min: Array(7).fill(tmax - 15),
      precipitation_probability_max: Array(7).fill(20),
      weather_code: Array(7).fill(code),
    },
  };
}
const nineLocs = Array.from({ length: 9 }, () => loc(2, 78));
const mockFetch = (ok: boolean, body: unknown) => vi.fn().mockResolvedValue({ ok, json: () => Promise.resolve(body) });

afterEach(() => vi.restoreAllMocks());

describe('weather live adapter', () => {
  it('maps WMO codes to the Condition set', () => {
    expect(wmoToCond(95, 70)).toBe('storm');
    expect(wmoToCond(71, 30)).toBe('snow');
    expect(wmoToCond(61, 60)).toBe('rain');
    expect(wmoToCond(0, 70)).toBe('sun');
    expect(wmoToCond(0, 98)).toBe('heat'); // clear + hot
    expect(wmoToCond(3, 70)).toBe('cloud');
  });

  it('maps a valid response into 9 regions with today-vs-yesterday change + forecast', async () => {
    vi.stubGlobal('fetch', mockFetch(true, nineLocs));
    const r = await fetchWeatherLive();
    expect(r).not.toBeNull();
    expect(r!).toHaveLength(9);
    const dc = r![0]!;
    expect(dc.id).toBe('dc');
    expect(dc.tempF).toBe(78);
    expect(dc.changeF).toBe(4);          // todayMax 78 − yesterdayMax 74
    expect(dc.forecast.length).toBe(6);  // today onward (yesterday dropped)
    expect(dc.cond).toBe('cloud');
  });

  it('fails closed on non-200, wrong length, and throw', async () => {
    vi.stubGlobal('fetch', mockFetch(false, nineLocs));
    expect(await fetchWeatherLive()).toBeNull();
    vi.stubGlobal('fetch', mockFetch(true, [loc(2, 70)])); // only 1 location → reject
    expect(await fetchWeatherLive()).toBeNull();
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
    expect(await fetchWeatherLive()).toBeNull();
  });
});
