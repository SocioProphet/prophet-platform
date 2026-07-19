import { describe, it, expect, vi, afterEach } from 'vitest';
import { fetchStreets } from '../data/adapters/streetsLive';

const bbox = { s: 40.70, w: -74.02, n: 40.75, e: -73.97 };
const sample = {
  elements: [
    { id: 10, tags: { highway: 'primary' }, geometry: [{ lat: 40.71, lon: -74.0 }, { lat: 40.72, lon: -73.99 }, { lat: 40.73, lon: -73.98 }] },
    { id: 11, tags: { highway: 'residential' }, geometry: [{ lat: 40.74, lon: -73.99 }, { lat: 40.745, lon: -73.985 }] },
    { id: 12, tags: { highway: 'footway' }, geometry: [{ lat: 40.72, lon: -73.99 }] }, // <2 pts → dropped
  ],
};
const mockFetch = (ok: boolean, body: unknown) => vi.fn().mockResolvedValue({ ok, json: () => Promise.resolve(body) });
afterEach(() => vi.restoreAllMocks());

describe('streets live (Overpass) adapter', () => {
  it('turns ways into LineString segments + points, mapping highway → kind', async () => {
    vi.stubGlobal('fetch', mockFetch(true, sample));
    const r = await fetchStreets(bbox);
    expect(r).not.toBeNull();
    // way 10 (3 pts) → 2 segments, way 11 (2 pts) → 1 segment, way 12 dropped
    expect(r!.network.features).toHaveLength(3);
    expect(r!.network.features[0]!.geometry.type).toBe('LineString');
    expect(r!.network.features[0]!.properties.kind).toBe('commercial'); // primary
    expect(r!.network.features[2]!.properties.kind).toBe('residential');
    // base normalized to 0..1
    for (const f of r!.network.features) { expect(f.properties.base).toBeGreaterThanOrEqual(0); expect(f.properties.base).toBeLessThanOrEqual(1); }
    // points collected as [lon, lat] for the land-mask
    expect(r!.points.length).toBeGreaterThan(0);
    expect(r!.points[0]).toEqual([-74.0, 40.71]);
  });

  it('fails closed on non-200, throw, and no ways', async () => {
    vi.stubGlobal('fetch', mockFetch(false, sample));
    expect(await fetchStreets(bbox)).toBeNull();
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('timeout')));
    expect(await fetchStreets(bbox)).toBeNull();
    vi.stubGlobal('fetch', mockFetch(true, { elements: [] }));
    expect(await fetchStreets(bbox)).toBeNull();
  });
});
