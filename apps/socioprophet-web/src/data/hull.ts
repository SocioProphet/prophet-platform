// Convex hull + point-in-polygon for drive-time trade areas. We already run Dijkstra
// on the real OSM street graph (routeGraph.ts); wrapping the reached nodes in a hull
// turns "which hexes are reachable" into an actual catchment POLYGON — the trade-area
// product Placer/CoStar sell for site selection. Pure + testable; points are [lon,lat].

// Andrew's monotone-chain convex hull. Returns the hull ring (not closed), CCW.
export function convexHull(points: Array<[number, number]>): Array<[number, number]> {
  const uniq = Array.from(new Map(points.map((p) => [`${p[0]},${p[1]}`, p])).values());
  if (uniq.length < 3) return uniq;
  const p = uniq.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cross = (o: [number, number], a: [number, number], b: [number, number]) =>
    (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const lower: Array<[number, number]> = [];
  for (const q of p) { while (lower.length >= 2 && cross(lower[lower.length - 2]!, lower[lower.length - 1]!, q) <= 0) lower.pop(); lower.push(q); }
  const upper: Array<[number, number]> = [];
  for (let i = p.length - 1; i >= 0; i -= 1) { const q = p[i]!; while (upper.length >= 2 && cross(upper[upper.length - 2]!, upper[upper.length - 1]!, q) <= 0) upper.pop(); upper.push(q); }
  lower.pop(); upper.pop();
  return lower.concat(upper);
}

// GeoJSON polygon coordinates ([[ [lon,lat], … , firstPointRepeated ]]) for a hull.
export function hullToPolygon(hull: Array<[number, number]>): number[][][] {
  if (hull.length < 3) return [];
  return [[...hull, hull[0]!]];
}

// Ray-casting point-in-polygon over a closed or open ring of [lon,lat].
export function pointInPolygon(lon: number, lat: number, ring: Array<[number, number]>): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const xi = ring[i]![0], yi = ring[i]![1], xj = ring[j]![0], yj = ring[j]![1];
    if (((yi > lat) !== (yj > lat)) && (lon < ((xj - xi) * (lat - yi)) / ((yj - yi) || 1e-12) + xi)) inside = !inside;
  }
  return inside;
}
