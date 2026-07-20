// useLiveTicks — Bloomberg-style live pulse for the dashboard. On an interval it drifts each
// item's latest value, appends to its sparkline series, recomputes the delta, and flags the tick
// direction so the cell can flash green/red. This is a fixture-driven simulation (there's no live
// quote feed wired yet), but it turns a frozen "as of Jul 4" board into a terminal that breathes.
// Honours prefers-reduced-motion (no flashes; values still update). Clears itself on scope dispose.
import { onScopeDispose } from 'vue';

export interface TickSpec {
  valueKey: string;                 // e.g. 'price' | 'value' | 'tempF'
  deltaKey: string;                 // e.g. 'changePct' | 'changeAbs' | 'changeF'
  deltaMode: 'pct' | 'abs';
  vol: number;                      // per-tick jitter as a fraction of the value (e.g. 0.0012)
  decimals?: number;
  hasSeries?: boolean;
  seriesCap?: number;
}

export type Ticked = Record<string, unknown> & {
  _dir?: 'up' | 'down' | 'flat';
  _flash?: 'up' | 'down' | null;
  _tick?: number;
};

export function useLiveTicks(items: Ticked[], spec: TickSpec, intervalMs = 2600): void {
  const reduce =
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const dec = spec.decimals ?? 2;
  const cap = spec.seriesCap ?? 40;
  const round = (n: number) => +n.toFixed(dec);

  function tickOne(it: Ticked): void {
    const cur = Number(it[spec.valueKey]) || 0;
    const step = (Math.random() - 0.5) * 2 * spec.vol * (Math.abs(cur) || 1);
    const next = round(cur + step);
    const dir: 'up' | 'down' | 'flat' = next > cur ? 'up' : next < cur ? 'down' : 'flat';
    it[spec.valueKey] = next;

    const series = it.series as number[] | undefined;
    if (spec.hasSeries && Array.isArray(series)) {
      series.push(next);
      if (series.length > cap) series.shift();
      const baseline = series[Math.max(0, series.length - 9)] ?? series[0] ?? next;
      it[spec.deltaKey] =
        spec.deltaMode === 'pct' ? round(((next - baseline) / (baseline || 1)) * 100) : round(next - baseline);
    } else {
      it[spec.deltaKey] = round((Number(it[spec.deltaKey]) || 0) + step);
    }

    it._dir = dir;
    it._tick = (it._tick ?? 0) + 1;
    if (!reduce && dir !== 'flat') {
      it._flash = dir;
      window.setTimeout(() => { it._flash = null; }, 700);
    }
  }

  const timer = window.setInterval(() => { for (const it of items) tickOne(it); }, intervalMs);
  onScopeDispose(() => window.clearInterval(timer));
}
