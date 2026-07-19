import { describe, it, expect, vi, afterEach } from 'vitest';
import { fetchFloodZones, floodRiskForZone, floodRiskAt } from '../data/adapters/floodLive';

const ok = (body: unknown) => Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
afterEach(() => vi.restoreAllMocks());

describe('floodLive (FEMA NFHL)', () => {
  it('maps FEMA zone codes to risk %', () => {
    expect(floodRiskForZone('AE')).toBe(35); // SFHA
    expect(floodRiskForZone('VE')).toBe(35);
    expect(floodRiskForZone('X')).toBe(8);
    expect(floodRiskForZone('0.2 PCT ANNUAL CHANCE FLOOD HAZARD')).toBe(8);
    expect(floodRiskForZone('D')).toBe(15);
  });

  it('parses zones and joins the highest-risk zone at a point', async () => {
    vi.stubGlobal('fetch', vi.fn(() => ok({ features: [
      { properties: { FLD_ZONE: 'AE' }, geometry: { type: 'Polygon', coordinates: [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]] } },
      { properties: { FLD_ZONE: 'X' }, geometry: { type: 'Polygon', coordinates: [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]] } }, // overlaps
    ] })));
    const zones = await fetchFloodZones({ s: 0, w: 0, n: 1, e: 1 });
    expect(zones).toHaveLength(2);
    expect(floodRiskAt(0.5, 0.5, zones!)).toBe(35); // AE wins over X
    expect(floodRiskAt(5, 5, zones!)).toBe(-1);     // outside every zone
  });

  it('fails closed on empty, non-200, and throw', async () => {
    vi.stubGlobal('fetch', vi.fn(() => ok({ features: [] })));
    expect(await fetchFloodZones({ s: 0, w: 0, n: 1, e: 1 })).toBeNull();
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response('', { status: 503 }))));
    expect(await fetchFloodZones({ s: 0, w: 0, n: 1, e: 1 })).toBeNull();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('net'))));
    expect(await fetchFloodZones({ s: 0, w: 0, n: 1, e: 1 })).toBeNull();
  });
});
