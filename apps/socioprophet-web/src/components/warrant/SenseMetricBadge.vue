<template>
  <!-- W11.3 — the sense metric as three LEGIBLE axes, not one opaque number.
       coverage · groundedness(creativity) · similarity, each with its weight and its
       actual contribution to the composite. When a reference metric is supplied (the
       winner's), every axis also shows its delta — so the surface answers WHY a plan
       lost, not merely that it did.

       Creativity is not a separate axis: it is `1 − groundedness`, the ungrounded-node
       penalty routed through claim-admissibility. The ledger below names each node that
       cost the plan groundedness and the discount the gate applied. -->
  <div class="sm" :class="{ 'sm-compact': compact }">
    <div class="sm-axes">
      <div v-for="a in axes" :key="a.key" class="sm-axis" :style="{ '--ax': a.color }">
        <div class="sm-axis-top">
          <span class="sm-axis-name">{{ a.label }}</span>
          <span class="sm-axis-val tnum">{{ pct(a.value) }}</span>
          <span v-if="reference" class="sm-delta tnum" :class="deltaClass(a.delta)">{{ signed(a.delta) }}</span>
        </div>
        <div class="sm-bar" role="img" :aria-label="`${a.label} ${pct(a.value)}`">
          <span class="sm-bar-fill" :style="{ width: `${Math.max(0, Math.min(1, a.value)) * 100}%` }" />
          <!-- the weighted contribution, marked on the same track -->
          <span class="sm-bar-tick" :style="{ left: `${Math.max(0, Math.min(1, a.value * a.weight)) * 100}%` }" />
        </div>
        <div v-if="!compact" class="sm-axis-foot">
          <span class="sm-w tnum">w {{ a.weight.toFixed(2) }}</span>
          <span class="sm-contrib tnum">contributes {{ (a.value * a.weight).toFixed(3) }}</span>
        </div>
      </div>
    </div>

    <div class="sm-composite">
      <span class="sm-comp-l">composite</span>
      <span class="sm-comp-v tnum">{{ metric.composite.toFixed(3) }}</span>
      <span v-if="reference" class="sm-delta tnum" :class="deltaClass(metric.composite - reference.composite)">
        {{ signed(metric.composite - reference.composite) }}
      </span>
    </div>

    <template v-if="!compact">
      <!-- Creativity, stated as the mechanism rather than as a vibe. -->
      <div class="sm-creativity" :class="{ 'sm-clean': metric.ungroundedNodes === 0 }">
        <span class="sm-cr-head">
          <b>creativity</b>
          <span class="tnum">{{ pct(metric.creativity) }}</span>
          <span class="sm-cr-def">= 1 − groundedness</span>
        </span>
        <span class="sm-cr-body">
          <template v-if="metric.ungroundedNodes === 0">
            Every one of the {{ metric.nodes }} plan node{{ metric.nodes === 1 ? '' : 's' }} is grounded — no
            invention, no admissibility discount.
          </template>
          <template v-else>
            {{ metric.ungroundedNodes }} of {{ metric.nodes }} node{{ metric.nodes === 1 ? '' : 's' }} invented.
            Each is filed as a <i>model-generated</i> claim; the admissibility gate's weight IS the
            groundedness contribution.
          </template>
        </span>
        <ul v-if="metric.admissibility.length" class="sm-adm">
          <li v-for="entry in metric.admissibility" :key="entry.nodeId" class="sm-adm-row">
            <code class="mono">{{ entry.nodeId }}</code>
            <span class="sm-adm-action mono">{{ entry.actionId }}</span>
            <span class="sm-adm-reason">{{ REASON_TEXT[entry.reason] ?? entry.reason }}</span>
            <span class="sm-adm-w tnum">×{{ entry.weight.toFixed(2) }}</span>
          </li>
        </ul>
      </div>

      <div class="sm-cov">
        consumed <span class="tnum">{{ metric.consumedContentTokens }}</span> of
        <span class="tnum">{{ metric.contentTokens }}</span> content tokens ·
        <span class="tnum">{{ metric.groundedNodes }}</span> grounded /
        <span class="tnum">{{ metric.nodes }}</span> nodes
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { pct, type SenseMetric, type UngroundedReason } from '../../features/warrant/types';

const props = withDefaults(
  defineProps<{
    metric: SenseMetric;
    /** The winner's metric, to show per-axis deltas — i.e. exactly where this plan lost. */
    reference?: SenseMetric | null;
    compact?: boolean;
  }>(),
  { reference: null, compact: false },
);

const REASON_TEXT: Record<UngroundedReason, string> = {
  'no-token-span': 'no token span — nothing in the question evoked it',
  'unbound-required-input': 'a required input never bound',
};

/** One saturated colour per axis, off the epistemic ramp so the moat stays the one hue family. */
const axes = computed(() => {
  const m = props.metric;
  const r = props.reference;
  return [
    {
      key: 'coverage',
      label: 'coverage',
      value: m.coverage,
      weight: m.weights.coverage,
      color: 'var(--epi-observed, #5b95f9)',
      delta: r ? m.coverage - r.coverage : 0,
    },
    {
      key: 'groundedness',
      label: 'groundedness',
      value: m.groundedness,
      weight: m.weights.groundedness,
      color: 'var(--epi-verified, #2dd4bf)',
      delta: r ? m.groundedness - r.groundedness : 0,
    },
    {
      key: 'similarity',
      label: 'similarity',
      value: m.similarity,
      weight: m.weights.similarity,
      color: 'var(--epi-derived, #a082f8)',
      delta: r ? m.similarity - r.similarity : 0,
    },
  ];
});

function signed(d: number): string {
  if (Math.abs(d) < 0.0005) return '±0';
  return `${d > 0 ? '+' : '−'}${Math.abs(d).toFixed(3)}`;
}

function deltaClass(d: number): string {
  if (Math.abs(d) < 0.0005) return 'd-flat';
  return d > 0 ? 'd-up' : 'd-down';
}
</script>

<style scoped>
.sm {
  display: grid;
  gap: 0.45rem;
  font-size: 0.72rem;
  color: var(--ink-2, #b4c0cd);
}
.sm-axes {
  display: grid;
  gap: 0.4rem;
}
.sm-compact .sm-axes {
  gap: 0.25rem;
}
.sm-axis {
  display: grid;
  gap: 2px;
}
.sm-axis-top {
  display: flex;
  align-items: baseline;
  gap: 0.4rem;
  font-size: 0.66rem;
}
.sm-axis-name {
  color: var(--muted, #8a97a5);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-size: 0.6rem;
}
.sm-axis-val {
  margin-left: auto;
  color: var(--ax);
  font-weight: 700;
}
.sm-bar {
  position: relative;
  height: 5px;
  border-radius: 999px;
  background: var(--sunken, #080b10);
  border: 1px solid var(--hairline, #232c38);
  overflow: hidden;
}
.sm-compact .sm-bar {
  height: 4px;
}
.sm-bar-fill {
  position: absolute;
  inset: 0 auto 0 0;
  background: var(--ax);
  opacity: 0.85;
  border-radius: 999px;
}
/* Where the axis lands AFTER its weight — the honest picture of what it actually bought. */
.sm-bar-tick {
  position: absolute;
  top: -1px;
  bottom: -1px;
  width: 2px;
  background: var(--ink, #e8eef5);
  opacity: 0.75;
}
.sm-axis-foot {
  display: flex;
  gap: 0.5rem;
  font-size: 0.6rem;
  color: var(--faint, #5d6a78);
}
.sm-contrib {
  margin-left: auto;
}
.sm-composite {
  display: flex;
  align-items: baseline;
  gap: 0.4rem;
  border-top: 1px solid var(--hairline, #232c38);
  padding-top: 0.35rem;
}
.sm-comp-l {
  color: var(--muted, #8a97a5);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-size: 0.6rem;
}
.sm-comp-v {
  margin-left: auto;
  color: var(--ink, #e8eef5);
  font-weight: 700;
  font-size: 0.84rem;
}
.sm-delta {
  font-size: 0.62rem;
  font-weight: 600;
  padding: 0 4px;
  border-radius: var(--r-1, 3px);
}
.d-up {
  color: var(--ok, #3fb950);
  background: var(--ok-wash, #0f2417);
}
.d-down {
  color: var(--fail, #e5534b);
  background: var(--fail-wash, #2a1315);
}
.d-flat {
  color: var(--faint, #5d6a78);
}

.sm-creativity {
  display: grid;
  gap: 0.25rem;
  padding: 0.4rem 0.5rem;
  border-radius: var(--r-1, 3px);
  background: var(--epi-hypothesis-wash, #1a2029);
  border: 1px solid color-mix(in srgb, var(--epi-hypothesis, #8592a3) 30%, transparent);
}
.sm-creativity.sm-clean {
  background: var(--epi-verified-wash, #0e2c2b);
  border-color: color-mix(in srgb, var(--epi-verified, #2dd4bf) 30%, transparent);
}
.sm-cr-head {
  display: flex;
  align-items: baseline;
  gap: 0.4rem;
  font-size: 0.66rem;
}
.sm-cr-head b {
  color: var(--epi-hypothesis, #8592a3);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-size: 0.6rem;
}
.sm-clean .sm-cr-head b {
  color: var(--epi-verified, #2dd4bf);
}
.sm-cr-def {
  margin-left: auto;
  color: var(--faint, #5d6a78);
  font-family: var(--mono, ui-monospace, monospace);
  font-size: 0.6rem;
}
.sm-cr-body {
  color: var(--faint, #5d6a78);
  font-size: 0.64rem;
  line-height: 1.45;
}
.sm-adm {
  list-style: none;
  margin: 0.15rem 0 0;
  padding: 0;
  display: grid;
  gap: 2px;
}
.sm-adm-row {
  display: flex;
  align-items: baseline;
  gap: 0.4rem;
  font-size: 0.62rem;
  flex-wrap: wrap;
}
.sm-adm-row code {
  color: var(--epi-hypothesis, #8592a3);
  font-family: var(--mono, ui-monospace, monospace);
}
.sm-adm-action {
  color: var(--muted, #8a97a5);
  font-family: var(--mono, ui-monospace, monospace);
}
.sm-adm-reason {
  color: var(--faint, #5d6a78);
}
.sm-adm-w {
  margin-left: auto;
  color: var(--warn, #d29922);
  font-weight: 700;
}
.sm-cov {
  color: var(--faint, #5d6a78);
  font-size: 0.62rem;
}
.mono {
  font-family: var(--mono, ui-monospace, monospace);
}
.tnum {
  font-variant-numeric: tabular-nums;
}
</style>
