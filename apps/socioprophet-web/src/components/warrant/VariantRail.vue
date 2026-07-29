<template>
  <!-- W11.2 — the alternatives that LOST.
       The compiler keeps every variant that type-checked, ranked by composite. Showing only
       the winner hides the fact that a choice was made at all. This rail shows the whole
       ranked field, each with its three axes, each with the one axis that actually cost it
       the win — and lets the user re-run on any of them. -->
  <div class="vr">
    <div class="vr-head">
      <span class="vr-title">Ranked variants</span>
      <span class="vr-count tnum">{{ variants.length }}</span>
      <span class="vr-sub">ranked by composite · {{ weightsLabel }}</span>
    </div>

    <p v-if="!variants.length" class="vr-empty">
      Nothing type-checked. The compiler returned no admissible variant for this question.
    </p>

    <ul v-else class="vr-list">
      <li
        v-for="v in variants"
        :key="v.rank"
        class="vr-item"
        :class="{ 'vr-on': v.rank === selectedRank, 'vr-winner': v.rank === 1 }"
      >
        <button
          class="vr-pick"
          type="button"
          :aria-pressed="v.rank === selectedRank"
          :aria-label="`Variant ${v.rank}, composite ${v.senseMetric.composite.toFixed(3)}`"
          @click="emit('select', v.rank)"
        >
          <span class="vr-rank tnum">#{{ v.rank }}</span>
          <span class="vr-plan">
            <span class="vr-plan-name">{{ v.plan.actionName }}</span>
            <span class="vr-plan-meta tnum">
              {{ v.senseMetric.nodes }} node{{ v.senseMetric.nodes === 1 ? '' : 's' }}
              <template v-if="v.senseMetric.ungroundedNodes">
                · <span class="vr-ung">{{ v.senseMetric.ungroundedNodes }} invented</span>
              </template>
            </span>
          </span>
          <span class="vr-comp tnum">{{ v.senseMetric.composite.toFixed(3) }}</span>
          <span v-if="v.rank === 1" class="vr-crown" title="Winning variant">won</span>
        </button>

        <SenseMetricBadge :metric="v.senseMetric" :reference="v.rank === 1 ? null : winnerMetric" compact />

        <!-- The whole point of the rail: not that it lost, but WHERE. -->
        <p v-if="v.rank !== 1 && lossOf(v)" class="vr-why">
          lost on <b>{{ lossOf(v)!.axis }}</b>
          <span class="tnum">
            ({{ lossOf(v)!.delta.toFixed(3) }} × w{{ lossOf(v)!.weight.toFixed(2) }} =
            {{ lossOf(v)!.cost.toFixed(3) }} of the gap)
          </span>
        </p>

        <div class="vr-actions">
          <button class="vr-rerun" type="button" @click="emit('rerun', v)">
            Re-run on #{{ v.rank }}
          </button>
        </div>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import SenseMetricBadge from './SenseMetricBadge.vue';
import type { PlanVariant, SenseMetric } from '../../features/warrant/types';

const props = withDefaults(
  defineProps<{
    variants: PlanVariant[];
    /** Rank of the variant currently shown in the plan tree. */
    selectedRank?: number;
  }>(),
  { selectedRank: 1 },
);

const emit = defineEmits<{
  (e: 'select', rank: number): void;
  (e: 'rerun', variant: PlanVariant): void;
}>();

const winnerMetric = computed<SenseMetric | null>(
  () => props.variants.find((v) => v.rank === 1)?.senseMetric ?? null,
);

const weightsLabel = computed(() => {
  const w = props.variants[0]?.senseMetric.weights;
  if (!w) return '';
  return `cov ${w.coverage} · grd ${w.groundedness} · sim ${w.similarity}`;
});

/**
 * The axis that cost this variant the most, in COMPOSITE POINTS — deficit × weight. A big
 * raw gap on a 0.2-weighted axis matters less than a small gap on a 0.5-weighted one, and
 * saying "lost on coverage" when similarity did the damage would be a nicer-sounding lie.
 */
function lossOf(v: PlanVariant): { axis: string; delta: number; weight: number; cost: number } | null {
  const w = winnerMetric.value;
  if (!w || v.rank === 1) return null;
  const m = v.senseMetric;
  const rows = [
    { axis: 'coverage', delta: m.coverage - w.coverage, weight: m.weights.coverage },
    { axis: 'groundedness', delta: m.groundedness - w.groundedness, weight: m.weights.groundedness },
    { axis: 'similarity', delta: m.similarity - w.similarity, weight: m.weights.similarity },
  ].map((r) => ({ ...r, cost: r.delta * r.weight }));
  const worst = rows.reduce((a, b) => (b.cost < a.cost ? b : a));
  return worst.cost < 0 ? worst : null;
}
</script>

<style scoped>
.vr {
  display: grid;
  gap: 0.5rem;
}
.vr-head {
  display: flex;
  align-items: baseline;
  gap: 0.4rem;
  flex-wrap: wrap;
}
.vr-title {
  color: var(--ink-2, #b4c0cd);
  font-size: 0.66rem;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  font-weight: 600;
}
.vr-count {
  color: var(--accent, #5b95f9);
  background: var(--accent-wash, #16233b);
  border-radius: var(--pill, 999px);
  padding: 0 6px;
  font-size: 0.62rem;
  font-weight: 700;
}
.vr-sub {
  margin-left: auto;
  color: var(--faint, #5d6a78);
  font-size: 0.6rem;
  font-family: var(--mono, ui-monospace, monospace);
}
.vr-empty {
  color: var(--muted, #8a97a5);
  font-size: 0.72rem;
  margin: 0;
  padding: 0.6rem;
  background: var(--sunken, #080b10);
  border: 1px dashed var(--hairline-strong, #33404f);
  border-radius: var(--r-2, 5px);
}
.vr-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.4rem;
}
.vr-item {
  display: grid;
  gap: 0.35rem;
  padding: 0.5rem 0.55rem;
  border-radius: var(--r-2, 5px);
  background: var(--surface, #141b24);
  border: 1px solid var(--hairline, #232c38);
  border-left: 3px solid var(--idle, #6b7684);
}
.vr-item.vr-winner {
  border-left-color: var(--epi-verified, #2dd4bf);
}
.vr-item.vr-on {
  border-color: var(--accent, #5b95f9);
  background: var(--accent-wash, #16233b);
}
.vr-pick {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  background: none;
  border: 0;
  padding: 0;
  cursor: pointer;
  text-align: left;
  color: inherit;
  font-family: inherit;
}
.vr-pick:focus-visible {
  outline: 2px solid var(--accent, #5b95f9);
  outline-offset: 2px;
}
.vr-rank {
  color: var(--faint, #5d6a78);
  font-size: 0.66rem;
  font-weight: 700;
  flex: 0 0 auto;
}
.vr-plan {
  display: grid;
  gap: 1px;
  min-width: 0;
}
.vr-plan-name {
  color: var(--ink, #e8eef5);
  font-size: 0.76rem;
  font-weight: 600;
}
.vr-plan-meta {
  color: var(--faint, #5d6a78);
  font-size: 0.62rem;
}
.vr-ung {
  color: var(--epi-hypothesis, #8592a3);
}
.vr-comp {
  margin-left: auto;
  color: var(--ink, #e8eef5);
  font-size: 0.86rem;
  font-weight: 700;
  flex: 0 0 auto;
}
.vr-crown {
  color: var(--epi-verified, #2dd4bf);
  background: var(--epi-verified-wash, #0e2c2b);
  border-radius: var(--pill, 999px);
  padding: 0 6px;
  font-size: 0.58rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  flex: 0 0 auto;
}
.vr-why {
  margin: 0;
  color: var(--warn, #d29922);
  font-size: 0.64rem;
}
.vr-why b {
  font-weight: 700;
}
.vr-why .tnum {
  color: var(--faint, #5d6a78);
}
.vr-actions {
  display: flex;
  justify-content: flex-end;
}
.vr-rerun {
  background: transparent;
  color: var(--ink-2, #b4c0cd);
  border: 1px solid var(--hairline-strong, #33404f);
  border-radius: var(--r-1, 3px);
  padding: 2px 8px;
  font-size: 0.64rem;
  cursor: pointer;
  font-family: inherit;
}
.vr-rerun:hover {
  border-color: var(--accent, #5b95f9);
  color: var(--accent-ink, #bcd4ff);
  background: var(--accent-wash, #16233b);
}
.vr-rerun:focus-visible {
  outline: 2px solid var(--accent, #5b95f9);
  outline-offset: 1px;
}
.tnum {
  font-variant-numeric: tabular-nums;
}
</style>
