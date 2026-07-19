import { fetchT } from './http';

// Real significant earthquakes from the USGS feed (earthquake.usgs.gov, public, no key,
// CORS: access-control-allow-origin *). A global, live disruption signal for the supply-chain
// orchestrator's risk radar. Fails closed (null) so the surface falls back to fixture risk.
export interface Quake { id: string; mag: number; place: string; lon: number; lat: number; time: number; url: string }

// M4.5+ over the past day — the threshold at which a quake can plausibly disrupt logistics/ops.
const FEED = 'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson';

interface RawFeature {
  id?: string;
  properties?: { mag?: number; place?: string; time?: number; url?: string };
  geometry?: { coordinates?: [number, number, number] };
}

export async function fetchSignificantQuakes(): Promise<Quake[] | null> {
  try {
    const res = await fetchT(FEED, { headers: { accept: 'application/geo+json' } }, 10000);
    if (!res.ok) return null;
    const j = (await res.json()) as { features?: RawFeature[] };
    const feats = j.features ?? [];
    const out: Quake[] = [];
    for (const f of feats) {
      const c = f.geometry?.coordinates;
      const mag = f.properties?.mag;
      if (!c || typeof c[0] !== 'number' || typeof c[1] !== 'number' || typeof mag !== 'number') continue;
      out.push({
        id: f.id ?? `${c[1]},${c[0]}`,
        mag: +mag.toFixed(1),
        place: f.properties?.place ?? 'unknown',
        lon: c[0], lat: c[1],
        time: f.properties?.time ?? Date.now(),
        url: f.properties?.url ?? 'https://earthquake.usgs.gov',
      });
    }
    // [] = reached the feed but nothing M4.5+ today (a valid live state); null = unreachable.
    return out.sort((a, b) => b.mag - a.mag);
  } catch {
    return null;
  }
}
