<template>
  <!-- W11.1 — the PLAN, not just the answer.
       The NLQ compiler returns ranked variant plans as typed action trees. This renders one
       of them: a collapsible tree of typed actions, each node carrying its own <Warrant>,
       above a strip of the original question with the consumed spans lit up — which is what
       "coverage" means, made literal. -->
  <div class="pt">
    <div v-if="question" class="pt-question">
      <span class="pt-q-l">question</span>
      <span class="pt-q-text">
        <span v-for="(seg, i) in segments" :key="i" :class="seg.consumed ? 'pt-q-hit' : 'pt-q-miss'">{{ seg.text }}</span>
      </span>
    </div>

    <ul class="pt-root">
      <PlanTreeNode :node="plan" :provenance="provenance" :seal="seal" :walk="walk" :depth="0" />
    </ul>

    <div class="pt-legend">
      <span><i class="lg lg-obs" />grounded in a span</span>
      <span><i class="lg lg-der" />registry default</span>
      <span><i class="lg lg-hyp" />model-generated</span>
      <span class="pt-legend-note">every node's badge opens its receipt walk</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import PlanTreeNode from './PlanTreeNode.vue';
import type {
  NodeProvenance,
  PlanNode,
  ReceiptVerifyWalk,
  SealOutcome,
} from '../../features/warrant/types';

const props = withDefaults(
  defineProps<{
    plan: PlanNode;
    provenance: NodeProvenance[];
    /** The question the plan was compiled from, for the span strip. */
    question?: string;
    seal?: SealOutcome | null;
    walk?: ReceiptVerifyWalk | null;
  }>(),
  { question: '', seal: null, walk: null },
);

/**
 * Split the question into consumed / not-consumed segments using the plan's own token spans.
 * Spans are `[start, end)` character offsets into the question — the compiler guarantees every
 * downstream claim can point back at the exact characters, so no re-tokenizing here.
 */
const segments = computed(() => {
  const q = props.question;
  if (!q) return [];
  const spans = props.provenance
    .map((p) => p.tokenSpan)
    .filter((s): s is NonNullable<typeof s> => !!s)
    .sort((a, b) => a.start - b.start);

  const out: { text: string; consumed: boolean }[] = [];
  let cursor = 0;
  for (const s of spans) {
    if (s.start < cursor) continue; // overlapping spans: first one wins
    if (s.start > cursor) out.push({ text: q.slice(cursor, s.start), consumed: false });
    out.push({ text: q.slice(s.start, s.end), consumed: true });
    cursor = s.end;
  }
  if (cursor < q.length) out.push({ text: q.slice(cursor), consumed: false });
  return out;
});
</script>

<style scoped>
.pt {
  display: grid;
  gap: 0.5rem;
}
.pt-question {
  display: grid;
  gap: 3px;
  padding: 0.45rem 0.55rem;
  background: var(--sunken, #080b10);
  border: 1px solid var(--hairline, #232c38);
  border-radius: var(--r-2, 5px);
}
.pt-q-l {
  color: var(--faint, #5d6a78);
  font-size: 0.58rem;
  text-transform: uppercase;
  letter-spacing: 0.09em;
}
.pt-q-text {
  font-size: 0.82rem;
  line-height: 1.6;
  color: var(--muted, #8a97a5);
}
.pt-q-hit {
  color: var(--ink, #e8eef5);
  background: color-mix(in srgb, var(--epi-observed, #5b95f9) 22%, transparent);
  border-bottom: 1px solid var(--epi-observed, #5b95f9);
  border-radius: 2px;
  padding: 1px 1px;
}
.pt-q-miss {
  color: var(--faint, #5d6a78);
}
.pt-root {
  list-style: none;
  margin: 0;
  padding: 0;
}
.pt-legend {
  display: flex;
  gap: 0.8rem;
  flex-wrap: wrap;
  align-items: center;
  color: var(--faint, #5d6a78);
  font-size: 0.62rem;
  border-top: 1px solid var(--hairline, #232c38);
  padding-top: 0.4rem;
}
.pt-legend span {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
}
.lg {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  display: inline-block;
}
.lg-obs {
  background: var(--epi-observed, #5b95f9);
}
.lg-der {
  background: var(--epi-derived, #a082f8);
}
.lg-hyp {
  background: var(--epi-hypothesis, #8592a3);
}
.pt-legend-note {
  margin-left: auto;
  font-style: italic;
}
</style>
