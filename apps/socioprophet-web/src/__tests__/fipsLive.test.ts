import { describe, it, expect, vi, afterEach } from 'vitest';
import { fetchCountyFips } from '../data/adapters/fipsLive';

const ok = (body: unknown) => Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
afterEach(() => vi.restoreAllMocks());

describe('fipsLive (FCC county reverse-geocode)', () => {
  it('splits a 5-digit county_fips into state + county', async () => {
    vi.stubGlobal('fetch', vi.fn(() => ok({ results: [{ county_fips: '36061', county_name: 'New York', state_name: 'New York' }] })));
    expect(await fetchCountyFips(40.75, -73.98)).toEqual({ state: '36', county: '061', name: 'New York, New York' });
  });

  it('picks the first well-formed result (Cook County, IL)', async () => {
    vi.stubGlobal('fetch', vi.fn(() => ok({ results: [{ county_fips: '', county_name: 'x' }, { county_fips: '17031', county_name: 'Cook', state_name: 'Illinois' }] })));
    expect(await fetchCountyFips(41.88, -87.63)).toEqual({ state: '17', county: '031', name: 'Cook, Illinois' });
  });

  it('fails closed on no results, non-200, and throw', async () => {
    vi.stubGlobal('fetch', vi.fn(() => ok({ results: [] })));
    expect(await fetchCountyFips(0, 0)).toBeNull();
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response('', { status: 500 }))));
    expect(await fetchCountyFips(40, -73)).toBeNull();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('net'))));
    expect(await fetchCountyFips(40, -73)).toBeNull();
  });
});
