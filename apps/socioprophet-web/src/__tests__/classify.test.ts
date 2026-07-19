import { describe, it, expect } from 'vitest';
import { equalBreaks, quantileBreaks, jenksBreaks, breaksFor, classOf, sampleRamp } from '../data/classify';

describe('choropleth classification', () => {
  it('equal-interval splits the range into n even bands', () => {
    expect(equalBreaks(0, 100, 5)).toEqual([20, 40, 60, 80]);
    expect(equalBreaks(0, 10, 2)).toEqual([5]);
  });

  it('quantile gives n-1 ascending breaks within the data range', () => {
    const vals = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
    const b = quantileBreaks(vals, 5);
    expect(b.length).toBe(4);
    expect([...b].sort((x, y) => x - y)).toEqual(b); // ascending
    expect(b[0]).toBeGreaterThanOrEqual(1);
    expect(b[b.length - 1]!).toBeLessThanOrEqual(10);
  });

  it('jenks separates two clusters at the natural gap', () => {
    // Two tight clusters around 10 and 100 → the break should fall in the gap.
    const vals = [9, 10, 11, 10, 9, 98, 100, 102, 101, 99];
    const b = jenksBreaks(vals, 2);
    expect(b.length).toBe(1);
    expect(b[0]!).toBeGreaterThan(11);
    expect(b[0]!).toBeLessThanOrEqual(98);
  });

  it('jenks breaks are ascending and in-range for n classes', () => {
    const vals = [400000, 420000, 500000, 900000, 950000, 1_600000, 1_700000, 2_400000];
    const b = jenksBreaks(vals, 5);
    expect(b.length).toBe(4);
    for (let i = 1; i < b.length; i++) expect(b[i]!).toBeGreaterThanOrEqual(b[i - 1]!);
    expect(b[0]!).toBeGreaterThanOrEqual(400000);
    expect(b[b.length - 1]!).toBeLessThanOrEqual(2_400000);
  });

  it('falls back to quantile when there are fewer points than classes', () => {
    expect(jenksBreaks([5, 9], 5).length).toBeLessThanOrEqual(4);
  });

  it('classOf places values into the right class', () => {
    const breaks = [20, 40, 60, 80];
    expect(classOf(10, breaks)).toBe(0);
    expect(classOf(20, breaks)).toBe(1);
    expect(classOf(75, breaks)).toBe(3);
    expect(classOf(999, breaks)).toBe(4);
  });

  it('breaksFor dispatches by mode', () => {
    const vals = [1, 2, 3, 4, 5, 6, 7, 8];
    expect(breaksFor('equal', vals, 0, 8, 4)).toEqual([2, 4, 6]);
    expect(breaksFor('quantile', vals, 0, 8, 4).length).toBe(3);
    expect(breaksFor('jenks', vals, 0, 8, 4).length).toBe(3);
  });

  it('sampleRamp interpolates between stops', () => {
    const ramp: Array<[number, string]> = [[0, '#000000'], [1, '#ffffff']];
    expect(sampleRamp(ramp, 0)).toBe('#000000');
    expect(sampleRamp(ramp, 1)).toBe('#ffffff');
    expect(sampleRamp(ramp, 0.5)).toBe('#808080');
  });
});
