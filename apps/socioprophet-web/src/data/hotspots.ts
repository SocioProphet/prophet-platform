// Spatial-statistics hotspot detection — Getis-Ord Gi* — over the map's H3 grid.
// This is Esri/Carto's turf (ESDA / hot-spot analysis). We compute the same
// statistic AND ship it as a GOVERNED claim: each cell gets a real z-score that
// lands in the WorldClaim's uncertainty, so we deliver *governed significance*
// where the incumbents deliver a raw number. Pure + testable; neighbour adjacency
// is injected (the map supplies H3 gridDisk) so this file has no h3 dependency.

export interface HotResult { id: string; z: number; klass: 'hot' | 'cold' | 'none' }

// z ≥ 1.96 (95%) → statistically significant HIGH cluster (hot spot); ≤ −1.96 → cold.
const CONF_95 = 1.96;

export function getisOrdGiStar(
  cells: Array<{ id: string; value: number }>,
  neighborsOf: (id: string) => string[],
): HotResult[] {
  const n = cells.length;
  if (n < 3) return cells.map((c) => ({ id: c.id, z: 0, klass: 'none' }));
  const valueById = new Map<string, number>();
  for (const c of cells) valueById.set(c.id, c.value);
  const idSet = new Set(cells.map((c) => c.id));

  let sum = 0, sumSq = 0;
  for (const c of cells) { sum += c.value; sumSq += c.value * c.value; }
  const mean = sum / n;
  const variance = sumSq / n - mean * mean;
  const S = Math.sqrt(Math.max(variance, 0));
  if (S === 0) return cells.map((c) => ({ id: c.id, z: 0, klass: 'none' })); // no variation → no clusters

  return cells.map((c) => {
    // Gi* includes the focal cell itself in its neighbourhood.
    const nbrs = neighborsOf(c.id).filter((id) => idSet.has(id));
    const wset = new Set(nbrs); wset.add(c.id);
    const wi = wset.size;
    let lagSum = 0; for (const id of wset) lagSum += valueById.get(id) ?? 0;
    const denom = S * Math.sqrt(Math.max((n * wi - wi * wi) / (n - 1), 0));
    if (denom === 0) return { id: c.id, z: 0, klass: 'none' as const };
    const z = (lagSum - mean * wi) / denom;
    const klass = z >= CONF_95 ? 'hot' : z <= -CONF_95 ? 'cold' : 'none';
    return { id: c.id, z: +z.toFixed(3), klass };
  });
}
