import { fetchT } from './http';
// Live POI adapter — real businesses/amenities from OpenStreetMap via the public
// Overpass API (overpass-api.de, no key, CORS-enabled). Given the current map
// bounds + a business category (aligned to the site-selection profiles), it
// returns the actual existing places of that type — i.e. the real competitors in
// view. Fails closed (returns null) so the map stays fixture-only on error/timeout.

export interface Poi { id: string; name: string; lat: number; lon: number; category: string }
export interface BBox { s: number; w: number; n: number; e: number }

// Site-selection profile id → an Overpass tag filter for that business type.
const CATEGORY_QUERY: Record<string, string> = {
  coffee: 'node["amenity"="cafe"]',
  restaurant: 'node["amenity"="restaurant"]',
  retail: 'node["shop"~"^(clothes|boutique|department_store|mall|gift|shoes|jewelry)$"]',
  fitness: 'node["leisure"="fitness_centre"]',
  grocery: 'node["shop"~"^(supermarket|grocery|convenience|greengrocer)$"]',
};

const ENDPOINT = 'https://overpass-api.de/api/interpreter';

export async function fetchPois(bbox: BBox, category: string, limit = 250): Promise<Poi[] | null> {
  try {
    const q = CATEGORY_QUERY[category] ?? CATEGORY_QUERY.coffee;
    const ql = `[out:json][timeout:20];(${q}(${bbox.s},${bbox.w},${bbox.n},${bbox.e}););out ${limit};`;
    const res = await fetchT(ENDPOINT, {
      method: 'POST',
      headers: { 'content-type': 'application/x-www-form-urlencoded' },
      body: 'data=' + encodeURIComponent(ql),
    }, 15000);
    if (!res.ok) return null;
    const j = (await res.json()) as { elements?: Array<{ id: number; lat?: number; lon?: number; tags?: Record<string, string> }> };
    return (j.elements ?? [])
      .filter((el) => typeof el.lat === 'number' && typeof el.lon === 'number')
      .map((el) => ({ id: `osm-${el.id}`, name: el.tags?.name ?? '(unnamed)', lat: el.lat!, lon: el.lon!, category }));
  } catch {
    return null;
  }
}
