// Choropleth classification — turn a set of values into class breaks so the map
// reads cleanly regardless of distribution. Equal-interval spreads outliers;
// quantile gives equal-count classes; Jenks (natural breaks) minimises within-
// class variance (the cartographic default). Each returns n-1 internal breaks
// for n classes (ascending), plus helpers to sample a color ramp and classify.

export type ClassMode = 'equal' | 'quantile' | 'jenks';

const asc = (a: number, b: number) => a - b;
const finite = (v: number) => Number.isFinite(v);

// n-1 equally spaced thresholds between min and max.
export function equalBreaks(min: number, max: number, n: number): number[] {
  const out: number[] = [];
  for (let i = 1; i < n; i++) out.push(min + ((max - min) * i) / n);
  return out;
}

// n-1 thresholds at equal-count quantiles of the data.
export function quantileBreaks(values: number[], n: number): number[] {
  const s = values.filter(finite).sort(asc);
  if (s.length === 0) return [];
  const out: number[] = [];
  for (let i = 1; i < n; i++) {
    const idx = Math.min(s.length - 1, Math.floor((i / n) * s.length));
    out.push(s[idx]!);
  }
  return out;
}

// Fisher–Jenks natural breaks (goodness-of-variance fit). Faithful transcription
// of the classic matrix algorithm; returns n-1 internal breaks.
export function jenksBreaks(values: number[], n: number): number[] {
  const data = values.filter(finite).sort(asc);
  const len = data.length;
  if (len <= n) return quantileBreaks(data, n);

  const lowerClass: number[][] = [];
  const variance: number[][] = [];
  for (let i = 0; i <= len; i++) {
    lowerClass.push(new Array(n + 1).fill(0));
    variance.push(new Array(n + 1).fill(0));
  }
  for (let j = 1; j <= n; j++) {
    lowerClass[1]![j] = 1;
    variance[1]![j] = 0;
    for (let i = 2; i <= len; i++) variance[i]![j] = Infinity;
  }

  for (let l = 2; l <= len; l++) {
    let sum = 0;
    let sumSq = 0;
    let w = 0;
    for (let m = 1; m <= l; m++) {
      const lower = l - m + 1;
      const val = data[lower - 1]!;
      w += 1;
      sum += val;
      sumSq += val * val;
      const v = sumSq - (sum * sum) / w;
      const prev = lower - 1;
      if (prev !== 0) {
        for (let j = 2; j <= n; j++) {
          if (variance[l]![j] >= v + variance[prev]![j - 1]!) {
            lowerClass[l]![j] = lower;
            variance[l]![j] = v + variance[prev]![j - 1]!;
          }
        }
      }
    }
    lowerClass[l]![1] = 1;
    variance[l]![1] = sumSq - (sum * sum) / w;
  }

  const breaks: number[] = [];
  let k = len;
  for (let j = n; j >= 2; j--) {
    const id = lowerClass[k]![j]! - 1;
    breaks.push(data[id]!);
    k = lowerClass[k]![j]! - 1;
  }
  return breaks.reverse().filter(finite);
}

export function breaksFor(mode: ClassMode, values: number[], min: number, max: number, n: number): number[] {
  if (mode === 'equal') return equalBreaks(min, max, n);
  if (mode === 'quantile') return quantileBreaks(values, n);
  return jenksBreaks(values, n);
}

// Which class (0..breaks.length) a value falls in.
export function classOf(v: number, breaks: number[]): number {
  let i = 0;
  while (i < breaks.length && v >= breaks[i]!) i++;
  return i;
}

// Linear-interpolate a color from a ramp of [position 0..1, "#rrggbb"] stops.
export function sampleRamp(ramp: Array<[number, string]>, t: number): string {
  const x = Math.max(0, Math.min(1, t));
  let lo = ramp[0]!;
  let hi = ramp[ramp.length - 1]!;
  for (let i = 0; i < ramp.length - 1; i++) {
    if (x >= ramp[i]![0] && x <= ramp[i + 1]![0]) { lo = ramp[i]!; hi = ramp[i + 1]!; break; }
  }
  const span = hi[0] - lo[0] || 1;
  const f = (x - lo[0]) / span;
  const [lr, lg, lb] = hexToRgb(lo[1]);
  const [hr, hg, hb] = hexToRgb(hi[1]);
  const r = Math.round(lr + (hr - lr) * f);
  const g = Math.round(lg + (hg - lg) * f);
  const b = Math.round(lb + (hb - lb) * f);
  return `#${[r, g, b].map((c) => c.toString(16).padStart(2, '0')).join('')}`;
}

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace('#', '');
  const s = h.length === 3 ? h.split('').map((c) => c + c).join('') : h;
  return [parseInt(s.slice(0, 2), 16), parseInt(s.slice(2, 4), 16), parseInt(s.slice(4, 6), 16)];
}
