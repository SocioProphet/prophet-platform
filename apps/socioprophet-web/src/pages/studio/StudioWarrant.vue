<script setup lang="ts">
// W11 — Warrant: the proof, made visible.
//
// The estate's moat is proof-carrying reasoning, and until now none of it reached a pixel:
// the cockpit showed answers with the reasoning invisible. This surface renders the four
// W11 primitives over one compilation — the plan that ran, the plans that lost, why they
// lost, and whether any of it is sealed.
//
// Composed from the Studio design language only (.studio-scope tokens, .card/.btn/.pill,
// the epistemic ramp). No new design system, no Carbon global import.
import { computed, onMounted, ref } from 'vue';
import PlanTree from '../../components/warrant/PlanTree.vue';
import VariantRail from '../../components/warrant/VariantRail.vue';
import SenseMetricBadge from '../../components/warrant/SenseMetricBadge.vue';
import Warrant from '../../components/warrant/Warrant.vue';
import { compileQuestion, verifyReceipt, type WarrantLoadMode } from '../../services/warrantApi';
import {
  FIXTURE_QUESTION,
  FIXTURE_RECEIPT_ID,
  FIXTURE_SEAL_DEGRADED,
  FIXTURE_SEAL_OK,
  FIXTURE_WALK_TAMPERED,
  FIXTURE_WALK_VALID,
} from '../../data/warrantFixture';
import type {
  NlqCompilation,
  PlanVariant,
  ReceiptVerifyWalk,
  SealOutcome,
} from '../../features/warrant/types';

const question = ref(FIXTURE_QUESTION);
const compilation = ref<NlqCompilation | null>(null);
const mode = ref<WarrantLoadMode>('fixture');
const compileNote = ref<string | null>(null);
const selectedRank = ref(1);
const busy = ref(false);

/**
 * Fixture proof-states. The three ways a warrant can read, side by side, because the
 * honest-degradation contract is the single most important thing this surface asserts and
 * "trust me, it degrades" is not a demonstration. Labelled as fixture, because it is.
 */
type ProofState = 'sealed' | 'tampered' | 'degraded';
const proofState = ref<ProofState>('sealed');
const liveWalk = ref<ReceiptVerifyWalk | null>(null);
const walkError = ref<string | null>(null);

const seal = computed<SealOutcome>(() =>
  proofState.value === 'degraded' ? FIXTURE_SEAL_DEGRADED : FIXTURE_SEAL_OK,
);
const walk = computed<ReceiptVerifyWalk | null>(() => {
  if (liveWalk.value) return liveWalk.value;
  if (proofState.value === 'sealed') return FIXTURE_WALK_VALID;
  if (proofState.value === 'tampered') return FIXTURE_WALK_TAMPERED;
  return null; // degraded — never sealed, so there is nothing to walk
});

const selected = computed<PlanVariant | null>(
  () => compilation.value?.variants.find((v) => v.rank === selectedRank.value) ?? null,
);

const winnerMetric = computed(
  () => compilation.value?.variants.find((v) => v.rank === 1)?.senseMetric ?? null,
);

/** The compilation-level warrant: the whole run's claim, and whether it is sealed. */
const runWarrant = computed(() => ({
  claim: compilation.value
    ? `Compiled “${compilation.value.question}” into ${compilation.value.variants.length} typed plan variant(s) against snapshot seq ${compilation.value.snapshot.seq}`
    : 'No compilation',
  seal: seal.value,
  walk: walk.value ?? undefined,
  receiptRef: FIXTURE_RECEIPT_ID,
}));

async function run() {
  busy.value = true;
  try {
    const r = await compileQuestion(question.value);
    compilation.value = r.data;
    mode.value = r.mode;
    compileNote.value = r.error ?? null;
    selectedRank.value = r.data?.winner?.rank ?? 1;
  } finally {
    busy.value = false;
  }
}

/** Ask the gateway to walk the receipt for real. Reports unavailability as unavailability. */
async function walkReceipt(receiptRef: string) {
  walkError.value = null;
  const r = await verifyReceipt(receiptRef);
  if (r.data) liveWalk.value = r.data;
  else walkError.value = r.error ?? 'verify walk unavailable';
}

function rerun(v: PlanVariant) {
  selectedRank.value = v.rank;
}

onMounted(run);
</script>

<template>
  <div class="wsurf">
    <!-- Provenance of the surface itself. If the plan is a fixture, the surface says so
         first, above everything it renders. -->
    <div class="wsurf-mode" :class="`m-${mode}`">
      <span class="wsurf-mode-tag">{{ mode }}</span>
      <span v-if="mode === 'fixture'">
        The NLQ typed-plan compiler ships in the hellgraph engine (<code class="mono">ts/src/nlq.ts</code>,
        v0.4.44+). No service in this repo exposes it over HTTP yet, so this plan comes from a
        fixture built to the compiler's real types. The receipt walk below calls the gateway's
        real endpoint.
      </span>
      <span v-else>Compiled live.</span>
    </div>

    <div class="card">
      <h3>Question</h3>
      <p class="desc">
        The compiler tokenizes, annotates, and searches typed action plans — then ranks them.
        Everything below is that search, made inspectable.
      </p>
      <div class="row">
        <input v-model="question" type="text" aria-label="Question" @keydown.enter="run" />
        <button class="btn" type="button" :disabled="busy" @click="run">
          {{ busy ? 'Compiling…' : 'Compile' }}
        </button>
      </div>
      <p v-if="compileNote" class="wsurf-note">{{ compileNote }}</p>
    </div>

    <div v-if="compilation" class="card">
      <div class="wsurf-runhead">
        <div>
          <h3>Run warrant</h3>
          <p class="desc">
            method <code class="mono">{{ compilation.method }}</code> · contract
            <code class="mono">{{ compilation.contract.schema }}</code> v{{ compilation.contract.specVersion }} ·
            snapshot seq <span class="tnum">{{ compilation.snapshot.seq }}</span>
          </p>
        </div>
        <Warrant :w="runWarrant" @walk="walkReceipt" />
      </div>

      <!-- The fixture proof-state switch. -->
      <div class="wsurf-states">
        <span class="wsurf-states-l">fixture proof state</span>
        <button
          v-for="s in (['sealed', 'tampered', 'degraded'] as ProofState[])"
          :key="s"
          class="wsurf-state"
          type="button"
          :class="{ on: proofState === s }"
          :aria-pressed="proofState === s"
          @click="proofState = s; liveWalk = null"
        >
          {{ s }}
        </button>
        <span class="wsurf-states-hint">
          {{
            proofState === 'sealed'
              ? 'all three walk steps ok'
              : proofState === 'tampered'
                ? 'engine-seal-hash fails; the binding step is skipped, not guessed'
                : 'sealed:false + sealError — the service answered, the gateway never sealed it'
          }}
        </span>
      </div>
      <p v-if="walkError" class="err">{{ walkError }}</p>
    </div>

    <div v-if="compilation && selected" class="grid cols-2 wsurf-body">
      <div class="card">
        <h3>Plan · variant #{{ selected.rank }}</h3>
        <p class="desc">The typed action tree that {{ selected.rank === 1 ? 'won' : 'was selected' }}.</p>
        <PlanTree
          :plan="selected.plan"
          :provenance="selected.provenance"
          :question="compilation.question"
          :seal="seal"
          :walk="walk"
        />
      </div>

      <div class="wsurf-right">
        <div class="card">
          <h3>Score · variant #{{ selected.rank }}</h3>
          <p class="desc">Three axes, weighted. Creativity is the ungrounded-node penalty.</p>
          <SenseMetricBadge
            :metric="selected.senseMetric"
            :reference="selected.rank === 1 ? null : winnerMetric"
          />
        </div>

        <div class="card">
          <VariantRail
            :variants="compilation.variants"
            :selected-rank="selectedRank"
            @select="selectedRank = $event"
            @rerun="rerun"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.wsurf {
  display: grid;
  gap: 1rem;
}
.wsurf-mode {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  flex-wrap: wrap;
  padding: 0.5rem 0.7rem;
  border-radius: var(--r-2);
  font-size: 0.72rem;
  line-height: 1.5;
  color: var(--ink-2);
  background: var(--warn-wash);
  border: 1px solid color-mix(in srgb, var(--warn) 34%, transparent);
}
.wsurf-mode.m-live {
  background: var(--ok-wash);
  border-color: color-mix(in srgb, var(--ok) 34%, transparent);
}
.wsurf-mode-tag {
  color: var(--warn);
  text-transform: uppercase;
  letter-spacing: 0.07em;
  font-size: 0.62rem;
  font-weight: 700;
  flex: 0 0 auto;
}
.m-live .wsurf-mode-tag {
  color: var(--ok);
}
.wsurf-mode code {
  font-family: var(--mono);
  font-size: 0.66rem;
}
.wsurf-note {
  margin: 0.6rem 0 0;
  padding: 0.4rem 0.55rem;
  border-radius: var(--r-1);
  background: var(--warn-wash);
  border: 1px solid color-mix(in srgb, var(--warn) 34%, transparent);
  color: var(--warn);
  font-size: 0.68rem;
  line-height: 1.5;
}
.wsurf-runhead {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  justify-content: space-between;
  flex-wrap: wrap;
}
.wsurf-runhead h3 {
  margin: 0 0 0.3rem;
}
.wsurf-states {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
  margin-top: 0.8rem;
  padding-top: 0.6rem;
  border-top: 1px solid var(--hairline);
}
.wsurf-states-l {
  color: var(--faint);
  font-size: 0.6rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.wsurf-state {
  background: transparent;
  color: var(--muted);
  border: 1px solid var(--border-2);
  border-radius: var(--r-1);
  padding: 1px 8px;
  font-size: 0.66rem;
  cursor: pointer;
  font-family: inherit;
}
.wsurf-state.on {
  color: var(--accent-ink);
  border-color: var(--accent);
  background: var(--accent-wash);
}
.wsurf-state:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}
.wsurf-states-hint {
  color: var(--faint);
  font-size: 0.64rem;
  margin-left: auto;
}
.wsurf-body {
  align-items: start;
}
.wsurf-right {
  display: grid;
  gap: 1rem;
  align-content: start;
}
.wsurf-right .card + .card {
  margin-top: 0;
}
.mono {
  font-family: var(--mono);
}
.tnum {
  font-variant-numeric: tabular-nums;
}
</style>
