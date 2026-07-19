import { fetchT } from './http';
// Reverse-geocode a lat/lon to its US county FIPS via the FCC Area API (public, no
// key, CORS). This is what lets the census/income layer FOLLOW the viewport — real
// ACS data anywhere in the US, not just the pinned New York County. Fails closed
// (null) → callers fall back to the default county.
export interface CountyFips { state: string; county: string; name: string }

const ENDPOINT = 'https://geo.fcc.gov/api/census/area';

export async function fetchCountyFips(lat: number, lon: number): Promise<CountyFips | null> {
  try {
    const url = `${ENDPOINT}?lat=${lat}&lon=${lon}&censusYear=2020&format=json`;
    const res = await fetchT(url, { headers: { accept: 'application/json' } }, 10000);
    if (!res.ok) return null;
    const j = (await res.json()) as { results?: Array<{ county_fips?: string; county_name?: string; state_name?: string }> };
    const r = j.results?.find((x) => x.county_fips && x.county_fips.length === 5);
    if (!r || !r.county_fips) return null;
    return { state: r.county_fips.slice(0, 2), county: r.county_fips.slice(2), name: `${r.county_name ?? ''}${r.state_name ? ', ' + r.state_name : ''}`.trim() };
  } catch {
    return null;
  }
}
