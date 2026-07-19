// Join real ACS census-tract median income onto the map's aggregation cells by
// point-in-polygon: a cell takes the income of the tract its centroid falls in.
// This turns the economic layer's income metric from synthetic sample data into a
// real, sourced value (the rest of the civic grid stays illustrative). Tracts are
// GeoJSON Polygon / MultiPolygon in [lon, lat]; we ray-cast the exterior ring(s)
// with a bbox pre-filter so the whole join stays ~cells × few-candidate-tracts.
import type { CensusFC } from './adapters/censusLive';

export interface PreppedTract {
  income: number;
  population: number;
  minLon: number; minLat: number; maxLon: number; maxLat: number;
  rings: number[][][]; // exterior ring per polygon part
}

// Exterior ring(s) of a GeoJSON Polygon / MultiPolygon (holes ignored — tract
// interiors don't change which tract a centroid lands in for our purposes).
function exteriorRings(geometry: unknown): number[][][] {
  const g = geometry as { type?: string; coordinates?: unknown } | null;
  if (!g || !Array.isArray(g.coordinates)) return [];
  if (g.type === 'Polygon') return [(g.coordinates as number[][][])[0] ?? []];
  if (g.type === 'MultiPolygon') return (g.coordinates as number[][][][]).map((p) => p?.[0] ?? []);
  return [];
}

export function prepTracts(fc: CensusFC): PreppedTract[] {
  const out: PreppedTract[] = [];
  for (const t of fc.features) {
    if (!(t.properties.medianIncome > 0)) continue;
    const rings = exteriorRings(t.geometry).filter((r) => r.length >= 3);
    if (!rings.length) continue;
    let minLon = Infinity, minLat = Infinity, maxLon = -Infinity, maxLat = -Infinity;
    for (const r of rings) for (const pt of r) {
      const lon = pt[0]!, lat = pt[1]!;
      if (lon < minLon) minLon = lon; if (lon > maxLon) maxLon = lon;
      if (lat < minLat) minLat = lat; if (lat > maxLat) maxLat = lat;
    }
    out.push({ income: t.properties.medianIncome, population: t.properties.population ?? 0, minLon, minLat, maxLon, maxLat, rings });
  }
  return out;
}

function inRing(lon: number, lat: number, ring: number[][]): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const xi = ring[i]![0]!, yi = ring[i]![1]!, xj = ring[j]![0]!, yj = ring[j]![1]!;
    const intersect = ((yi > lat) !== (yj > lat)) && (lon < ((xj - xi) * (lat - yi)) / ((yj - yi) || 1e-12) + xi);
    if (intersect) inside = !inside;
  }
  return inside;
}

// Median income of the tract containing (lon, lat), or 0 if none.
export function tractIncomeAt(lon: number, lat: number, tracts: PreppedTract[]): number {
  for (const t of tracts) {
    if (lon < t.minLon || lon > t.maxLon || lat < t.minLat || lat > t.maxLat) continue;
    for (const r of t.rings) if (inRing(lon, lat, r)) return t.income;
  }
  return 0;
}

// Population of the tract containing (lon, lat), or 0 if none.
export function tractPopulationAt(lon: number, lat: number, tracts: PreppedTract[]): number {
  for (const t of tracts) {
    if (lon < t.minLon || lon > t.maxLon || lat < t.minLat || lat > t.maxLat) continue;
    for (const r of t.rings) if (inRing(lon, lat, r)) return t.population;
  }
  return 0;
}
