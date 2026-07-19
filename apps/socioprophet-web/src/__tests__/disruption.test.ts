import { describe, it, expect, vi, afterEach } from 'vitest';
import { haversineKm, nearestQuake, computeDisruptions, isUsProvider } from '../features/supplyChain/disruption';
import { fetchSignificantQuakes } from '../data/adapters/quakesLive';
import type { Provider } from '../data/providersFixture';
import type { Quake } from '../data/adapters/quakesLive';

const prov = (id: string, lat: number, lon: number, place = 'x'): Provider => ({
  id, name: id, stage: 'source', kind: 'k', capabilities: [], geo: { lat, lon, place },
  capacityPct: 50, leadDays: 1, unitCost: 1, rating: 4, reputation: 'verified', provenanceHash: 'sha256:x',
} as Provider);

const quake = (mag: number, lat: number, lon: number): Quake => ({ id: `${lat},${lon}`, mag, place: 'q', lat, lon, time: Date.now(), url: 'u' });

afterEach(() => vi.restoreAllMocks());

describe('haversine + nearest quake', () => {
  it('measures great-circle distance (~111km per degree of latitude)', () => {
    expect(haversineKm(40, -74, 41, -74)).toBeGreaterThan(108);
    expect(haversineKm(40, -74, 41, -74)).toBeLessThan(113);
  });
  it('finds the nearest quake within the radius and ignores far ones', () => {
    const p = prov('p', 24.78, 120.97, 'Hsinchu, TW'); // Taiwan
    const near = quake(5.2, 24.9, 121.0); // ~15km
    const far = quake(6.0, 40.7, -74.0);  // New York, far
    const hit = nearestQuake(p, [far, near], 750);
    expect(hit?.quake).toBe(near);
    expect(nearestQuake(p, [far], 750)).toBeNull();
  });
});

describe('computeDisruptions — join events to chain nodes', () => {
  const tw = prov('tw', 24.78, 120.97, 'Hsinchu, TW');
  const nj = prov('nj', 40.72, -74.10, 'Newark, NJ');
  const cl = prov('cl', -24.27, -69.07, 'Antofagasta, CL');

  it('flags only exposed providers, worst-first, and grades severity', () => {
    const quakes = [quake(6.4, 24.9, 121.0)]; // big quake near Taiwan
    const alerts = { nj: { event: 'Blizzard Warning', headline: 'h', severity: 'Extreme', area: 'NJ', expires: '' } };
    const out = computeDisruptions([tw, nj, cl], quakes, alerts);
    expect(out.map((e) => e.provider.id)).toEqual(expect.arrayContaining(['tw', 'nj']));
    expect(out.some((e) => e.provider.id === 'cl')).toBe(false); // Chile: no quake nearby, no US alert
    expect(out[0].severity).toBe('high'); // M6.4 or Extreme alert → high, sorted first
  });

  it('returns empty when nothing is exposed (honest all-clear)', () => {
    expect(computeDisruptions([tw, nj, cl], [quake(5.0, 0, 0)], {})).toEqual([]);
  });

  it('US bbox gate: only US providers qualify for NWS lookups', () => {
    expect(isUsProvider(nj)).toBe(true);
    expect(isUsProvider(tw)).toBe(false);
    expect(isUsProvider(cl)).toBe(false);
  });
});

describe('fetchSignificantQuakes', () => {
  it('maps the USGS GeoJSON feed and sorts by magnitude desc', async () => {
    const feed = { features: [
      { id: 'a', properties: { mag: 4.6, place: 'Sea of Okhotsk', time: 1, url: 'ua' }, geometry: { coordinates: [150.1, 54.2, 500] } },
      { id: 'b', properties: { mag: 6.1, place: 'Chile', time: 2, url: 'ub' }, geometry: { coordinates: [-70.1, -24.2, 30] } },
    ] };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(feed) }));
    const q = await fetchSignificantQuakes();
    expect(q).toHaveLength(2);
    expect(q![0].mag).toBe(6.1); // sorted desc
    expect(q![0].lat).toBe(-24.2);
  });
  it('returns [] when reached-but-quiet, null when unreachable (fail-closed)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ features: [] }) }));
    expect(await fetchSignificantQuakes()).toEqual([]);
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('down')));
    expect(await fetchSignificantQuakes()).toBeNull();
  });
});
