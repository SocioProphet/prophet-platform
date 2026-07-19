import { describe, it, expect } from 'vitest';
import { SITUATIONS, MEMBER_META, binaryEdgeCount } from '../features/situations/situations';

describe('situations (n-ary hyperedges)', () => {
  it('each situation binds members of 3+ distinct kinds', () => {
    for (const s of SITUATIONS) {
      const kinds = new Set(s.members.map((m) => m.type));
      expect(kinds.size).toBeGreaterThanOrEqual(3);
      expect(s.members.length).toBeGreaterThanOrEqual(4);
    }
  });

  it('every member type has render metadata', () => {
    for (const s of SITUATIONS) for (const m of s.members) expect(MEMBER_META[m.type]).toBeTruthy();
  });

  it('binaryEdgeCount is k*(k-1)/2 — the fragmentation an n-ary edge avoids', () => {
    expect(binaryEdgeCount(6)).toBe(15);
    expect(binaryEdgeCount(5)).toBe(10);
    // a single n-ary edge replaces this many pairwise links
    for (const s of SITUATIONS) expect(binaryEdgeCount(s.members.length)).toBeGreaterThan(s.members.length - 1);
  });

  it('provenance carries source/method/confidence', () => {
    for (const s of SITUATIONS) {
      expect(s.provenance.source).toBeTruthy();
      expect(s.provenance.confidence).toBeGreaterThan(0);
      expect(s.provenance.confidence).toBeLessThanOrEqual(1);
    }
  });
});
