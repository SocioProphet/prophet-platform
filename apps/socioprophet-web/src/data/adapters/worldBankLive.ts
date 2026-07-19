import { fetchT } from './http';
import type { Indicator } from '../economyFixture';
// Live macro indicators — REAL series from the World Bank Open Data API (public, NO
// key, CORS, global). Turns the Economy board's synthetic KPI tiles into real
// GDP growth / inflation / unemployment / labour-participation for a country.
// Fails closed (null) → the board stays on the illustrative indicators.
const BASE = 'https://api.worldbank.org/v2';

interface WbDef { id: string; code: string; name: string; unit: string; better: 'higher' | 'lower' }
const SERIES: WbDef[] = [
  { id: 'wb-gdp', code: 'NY.GDP.MKTP.KD.ZG', name: 'GDP growth', unit: '%', better: 'higher' },
  { id: 'wb-cpi', code: 'FP.CPI.TOTL.ZG', name: 'Inflation (CPI)', unit: '%', better: 'lower' },
  { id: 'wb-unemp', code: 'SL.UEM.TOTL.ZS', name: 'Unemployment', unit: '%', better: 'lower' },
  { id: 'wb-lfpr', code: 'SL.TLF.CACT.ZS', name: 'Labour participation', unit: '%', better: 'higher' },
];

type WbRow = { date?: string; value?: number | null };

async function fetchSeries(country: string, def: WbDef): Promise<Indicator | null> {
  const url = `${BASE}/country/${country}/indicator/${def.code}?format=json&per_page=14&date=2012:2025`;
  const res = await fetchT(url, { headers: { accept: 'application/json' } }, 12000);
  if (!res.ok) return null;
  const j = (await res.json()) as [unknown, WbRow[] | null];
  const rows = Array.isArray(j) ? j[1] : null;
  if (!Array.isArray(rows)) return null;
  // API returns newest-first; keep non-null, order oldest→newest for the sparkline.
  const pts = rows.filter((r) => typeof r.value === 'number').reverse() as Array<{ date: string; value: number }>;
  if (pts.length < 2) return null;
  const series = pts.map((p) => +p.value.toFixed(2));
  const value = series[series.length - 1]!;
  const prev = series[series.length - 2]!;
  return {
    id: def.id, name: def.name, group: def.better === 'higher' ? 'macro' : 'macro',
    value, unit: def.unit, changeAbs: +(value - prev).toFixed(2), better: def.better,
    series, note: `World Bank ${def.code} — real annual series (${pts[0]!.date}–${pts[pts.length - 1]!.date}).`,
  } as Indicator;
}

export async function fetchWorldBankIndicators(country = 'USA'): Promise<Indicator[] | null> {
  try {
    const settled = await Promise.all(SERIES.map((d) => fetchSeries(country, d).catch(() => null)));
    const out = settled.filter((x): x is Indicator => x != null);
    return out.length ? out : null;
  } catch {
    return null;
  }
}
