import { describe, it, expect } from 'vitest';
import { minOf, maxOf } from '../utils/arrayMath';

describe('arrayMath minOf/maxOf', () => {
  it('matches Math.min/max on ordinary arrays', () => {
    const a = [3, 1, 4, 1, 5, 9, 2, 6];
    expect(minOf(a)).toBe(1);
    expect(maxOf(a)).toBe(9);
  });

  it('matches Math.min/max semantics on the empty array', () => {
    expect(minOf([])).toBe(Infinity);
    expect(maxOf([])).toBe(-Infinity);
  });

  it('handles negatives and a single element', () => {
    expect(minOf([-5])).toBe(-5);
    expect(maxOf([-5, -2, -9])).toBe(-2);
  });

  it('does NOT overflow the call stack on a huge array (the whole point)', () => {
    // Math.min(...arr) throws RangeError past ~1e5 args in many engines; this must not.
    const big = new Array(500_000);
    for (let i = 0; i < big.length; i += 1) big[i] = i % 997;
    expect(() => minOf(big)).not.toThrow();
    expect(minOf(big)).toBe(0);
    expect(maxOf(big)).toBe(996);
  });
});
