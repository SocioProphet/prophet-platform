import { fetchT } from './http';
// Live weather adapter — flips WeatherMonitor's regions from FIXTURE to real
// current conditions + forecast via Open-Meteo (open-meteo.com): free, no API
// key, CORS-enabled. One batched request for all regions. Maps into the same
// Region / DayForecast shape the fixture uses. Fails closed (returns null) so the
// surface falls back to fixture when offline/blocked.
import type { Region, Condition, DayForecast } from '../weatherFixture';

// The fixture regions carry no coordinates — supply them here so the adapter can
// resolve each to a real Open-Meteo point (order-aligned with the response array).
const COORDS: Array<{ id: string; name: string; country: string; lat: number; lon: number }> = [
  { id: 'dc', name: 'Washington', country: 'US', lat: 38.90, lon: -77.04 },
  { id: 'nyc', name: 'New York', country: 'US', lat: 40.71, lon: -74.01 },
  { id: 'bru', name: 'Brussels', country: 'BE', lat: 50.85, lon: 4.35 },
  { id: 'sto', name: 'Stockholm', country: 'SE', lat: 59.33, lon: 18.07 },
  { id: 'amm', name: 'Amman', country: 'JO', lat: 31.95, lon: 35.93 },
  { id: 'sin', name: 'Singapore', country: 'SG', lat: 1.35, lon: 103.82 },
  { id: 'anf', name: 'Antofagasta', country: 'CL', lat: -23.65, lon: -70.40 },
  { id: 'tpe', name: 'Hsinchu / Taipei', country: 'TW', lat: 24.80, lon: 120.97 },
  { id: 'sha', name: 'Shanghai', country: 'CN', lat: 31.23, lon: 121.47 },
];

// WMO weather code → our Condition set.
export function wmoToCond(code: number, tempF: number): Condition {
  if ([95, 96, 99].includes(code)) return 'storm';
  if ([71, 72, 73, 74, 75, 77, 85, 86].includes(code)) return 'snow';
  if (code >= 51 && code <= 82) return 'rain';
  if (code === 0 || code === 1) return tempF >= 95 ? 'heat' : 'sun';
  return 'cloud';
}

const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const dayLabel = (iso: string) => DAYS[new Date(iso).getUTCDay()] ?? iso.slice(5, 10);
const n = (v: unknown, d = 0) => (Number.isFinite(Number(v)) ? Number(v) : d);

interface RawLoc {
  current?: { temperature_2m?: number; relative_humidity_2m?: number; weather_code?: number; wind_speed_10m?: number };
  daily?: { time?: string[]; temperature_2m_max?: number[]; temperature_2m_min?: number[]; precipitation_probability_max?: number[]; weather_code?: number[] };
}

export async function fetchWeatherLive(): Promise<Region[] | null> {
  try {
    const lat = COORDS.map((c) => c.lat).join(',');
    const lon = COORDS.map((c) => c.lon).join(',');
    const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}`
      + '&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m'
      + '&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code'
      + '&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=auto&past_days=1&forecast_days=6';
    const res = await fetchT(url, { headers: { accept: 'application/json' } });
    if (!res.ok) return null;
    const j = (await res.json()) as RawLoc | RawLoc[];
    const arr = Array.isArray(j) ? j : [j];
    if (arr.length !== COORDS.length) return null;
    return arr.map((loc, k): Region => {
      const c = COORDS[k]!;
      const cur = loc.current ?? {};
      const d = loc.daily ?? {};
      const maxes = d.temperature_2m_max ?? [];
      const mins = d.temperature_2m_min ?? [];
      const codes = d.weather_code ?? [];
      const precs = d.precipitation_probability_max ?? [];
      const times = d.time ?? [];
      const tempF = Math.round(n(cur.temperature_2m, maxes[1] ?? 0));
      const cond = wmoToCond(n(cur.weather_code, codes[1] ?? 0), tempF);
      const changeF = Math.round(n(maxes[1], tempF) - n(maxes[0], tempF)); // today vs yesterday max
      const forecast: DayForecast[] = times.slice(1).map((t, i) => ({
        day: dayLabel(t),
        hi: Math.round(n(maxes[i + 1])),
        lo: Math.round(n(mins[i + 1])),
        precip: Math.round(n(precs[i + 1])),
        cond: wmoToCond(n(codes[i + 1]), Math.round(n(maxes[i + 1]))),
      }));
      return {
        id: c.id,
        name: c.name,
        country: c.country,
        tempF,
        cond,
        changeF,
        windMph: Math.round(n(cur.wind_speed_10m)),
        humidity: Math.round(n(cur.relative_humidity_2m)),
        series: maxes.slice(1).map((x) => Math.round(n(x))),
        forecast,
      };
    });
  } catch {
    return null;
  }
}
