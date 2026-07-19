import { describe, it, expect, vi, afterEach } from 'vitest';
import { joinCensus, fetchCensus } from '../data/adapters/censusLive';

const acs = [
  ['NAME', 'B19013_001E', 'B01003_001E', 'state', 'county', 'tract'],
  ['Census Tract 1; New York County; New York', '182000', '4200', '36', '061', '000100'],
  ['Census Tract 2; New York County; New York', '-666666666', '3100', '36', '061', '000200'], // ACS null sentinel
];
const tiger = {
  features: [
    { properties: { GEOID: '36061000100' }, geometry: { type: 'Polygon', coordinates: [[[0, 0]]] } },
    { properties: { GEOID: '36061000200' }, geometry: { type: 'Polygon', coordinates: [[[1, 1]]] } },
    { properties: { GEOID: '36061999999' }, geometry: { type: 'Polygon', coordinates: [[[2, 2]]] } }, // no ACS → dropped
    { properties: { GEOID: '36061000300' } }, // no geometry → dropped
  ],
};

describe('census live (ACS × TIGER) adapter', () => {
  it('joins ACS rows to tract polygons by GEOID, clamping ACS null sentinels', () => {
    const fc = joinCensus(acs, tiger);
    expect(fc.features).toHaveLength(2); // 999999 (no acs) + no-geometry dropped
    const t1 = fc.features.find((f) => f.properties.geoid === '36061000100')!;
    expect(t1.properties.medianIncome).toBe(182000);
    expect(t1.properties.population).toBe(4200);
    expect(t1.geometry).toBeTruthy();
    const t2 = fc.features.find((f) => f.properties.geoid === '36061000200')!;
    expect(t2.properties.medianIncome).toBe(0); // -666666666 sentinel → 0
  });

  afterEach(() => vi.restoreAllMocks());
  it('fails closed when either service is not ok', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, json: () => Promise.resolve([]) }));
    expect(await fetchCensus()).toBeNull();
  });
});
