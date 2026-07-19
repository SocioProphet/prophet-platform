// Civic-statistics aggregation grid for the Map Workbench — the map as the
// place-based unifier. The extent is binned into cells (an H3-style aggregation
// grid), each carrying the "know your area" statistics a citizen cares about:
// Health, Public Safety, Education, People. The map shades areas by any metric.
// Deterministic + correlated (affluent/dense cells trend healthier, safer, better
// schools) so the choropleth reads believably. UI-only; a census/CDC/DOJ/DOE
// adapter can emit the same GeoJSON shape.

export interface MetricDef {
  key: string;
  label: string;
  min: number;
  max: number;
  unit: string;
  higherBetter: boolean;
  ramp: Array<[number, string]>; // [position 0..1, color]
  format?: 'money' | 'pct' | 'plain';
}
export interface LayerGroup { id: string; label: string; blurb: string; metrics: MetricDef[]; segmented?: boolean }

// Real-estate segment multipliers (applied per metric at render): commercial and
// industrial re-price the same cells so one layer serves all property types.
export interface Segment { id: string; label: string; f: Record<string, number> }
export const SEGMENTS: Segment[] = [
  { id: 'res', label: 'Residential', f: {} },
  { id: 'com', label: 'Commercial', f: { reMedianPrice: 2.3, reMedianRent: 2.0, reGrossYield: 1.15, reTurnoverPct: 0.8, reDefaultPct: 1.4, reOwnerOccPct: 0.35, reVacancyPct: 1.5, reChurnPct: 1.2 } },
  { id: 'ind', label: 'Industrial', f: { reMedianPrice: 1.5, reMedianRent: 1.7, reGrossYield: 1.45, reTurnoverPct: 0.6, reDefaultPct: 0.8, reOwnerOccPct: 0.3, reVacancyPct: 0.7, reChurnPct: 0.9 } },
];
export const segFactor = (segId: string, key: string): number => (SEGMENTS.find((s) => s.id === segId)?.f[key] ?? 1);

const GOOD_HIGH: Array<[number, string]> = [[0, '#d73027'], [0.5, '#fee08b'], [1, '#1a9850']]; // low=red, high=green
const BAD_HIGH: Array<[number, string]> = [[0, '#1a9850'], [0.5, '#fee08b'], [1, '#d73027']];  // low=green, high=red
const BLUE: Array<[number, string]> = [[0, '#eff3ff'], [0.5, '#6baed6'], [1, '#08519c']];

export const CIVIC_LAYERS: LayerGroup[] = [
  {
    id: 'health', label: 'Health', blurb: 'Population health, coverage, longevity.',
    metrics: [
      { key: 'healthIndex', label: 'Health index', min: 42, max: 94, unit: '', higherBetter: true, ramp: GOOD_HIGH },
      { key: 'uninsuredPct', label: 'Uninsured', min: 3, max: 24, unit: '%', higherBetter: false, ramp: BAD_HIGH },
      { key: 'lifeExpectancy', label: 'Life expectancy', min: 74, max: 85, unit: 'yr', higherBetter: true, ramp: GOOD_HIGH },
    ],
  },
  {
    id: 'safety', label: 'Public Safety', blurb: 'Crime rates and emergency response.',
    metrics: [
      { key: 'crimeRate', label: 'Violent crime', min: 5, max: 85, unit: '/1k', higherBetter: false, ramp: BAD_HIGH },
      { key: 'propertyCrime', label: 'Property crime', min: 10, max: 120, unit: '/1k', higherBetter: false, ramp: BAD_HIGH },
      { key: 'response911', label: '911 response', min: 4, max: 14, unit: 'min', higherBetter: false, ramp: BAD_HIGH },
    ],
  },
  {
    id: 'education', label: 'Education', blurb: 'School quality and outcomes.',
    metrics: [
      { key: 'schoolRating', label: 'School rating', min: 3, max: 9.5, unit: '/10', higherBetter: true, ramp: GOOD_HIGH },
      { key: 'gradRate', label: 'Graduation', min: 62, max: 98, unit: '%', higherBetter: true, ramp: GOOD_HIGH },
      { key: 'studentTeacher', label: 'Student:teacher', min: 11, max: 28, unit: ':1', higherBetter: false, ramp: BAD_HIGH },
    ],
  },
  {
    id: 'realestate', label: 'Real Estate', blurb: 'Investment lens — pricing, yield, turnover, defaults, owner/renter mix.', segmented: true,
    metrics: [
      { key: 'reMedianPrice', label: 'Median price', min: 400000, max: 2500000, unit: '', higherBetter: true, ramp: BLUE, format: 'money' },
      { key: 'reMedianRent', label: 'Median rent', min: 1800, max: 6000, unit: '/mo', higherBetter: true, ramp: BLUE, format: 'money' },
      { key: 'reGrossYield', label: 'Gross yield', min: 2.5, max: 8, unit: '%', higherBetter: true, ramp: GOOD_HIGH, format: 'pct' },
      { key: 'reTurnoverPct', label: 'Turnover', min: 3, max: 14, unit: '%', higherBetter: true, ramp: BLUE, format: 'pct' },
      { key: 'reDefaultPct', label: 'Default rate', min: 0.5, max: 6, unit: '%', higherBetter: false, ramp: BAD_HIGH, format: 'pct' },
      { key: 'reOwnerOccPct', label: 'Owner-occupied', min: 25, max: 80, unit: '%', higherBetter: true, ramp: BLUE, format: 'pct' },
      { key: 'reVacancyPct', label: 'Vacancy', min: 2, max: 12, unit: '%', higherBetter: false, ramp: BAD_HIGH, format: 'pct' },
      { key: 'reChurnPct', label: 'Renter churn', min: 8, max: 35, unit: '%', higherBetter: false, ramp: BAD_HIGH, format: 'pct' },
    ],
  },
  {
    id: 'housing', label: 'Housing', blurb: 'Affordability, burden, and stability.',
    metrics: [
      { key: 'rentBurdenPct', label: 'Rent burden', min: 18, max: 55, unit: '%', higherBetter: false, ramp: BAD_HIGH, format: 'pct' },
      { key: 'costBurdenedPct', label: 'Cost-burdened', min: 20, max: 60, unit: '%', higherBetter: false, ramp: BAD_HIGH, format: 'pct' },
      { key: 'evictionPct', label: 'Eviction rate', min: 0.3, max: 5, unit: '%', higherBetter: false, ramp: BAD_HIGH, format: 'pct' },
      { key: 'housingVacancyPct', label: 'Vacancy', min: 2, max: 14, unit: '%', higherBetter: false, ramp: BAD_HIGH, format: 'pct' },
    ],
  },
  {
    id: 'environment', label: 'Environment', blurb: 'Air, flood risk, and green space.',
    metrics: [
      { key: 'airQualityAqi', label: 'Air quality (AQI)', min: 20, max: 120, unit: '', higherBetter: false, ramp: BAD_HIGH },
      { key: 'floodRiskPct', label: 'Flood risk', min: 2, max: 40, unit: '%', higherBetter: false, ramp: BAD_HIGH, format: 'pct' },
      { key: 'greenSpacePct', label: 'Green space', min: 3, max: 45, unit: '%', higherBetter: true, ramp: GOOD_HIGH, format: 'pct' },
    ],
  },
  {
    id: 'mobility', label: 'Mobility', blurb: 'Transit access, commute, walkability, safety.',
    metrics: [
      { key: 'transitAccessIdx', label: 'Transit access', min: 20, max: 95, unit: '', higherBetter: true, ramp: GOOD_HIGH },
      { key: 'walkScore', label: 'Walk score', min: 25, max: 98, unit: '', higherBetter: true, ramp: GOOD_HIGH },
      { key: 'commuteMin', label: 'Commute', min: 18, max: 52, unit: 'min', higherBetter: false, ramp: BAD_HIGH },
      { key: 'crashRate', label: 'Crash rate', min: 2, max: 30, unit: '/1k', higherBetter: false, ramp: BAD_HIGH },
    ],
  },
  {
    id: 'economic', label: 'Economic', blurb: 'Income, employment, poverty, business density.',
    metrics: [
      { key: 'medianIncome', label: 'Median income', min: 35000, max: 180000, unit: '', higherBetter: true, ramp: BLUE, format: 'money' },
      { key: 'unemploymentPct', label: 'Unemployment', min: 2, max: 14, unit: '%', higherBetter: false, ramp: BAD_HIGH, format: 'pct' },
      { key: 'povertyPct', label: 'Poverty', min: 4, max: 32, unit: '%', higherBetter: false, ramp: BAD_HIGH, format: 'pct' },
      { key: 'businessDensity', label: 'Business density', min: 5, max: 90, unit: '/1k', higherBetter: true, ramp: GOOD_HIGH },
    ],
  },
  {
    id: 'foottraffic', label: 'Foot Traffic', blurb: 'Visits, dwell time, and capture rate.',
    metrics: [
      { key: 'footTrafficDaily', label: 'Daily visits', min: 200, max: 25000, unit: '', higherBetter: true, ramp: BLUE },
      { key: 'dwellMin', label: 'Dwell time', min: 8, max: 45, unit: 'min', higherBetter: true, ramp: GOOD_HIGH },
      { key: 'captureRate', label: 'Capture rate', min: 2, max: 18, unit: '%', higherBetter: true, ramp: GOOD_HIGH, format: 'pct' },
    ],
  },
  {
    id: 'newssocial', label: 'News & Social', blurb: 'Where the story is — news volume, social activity, sentiment, civic engagement by area.',
    metrics: [
      { key: 'newsVolume', label: 'News volume', min: 0, max: 120, unit: '/wk', higherBetter: true, ramp: BLUE },
      { key: 'socialPosts', label: 'Social activity', min: 100, max: 8000, unit: '/day', higherBetter: true, ramp: BLUE },
      { key: 'netSentiment', label: 'Net sentiment', min: -60, max: 60, unit: '', higherBetter: true, ramp: GOOD_HIGH },
      { key: 'civicEngagement', label: 'Civic engagement', min: 10, max: 90, unit: '', higherBetter: true, ramp: GOOD_HIGH },
    ],
  },
  {
    id: 'people', label: 'People', blurb: 'Population and density.',
    metrics: [
      { key: 'population', label: 'Population', min: 2000, max: 42000, unit: '', higherBetter: true, ramp: BLUE },
    ],
  },
];

// ── Site selection ("should I open my next location here?") ──
// A verified, computed suitability score per area for a business type. Different
// profiles weight foot traffic / income / walkability / rent / population
// differently, so the best areas genuinely differ by use-case (a high-traffic,
// affordable cell beats a rich but sleepy one for a coffee shop).
export interface SiteProfile { id: string; label: string; icon: string; w: Record<string, number> }
export const SITE_PROFILES: SiteProfile[] = [
  { id: 'coffee', label: 'Coffee shop', icon: '☕', w: { footTrafficDaily: 0.35, walkScore: 0.2, medianIncome: 0.2, businessDensity: 0.1, reMedianRent: -0.25 } },
  { id: 'restaurant', label: 'Restaurant', icon: '🍽', w: { footTrafficDaily: 0.3, medianIncome: 0.25, dwellMin: 0.15, walkScore: 0.1, reMedianRent: -0.25 } },
  { id: 'retail', label: 'Retail store', icon: '🛍', w: { footTrafficDaily: 0.35, captureRate: 0.2, medianIncome: 0.2, businessDensity: 0.1, reMedianRent: -0.25 } },
  { id: 'fitness', label: 'Fitness studio', icon: '🏋', w: { population: 0.3, medianIncome: 0.25, footTrafficDaily: 0.2, walkScore: 0.15, reMedianRent: -0.2 } },
  { id: 'grocery', label: 'Grocery', icon: '🛒', w: { population: 0.35, footTrafficDaily: 0.2, reOwnerOccPct: 0.15, medianIncome: 0.15, reMedianRent: -0.15 } },
];
const NORM: Record<string, [number, number]> = {
  footTrafficDaily: [200, 25000], medianIncome: [35000, 180000], walkScore: [25, 98], businessDensity: [5, 90],
  reMedianRent: [1800, 6000], population: [2000, 42000], dwellMin: [8, 45], captureRate: [2, 18], reOwnerOccPct: [25, 80],
};
export function scoreCell(props: Record<string, string | number>, profileId: string): number {
  const p = SITE_PROFILES.find((x) => x.id === profileId);
  if (!p) return 0;
  let score = 0; let wsum = 0;
  for (const [key, w] of Object.entries(p.w)) {
    const range = NORM[key]; if (!range) continue;
    const nv = clamp((Number(props[key] ?? 0) - range[0]) / (range[1] - range[0]), 0, 1);
    score += Math.abs(w) * (w < 0 ? 1 - nv : nv); // negative weight = lower is better (e.g. rent)
    wsum += Math.abs(w);
  }
  return Math.round((score / (wsum || 1)) * 100);
}

export const METRIC_BY_KEY: Record<string, MetricDef> = Object.fromEntries(
  CIVIC_LAYERS.flatMap((g) => g.metrics).map((m) => [m.key, m]),
);

// Map extent around NYC / Hudson (matches the workbench default view).
import { polygonToCells, cellToBoundary, cellToLatLng } from 'h3-js';
import { minOf, maxOf } from '../utils/arrayMath';

const BBOX = { minLon: -74.09, maxLon: -73.90, minLat: 40.64, maxLat: 40.82 };
function hash(a: number, b: number): number { let h = (a * 73856093) ^ (b * 19349663); h = (h ^ (h >>> 13)) >>> 0; return h / 4294967296; }

// Land mask — cells / corridors should not cover water or non-livable space. These
// are approximate [lon,lat] polygons of the major water bodies in the bbox (Hudson
// River, East River, Upper Bay / harbor); anything inside them is excluded. A real
// deployment swaps these for an actual coastline / land-cover layer.
const WATER: number[][][] = [
  // Hudson River — between the Jersey shore (west) and Manhattan's west shore (east)
  [[-73.985, 40.82], [-73.995, 40.79], [-74.0, 40.766], [-74.008, 40.744], [-74.013, 40.72], [-74.018, 40.704], [-74.033, 40.714], [-74.028, 40.74], [-74.024, 40.76], [-74.024, 40.82]],
  // East River — between Manhattan (west) and Brooklyn / Queens (east)
  [[-74.0, 40.707], [-73.975, 40.72], [-73.965, 40.75], [-73.952, 40.778], [-73.935, 40.80], [-73.927, 40.795], [-73.945, 40.767], [-73.957, 40.744], [-73.958, 40.718], [-73.969, 40.702], [-73.99, 40.699]],
  // Upper Bay / harbor — south of the Battery, between Jersey and Brooklyn
  [[-74.05, 40.702], [-74.018, 40.703], [-73.99, 40.699], [-73.975, 40.68], [-73.99, 40.659], [-74.02, 40.645], [-74.055, 40.66]],
];
function pointInPoly(x: number, y: number, poly: number[][]): boolean {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const xi = poly[i]![0]!; const yi = poly[i]![1]!; const xj = poly[j]![0]!; const yj = poly[j]![1]!;
    if (((yi > y) !== (yj > y)) && (x < ((xj - xi) * (y - yi)) / (yj - yi) + xi)) inside = !inside;
  }
  return inside;
}
export function isLand(lon: number, lat: number): boolean { return !WATER.some((w) => pointInPoly(lon, lat, w)); }
const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));

// Smooth 0..1 spatial field (bilinear value noise over a coarse lattice) so a
// finer grid forms COHERENT neighborhoods with gradients rather than salt-and-
// pepper. `freq` = lattice cells across the bbox — higher = smaller districts.
function field(u: number, v: number, seed: number, freq: number): number {
  const x = u * freq;
  const y = v * freq;
  const xi = Math.floor(x);
  const yi = Math.floor(y);
  const sm = (t: number) => t * t * (3 - 2 * t);
  const g = (a: number, b: number) => hash(a + seed * 101, b + seed * 211);
  const sx = sm(x - xi);
  const sy = sm(y - yi);
  const top = g(xi, yi) + (g(xi + 1, yi) - g(xi, yi)) * sx;
  const bot = g(xi, yi + 1) + (g(xi + 1, yi + 1) - g(xi, yi + 1)) * sx;
  return top + (bot - top) * sy;
}
// Two octaves — broad districts + finer texture within them. Range is stretched
// to full 0..1 by normalising across the whole grid in civicGrid() (value noise
// regresses to the mean, so a raw field would wash out the choropleth).
function sfield(u: number, v: number, seed: number): number {
  return 0.68 * field(u, v, seed, 5) + 0.32 * field(u, v, seed + 7, 12);
}

// The city bbox + the commercial-intensity field, exposed so the foot-traffic
// corridor network aligns with the same underlying geography as the cells.
export const CITY_BBOX = BBOX;
export function sampleCommercial(lon: number, lat: number): number {
  const u = (lon - BBOX.minLon) / (BBOX.maxLon - BBOX.minLon);
  const v = (lat - BBOX.minLat) / (BBOX.maxLat - BBOX.minLat);
  return sfield(u, v, 2);
}

interface Cell { type: 'Feature'; properties: Record<string, number | string>; geometry: { type: 'Polygon'; coordinates: number[][][] } }
export interface CivicGrid { type: 'FeatureCollection'; features: Cell[] }

// Build the aggregation grid; deterministic + spatially coherent. Fine-grained by
// default (a ~1k-cell neighborhood lattice); pass cols/rows to change resolution.
export function civicGrid(cols = 34, rows = 34, box: GeoBox = BBOX): CivicGrid {
  const dLon = (box.maxLon - box.minLon) / cols;
  const dLat = (box.maxLat - box.minLat) / rows;
  const refLon = BBOX.maxLon - BBOX.minLon; // fixed reference span so the field is stable across pans
  const refLat = BBOX.maxLat - BBOX.minLat;
  const uv = (lon: number, lat: number): [number, number] => [(lon - BBOX.minLon) / refLon, (lat - BBOX.minLat) / refLat];
  // Pass 1: raw smooth fields (sampled in absolute space), normalised to full 0..1.
  const rawA: number[] = [];
  const rawB: number[] = [];
  for (let i = 0; i < cols; i += 1) for (let j = 0; j < rows; j += 1) { const [u, v] = uv(box.minLon + (i + 0.5) * dLon, box.minLat + (j + 0.5) * dLat); rawA.push(sfield(u, v, 1)); rawB.push(sfield(u, v, 2)); }
  const norm = (arr: number[]) => { const mn = minOf(arr); const d = (maxOf(arr) - mn) || 1; return arr.map((x) => (x - mn) / d); };
  const A = norm(rawA);
  const B = norm(rawB);
  const features: Cell[] = [];
  for (let i = 0; i < cols; i += 1) {
    for (let j = 0; j < rows; j += 1) {
      const lon0 = box.minLon + i * dLon;
      const lat0 = box.minLat + j * dLat;
      const a = A[i * rows + j]!;             // "advantage" axis 0..1 (affluence) — smooth, full-range
      const b = B[i * rows + j]!;             // "commercial intensity" 0..1 (foot traffic) — decorrelated
      const n = (hash(i + 31, j + 17) - 0.5) * 0.6; // fine per-cell texture
      const cLon = +(lon0 + dLon / 2).toFixed(5);
      const cLat = +(lat0 + dLat / 2).toFixed(5);
      if (!isLand(cLon, cLat)) continue; // skip water / non-livable cells
      features.push({
        type: 'Feature',
        properties: buildCellProps(a, b, n, `cell-${i}-${j}`, cLon, cLat, i * 131 + j),
        geometry: {
          type: 'Polygon',
          coordinates: [[[lon0, lat0], [lon0 + dLon, lat0], [lon0 + dLon, lat0 + dLat], [lon0, lat0 + dLat], [lon0, lat0]]],
        },
      });
    }
  }
  return { type: 'FeatureCollection', features };
}

// Shared per-cell metric schema — identical for square + hex grids, driven by the
// affluence (a), commercial-intensity (b), and fine-texture (n) fields.
function buildCellProps(a: number, b: number, n: number, id: string, cLon: number, cLat: number, seed: number): Record<string, number | string> {
  const reMedianPrice = Math.round(400000 + a * 2100000 + n * 200000);
  const reMedianRent = Math.round(1800 + a * 4000 + n * 500);
  const rePriceTrend = Array.from({ length: 8 }, (_, k) => +(100 - (7 - k) * (1.2 + a * 1.4) + (hash(seed + k, seed + k * 3) - 0.5) * 1.6).toFixed(1));
  return {
    id,
    cLon,
    cLat,
    // Development momentum — per-quarter rate of change (gentrifying > 0, declining < 0).
    // Drives the temporal replay: "better" metrics rise where momentum is positive.
    momentum: +((a - 0.45) * 0.09 + n * 0.015).toFixed(4),
    population: Math.round(2000 + a * 40000),
    healthIndex: Math.round(clamp(42 + a * 40 + n * 14, 42, 94)),
    uninsuredPct: +clamp(24 - a * 18 + n * 5, 3, 24).toFixed(1),
    lifeExpectancy: +clamp(74 + a * 10 + n * 1.5, 74, 85).toFixed(1),
    crimeRate: +clamp(85 - a * 70 + n * 18, 5, 85).toFixed(1),
    propertyCrime: +clamp(120 - a * 95 + n * 24, 10, 120).toFixed(1),
    response911: +clamp(14 - a * 8 + n * 2.5, 4, 14).toFixed(1),
    schoolRating: +clamp(3 + a * 6 + n * 1.2, 3, 9.5).toFixed(1),
    gradRate: Math.round(clamp(62 + a * 34 + n * 6, 62, 98)),
    studentTeacher: Math.round(clamp(28 - a * 15 + n * 4, 11, 28)),
    reMedianPrice,
    reMedianRent,
    reGrossYield: +clamp((reMedianRent * 12) / reMedianPrice * 100, 2.5, 8).toFixed(2),
    reTurnoverPct: +clamp(4 + a * 7 + n * 3, 3, 14).toFixed(1),
    reDefaultPct: +clamp(6 - a * 5 + n * 1.5, 0.5, 6).toFixed(1),
    reOwnerOccPct: Math.round(clamp(25 + a * 50 + n * 8, 25, 80)),
    reVacancyPct: +clamp(12 - a * 8 + n * 2.5, 2, 12).toFixed(1),
    reChurnPct: Math.round(clamp(35 - a * 22 + n * 6, 8, 35)),
    rePriceTrend: JSON.stringify(rePriceTrend),
    // Housing
    rentBurdenPct: Math.round(clamp(55 - a * 35 + n * 6, 18, 55)),
    costBurdenedPct: Math.round(clamp(60 - a * 38 + n * 6, 20, 60)),
    evictionPct: +clamp(5 - a * 4.5 + n * 1, 0.3, 5).toFixed(1),
    housingVacancyPct: +clamp(14 - a * 10 + n * 3, 2, 14).toFixed(1),
    // Environment
    airQualityAqi: Math.round(clamp(120 - a * 95 + n * 22, 20, 120)),
    floodRiskPct: +clamp(2 + (1 - a) * 30 + n * 8, 2, 40).toFixed(1),
    greenSpacePct: +clamp(3 + a * 40 + n * 6, 3, 45).toFixed(1),
    // Mobility
    transitAccessIdx: Math.round(clamp(20 + a * 70 + n * 10, 20, 95)),
    walkScore: Math.round(clamp(25 + a * 70 + n * 8, 25, 98)),
    commuteMin: Math.round(clamp(52 - a * 32 + n * 6, 18, 52)),
    crashRate: +clamp(30 - a * 24 + n * 6, 2, 30).toFixed(1),
    // Economic
    medianIncome: Math.round(clamp(35000 + a * 140000 + n * 15000, 35000, 180000)),
    unemploymentPct: +clamp(14 - a * 11 + n * 2, 2, 14).toFixed(1),
    povertyPct: +clamp(32 - a * 26 + n * 5, 4, 32).toFixed(1),
    businessDensity: Math.round(clamp(5 + b * 70 + a * 15 + n * 10, 5, 90)),
    // Foot traffic (driven by commercial intensity b, not just affluence a)
    footTrafficDaily: Math.round(clamp(200 + b * 22000 + a * 3000 + n * 3000, 200, 25000)),
    dwellMin: Math.round(clamp(12 + a * 22 + (1 - b) * 8 + n * 4, 8, 45)),
    captureRate: +clamp(2 + b * 13 + n * 3, 2, 18).toFixed(1),
    // News & social by region
    newsVolume: Math.round(clamp(5 + b * 100 + n * 15, 0, 120)),
    socialPosts: Math.round(clamp(100 + b * 7000 + a * 800 + n * 800, 100, 8000)),
    netSentiment: Math.round(clamp((a - 0.5) * 100 + n * 25, -60, 60)),
    civicEngagement: Math.round(clamp(10 + a * 70 + n * 12, 10, 90)),
  };
}

// H3 hexagon aggregation — the industry-standard atomic tiling (Uber H3, the same
// index space the GAIA panels reference). Same metric schema as the square grid,
// sampled at each hex centroid; fields normalised across the tessellation.
export interface GeoBox { minLon: number; maxLon: number; minLat: number; maxLat: number }
export function civicHexGrid(res = 8, box: GeoBox = BBOX): CivicGrid {
  const poly: number[][] = [[box.minLat, box.minLon], [box.minLat, box.maxLon], [box.maxLat, box.maxLon], [box.maxLat, box.minLon]];
  const cells = polygonToCells(poly, res).filter((h3) => { const [lat, lon] = cellToLatLng(h3); return isLand(lon, lat); }); // land only
  // Field is sampled relative to the FIXED reference bbox, so neighborhoods stay
  // put as you pan/zoom — only the cells shown change with the viewport.
  const spanLon = BBOX.maxLon - BBOX.minLon;
  const spanLat = BBOX.maxLat - BBOX.minLat;
  const centers = cells.map((h3) => cellToLatLng(h3)); // [lat, lng]
  const rawA = centers.map(([lat, lon]) => sfield((lon - BBOX.minLon) / spanLon, (lat - BBOX.minLat) / spanLat, 1));
  const rawB = centers.map(([lat, lon]) => sfield((lon - BBOX.minLon) / spanLon, (lat - BBOX.minLat) / spanLat, 2));
  const norm = (arr: number[]) => { const mn = minOf(arr); const d = (maxOf(arr) - mn) || 1; return arr.map((x) => (x - mn) / d); };
  const A = norm(rawA);
  const B = norm(rawB);
  const features: Cell[] = cells.map((h3, k) => {
    const [lat, lon] = centers[k]!;
    const a = A[k]!;
    const b = B[k]!;
    const n = (hash(Math.round(lon * 1e4), Math.round(lat * 1e4)) - 0.5) * 0.6;
    const ring = cellToBoundary(h3, true) as number[][]; // [lng, lat] pairs (GeoJSON order)
    const first = ring[0]!;
    const last = ring[ring.length - 1]!;
    const closed = first[0] === last[0] && first[1] === last[1] ? ring : [...ring, first];
    return {
      type: 'Feature',
      properties: buildCellProps(a, b, n, h3, +lon.toFixed(5), +lat.toFixed(5), (parseInt(h3.slice(-6), 16) || 0)),
      geometry: { type: 'Polygon', coordinates: [closed] },
    };
  });
  return { type: 'FeatureCollection', features };
}
