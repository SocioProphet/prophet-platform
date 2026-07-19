import { describe, it, expect } from 'vitest';
import { buildRouteGraph, reachableMinutes, nearestNode } from '../data/routeGraph';

// A tiny grid of streets: a straight E-W chain of 4 nodes ~0.1km apart, plus an
// isolated segment far away (unreachable). Coordinates near the equator so
// 0.001° ≈ 0.111 km.
const seg = (a: [number, number], b: [number, number]) => ({ geometry: { coordinates: [a, b] } });
const chain = [
  seg([0, 0], [0.001, 0]),
  seg([0.001, 0], [0.002, 0]),
  seg([0.002, 0], [0.003, 0]),
  seg([10, 10], [10.001, 10]), // disconnected island
];

describe('OSM route graph', () => {
  const g = buildRouteGraph(chain);

  it('merges shared coordinates into connected nodes', () => {
    // 6 distinct endpoints: 4 on the chain + 2 on the island
    expect(g.nodes.size).toBe(6);
    // the middle node [0.001,0] links to both neighbours
    expect(g.adj.get('0.001000,0.000000')!.length).toBe(2);
  });

  it('snaps an origin to the nearest node', () => {
    expect(nearestNode(g, 0.0009, 0.0001)).toBe('0.001000,0.000000');
  });

  it('routes along the network within a time budget, excluding the disconnected island', () => {
    // walk 4.8 km/h: 0.111km ≈ 1.39 min/hop. 5 min budget reaches all 4 chain nodes.
    const reached = reachableMinutes(g, 0, 0, 4.8, 5);
    expect(reached.has('0.000000,0.000000')).toBe(true);
    expect(reached.has('0.003000,0.000000')).toBe(true); // 3 hops ≈ 4.2 min
    expect(reached.has('10.000000,10.000000')).toBe(false); // island unreachable
  });

  it('respects the budget — a tight limit truncates the far end', () => {
    const reached = reachableMinutes(g, 0, 0, 4.8, 2); // ~2 min ≈ 1.4 hops
    expect(reached.has('0.000000,0.000000')).toBe(true);
    expect(reached.has('0.001000,0.000000')).toBe(true);
    expect(reached.has('0.003000,0.000000')).toBe(false); // 3 hops > 2 min
  });
});
