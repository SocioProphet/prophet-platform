import { describe, it, expect, vi, afterEach } from 'vitest';
import { fetchGeocode } from '../data/adapters/geocodeLive';

const ok = (body: unknown) => Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
afterEach(() => vi.restoreAllMocks());

describe('geocodeLive (Nominatim)', () => {
  it('maps hits and converts the boundingbox to [s,w,n,e]', async () => {
    vi.stubGlobal('fetch', vi.fn(() => ok([
      { display_name: 'Chicago, Illinois, USA', lat: '41.8757', lon: '-87.6244', boundingbox: ['41.6', '42.0', '-87.9', '-87.5'] },
    ])));
    const r = await fetchGeocode('chicago');
    expect(r).toHaveLength(1);
    expect(r![0]).toMatchObject({ label: 'Chicago, Illinois, USA', lat: 41.8757, lon: -87.6244, bbox: [41.6, -87.9, 42.0, -87.5] });
  });

  it('falls back to a small box when boundingbox is missing', async () => {
    vi.stubGlobal('fetch', vi.fn(() => ok([{ display_name: 'X', lat: '10', lon: '20' }])));
    const r = await fetchGeocode('x');
    expect(r![0].bbox).toEqual([9.95, 19.95, 10.05, 20.05]);
  });

  it('returns null on empty query, empty result, non-200, throw', async () => {
    expect(await fetchGeocode('   ')).toBeNull();
    vi.stubGlobal('fetch', vi.fn(() => ok([])));
    expect(await fetchGeocode('nowhere')).toBeNull();
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response('', { status: 429 }))));
    expect(await fetchGeocode('x')).toBeNull();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('net'))));
    expect(await fetchGeocode('x')).toBeNull();
  });
});
