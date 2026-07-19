// Live street-network adapter — the real OSM road/path graph from Overpass (no
// key, CORS). Foot traffic rides THIS instead of a synthetic straight-line grid,
// so it follows the actual city grid and stays on land by construction. Returns
// the same FtNetwork shape the fixture uses (so the renderer is unchanged), plus
// the raw street points — a hex that contains a street is developable land, which
// gives a REAL land mask for the choropleth (no hand-drawn coastline). Fails
// closed (null) → fall back to the synthetic corridors.
import { CITY_BBOX, sampleCommercial } from '../healthMapFixture';
import type { FtNetwork, FtSeg, FtKind } from '../footTrafficFixture';
import { minOf, maxOf } from '../../utils/arrayMath';
import { fetchT } from './http';

export interface BBox { s: number; w: number; n: number; e: number }
// `truncated`: the result hit the way cap, so the network may have coverage holes.
export interface LiveStreets { network: FtNetwork; points: Array<[number, number]>; truncated: boolean } // points = [lon, lat]

// OSM highway class → our foot-traffic kind (drives the time-of-day profile).
function highwayKind(hw: string): FtKind {
  if (/^(motorway|trunk|primary|secondary|tertiary)/.test(hw)) return 'commercial';
  if (/^(pedestrian|footway|path|living_street)/.test(hw)) return 'transit';
  return 'residential';
}

const ENDPOINT = 'https://overpass-api.de/api/interpreter';

// Way cap. `out geom N` limits the number of WAYS (not spatially), so too low a
// cap makes dense views drop whole neighbourhoods → the land mask reads them as
// water and the choropleth punches holes in solid land. Overpass handles 10k+
// ways within the 25s timeout, so cap high and clamp the fetched span elsewhere.
export async function fetchStreets(bbox: BBox, limit = 12000): Promise<LiveStreets | null> {
  try {
    const ql = `[out:json][timeout:25];way["highway"~"^(motorway|trunk|primary|secondary|tertiary|residential|living_street|unclassified|pedestrian|footway)$"](${bbox.s},${bbox.w},${bbox.n},${bbox.e});out geom ${limit};`;
    const res = await fetchT(ENDPOINT, {
      method: 'POST',
      headers: { 'content-type': 'application/x-www-form-urlencoded' },
      body: 'data=' + encodeURIComponent(ql),
    }, 15000);
    if (!res.ok) return null;
    const j = (await res.json()) as { elements?: Array<{ id: number; tags?: Record<string, string>; geometry?: Array<{ lat: number; lon: number }> }> };
    const ways = (j.elements ?? []).filter((w) => Array.isArray(w.geometry) && w.geometry.length >= 2);
    if (!ways.length) return null;
    const truncated = ways.length >= limit;
    const raw: FtSeg[] = [];
    const points: Array<[number, number]> = [];
    for (const w of ways) {
      const kind = highwayKind(w.tags?.highway ?? '');
      const g = w.geometry!;
      for (let k = 0; k < g.length - 1; k += 1) {
        const a = g[k]!;
        const b = g[k + 1]!;
        points.push([a.lon, a.lat]);
        const midLon = (a.lon + b.lon) / 2;
        const midLat = (a.lat + b.lat) / 2;
        raw.push({
          type: 'Feature',
          properties: { id: `w${w.id}-${k}`, corridor: `w${w.id}`, kind, base: sampleCommercial(midLon, midLat) },
          geometry: { type: 'LineString', coordinates: [[a.lon, a.lat], [b.lon, b.lat]] },
        });
      }
      const last = g[g.length - 1]!;
      points.push([last.lon, last.lat]);
    }
    // Normalise base 0..1 across the network, lifting commercial/transit spines.
    const bases = raw.map((s) => s.properties.base);
    const mn = minOf(bases);
    const d = (maxOf(bases) - mn) || 1;
    for (const s of raw) {
      let nb = (s.properties.base - mn) / d;
      if (s.properties.kind === 'commercial') nb = Math.min(1, nb * 1.15 + 0.15);
      else if (s.properties.kind === 'transit') nb = Math.min(1, nb * 1.1 + 0.1);
      s.properties.base = +nb.toFixed(3);
    }
    return { network: { type: 'FeatureCollection', features: raw }, points, truncated };
  } catch {
    return null;
  }
}

// Convenience for callers that only want the bbox from the shared city extent.
export const cityBounds = (): BBox => ({ s: CITY_BBOX.minLat, w: CITY_BBOX.minLon, n: CITY_BBOX.maxLat, e: CITY_BBOX.maxLon });
