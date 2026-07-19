import { describe, it, expect } from 'vitest';
import { getisOrdGiStar } from '../data/hotspots';

// A 1-D chain of 9 cells; a-b-c are a high-value cluster, the rest low.
const chain = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i'];
const idx = (id: string) => chain.indexOf(id);
const neighborsOf = (id: string) => { const i = idx(id); return [chain[i - 1], chain[i + 1]].filter(Boolean) as string[]; };
const cells = chain.map((id, i) => ({ id, value: i <= 2 ? 100 : 8 }));

describe('Getis-Ord Gi* hotspots', () => {
  const res = getisOrdGiStar(cells, neighborsOf);
  const byId = new Map(res.map((r) => [r.id, r]));

  it('flags the high-value cluster as a hot spot (z ≥ 1.96)', () => {
    expect(byId.get('b')!.klass).toBe('hot');
    expect(byId.get('b')!.z).toBeGreaterThanOrEqual(1.96);
  });

  it('does not flag interior low cells as hot', () => {
    expect(byId.get('g')!.klass).not.toBe('hot');
  });

  it('returns none for a flat field (no variation)', () => {
    const flat = getisOrdGiStar(chain.map((id) => ({ id, value: 50 })), neighborsOf);
    expect(flat.every((r) => r.klass === 'none' && r.z === 0)).toBe(true);
  });

  it('degrades gracefully below 3 cells', () => {
    expect(getisOrdGiStar([{ id: 'x', value: 1 }, { id: 'y', value: 2 }], neighborsOf)).toHaveLength(2);
  });
});
