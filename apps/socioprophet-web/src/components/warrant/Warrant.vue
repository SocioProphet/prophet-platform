<template>
  <!-- W11.0 — the proof chain at three depths, in one primitive.
       1. BADGE      always on: sealed / UNSEALED / unknown, on the epistemic ramp.
       2. POPOVER    hover or keyboard focus: the claim, its warrant type, and the source
                     span it points back at (or "model-generated" when it invented).
       3. RECEIPT    click: the full three-step verify walk the gateway returns —
                     gateway signature → engine seal hash → snapshot.seq binding.

       Honest degradation is the contract, not a nicety: an unsealed receipt renders in
       --fail with the reason spelled out, and the epistemic ramp colour degrades with it.
       This component must never make an unproven claim look fine. -->
  <span class="wr" :class="[`wr-${view.seal}`, { 'wr-open': open }]" :style="{ '--epi': epiColor }">
    <button
      class="wr-badge"
      type="button"
      :aria-label="`Warrant: ${view.kindLabel}, ${view.sealLabel}`"
      :aria-expanded="open"
      @click="toggle"
    >
      <span class="epi-dot wr-dot" aria-hidden="true" />
      <span v-if="!compact" class="wr-seal">{{ view.sealLabel }}</span>
      <span v-if="!compact" class="wr-kind">{{ view.kindLabel }}</span>
    </button>

    <!-- depth 2 — the popover -->
    <span class="wr-pop" role="tooltip">
      <span class="wr-pop-head">
        <span class="epi-dot wr-dot" aria-hidden="true" />
        <b>{{ view.sealLabel }}</b>
        <span class="wr-pop-kind">{{ view.kindLabel }}</span>
      </span>
      <span class="wr-pop-claim">{{ view.claim }}</span>
      <span class="wr-pop-blurb">{{ view.kindBlurb }}</span>

      <span v-if="view.span" class="wr-row">
        <b>Source span</b>
        <span class="wr-span"
          >“<mark>{{ view.span.text }}</mark
          >” <span class="wr-off tnum">[{{ view.span.start }},{{ view.span.end }})</span></span
        >
      </span>
      <span v-else class="wr-row">
        <b>Source span</b>
        <span class="wr-nospan">none — model-generated</span>
      </span>

      <span v-if="view.admissibility" class="wr-row">
        <b>Admissibility</b>
        <span>
          {{ view.admissibility.admitted ? 'admitted' : 'excluded' }}
          <span class="tnum">· weight {{ view.admissibility.weight.toFixed(2) }}</span>
          <span v-if="view.admissibility.excludedAt"> · at {{ view.admissibility.excludedAt }}</span>
        </span>
      </span>

      <span v-if="view.receiptRef" class="wr-row">
        <b>Receipt</b><code class="wr-hash">{{ view.receiptRef }}</code>
      </span>

      <!-- The reason, whenever there is one. This is the honest-degradation surface. -->
      <span v-if="view.sealDetail" class="wr-why">{{ view.sealDetail }}</span>

      <span class="wr-hint">{{ open ? 'Click to collapse the receipt walk' : 'Click for the full receipt walk' }}</span>
    </span>

    <!-- depth 3 — the full receipt walk -->
    <span v-if="open" class="wr-walk">
      <span class="wr-walk-head">
        <b>Receipt walk</b>
        <span v-if="view.receiptRef" class="wr-hash mono">{{ view.receiptRef }}</span>
        <span class="wr-walk-verdict" :class="view.walk?.valid ? 'v-ok' : 'v-bad'">
          {{ view.walk ? (view.walk.valid ? 'valid' : 'INVALID') : 'not walked' }}
        </span>
      </span>

      <ol v-if="view.walk" class="wr-steps">
        <li v-for="s in view.walk.steps" :key="s.step" class="wr-step" :class="`s-${s.status}`">
          <span class="wr-step-top">
            <span class="wr-step-mark" aria-hidden="true">{{ STEP_GLYPH[s.status] }}</span>
            <span class="wr-step-name mono">{{ s.step }}</span>
            <span class="wr-step-status">{{ s.status }}</span>
          </span>
          <span class="wr-step-means">{{ meaning(s.step) }}</span>
          <span v-if="s.detail" class="wr-step-detail mono">{{ s.detail }}</span>
        </li>
      </ol>

      <!-- No walk: say so plainly. An unwalked receipt is NOT a verified one. -->
      <span v-else class="wr-nowalk">
        <template v-if="view.seal === 'unsealed'">
          Nothing to walk — this claim was never sealed.
          <span v-if="view.sealDetail" class="wr-why-inline">{{ view.sealDetail }}</span>
        </template>
        <template v-else-if="view.receiptRef">
          Receipt not yet verified. The three-step walk runs against
          <code>GET /v1/engine-receipts/{{ view.receiptRef }}/verify</code>.
        </template>
        <template v-else>
          No receipt reference on this claim — its proof chain cannot be walked.
        </template>
      </span>
    </span>
  </span>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { WALK_STEP_MEANING, warrantView, type WarrantInput } from '../../features/warrant/types';

const props = withDefaults(defineProps<{ w: WarrantInput; compact?: boolean; defaultOpen?: boolean }>(), {
  compact: false,
  defaultOpen: false,
});

const emit = defineEmits<{ (e: 'walk', receiptRef: string): void }>();

const open = ref(props.defaultOpen);
const view = computed(() => warrantView(props.w));

/** Ramp colour, with literal fallbacks so the badge still reads outside `.studio-scope`. */
const EPI_FALLBACK: Record<string, string> = {
  observed: '#5b95f9',
  derived: '#a082f8',
  hypothesis: '#8592a3',
  attested: '#34d399',
  unknown: '#4a5568',
};
const epiColor = computed(() => {
  // An unsealed warrant is never allowed a reassuring colour.
  if (view.value.seal === 'unsealed') return 'var(--fail, #e5534b)';
  const m = view.value.epistemic;
  return `var(--epi-${m}, ${EPI_FALLBACK[m]})`;
});

const STEP_GLYPH: Record<string, string> = { ok: '✓', fail: '✕', skipped: '·' };

function meaning(step: string): string {
  return WALK_STEP_MEANING[step] ?? 'Step reported by the gateway verify walk.';
}

function toggle() {
  open.value = !open.value;
  if (open.value && !view.value.walk && view.value.receiptRef) emit('walk', view.value.receiptRef);
}
</script>

<style scoped>
.wr {
  position: relative;
  display: inline-flex;
  flex-direction: column;
  vertical-align: middle;
  align-items: flex-start;
}
.wr-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  cursor: pointer;
  border: 1px solid color-mix(in srgb, var(--epi) 42%, transparent);
  border-radius: var(--r-1, 3px);
  background: color-mix(in srgb, var(--epi) 12%, transparent);
  color: var(--epi);
  padding: 1px 7px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.01em;
  line-height: 1.5;
  font-family: inherit;
}
.wr-badge:hover {
  background: color-mix(in srgb, var(--epi) 20%, transparent);
}
.wr-badge:focus-visible {
  outline: 2px solid var(--accent, #5b95f9);
  outline-offset: 1px;
}
.wr-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: var(--epi);
  flex: 0 0 auto;
}
.wr-seal {
  text-transform: uppercase;
  letter-spacing: 0.04em;
  font-size: 10px;
}
.wr-kind {
  color: var(--muted, #8a97a5);
  font-weight: 500;
}
/* UNSEALED is shouted, deliberately: it is the state most likely to be skimmed past. */
.wr-unsealed .wr-seal {
  font-weight: 800;
}

/* ── depth 2: popover ─────────────────────────────────────────────────────── */
.wr-pop {
  position: absolute;
  z-index: 60;
  bottom: calc(100% + 6px);
  left: 0;
  display: grid;
  gap: 0.3rem;
  width: max-content;
  max-width: 26rem;
  padding: 0.6rem 0.7rem;
  border-radius: var(--r-3, 8px);
  background: var(--surface, #141b24);
  border: 1px solid var(--hairline-strong, #33404f);
  box-shadow: var(--e-3, 0 12px 40px rgba(0, 0, 0, 0.6));
  opacity: 0;
  visibility: hidden;
  transform: translateY(4px);
  transition: opacity 0.12s ease, transform 0.12s ease;
  color: var(--ink-2, #b4c0cd);
  font-size: 0.72rem;
  font-weight: 400;
  text-align: left;
  white-space: normal;
}
.wr-badge:hover + .wr-pop,
.wr-badge:focus-visible + .wr-pop {
  opacity: 1;
  visibility: visible;
  transform: translateY(0);
}
.wr-pop-head {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  color: var(--epi);
  text-transform: uppercase;
  font-size: 0.66rem;
  letter-spacing: 0.05em;
}
.wr-pop-kind {
  color: var(--muted, #8a97a5);
  text-transform: none;
  letter-spacing: 0;
  font-weight: 500;
}
.wr-pop-claim {
  color: var(--ink, #e8eef5);
  font-size: 0.76rem;
  line-height: 1.4;
}
.wr-pop-blurb {
  color: var(--faint, #5d6a78);
  font-size: 0.68rem;
  line-height: 1.4;
}
.wr-row {
  display: grid;
  grid-template-columns: 5.2rem 1fr;
  gap: 0.5rem;
  align-items: baseline;
}
.wr-row b {
  color: var(--faint, #5d6a78);
  font-weight: 600;
  font-size: 0.64rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.wr-span mark {
  background: color-mix(in srgb, var(--epi) 26%, transparent);
  color: var(--ink, #e8eef5);
  border-radius: 2px;
  padding: 0 2px;
}
.wr-off {
  color: var(--faint, #5d6a78);
  font-size: 0.64rem;
}
.wr-nospan {
  color: var(--epi-hypothesis, #8592a3);
  font-style: italic;
}
.wr-hash {
  font-family: var(--mono, ui-monospace, monospace);
  font-size: 0.64rem;
  color: var(--ink-2, #b4c0cd);
  overflow-wrap: anywhere;
}
.wr-why {
  color: var(--fail, #e5534b);
  background: var(--fail-wash, #2a1315);
  border: 1px solid color-mix(in srgb, var(--fail, #e5534b) 34%, transparent);
  border-radius: var(--r-1, 3px);
  padding: 0.3rem 0.4rem;
  font-size: 0.68rem;
  font-family: var(--mono, ui-monospace, monospace);
  overflow-wrap: anywhere;
}
.wr-hint {
  color: var(--faint, #5d6a78);
  font-size: 0.62rem;
  border-top: 1px solid var(--hairline, #232c38);
  padding-top: 0.3rem;
}

/* ── depth 3: the receipt walk ────────────────────────────────────────────── */
.wr-walk {
  display: block;
  margin-top: 6px;
  width: 100%;
  min-width: 20rem;
  max-width: 46rem;
  background: var(--sunken, #080b10);
  border: 1px solid var(--hairline, #232c38);
  border-radius: var(--r-2, 5px);
  padding: 0.5rem 0.6rem;
}
.wr-walk-head {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  font-size: 0.68rem;
  color: var(--muted, #8a97a5);
  margin-bottom: 0.4rem;
}
.wr-walk-head b {
  color: var(--ink-2, #b4c0cd);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-size: 0.62rem;
}
.wr-walk-verdict {
  margin-left: auto;
  font-weight: 700;
  font-size: 0.62rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 1px 6px;
  border-radius: var(--pill, 999px);
}
.v-ok {
  color: var(--ok, #3fb950);
  background: var(--ok-wash, #0f2417);
}
.v-bad {
  color: var(--fail, #e5534b);
  background: var(--fail-wash, #2a1315);
}
.wr-steps {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.35rem;
}
.wr-step {
  display: grid;
  gap: 2px;
  padding: 0.35rem 0.45rem;
  border-radius: var(--r-1, 3px);
  border-left: 3px solid var(--idle, #6b7684);
  background: var(--surface, #141b24);
}
.wr-step.s-ok {
  border-left-color: var(--ok, #3fb950);
}
.wr-step.s-fail {
  border-left-color: var(--fail, #e5534b);
  background: var(--fail-wash, #2a1315);
}
.wr-step.s-skipped {
  opacity: 0.6;
}
.wr-step-top {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.7rem;
}
.wr-step-mark {
  width: 0.9rem;
  text-align: center;
  font-weight: 700;
}
.s-ok .wr-step-mark {
  color: var(--ok, #3fb950);
}
.s-fail .wr-step-mark {
  color: var(--fail, #e5534b);
}
.s-skipped .wr-step-mark {
  color: var(--idle, #6b7684);
}
.wr-step-name {
  color: var(--ink, #e8eef5);
  font-family: var(--mono, ui-monospace, monospace);
  font-size: 0.68rem;
}
.wr-step-status {
  margin-left: auto;
  font-size: 0.6rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--muted, #8a97a5);
}
.s-fail .wr-step-status {
  color: var(--fail, #e5534b);
  font-weight: 700;
}
.wr-step-means {
  color: var(--faint, #5d6a78);
  font-size: 0.64rem;
  line-height: 1.4;
}
.wr-step-detail {
  color: var(--ink-2, #b4c0cd);
  font-family: var(--mono, ui-monospace, monospace);
  font-size: 0.62rem;
  overflow-wrap: anywhere;
  line-height: 1.4;
}
.s-fail .wr-step-detail {
  color: var(--fail, #e5534b);
}
.wr-nowalk {
  display: block;
  color: var(--muted, #8a97a5);
  font-size: 0.68rem;
  line-height: 1.5;
}
.wr-nowalk code {
  font-family: var(--mono, ui-monospace, monospace);
  font-size: 0.62rem;
  color: var(--ink-2, #b4c0cd);
  overflow-wrap: anywhere;
}
.wr-why-inline {
  display: block;
  margin-top: 0.25rem;
  color: var(--fail, #e5534b);
  font-family: var(--mono, ui-monospace, monospace);
  font-size: 0.64rem;
  overflow-wrap: anywhere;
}
</style>
