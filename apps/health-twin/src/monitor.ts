// monitor.ts — longitudinal acuity (verb 8 Monitor). Generalizes the fitness–fatigue load model
// (external load + internal response → homeostasis / underload / overload / failure) into clinical
// trend monitoring: for each tracked metric we read its series, find the direction and distance from
// the reference range, and band it — stable / improving / watch / worsening / critical. A metric that
// is out of range AND moving further out (or far out) is DETERIORATING and raises an escalate signal
// that feeds the triage/routing core. Non-diagnostic: it tracks change and flags deterioration; a
// clinician interprets. "Today vs earlier" is a delta over the series, not a blank-slate reading.
import { OBSERVATIONS, type Observation } from './data.js';

export type AcuityBand = 'stable' | 'improving' | 'watch' | 'worsening' | 'critical';
export const BAND_RANK: Record<AcuityBand, number> = { stable: 0, improving: 0, watch: 1, worsening: 2, critical: 3 };

export interface MetricAcuity {
  id: string; display: string; value: number; unit: string;
  refLow?: number; refHigh?: number;
  band: AcuityBand;
  direction: 'rising' | 'falling' | 'flat';
  deltaRecent: number;          // change over the recent window of the series (today vs earlier)
  outOfRange: boolean;
  adverse: 'high' | 'low' | 'none'; // which bound the metric is breaching / trending toward
  escalate: boolean;            // deterioration that warrants a clinician look
  note: string;
}

const round = (n: number, p = 2) => Math.round(n * 10 ** p) / 10 ** p;

// Band a single metric from its value, reference range, and trend series. Direction is read from the
// series (recent vs earlier mean). "Adverse" is the bound in play: over refHigh (or trending up toward
// it) = high-adverse; under refLow (or trending down toward it) = low-adverse. Worsening = out of
// range and moving further out; improving = out of range but moving back toward it.
export function acuity(o: Pick<Observation, 'id' | 'display' | 'value' | 'unit' | 'refLow' | 'refHigh' | 'trend'>): MetricAcuity {
  const { value, refLow, refHigh } = o;
  const series = (o.trend && o.trend.length ? o.trend : [value]).slice();
  if (series[series.length - 1] !== value) series.push(value);
  const n = series.length;
  const recent = series[n - 1]!;
  const earlier = series[Math.max(0, n - 3)]!; // ~3 points back = the recent window
  const deltaRecent = round(recent - earlier);
  const span = Math.max(1e-9, Math.abs((refHigh ?? recent) - (refLow ?? recent)) || Math.abs(recent) || 1);
  const eps = span * 0.02; // flat-band: <2% of the range is "flat"
  const direction: MetricAcuity['direction'] = deltaRecent > eps ? 'rising' : deltaRecent < -eps ? 'falling' : 'flat';

  const overHigh = refHigh != null && value > refHigh;
  const underLow = refLow != null && value < refLow;
  const outOfRange = overHigh || underLow;
  const adverse: MetricAcuity['adverse'] = overHigh ? 'high' : underLow ? 'low' : 'none';

  // how far out of range, as a fraction of the reference span (0 = at the bound, 1 = a full span past)
  const excess = overHigh ? (value - refHigh!) / span : underLow ? (refLow! - value) / span : 0;

  let band: AcuityBand;
  if (!outOfRange) {
    // in range: watch if trending hard toward a bound, else stable
    const nearHigh = refHigh != null && direction === 'rising' && (refHigh - value) < span * 0.15;
    const nearLow = refLow != null && direction === 'falling' && (value - refLow) < span * 0.15;
    band = nearHigh || nearLow ? 'watch' : 'stable';
  } else {
    const movingAway = (adverse === 'high' && direction === 'rising') || (adverse === 'low' && direction === 'falling');
    const movingBack = (adverse === 'high' && direction === 'falling') || (adverse === 'low' && direction === 'rising');
    if (excess >= 0.5 || (excess >= 0.25 && movingAway)) band = 'critical';
    else if (movingBack) band = 'improving';
    else if (movingAway) band = 'worsening';
    else band = 'watch'; // out of range but flat
  }

  const escalate = band === 'critical' || band === 'worsening';
  const arrow = direction === 'rising' ? '↑' : direction === 'falling' ? '↓' : '→';
  const note = outOfRange
    ? `${o.display} ${value}${o.unit ? ' ' + o.unit : ''} ${arrow} — ${band}${escalate ? ' (deteriorating)' : ''}; ${adverse === 'high' ? 'above' : 'below'} the reference range`
    : `${o.display} ${value}${o.unit ? ' ' + o.unit : ''} ${arrow} — ${band}, within range`;

  return { id: o.id, display: o.display, value, unit: o.unit, refLow, refHigh, band, direction, deltaRecent, outOfRange, adverse, escalate, note };
}

export interface MonitorReport {
  asOf: string;
  metrics: MetricAcuity[];
  overall: AcuityBand;
  deteriorating: string[];   // display names of metrics raising an escalate signal
  escalate: boolean;         // any metric deteriorating
  summary: string;
  disclaimer: string;
}

type MonitorInput = Pick<Observation, 'id' | 'display' | 'value' | 'unit' | 'refLow' | 'refHigh' | 'trend'>;
export function monitorTwin(observations: readonly MonitorInput[] = OBSERVATIONS): MonitorReport {
  const metrics = observations.map((o) => acuity(o));
  const worst = metrics.reduce<AcuityBand>((w, m) => (BAND_RANK[m.band] > BAND_RANK[w] ? m.band : w), 'stable');
  const deteriorating = metrics.filter((m) => m.escalate).map((m) => m.display);
  return {
    asOf: new Date().toISOString(),
    metrics,
    overall: worst,
    deteriorating,
    escalate: deteriorating.length > 0,
    summary: deteriorating.length
      ? `${deteriorating.length} metric(s) trending the wrong way: ${deteriorating.join(', ')}. Worth a clinician review.`
      : `No metric is deteriorating; overall trend is ${worst}.`,
    disclaimer: 'Longitudinal monitoring is informational and non-diagnostic — it flags change over time; a clinician interprets it.',
  };
}
