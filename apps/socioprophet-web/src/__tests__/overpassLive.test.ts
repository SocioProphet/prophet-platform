import { describe, it, expect, vi, afterEach } from 'vitest';
import { fetchPois } from '../data/adapters/overpassLive';

const bbox = { s: 40.70, w: -74.02, n: 40.75, e: -73.97 };
const sample = {
  elements: [
    { id: 1, lat: 40.72, lon: -74.0, tags: { name: 'Blue Bottle', amenity: 'cafe' } },
    { id: 2, lat: 40.73, lon: -73.99, tags: { amenity: 'cafe' } }, // unnamed
    { id: 3, tags: { name: 'no-geo' } }, // no lat/lon → filtered
  ],
};
const mockFetch = (ok: boolean, body: unknown) => vi.fn().mockResolvedValue({ ok, json: () => Promise.resolve(body) });
afterEach(() => vi.restoreAllMocks());

describe('overpass live POI adapter', () => {
  it('maps OSM elements into POIs, skipping geometry-less nodes', async () => {
    const spy = mockFetch(true, sample);
    vi.stubGlobal('fetch', spy);
    const r = await fetchPois(bbox, 'coffee');
    expect(r).not.toBeNull();
    expect(r!).toHaveLength(2); // element 3 dropped
    expect(r![0]).toMatchObject({ id: 'osm-1', name: 'Blue Bottle', category: 'coffee', lat: 40.72 });
    expect(r![1]!.name).toBe('(unnamed)');
    // query carried the category tag + bbox
    const body = spy.mock.calls[0]![1]!.body as string;
    expect(decodeURIComponent(body)).toContain('amenity"="cafe"');
    expect(decodeURIComponent(body)).toContain('40.7,-74.02,40.75,-73.97');
  });

  it('returns [] for an empty area (valid), null only on failure', async () => {
    vi.stubGlobal('fetch', mockFetch(true, { elements: [] }));
    expect(await fetchPois(bbox, 'restaurant')).toEqual([]);
    vi.stubGlobal('fetch', mockFetch(false, sample));
    expect(await fetchPois(bbox, 'coffee')).toBeNull();
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('timeout')));
    expect(await fetchPois(bbox, 'coffee')).toBeNull();
  });
});
