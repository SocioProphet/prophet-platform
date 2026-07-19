import { describe, it, expect, vi, afterEach } from 'vitest';
import { fetchCrime, crimeCityForPoint } from '../data/adapters/crimeLive';

const ok = (rows: unknown) => Promise.resolve(new Response(JSON.stringify(rows), { status: 200 }));
afterEach(() => vi.restoreAllMocks());

describe('crimeLive (NYC Socrata NYPD complaints)', () => {
  const bbox = { s: 40.70, w: -74.02, n: 40.78, e: -73.95 };

  it('maps Socrata rows to CrimePoints and drops rows with bad coords', async () => {
    vi.stubGlobal('fetch', vi.fn(() => ok([
      { latitude: '40.75', longitude: '-73.98', law_cat_cd: 'FELONY' },
      { latitude: '40.72', longitude: '-73.99', law_cat_cd: 'MISDEMEANOR' },
      { latitude: null, longitude: '-73.99', law_cat_cd: 'VIOLATION' }, // dropped
      { latitude: 'NaN', longitude: 'x' }, // dropped
    ])));
    const r = await fetchCrime(bbox);
    expect(r).toHaveLength(2);
    expect(r![0]).toEqual({ lon: -73.98, lat: 40.75, category: 'FELONY' });
  });

  it('fails closed (null) on a non-200', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response('', { status: 429 }))));
    expect(await fetchCrime(bbox)).toBeNull();
  });

  it('fails closed (null) on a thrown fetch', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('network'))));
    expect(await fetchCrime(bbox)).toBeNull();
  });

  it('fails closed (null) on an empty result', async () => {
    vi.stubGlobal('fetch', vi.fn(() => ok([])));
    expect(await fetchCrime(bbox)).toBeNull();
  });

  it('resolves the city from the viewport centre (NYC, Chicago, SF)', () => {
    expect(crimeCityForPoint(40.75, -73.98)!.name).toBe('New York');
    expect(crimeCityForPoint(41.88, -87.63)!.name).toBe('Chicago');
    expect(crimeCityForPoint(37.77, -122.42)!.name).toBe('San Francisco');
    expect(crimeCityForPoint(51.5, -0.12)).toBeNull(); // London — unsupported
  });

  it('fails closed BEFORE fetching when the view is outside every supported city', async () => {
    const spy = vi.fn(() => ok([{ latitude: '1', longitude: '1', law_cat_cd: 'X' }]));
    vi.stubGlobal('fetch', spy);
    expect(await fetchCrime({ s: 51.4, w: -0.2, n: 51.6, e: 0.0 })).toBeNull(); // London
    expect(spy).not.toHaveBeenCalled();
  });

  it('uses the correct per-city field names (Chicago primary_type)', async () => {
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      expect(url).toContain('data.cityofchicago.org/resource/ijzp-q8t2');
      expect(url).toContain('primary_type');
      return ok([{ latitude: '41.88', longitude: '-87.63', primary_type: 'THEFT' }]);
    }));
    const r = await fetchCrime({ s: 41.80, w: -87.70, n: 41.95, e: -87.60 });
    expect(r).toEqual([{ lon: -87.63, lat: 41.88, category: 'THEFT' }]);
  });
});
