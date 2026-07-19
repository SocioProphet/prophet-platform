import { fetchT } from './http';
// Live civic data — real demographics from the US Census ACS 5-year API joined to
// real census-tract polygons from TIGERweb, both public + no key. ACS returns
// values keyed by GEOID (no geometry); TIGER returns tract polygons with GEOID; we
// join them into a GeoJSON choropleth of REAL median household income per tract.
// Fails closed (null) → the map stays on the fixture hex grid. Default extent is
// New York County (Manhattan, state 36 / county 061). NOTE: TIGERweb CORS + exact
// layer id can vary by deployment; the join logic below is what's unit-tested, and
// the whole thing degrades gracefully if either service is unreachable.

export interface CensusTract {
  type: 'Feature';
  properties: { geoid: string; name: string; medianIncome: number; population: number };
  geometry: unknown;
}
export interface CensusFC { type: 'FeatureCollection'; features: CensusTract[] }

type AcsRows = string[][];
interface TigerFeature { properties?: Record<string, string>; geometry?: unknown }

// Pure join — ACS table rows + TIGER geojson features → enriched tract features.
export function joinCensus(acs: AcsRows, tiger: { features?: TigerFeature[] }): CensusFC {
  const header = acs[0] ?? [];
  const iInc = header.indexOf('B19013_001E');
  const iPop = header.indexOf('B01003_001E');
  const iState = header.indexOf('state');
  const iCounty = header.indexOf('county');
  const iTract = header.indexOf('tract');
  const byGeoid = new Map<string, { income: number; population: number; name: string }>();
  for (const row of acs.slice(1)) {
    const geoid = `${row[iState]}${row[iCounty]}${row[iTract]}`;
    const income = Number(row[iInc]);
    const pop = Number(row[iPop]);
    // ACS returns a large negative sentinel (e.g. -666666666) for suppressed values —
    // guard BOTH income and population against it (|| 0 only catches falsy, not negatives).
    byGeoid.set(geoid, { income: income > 0 ? income : 0, population: pop > 0 ? pop : 0, name: row[0] ?? geoid });
  }
  const features: CensusTract[] = [];
  for (const f of tiger.features ?? []) {
    const geoid = f.properties?.GEOID ?? f.properties?.geoid ?? '';
    const d = byGeoid.get(geoid);
    if (!geoid || !d || !f.geometry) continue;
    features.push({ type: 'Feature', properties: { geoid, name: d.name, medianIncome: d.income, population: d.population }, geometry: f.geometry });
  }
  return { type: 'FeatureCollection', features };
}

const ACS = 'https://api.census.gov/data/2023/acs/acs5';
const TIGER = 'https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Tracts_Blocks/MapServer/0/query';

export async function fetchCensus(state = '36', county = '061'): Promise<CensusFC | null> {
  try {
    const acsUrl = `${ACS}?get=NAME,B19013_001E,B01003_001E&for=tract:*&in=state:${state}&in=county:${county}`;
    const tigerUrl = `${TIGER}?where=${encodeURIComponent(`STATE='${state}' AND COUNTY='${county}'`)}&outFields=GEOID&returnGeometry=true&outSR=4326&f=geojson`;
    const [acsRes, tigerRes] = await Promise.all([fetchT(acsUrl, { headers: { accept: 'application/json' } }, 12000), fetchT(tigerUrl, { headers: { accept: 'application/json' } }, 12000)]);
    if (!acsRes.ok || !tigerRes.ok) return null;
    const acs = (await acsRes.json()) as AcsRows;
    const tiger = (await tigerRes.json()) as { features?: TigerFeature[] };
    if (!Array.isArray(acs) || acs.length < 2 || !tiger.features?.length) return null;
    const fc = joinCensus(acs, tiger);
    return fc.features.length ? fc : null;
  } catch {
    return null;
  }
}
