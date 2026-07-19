import { fetchT } from './http';
// Live crime — real reported incidents from municipal Socrata Open Data portals (no
// key, CORS). We pick the city whose bbox contains the current viewport centre, pull
// incidents there, and bin them to the map's hex cells — turning the synthetic "safety"
// layer into REAL reported-incident intensity that climbs the ontogenesis Ω ladder.
// Fails closed (null) → fixture. Extensible: add a city to SOCRATA_CRIME_CITIES.
export interface CrimePoint { lon: number; lat: number; category: string }
export interface CrimeBBox { s: number; w: number; n: number; e: number }

export interface SocrataCrimeCity {
  name: string;
  s: number; w: number; n: number; e: number; // city bbox
  domain: string; dataset: string;             // Socrata host + 4x4 dataset id
  latField: string; lonField: string; catField: string;
}

// Well-known, stable municipal crime datasets (latitude/longitude columns confirmed).
export const SOCRATA_CRIME_CITIES: SocrataCrimeCity[] = [
  { name: 'New York', s: 40.49, w: -74.27, n: 40.92, e: -73.68, domain: 'data.cityofnewyork.us', dataset: '5uac-w243', latField: 'latitude', lonField: 'longitude', catField: 'law_cat_cd' },
  { name: 'Chicago', s: 41.64, w: -87.94, n: 42.02, e: -87.52, domain: 'data.cityofchicago.org', dataset: 'ijzp-q8t2', latField: 'latitude', lonField: 'longitude', catField: 'primary_type' },
  { name: 'San Francisco', s: 37.70, w: -122.52, n: 37.83, e: -122.35, domain: 'data.sfgov.org', dataset: 'wg3w-h783', latField: 'latitude', lonField: 'longitude', catField: 'incident_category' },
];

export function crimeCityForPoint(lat: number, lon: number): SocrataCrimeCity | null {
  return SOCRATA_CRIME_CITIES.find((c) => lat >= c.s && lat <= c.n && lon >= c.w && lon <= c.e) ?? null;
}

export async function fetchCrime(bbox: CrimeBBox, limit = 4000): Promise<CrimePoint[] | null> {
  const clat = (bbox.s + bbox.n) / 2, clon = (bbox.w + bbox.e) / 2;
  const city = crimeCityForPoint(clat, clon);
  if (!city) return null; // outside a supported city → fail closed (stay illustrative)
  try {
    const { latField: la, lonField: lo, catField: cat } = city;
    const where = `${la} > ${bbox.s} AND ${la} < ${bbox.n} AND ${lo} > ${bbox.w} AND ${lo} < ${bbox.e} AND ${la} IS NOT NULL`;
    const url = `https://${city.domain}/resource/${city.dataset}.json?$select=${la},${lo},${cat}&$where=${encodeURIComponent(where)}&$limit=${limit}`;
    const res = await fetchT(url, { headers: { accept: 'application/json' } }, 12000);
    if (!res.ok) return null;
    const rows = (await res.json()) as Array<Record<string, string | undefined>>;
    if (!Array.isArray(rows) || !rows.length) return null;
    const pts: CrimePoint[] = [];
    for (const r of rows) {
      const rlat = r[la], rlon = r[lo];
      // Number(null)/Number('') are 0 (not NaN) — reject empties + null-island coords.
      if (rlat == null || rlon == null || rlat === '' || rlon === '') continue;
      const lat = Number(rlat); const lon = Number(rlon);
      if (!Number.isFinite(lat) || !Number.isFinite(lon) || lat === 0 || lon === 0) continue;
      pts.push({ lon, lat, category: r[cat] ?? 'UNKNOWN' });
    }
    return pts.length ? pts : null;
  } catch {
    return null;
  }
}
