<script setup lang="ts">
// Word-sized trend line (Tufte sparkline): a metric's trajectory inline with its
// number, so a row shows shape + level + change at a glance. Neutral by default —
// the row's delta carries the up/down colour, so a list of sparklines stays calm
// (Tufte's "smallest effective difference"). A faint band marks the series' own
// range ("compared to what"). Pure SVG, no chart lib. Renders nothing for an empty
// series, so callers can pass optional data without guarding.
import { computed } from 'vue';

const props = withDefaults(
  defineProps<{
    series: number[];
    w?: number;
    h?: number;
    tone?: 'neutral' | 'up' | 'down' | 'accent';
  }>(),
  { w: 64, h: 20, tone: 'neutral' },
);

const points = computed(() => {
  const s = props.series ?? [];
  if (s.length === 0) return [] as { x: number; y: number }[];
  const min = Math.min(...s);
  const max = Math.max(...s);
  const span = max - min || 1;
  const pad = props.h * 0.16;
  return s.map((v, i) => ({
    x: s.length === 1 ? props.w : +((i / (s.length - 1)) * props.w).toFixed(1),
    y: +(props.h - pad - ((v - min) / span) * (props.h - pad * 2)).toFixed(1),
  }));
});

const line = computed(() => points.value.map((p) => `${p.x},${p.y}`).join(' '));
const last = computed(() => points.value[points.value.length - 1] ?? null);
const stroke = computed(() => {
  switch (props.tone) {
    case 'down': return 'var(--down)';
    case 'up': return 'var(--up)';
    case 'accent': return 'var(--accent)';
    default: return 'var(--spark-line, rgba(237, 238, 242, 0.55))';
  }
});
</script>

<template>
  <svg
    v-if="last"
    class="spark"
    :width="w"
    :height="h"
    :viewBox="`0 0 ${w} ${h}`"
    preserveAspectRatio="none"
    aria-hidden="true"
    focusable="false"
  >
    <rect class="spark-band" x="0" y="1" :width="w" :height="h - 2" rx="1" />
    <polyline
      :points="line"
      fill="none"
      :stroke="stroke"
      stroke-width="1.4"
      stroke-linejoin="round"
      stroke-linecap="round"
    />
    <circle :cx="last.x" :cy="last.y" r="2" :fill="stroke" />
  </svg>
</template>

<style scoped>
.spark { display: block; flex: 0 0 auto; }
.spark-band { fill: rgba(237, 238, 242, 0.05); }
</style>
