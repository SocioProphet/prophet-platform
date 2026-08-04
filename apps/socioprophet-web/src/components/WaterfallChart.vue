<script setup lang="ts">
// WaterfallChart — the "story" chart for a decision tool (Bostock rent-vs-buy lesson): baseline →
// each driver's signed contribution (green up / red down) → the total, as floating bars with
// connectors. Zoomed y-axis (starts near the baseline, not 0) so small uplifts on a large base are
// actually visible. Reusable for the GYG valuation and the Finance decision-tool suite. Pure SVG.
import { computed } from 'vue';

export interface WaterfallSeg { label: string; value: number }

const props = withDefaults(
  defineProps<{
    baseline: number;
    segments: WaterfallSeg[];
    total: number;
    baselineLabel?: string;
    totalLabel?: string;
    fmt?: (n: number) => string;
    w?: number;
    h?: number;
  }>(),
  { baselineLabel: 'Baseline', totalLabel: 'Projected', fmt: (n: number) => Math.round(n).toLocaleString(), w: 660, h: 240 },
);

const geo = computed(() => {
  const segs = props.segments ?? [];
  // running totals to find the value range (bars float between running levels)
  let run = props.baseline;
  const levels: number[] = [props.baseline];
  for (const s of segs) { run += s.value; levels.push(run); }
  levels.push(props.total);
  const lo = Math.min(...levels), hi = Math.max(...levels);
  const pad = (hi - lo || Math.abs(hi) || 1) * 0.12;
  const yMin = lo - pad, yMax = hi + pad, span = yMax - yMin || 1;

  const n = segs.length + 2; // baseline + segments + total
  const padX = 6, padT = 10, padB = 26, W = props.w, H = props.h;
  const bw = (W - padX * 2) / n * 0.62;
  const gap = (W - padX * 2) / n;
  const X = (i: number) => padX + gap * i + (gap - bw) / 2;
  const Y = (v: number) => padT + (H - padT - padB) * (1 - (v - yMin) / span);

  const bars: Array<{ x: number; y: number; w: number; h: number; kind: string; label: string; val: string; cxLine?: number }> = [];
  // baseline (full-ish column from yMin)
  bars.push({ x: X(0), y: Y(props.baseline), w: bw, h: Y(yMin) - Y(props.baseline), kind: 'base', label: props.baselineLabel, val: props.fmt(props.baseline) });
  let cur = props.baseline;
  segs.forEach((s, i) => {
    const next = cur + s.value;
    const yTop = Y(Math.max(cur, next)), yBot = Y(Math.min(cur, next));
    bars.push({ x: X(i + 1), y: yTop, w: bw, h: Math.max(1.5, yBot - yTop), kind: s.value >= 0 ? 'up' : 'down', label: s.label, val: (s.value >= 0 ? '+' : '') + props.fmt(s.value) });
    cur = next;
  });
  bars.push({ x: X(n - 1), y: Y(props.total), w: bw, h: Y(yMin) - Y(props.total), kind: 'total', label: props.totalLabel, val: props.fmt(props.total) });

  // connectors between successive bar tops (running level)
  const conns: Array<{ x1: number; y1: number; x2: number; y2: number }> = [];
  let lvl = props.baseline;
  for (let i = 0; i < segs.length; i++) {
    const y = Y(lvl);
    conns.push({ x1: X(i) + bw, y1: y, x2: X(i + 1), y2: y });
    lvl += segs[i]!.value;
  }
  conns.push({ x1: X(segs.length) + bw, y1: Y(lvl), x2: X(segs.length + 1), y2: Y(lvl) });

  return { W, H, bars, conns };
});
</script>

<template>
  <svg class="wf" :viewBox="`0 0 ${geo.W} ${geo.H}`" role="img" aria-label="Value waterfall: baseline to projected by driver">
    <line v-for="(c, i) in geo.conns" :key="'c' + i" :x1="c.x1" :y1="c.y1" :x2="c.x2" :y2="c.y2" class="wf-conn" />
    <g v-for="(b, i) in geo.bars" :key="'b' + i">
      <rect :x="b.x" :y="b.y" :width="b.w" :height="b.h" :class="['wf-bar', b.kind]" rx="1.5" />
      <text :x="b.x + b.w / 2" :y="b.y - 3" text-anchor="middle" class="wf-val" :class="b.kind">{{ b.val }}</text>
      <text :x="b.x + b.w / 2" :y="geo.H - 12" text-anchor="middle" class="wf-lab">{{ b.label }}</text>
    </g>
  </svg>
</template>

<style scoped>
.wf { width: 100%; height: auto; display: block; }
.wf-conn { stroke: rgba(237, 238, 242, 0.22); stroke-width: 1; stroke-dasharray: 2 3; }
.wf-bar.base, .wf-bar.total { fill: color-mix(in srgb, var(--accent) 55%, transparent); }
.wf-bar.up { fill: color-mix(in srgb, var(--up) 80%, transparent); }
.wf-bar.down { fill: color-mix(in srgb, var(--down) 80%, transparent); }
.wf-val { font-size: 9px; font-variant-numeric: tabular-nums; fill: var(--text-2); }
.wf-val.up { fill: var(--up); } .wf-val.down { fill: var(--down); } .wf-val.base, .wf-val.total { fill: var(--accent); }
.wf-lab { font-size: 8.5px; fill: var(--text-3); }
</style>
