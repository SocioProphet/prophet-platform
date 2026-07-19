// Foot traffic is a NETWORK phenomenon — it flows along streets, not across
// blocks — and it's TEMPORAL (rush hours, lunch, evenings). So we model it as a
// corridor network of street segments, each with a base intensity (sampled from
// the commercial field) and a kind whose time-of-day profile scales it. UI-only;
// a real mobility adapter (Placer/SafeGraph-style) emits the same segment shape.
import { CITY_BBOX, sampleCommercial, isLand } from './healthMapFixture';
import { minOf, maxOf } from '../utils/arrayMath';

export type FtKind = 'commercial' | 'transit' | 'residential';
export interface FtSeg {
  type: 'Feature';
  properties: { id: string; corridor: string; kind: FtKind; base: number };
  geometry: { type: 'LineString'; coordinates: number[][] };
}
export interface FtNetwork { type: 'FeatureCollection'; features: FtSeg[] }

// Build a street grid of avenues (N–S) and cross-streets (E–W), each split into
// segments so intensity varies ALONG the corridor. A few are commercial strips
// or transit spines; the rest residential.
export function footTrafficNetwork(): FtNetwork {
  const { minLon, maxLon, minLat, maxLat } = CITY_BBOX;
  const spanLon = maxLon - minLon;
  const spanLat = maxLat - minLat;
  const AV = 7;
  const ST = 8;
  const SEG = 12;
  const commercialAv = new Set([2, 4]);
  const transitAv = new Set([3]);
  const commercialSt = new Set([3, 5]);
  const transitSt = new Set([2]);
  const raw: FtSeg[] = [];
  const addCorridor = (corridor: string, kind: FtKind, pts: number[][]) => {
    for (let k = 0; k < pts.length - 1; k += 1) {
      const a = pts[k]!;
      const b = pts[k + 1]!;
      const midLon = (a[0]! + b[0]!) / 2;
      const midLat = (a[1]! + b[1]!) / 2;
      if (!isLand(midLon, midLat)) continue; // streets don't run across rivers/harbor
      const base = sampleCommercial(midLon, midLat);
      raw.push({ type: 'Feature', properties: { id: `${corridor}-${k}`, corridor, kind, base }, geometry: { type: 'LineString', coordinates: [a, b] } });
    }
  };
  for (let i = 0; i < AV; i += 1) {
    const lon = minLon + ((i + 0.5) / AV) * spanLon;
    const kind: FtKind = commercialAv.has(i) ? 'commercial' : transitAv.has(i) ? 'transit' : 'residential';
    addCorridor(`av${i}`, kind, Array.from({ length: SEG + 1 }, (_, k) => [lon, minLat + (k / SEG) * spanLat]));
  }
  for (let j = 0; j < ST; j += 1) {
    const lat = minLat + ((j + 0.5) / ST) * spanLat;
    const kind: FtKind = commercialSt.has(j) ? 'commercial' : transitSt.has(j) ? 'transit' : 'residential';
    addCorridor(`st${j}`, kind, Array.from({ length: SEG + 1 }, (_, k) => [minLon + (k / SEG) * spanLon, lat]));
  }
  // Normalise base to 0..1 across the network, then lift commercial/transit spines.
  const bases = raw.map((s) => s.properties.base);
  const mn = minOf(bases);
  const d = (maxOf(bases) - mn) || 1;
  for (const s of raw) {
    let nb = (s.properties.base - mn) / d;
    if (s.properties.kind === 'commercial') nb = Math.min(1, nb * 1.15 + 0.15);
    else if (s.properties.kind === 'transit') nb = Math.min(1, nb * 1.1 + 0.1);
    s.properties.base = +nb.toFixed(3);
  }
  return { type: 'FeatureCollection', features: raw };
}

// Time-of-day multiplier per corridor kind (hour 0..23, weekday vs weekend).
const g = (x: number, mu: number, s: number) => Math.exp(-((x - mu) ** 2) / (2 * s * s));
export function footTrafficFactor(kind: FtKind, hour: number, weekend: boolean): number {
  let f: number;
  if (kind === 'commercial') f = weekend ? 0.15 + g(hour, 14, 3.5) * 0.9 + g(hour, 20, 3) * 0.5 : 0.12 + g(hour, 13, 2.5) * 0.7 + g(hour, 19, 2.5) * 1.0;
  else if (kind === 'transit') f = weekend ? 0.2 + g(hour, 15, 4) * 0.5 : 0.12 + g(hour, 8, 1.4) * 1.0 + g(hour, 18, 1.6) * 1.0;
  else f = weekend ? 0.2 + g(hour, 12, 4) * 0.5 : 0.18 + g(hour, 8, 2) * 0.7 + g(hour, 18.5, 2.5) * 0.85;
  return Math.max(0, Math.min(1.1, f));
}

export const hourLabel = (h: number): string => { const ap = h < 12 ? 'AM' : 'PM'; const hr = h % 12 === 0 ? 12 : h % 12; return `${hr} ${ap}`; };
export const FT_KIND_LABEL: Record<FtKind, string> = { commercial: 'Commercial strip', transit: 'Transit spine', residential: 'Residential street' };
