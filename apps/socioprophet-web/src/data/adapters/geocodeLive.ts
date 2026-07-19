import { fetchT } from './http';
// Live place search — OSM Nominatim geocoder (public, no key, CORS). Lets the user
// fly the map to any place by name, which unblocks every other real layer beyond the
// default NYC view. Fails closed (null). Please respect Nominatim usage limits (light,
// user-initiated queries only).
export interface GeocodeHit {
  label: string;
  lat: number;
  lon: number;
  bbox: [number, number, number, number]; // [s, w, n, e]
}

const ENDPOINT = 'https://nominatim.openstreetmap.org/search';

export async function fetchGeocode(query: string, limit = 5): Promise<GeocodeHit[] | null> {
  const q = query.trim();
  if (!q) return null;
  try {
    const url = `${ENDPOINT}?q=${encodeURIComponent(q)}&format=jsonv2&limit=${limit}&addressdetails=0`;
    const res = await fetchT(url, { headers: { accept: 'application/json' } }, 10000);
    if (!res.ok) return null;
    const rows = (await res.json()) as Array<{ display_name?: string; lat?: string; lon?: string; boundingbox?: string[] }>;
    if (!Array.isArray(rows) || !rows.length) return null;
    const out: GeocodeHit[] = [];
    for (const r of rows) {
      const lat = Number(r.lat); const lon = Number(r.lon);
      if (!Number.isFinite(lat) || !Number.isFinite(lon) || !r.display_name) continue;
      // Nominatim boundingbox is [minLat, maxLat, minLon, maxLon] as strings.
      const bb = (r.boundingbox ?? []).map(Number);
      const bbox: [number, number, number, number] = bb.length === 4 && bb.every(Number.isFinite)
        ? [bb[0]!, bb[2]!, bb[1]!, bb[3]!] // → [s, w, n, e]
        : [lat - 0.05, lon - 0.05, lat + 0.05, lon + 0.05];
      out.push({ label: r.display_name, lat, lon, bbox });
    }
    return out.length ? out : null;
  } catch {
    return null;
  }
}
