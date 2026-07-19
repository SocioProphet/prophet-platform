// Real network routing over the OSM street graph we already fetch (streetsLive).
// Turns the map's isochrone from a straight-line "as the crow flies" estimate into
// an actual shortest-path travel-time surface — Esri Network Analyst's signature
// capability, done locally with no license. A river or highway now correctly cuts
// off reachability. Falls back to straight-line when the street network isn't loaded.

export interface RouteGraph {
  adj: Map<string, Array<{ to: string; km: number }>>;
  nodes: Map<string, [number, number]>; // key → [lon, lat]
}

const key = (lon: number, lat: number) => `${lon.toFixed(6)},${lat.toFixed(6)}`;

export function haversineKm(lo1: number, la1: number, lo2: number, la2: number): number {
  const R = 6371, rad = Math.PI / 180;
  const dLa = (la2 - la1) * rad, dLo = (lo2 - lo1) * rad;
  const a = Math.sin(dLa / 2) ** 2 + Math.cos(la1 * rad) * Math.cos(la2 * rad) * Math.sin(dLo / 2) ** 2;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(a)));
}

// Build an undirected weighted graph from LineString segments (each [[lon,lat],[lon,lat]]).
// Shared OSM node coordinates merge into one graph node, so ways connect at intersections.
export function buildRouteGraph(segments: Array<{ geometry: { coordinates: number[][] } }>): RouteGraph {
  const adj = new Map<string, Array<{ to: string; km: number }>>();
  const nodes = new Map<string, [number, number]>();
  const link = (aK: string, bK: string, km: number) => {
    (adj.get(aK) ?? adj.set(aK, []).get(aK)!).push({ to: bK, km });
    (adj.get(bK) ?? adj.set(bK, []).get(bK)!).push({ to: aK, km });
  };
  for (const s of segments) {
    const co = s.geometry?.coordinates;
    if (!co || co.length < 2) continue;
    const a = co[0]!, b = co[1]!;
    const aK = key(a[0]!, a[1]!), bK = key(b[0]!, b[1]!);
    if (aK === bK) continue;
    nodes.set(aK, [a[0]!, a[1]!]); nodes.set(bK, [b[0]!, b[1]!]);
    link(aK, bK, haversineKm(a[0]!, a[1]!, b[0]!, b[1]!));
  }
  return { adj, nodes };
}

// Minimal binary min-heap keyed by number, carrying a string node id.
class MinHeap {
  private h: Array<[number, string]> = [];
  get size() { return this.h.length; }
  push(cost: number, id: string) { const h = this.h; h.push([cost, id]); let i = h.length - 1; while (i > 0) { const p = (i - 1) >> 1; if (h[p]![0] <= h[i]![0]) break; [h[p], h[i]] = [h[i]!, h[p]!]; i = p; } }
  pop(): [number, string] | undefined { const h = this.h; if (!h.length) return undefined; const top = h[0]; const last = h.pop()!; if (h.length) { h[0] = last; let i = 0; for (;;) { const l = 2 * i + 1, r = l + 1; let m = i; if (l < h.length && h[l]![0] < h[m]![0]) m = l; if (r < h.length && h[r]![0] < h[m]![0]) m = r; if (m === i) break; [h[m], h[i]] = [h[i]!, h[m]!]; i = m; } } return top; }
}

// Nearest graph node to an origin (snap the click to the network).
export function nearestNode(g: RouteGraph, lon: number, lat: number): string | null {
  let best: string | null = null, bestKm = Infinity;
  for (const [k, [nlon, nlat]] of g.nodes) { const d = haversineKm(lon, lat, nlon, nlat); if (d < bestKm) { bestKm = d; best = k; } }
  return best;
}

// Dijkstra from the origin's nearest node → travel-time (minutes) to every node
// reachable within maxMinutes at speedKmh. Capped by the budget so it stays cheap.
export function reachableMinutes(g: RouteGraph, lon: number, lat: number, speedKmh: number, maxMinutes: number): Map<string, number> {
  const out = new Map<string, number>();
  const start = nearestNode(g, lon, lat);
  if (!start) return out;
  const perKmMin = 60 / speedKmh;
  const heap = new MinHeap();
  heap.push(0, start);
  while (heap.size) {
    const popped = heap.pop()!; const [t, id] = popped;
    if (t > maxMinutes) break; // heap is ordered — everything beyond is out of budget
    if (out.has(id) && out.get(id)! <= t) continue;
    out.set(id, t);
    for (const e of g.adj.get(id) ?? []) {
      const nt = t + e.km * perKmMin;
      if (nt <= maxMinutes && (!out.has(e.to) || out.get(e.to)! > nt)) heap.push(nt, e.to);
    }
  }
  return out;
}
