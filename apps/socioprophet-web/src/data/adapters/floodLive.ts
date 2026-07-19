import { fetchT } from './http';
// Live flood risk — real FEMA National Flood Hazard Layer (NFHL) flood zones, public
// ArcGIS FeatureServer, no key, GLOBAL-US, CORS. We pull flood-hazard polygons in the
// viewport and assign each hex cell the risk of the zone its centroid falls in,
// turning the synthetic "environment / flood risk" metric into real FEMA designations.
// Fails closed (null) → the map keeps the illustrative flood field. US-only (FEMA).
export interface FloodZone { risk: number; zone: string; minLon: number; minLat: number; maxLon: number; maxLat: number; rings: number[][][] }
export interface FloodBBox { s: number; w: number; n: number; e: number }

// FEMA flood-zone code → approximate annual-risk % for the choropleth.
// A*/V* = Special Flood Hazard Area (1% annual, "100-year"); X/0.2% = moderate/minimal.
export function floodRiskForZone(zone: string): number {
  const z = (zone || '').toUpperCase();
  if (/^A|^V/.test(z)) return 35;              // SFHA — high
  if (z.includes('0.2') || z === 'X') return 8; // moderate / minimal
  if (z === 'D') return 15;                     // undetermined
  return 4;
}

const ENDPOINT = 'https://hazards.fema.gov/gis/nfhl/rest/services/public/NFHL/MapServer/28/query';

function exteriorRings(geometry: unknown): number[][][] {
  const g = geometry as { type?: string; coordinates?: unknown } | null;
  if (!g || !Array.isArray(g.coordinates)) return [];
  if (g.type === 'Polygon') return [(g.coordinates as number[][][])[0] ?? []];
  if (g.type === 'MultiPolygon') return (g.coordinates as number[][][][]).map((p) => p?.[0] ?? []);
  return [];
}

export async function fetchFloodZones(bbox: FloodBBox, limit = 2000): Promise<FloodZone[] | null> {
  try {
    const env = `${bbox.w},${bbox.s},${bbox.e},${bbox.n}`;
    const url = `${ENDPOINT}?geometry=${env}&geometryType=esriGeometryEnvelope&inSR=4326&outSR=4326&spatialRel=esriSpatialRelIntersects&outFields=FLD_ZONE&returnGeometry=true&resultRecordCount=${limit}&f=geojson`;
    const res = await fetchT(url, { headers: { accept: 'application/json' } }, 14000);
    if (!res.ok) return null;
    const j = (await res.json()) as { features?: Array<{ properties?: { FLD_ZONE?: string }; geometry?: unknown }> };
    if (!Array.isArray(j.features) || !j.features.length) return null;
    const out: FloodZone[] = [];
    for (const f of j.features) {
      const rings = exteriorRings(f.geometry).filter((r) => r.length >= 3);
      if (!rings.length) continue;
      let minLon = Infinity, minLat = Infinity, maxLon = -Infinity, maxLat = -Infinity;
      for (const r of rings) for (const pt of r) {
        const lon = pt[0]!, lat = pt[1]!;
        if (lon < minLon) minLon = lon; if (lon > maxLon) maxLon = lon;
        if (lat < minLat) minLat = lat; if (lat > maxLat) maxLat = lat;
      }
      const zone = f.properties?.FLD_ZONE ?? '';
      out.push({ risk: floodRiskForZone(zone), zone, minLon, minLat, maxLon, maxLat, rings });
    }
    return out.length ? out : null;
  } catch {
    return null;
  }
}

function inRing(lon: number, lat: number, ring: number[][]): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const xi = ring[i]![0]!, yi = ring[i]![1]!, xj = ring[j]![0]!, yj = ring[j]![1]!;
    if (((yi > lat) !== (yj > lat)) && (lon < ((xj - xi) * (lat - yi)) / ((yj - yi) || 1e-12) + xi)) inside = !inside;
  }
  return inside;
}

// Highest-risk flood zone containing (lon, lat), with its label — so the painted
// risk and the reported FEMA zone can never disagree (both come from one argmax).
// risk = -1 / zone = '' when the point is in no mapped zone.
export function floodInfoAt(lon: number, lat: number, zones: FloodZone[]): { risk: number; zone: string } {
  let risk = -1; let zone = '';
  for (const z of zones) {
    if (lon < z.minLon || lon > z.maxLon || lat < z.minLat || lat > z.maxLat) continue;
    for (const r of z.rings) if (inRing(lon, lat, r)) { if (z.risk > risk) { risk = z.risk; zone = z.zone; } break; }
  }
  return { risk, zone };
}
export function floodRiskAt(lon: number, lat: number, zones: FloodZone[]): number {
  return floodInfoAt(lon, lat, zones).risk;
}
