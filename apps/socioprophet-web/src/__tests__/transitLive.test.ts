import { describe, it, expect, vi, afterEach } from 'vitest';
import { fetchTransitStops } from '../data/adapters/transitLive';

const ok = (body: unknown) => Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
afterEach(() => vi.restoreAllMocks());

describe('transitLive (OSM Overpass transit stops)', () => {
  const bbox = { s: 40.70, w: -74.02, n: 40.78, e: -73.95 };

  it('maps Overpass nodes to stops and classifies kind', async () => {
    vi.stubGlobal('fetch', vi.fn(() => ok({ elements: [
      { lat: 40.75, lon: -73.98, tags: { railway: 'station' } },
      { lat: 40.74, lon: -73.99, tags: { highway: 'bus_stop' } },
      { lat: 40.73, lon: -73.97, tags: { railway: 'subway_entrance' } },
      { lat: null, lon: -73.9, tags: {} }, // dropped — bad coord
    ] })));
    const r = await fetchTransitStops(bbox);
    expect(r).toHaveLength(3);
    expect(r!.map((s) => s.kind)).toEqual(['rail', 'bus', 'subway']);
  });

  it('fails closed on empty, non-200, and throw', async () => {
    vi.stubGlobal('fetch', vi.fn(() => ok({ elements: [] })));
    expect(await fetchTransitStops(bbox)).toBeNull();
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response('', { status: 429 }))));
    expect(await fetchTransitStops(bbox)).toBeNull();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('net'))));
    expect(await fetchTransitStops(bbox)).toBeNull();
  });
});
