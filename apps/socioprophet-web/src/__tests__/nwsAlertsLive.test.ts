import { describe, it, expect, vi, afterEach } from 'vitest';
import { fetchActiveAlerts } from '../data/adapters/nwsAlertsLive';

const ok = (body: unknown) => Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
afterEach(() => vi.restoreAllMocks());

describe('nwsAlertsLive', () => {
  it('maps NWS alert features and drops entries with no event', async () => {
    vi.stubGlobal('fetch', vi.fn(() => ok({ features: [
      { properties: { event: 'Flood Warning', headline: 'Flood Warning until 5pm', severity: 'Severe', areaDesc: 'New York, NY', expires: '2026-07-08T17:00:00Z' } },
      { properties: { severity: 'Minor' } }, // no event → dropped
    ] })));
    const r = await fetchActiveAlerts(40.75, -73.98);
    expect(r).toHaveLength(1);
    expect(r![0]).toMatchObject({ event: 'Flood Warning', severity: 'Severe', area: 'New York, NY' });
  });

  it('returns an empty array (all-clear) when a point has no active alerts', async () => {
    vi.stubGlobal('fetch', vi.fn(() => ok({ features: [] })));
    expect(await fetchActiveAlerts(40.75, -73.98)).toEqual([]);
  });

  it('fails closed (null) on non-200 and throw — distinct from all-clear', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response('', { status: 500 }))));
    expect(await fetchActiveAlerts(40.75, -73.98)).toBeNull();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('net'))));
    expect(await fetchActiveAlerts(40.75, -73.98)).toBeNull();
  });
});
