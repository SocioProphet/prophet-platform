<script setup lang="ts">
// W11.5 — one KnowledgeNugget, with its warrant on the front.
//
// The schema's normative rule is that model-generated content stays VISIBLY distinguishable on
// every downstream surface. So the difference is carried three ways at once, not buried in a
// tooltip: the epistemic stripe down the left edge, the <Warrant> badge, and — for
// model-generated only — a standing banner. Any one of them could be missed; all three cannot.
//
// Depth (W11.6) folds away evidence lists, provenance chains, URNs, hashes and payloads.
// It never folds away the warrant badge, the stripe, the model-generated banner, or the
// unsealed/unknown seal state. Those render at every level, by construction — there is no
// depth flag capable of hiding them.
import { computed } from 'vue';
import Warrant from '../warrant/Warrant.vue';
import {
  nuggetWarrantInput,
  refLabel,
  type KnowledgeNugget,
} from '../../features/nuggets/types';
import { clampText, depthPolicy, warrantGloss, type Expertise } from '../../features/depth/expertise';
import { isModelGenerated, pct } from '../../features/warrant/types';

const props = defineProps<{ nugget: KnowledgeNugget; level: Expertise }>();

const policy = computed(() => depthPolicy(props.level));
const kind = computed(() => props.nugget.warrant.type);
const modelGenerated = computed(() => isModelGenerated(kind.value));
const gloss = computed(() => warrantGloss(kind.value, props.level));
const w = computed(() => nuggetWarrantInput(props.nugget));
const body = computed(() => clampText(props.nugget.text, policy.value));
const span = computed(() => props.nugget.sourceRef.span);

/**
 * The stripe hue, by WARRANT KIND — a different axis from seal state.
 *
 * Deliberately mixed down to 62% rather than using the raw `--epi-*` token. A nugget's seal is
 * always `unknown` (no receipt exists for it), so `warrantView().epistemic` is `unknown` and
 * the <Warrant> badge beside this stripe renders desaturated. A full-strength `--epi-observed`
 * stripe next to an `unknown` badge would be a surface arguing with itself, and would re-open
 * the "colour outranks proof" hole that #1052 closed on the plan surfaces.
 *
 * So: hue still separates a quote from a model guess at a glance (which W11.5 requires), but
 * the intensity never claims proof the nugget does not carry.
 */
const KIND_HUE: Record<string, string> = {
  'direct-quote': 'var(--epi-observed)',
  computed: 'var(--epi-derived)',
  inferred: 'var(--epi-derived)',
  'model-generated': 'var(--epi-hypothesis)',
};
const stripe = computed(
  () => `color-mix(in srgb, ${KIND_HUE[kind.value] ?? 'var(--epi-unknown)'} 62%, var(--panel))`,
);

const payload = computed(() => {
  const p = props.nugget.canonicalPayload;
  return p && typeof p === 'object' ? (p as Record<string, unknown>) : null;
});
</script>

<template>
  <article class="ng" :class="{ 'ng-model': modelGenerated }" :style="{ '--epi': stripe }">
    <!-- Warrant row. Always first, always present, at every depth. -->
    <header class="ng-head">
      <Warrant :w="w" />
      <span class="ng-kind">{{ kind }}</span>
      <span v-if="policy.showConfidence" class="ng-conf tnum" :title="'Producer-stated confidence'">
        {{ pct(nugget.warrant.confidence) }}
      </span>
      <time class="ng-time" :datetime="nugget.wallTime">{{ nugget.wallTime.slice(0, 16).replace('T', ' ') }}</time>
    </header>

    <!--
      The banner is unconditional for model-generated. Not depth-gated, not collapsible:
      the schema says "MUST remain visibly distinguishable on every downstream surface".
    -->
    <p v-if="modelGenerated" class="ng-banner">
      <b>Model-generated.</b> Not warranted by the source. The span below is the window the model
      was conditioned on — it is not evidence for this statement.
    </p>

    <p class="ng-text" :class="{ quote: kind === 'direct-quote' }">{{ body.text }}</p>
    <p v-if="body.truncated" class="ng-trunc">
      Shortened for {{ policy.label.toLowerCase() }} depth — the full text is unchanged, raise depth to read it.
    </p>

    <!-- Plain-language reading of the warrant, at this depth. Never stronger than the warrant. -->
    <p class="ng-gloss">{{ gloss.text }}</p>

    <dl class="ng-meta">
      <div class="ng-row">
        <dt>Source</dt>
        <dd>
          <span v-if="policy.showRawRefs" class="mono">{{ nugget.sourceRef.docRef }}</span>
          <span v-else>{{ refLabel(nugget.sourceRef.docRef) }}</span>
          <span v-if="policy.showSpanOffsets" class="ng-span tnum">
            {{ modelGenerated ? 'conditioning window' : 'span' }} [{{ span.start }},{{ span.end }})
            <template v-if="span.page">· p{{ span.page }}</template>
          </span>
        </dd>
      </div>

      <div v-if="policy.showRawRefs" class="ng-row">
        <dt>Content hash</dt>
        <dd><code class="mono ng-hash">{{ nugget.sourceRef.contentHash }}</code></dd>
      </div>

      <!-- Evidence. For computed/inferred the schema guarantees >= 1; for model-generated the
           absence is itself the point, so it is stated rather than left blank. -->
      <div v-if="policy.showEvidenceList" class="ng-row">
        <dt>Evidence</dt>
        <dd>
          <template v-if="nugget.warrant.evidence.length">
            <span v-for="e in nugget.warrant.evidence" :key="e" class="ng-chip mono">
              {{ policy.showRawRefs ? e : refLabel(e) }}
            </span>
          </template>
          <span v-else-if="kind === 'direct-quote'" class="ng-none">
            none cited — a direct quote is grounded by its source span itself
          </span>
          <span v-else class="ng-none warn">none cited</span>
        </dd>
      </div>

      <div v-if="policy.showPolicyLabels && nugget.policyLabels.length" class="ng-row">
        <dt>Policy</dt>
        <dd><span v-for="p in nugget.policyLabels" :key="p" class="ng-chip">{{ p }}</span></dd>
      </div>

      <div v-if="policy.showCanonicalPayload && payload" class="ng-row">
        <dt>Canonical</dt>
        <dd>
          <span v-if="payload['normalizationRegime']" class="ng-regime mono">
            regime {{ payload['normalizationRegime'] }}
          </span>
          <code class="ng-payload mono">{{ JSON.stringify(payload) }}</code>
        </dd>
      </div>

      <div v-if="policy.showProvenanceChain && nugget.provenance?.length" class="ng-row">
        <dt>Provenance</dt>
        <dd>
          <span v-for="p in nugget.provenance" :key="`${p.rel}|${p.ref}`" class="ng-prov">
            <span class="ng-rel">{{ p.rel }}</span>
            <span class="mono">{{ policy.showRawRefs ? p.ref : refLabel(p.ref) }}</span>
          </span>
        </dd>
      </div>

      <div v-if="policy.showRawRefs" class="ng-row">
        <dt>Nugget</dt>
        <dd>
          <code class="mono ng-hash">{{ nugget.id }}</code>
          <span class="ng-by">by <span class="mono">{{ nugget.createdBy }}</span></span>
          <span class="ng-by">logical {{ nugget.logicalTime }}</span>
        </dd>
      </div>
    </dl>

    <!-- Seal state, stated once per card. `unknown` is not `unsealed`, and neither is `sealed`. -->
    <p class="ng-seal">
      Seal: <b>unknown</b> — KnowledgeNugget 0.1.0 carries no receipt reference. The extractor
      seals the emitted BATCH, not the individual nugget, so nothing here proves this one is on
      the chain.
    </p>
  </article>
</template>

<style scoped>
.ng {
  position: relative;
  display: grid;
  gap: 0.45rem;
  padding: 0.7rem 0.85rem 0.7rem 1rem;
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: var(--r-3);
}
/* The epistemic stripe — the at-a-glance signal. */
.ng::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  border-radius: var(--r-3) 0 0 var(--r-3);
  background: var(--epi);
}
/* Model-generated is dimmer and dashed: it must not read like the quotes around it. */
.ng-model {
  border-style: dashed;
  border-color: color-mix(in srgb, var(--epi-hypothesis) 46%, transparent);
  background: color-mix(in srgb, var(--epi-hypothesis) 7%, var(--panel));
}

.ng-head {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.ng-kind {
  color: var(--epi);
  font-size: 0.62rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: 700;
}
.ng-conf {
  color: var(--muted);
  font-size: 0.64rem;
}
.ng-time {
  margin-left: auto;
  color: var(--faint);
  font-size: 0.62rem;
  font-variant-numeric: tabular-nums;
}

.ng-banner {
  margin: 0;
  padding: 0.35rem 0.5rem;
  border-radius: var(--r-1);
  background: color-mix(in srgb, var(--epi-hypothesis) 16%, transparent);
  border: 1px solid color-mix(in srgb, var(--epi-hypothesis) 44%, transparent);
  color: var(--ink-2);
  font-size: 0.66rem;
  line-height: 1.45;
}
.ng-banner b {
  color: var(--epi-hypothesis);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.ng-text {
  margin: 0;
  color: var(--ink);
  font-size: 0.86rem;
  line-height: 1.55;
}
/* A verbatim cut looks like a quotation. Nothing else does. */
.ng-text.quote {
  border-left: 2px solid color-mix(in srgb, var(--epi-observed) 55%, transparent);
  padding-left: 0.55rem;
  font-style: italic;
}
.ng-trunc,
.ng-gloss {
  margin: 0;
  color: var(--faint);
  font-size: 0.66rem;
  line-height: 1.45;
}

.ng-meta {
  display: grid;
  gap: 0.25rem;
  margin: 0.1rem 0 0;
}
.ng-row {
  display: grid;
  grid-template-columns: 6rem 1fr;
  gap: 0.5rem;
  align-items: baseline;
}
.ng-row dt {
  color: var(--faint);
  font-size: 0.6rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.ng-row dd {
  margin: 0;
  color: var(--ink-2);
  font-size: 0.68rem;
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
  align-items: baseline;
}
.ng-span {
  color: var(--faint);
  font-size: 0.62rem;
}
.ng-hash {
  color: var(--muted);
  font-size: 0.6rem;
  overflow-wrap: anywhere;
}
.ng-chip {
  border: 1px solid var(--border-2);
  border-radius: var(--pill);
  padding: 0 7px;
  font-size: 0.62rem;
  color: var(--muted);
}
.ng-none {
  color: var(--faint);
  font-style: italic;
  font-size: 0.64rem;
}
.ng-none.warn {
  color: var(--epi-hypothesis);
  font-style: normal;
}
.ng-regime {
  color: var(--epi-derived);
  font-size: 0.62rem;
}
.ng-payload {
  color: var(--muted);
  font-size: 0.6rem;
  overflow-wrap: anywhere;
}
.ng-prov {
  display: inline-flex;
  gap: 0.3rem;
  align-items: baseline;
  font-size: 0.62rem;
}
.ng-rel {
  color: var(--faint);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  font-size: 0.56rem;
}
.ng-by {
  color: var(--faint);
  font-size: 0.6rem;
}
.ng-seal {
  margin: 0;
  padding-top: 0.35rem;
  border-top: 1px solid var(--hairline);
  color: var(--faint);
  font-size: 0.62rem;
  line-height: 1.45;
}
.ng-seal b {
  color: var(--epi-unknown);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.mono {
  font-family: var(--mono);
}
.tnum {
  font-variant-numeric: tabular-nums;
}
</style>
