import { fetchT } from './http';
// Live transit access — real public-transit stops from OpenStreetMap (Overpass, no
// key, CORS, GLOBAL). We pull stations / subway entrances / bus stops / platforms in
// the view and bin them to hex cells, turning the synthetic "mobility / transit
// access" metric into real stop density. OSM is a canonical GAIA source type (no local
// extension needed). Fails closed (null) → the map keeps the illustrative field.
export interface TransitStop { lon: number; lat: number; kind: string }
export interface TransitBBox { s: number; w: number; n: number; e: number }

const ENDPOINT = 'https://overpass-api.de/api/interpreter';

export async function fetchTransitStops(bbox: TransitBBox, limit = 3000): Promise<TransitStop[] | null> {
  try {
    const b = `${bbox.s},${bbox.w},${bbox.n},${bbox.e}`;
    const ql = `[out:json][timeout:20];(node["railway"="station"](${b});node["railway"="subway_entrance"](${b});node["highway"="bus_stop"](${b});node["public_transport"="platform"](${b}););out ${limit};`;
    const res = await fetchT(ENDPOINT, {
      method: 'POST',
      headers: { 'content-type': 'application/x-www-form-urlencoded' },
      body: 'data=' + encodeURIComponent(ql),
    }, 15000);
    if (!res.ok) return null;
    const j = (await res.json()) as { elements?: Array<{ lat?: number; lon?: number; tags?: Record<string, string> }> };
    if (!Array.isArray(j.elements) || !j.elements.length) return null;
    const out: TransitStop[] = [];
    for (const e of j.elements) {
      if (!Number.isFinite(e.lat) || !Number.isFinite(e.lon)) continue;
      const kind = e.tags?.railway === 'station' ? 'rail' : e.tags?.railway === 'subway_entrance' ? 'subway' : e.tags?.highway === 'bus_stop' ? 'bus' : 'transit';
      out.push({ lon: e.lon!, lat: e.lat!, kind });
    }
    return out.length ? out : null;
  } catch {
    return null;
  }
}
