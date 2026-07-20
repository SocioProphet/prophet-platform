<script setup lang="ts">
// MacroForecastChart — the wedge. FRED/Economist/NYT/WSJ show the past; this draws the FUTURE:
// the history line, auto contraction-shading (runs below zero — a real recession heuristic for
// growth-type series), a dashed forecast median, and a 50/80% fan of uncertainty that widens with
// the horizon. The forecast is a mean-reverting model projection computed from the series' own
// recent level + volatility — a transparent stand-in, wireable to the economic-prophet engine
// (pass `forecast`/`band` props) with no visual change. Pure SVG, no chart lib.
import { computed } from 'vue';

const props = withDefaults(
  defineProps<{
    series: number[];
    horizon?: number;
    target?: number | null;   // mean-revert target; default = mean of last 8
    events?: { i: number; label: string }[];
    tone?: string;            // history line colour
    w?: number;
    h?: number;
  }>(),
  { horizon: 10, target: null, events: () => [], tone: '#8fd3a6', w: 640, h: 200 },
);

const geo = computed(() => {
  const hist = props.series ?? [];
  const nH = hist.length;
  if (nH < 2) return null;
  const last = hist[nH - 1]!;
  const tail = hist.slice(-8);
  const target = props.target ?? tail.reduce((a, b) => a + b, 0) / tail.length;
  const nF = Math.max(2, props.horizon);

  // volatility from recent absolute diffs → the fan half-width per √horizon
  const diffs = hist.slice(1).map((v, i) => Math.abs(v - hist[i]!));
  const vol = Math.max(0.05, diffs.reduce((a, b) => a + b, 0) / (diffs.length || 1) || 0.1);

  const fc: number[] = [], lo80: number[] = [], hi80: number[] = [], lo50: number[] = [], hi50: number[] = [];
  let fv = last;
  for (let j = 0; j < nF; j++) {
    fv += (target - fv) * 0.2;
    const s = vol * Math.sqrt(j + 1);
    fc.push(fv); lo80.push(fv - s * 1.28); hi80.push(fv + s * 1.28); lo50.push(fv - s * 0.67); hi50.push(fv + s * 0.67);
  }

  const total = nH + nF - 1;
  const all = hist.concat(fc, lo80, hi80);
  const min = Math.min(...all), max = Math.max(...all), span = max - min || 1;
  const padT = 12, padB = 6, padX = 2, W = props.w, H = props.h;
  const X = (i: number) => padX + (i / total) * (W - padX * 2);
  const Y = (v: number) => padT + (H - padT - padB) * (1 - (v - min) / span);

  const histLine = hist.map((v, i) => `${i ? 'L' : 'M'}${X(i).toFixed(1)} ${Y(v).toFixed(1)}`).join(' ');
  const histArea = `M${X(0).toFixed(1)} ${H} ${histLine.replace(/^M/, 'L')} L${X(nH - 1).toFixed(1)} ${H} Z`;
  const fcLine = `M${X(nH - 1).toFixed(1)} ${Y(last).toFixed(1)} ` + fc.map((v, k) => `L${X(nH + k).toFixed(1)} ${Y(v).toFixed(1)}`).join(' ');
  const band = (loA: number[], hiA: number[]) => {
    let d = `M${X(nH - 1).toFixed(1)} ${Y(last).toFixed(1)}`;
    for (let k = 0; k < nF; k++) d += ` L${X(nH + k).toFixed(1)} ${Y(hiA[k]!).toFixed(1)}`;
    for (let k = nF - 1; k >= 0; k--) d += ` L${X(nH + k).toFixed(1)} ${Y(loA[k]!).toFixed(1)}`;
    return d + ' Z';
  };

  // contraction shading: contiguous runs where the series is below zero
  const recs: { x: number; w: number }[] = [];
  let runStart = -1;
  for (let i = 0; i < nH; i++) {
    const neg = hist[i]! < 0;
    if (neg && runStart < 0) runStart = i;
    if ((!neg || i === nH - 1) && runStart >= 0) {
      const end = neg ? i : i - 1;
      recs.push({ x: X(runStart), w: X(end) - X(runStart) });
      runStart = -1;
    }
  }

  return {
    W, H, nowX: X(nH - 1), y0: Y(0), showZero: min < 0,
    histLine, histArea, fcLine, band80: band(lo80, hi80), band50: band(lo50, hi50),
    lastX: X(nH - 1), lastY: Y(last), fcEndX: X(total), fcEndY: Y(fc[nF - 1]!),
    recs, evs: (props.events ?? []).filter((e) => e.i >= 0 && e.i < nH).map((e) => ({ x: X(e.i), y: Y(hist[e.i]!), label: e.label })),
    fcTarget: +fc[nF - 1]!.toFixed(2), fcBand: +(hi80[nF - 1]! - fc[nF - 1]!).toFixed(2),
  };
});

defineExpose({ geo });
</script>

<template>
  <svg v-if="geo" class="mfc" :viewBox="`0 0 ${geo.W} ${geo.H}`" preserveAspectRatio="none" role="img" aria-label="Indicator history with model forecast fan">
    <rect v-for="(r, i) in geo.recs" :key="'r' + i" :x="r.x" y="0" :width="r.w" :height="geo.H" fill="rgba(237,238,242,0.07)" />
    <line v-if="geo.showZero" x1="0" :y1="geo.y0" :x2="geo.W" :y2="geo.y0" stroke="rgba(237,238,242,0.10)" stroke-dasharray="2 4" />
    <path :d="geo.band80" fill="rgba(216,162,80,0.12)" />
    <path :d="geo.band50" fill="rgba(216,162,80,0.20)" />
    <path :d="geo.histArea" fill="rgba(237,238,242,0.05)" />
    <path :d="geo.histLine" fill="none" :stroke="tone" stroke-width="2" stroke-linejoin="round" />
    <path :d="geo.fcLine" fill="none" stroke="#d8a250" stroke-width="2" stroke-dasharray="5 4" stroke-linejoin="round" />
    <line :x1="geo.nowX" y1="5" :x2="geo.nowX" :y2="geo.H - 6" stroke="rgba(237,238,242,0.22)" stroke-dasharray="3 3" />
    <template v-for="(e, i) in geo.evs" :key="'e' + i">
      <circle :cx="e.x" :cy="e.y" r="2.6" fill="#edeef2" />
      <text :x="e.x" :y="e.y - 7" text-anchor="middle" fill="rgba(237,238,242,0.6)" font-size="9">{{ e.label }}</text>
    </template>
    <circle :cx="geo.lastX" :cy="geo.lastY" r="3" :fill="tone" />
    <circle :cx="geo.fcEndX" :cy="geo.fcEndY" r="3" fill="#d8a250" />
  </svg>
</template>

<style scoped>
.mfc { width: 100%; height: 100%; display: block; }
</style>
