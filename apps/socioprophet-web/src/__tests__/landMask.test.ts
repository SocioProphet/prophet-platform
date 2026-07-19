import { describe, it, expect } from 'vitest';
import { isLand, civicHexGrid, civicGrid } from '../data/healthMapFixture';
import { footTrafficNetwork } from '../data/footTrafficFixture';

describe('land mask', () => {
  it('classifies known points correctly', () => {
    expect(isLand(-73.99, 40.75)).toBe(true);   // Manhattan
    expect(isLand(-73.95, 40.72)).toBe(true);   // Brooklyn
    expect(isLand(-74.02, 40.74)).toBe(false);  // Hudson River
    expect(isLand(-73.96, 40.73)).toBe(false);  // East River
    expect(isLand(-74.02, 40.67)).toBe(false);  // Upper Bay / harbor
  });

  it('every emitted cell centroid is on land', () => {
    for (const f of civicHexGrid(8).features) expect(isLand(Number(f.properties.cLon), Number(f.properties.cLat))).toBe(true);
    for (const f of civicGrid().features) expect(isLand(Number(f.properties.cLon), Number(f.properties.cLat))).toBe(true);
  });

  it('drops water cells + corridor segments (fewer than the unmasked count)', () => {
    expect(civicHexGrid(8).features.length).toBeLessThan(433);
    expect(civicHexGrid(8).features.length).toBeGreaterThan(200);
    expect(footTrafficNetwork().features.length).toBeLessThan(180);
  });
});
