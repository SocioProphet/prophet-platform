<script setup lang="ts">
// A real, time-scaled execution timeline (Databricks-style gantt). Every bar is positioned and sized
// from actual timings — started_at + duration_ms — over a shared time axis, with a live "now" line and
// a still-running task that grows to the present. Rows are grouped by backend so you read where work
// ran. Bars carry a thin epistemic stripe (the run's proof-status) and colour by status. No fabricated
// widths: if timings aren't there, there's nothing to draw. Pure CSS/SVG, reduced-motion aware.
import { computed } from 'vue';
import { EPISTEMIC_COLORS, type ExecutionEvent } from '../../services/studioApi';

const props = defineProps<{ events: ExecutionEvent[] }>();

const now = Date.now();
function endOf(e: ExecutionEvent): number { return e.status === 'running' ? Math.max(now, e.started_at + e.duration_ms) : e.started_at + e.duration_ms; }

const win = computed(() => {
  const es = props.events;
  if (!es.length) return { t0: now - 60000, t1: now, span: 60000 };
  const t0 = Math.min(...es.map((e) => e.started_at));
  const t1 = Math.max(now, ...es.map(endOf));
  const pad = (t1 - t0) * 0.04 || 1000;
  return { t0: t0 - pad, t1: t1 + pad, span: (t1 - t0) + 2 * pad };
});

// rows grouped by backend, each backend's events sorted by start
const rows = computed(() => {
  const by = new Map<string, ExecutionEvent[]>();
  for (const e of props.events) (by.get(e.backend) ?? by.set(e.backend, []).get(e.backend)!).push(e);
  return [...by.entries()].map(([backend, evs]) => ({ backend, evs: evs.sort((a, b) => a.started_at - b.started_at) }));
});

function leftPct(e: ExecutionEvent): number { return ((e.started_at - win.value.t0) / win.value.span) * 100; }
function widthPct(e: ExecutionEvent): number { return Math.max(0.8, ((endOf(e) - e.started_at) / win.value.span) * 100); }
const nowPct = computed(() => ((now - win.value.t0) / win.value.span) * 100);
function epiColor(mode: string): string { return EPISTEMIC_COLORS[mode] || 'var(--epi-unknown)'; }

// a few relative time ticks along the axis
const ticks = computed(() => {
  const n = 5, out: { pct: number; label: string }[] = [];
  for (let i = 0; i <= n; i++) {
    const t = win.value.t0 + (win.value.span * i) / n;
    const agoMin = Math.round((now - t) / 60000);
    out.push({ pct: (i / n) * 100, label: agoMin <= 0 ? 'now' : `-${agoMin}m` });
  }
  return out;
});
function dur(e: ExecutionEvent): string {
  const ms = endOf(e) - e.started_at; const s = Math.round(ms / 1000);
  return s >= 60 ? `${Math.floor(s / 60)}m${String(s % 60).padStart(2, '0')}s` : `${s}s`;
}
</script>

<template>
  <div class="tl" v-if="events.length">
    <div class="tl-axis"><span v-for="(t, i) in ticks" :key="i" class="tick" :style="{ left: t.pct + '%' }">{{ t.label }}</span></div>
    <div class="tl-body">
      <span class="nowline" :style="{ left: nowPct + '%' }" aria-hidden="true" />
      <div v-for="grp in rows" :key="grp.backend" class="lane">
        <div class="lane-h">{{ grp.backend }}</div>
        <div class="lane-track">
          <div
            v-for="e in grp.evs" :key="e.id" class="bar" :class="e.status"
            :style="{ left: leftPct(e) + '%', width: widthPct(e) + '%' }"
            :title="`${e.label} · ${e.kind} · ${e.status} · ${dur(e)}`"
          >
            <i class="bar-epi" :style="{ background: epiColor(e.epistemic) }" />
            <span class="bar-l">{{ e.label }}</span>
            <span class="bar-d tnum">{{ dur(e) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
  <p v-else class="tl-empty">No executions in this window.</p>
</template>

<style scoped>
.tl { border: 1px solid var(--hairline); border-radius: var(--r-3); overflow: hidden; background: var(--sunken); }
.tl-axis { position: relative; height: 18px; border-bottom: 1px solid var(--hairline); }
.tl-axis .tick { position: absolute; top: 3px; transform: translateX(-50%); font-size: 9.5px; color: var(--faint); white-space: nowrap; }
.tl-axis .tick:first-child { transform: none; } .tl-axis .tick:last-child { transform: translateX(-100%); }
.tl-body { position: relative; padding: 6px 0; }
.nowline { position: absolute; top: 0; bottom: 0; width: 1px; background: color-mix(in srgb, var(--accent) 70%, transparent); z-index: 3; }
.lane { display: grid; grid-template-columns: 96px 1fr; align-items: center; gap: 8px; padding: 3px 8px 3px 0; }
.lane-h { font-size: 10.5px; color: var(--muted); text-align: right; font-family: var(--mono); overflow: hidden; text-overflow: ellipsis; }
.lane-track { position: relative; height: 22px; }
.bar { position: absolute; top: 1px; height: 20px; border-radius: var(--r-1); display: flex; align-items: center; gap: 5px; padding: 0 6px 0 9px; overflow: hidden;
  border: 1px solid var(--hairline-strong); background: var(--surface-2); min-width: 6px; }
.bar-epi { position: absolute; left: 0; top: 0; bottom: 0; width: 3px; }
.bar.done { background: color-mix(in srgb, var(--ok) 14%, var(--surface-2)); border-color: color-mix(in srgb, var(--ok) 34%, var(--hairline-strong)); }
.bar.running { background: color-mix(in srgb, var(--accent) 16%, var(--surface-2)); border-color: color-mix(in srgb, var(--accent) 45%, var(--hairline-strong)); }
.bar.failed { background: color-mix(in srgb, var(--fail) 14%, var(--surface-2)); border-color: color-mix(in srgb, var(--fail) 40%, var(--hairline-strong)); }
@media (prefers-reduced-motion: no-preference) { .bar.running { animation: livepulse 2.4s ease-in-out infinite; } }
@keyframes livepulse { 0%,100% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--accent) 40%, transparent); } 50% { box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 12%, transparent); } }
.bar-l { font-size: 11px; color: var(--ink); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.bar-d { font-size: 10px; color: var(--muted); margin-left: auto; flex: 0 0 auto; }
.tl-empty { color: var(--faint); font-size: 12px; }
</style>
