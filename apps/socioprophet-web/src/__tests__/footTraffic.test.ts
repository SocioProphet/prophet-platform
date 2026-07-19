import { describe, it, expect } from 'vitest';
import { footTrafficNetwork, footTrafficFactor, hourLabel } from '../data/footTrafficFixture';

describe('foot-traffic corridor network', () => {
  it('builds line segments with normalized base intensity', () => {
    const net = footTrafficNetwork();
    expect(net.features.length).toBeGreaterThan(100);
    for (const f of net.features) {
      expect(f.geometry.type).toBe('LineString');
      expect(f.geometry.coordinates.length).toBe(2);
      expect(f.properties.base).toBeGreaterThanOrEqual(0);
      expect(f.properties.base).toBeLessThanOrEqual(1);
    }
  });

  it('transit peaks at commute hours, troughs midday', () => {
    const commute = footTrafficFactor('transit', 8, false);
    const midday = footTrafficFactor('transit', 13, false);
    expect(commute).toBeGreaterThan(midday);
    expect(footTrafficFactor('transit', 18, false)).toBeGreaterThan(midday);
  });

  it('commercial peaks at lunch + evening, not early morning', () => {
    expect(footTrafficFactor('commercial', 13, false)).toBeGreaterThan(footTrafficFactor('commercial', 6, false));
    expect(footTrafficFactor('commercial', 19, false)).toBeGreaterThan(footTrafficFactor('commercial', 6, false));
  });

  it('weekend flattens the transit commute peak', () => {
    expect(footTrafficFactor('transit', 8, true)).toBeLessThan(footTrafficFactor('transit', 8, false));
  });

  it('formats hours', () => {
    expect(hourLabel(0)).toBe('12 AM');
    expect(hourLabel(13)).toBe('1 PM');
    expect(hourLabel(18)).toBe('6 PM');
  });
});
