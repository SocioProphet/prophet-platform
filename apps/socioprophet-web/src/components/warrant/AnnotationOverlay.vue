<script setup lang="ts">
// W11.4 — the annotation overlay. The question, with every competing reading kept.
//
// Consumed spans are lit; hover or keyboard-focus a span to see EVERY ontology concept that
// competed for those characters, each with its annotator and confidence, and which one the plan
// actually bound. The interesting cases get their own marks:
//
//   • ambiguous          more than one distinct concept claimed the span
//   • overridden         the plan did NOT take the highest-confidence candidate  ← the EBA lesson
//   • unconsumed         annotated, but no plan node bound anything here
//
// "Used" is read from the selected variant's provenance, never guessed from confidence order —
// which is the only reason `overridden` can be detected at all.
//
// Depth (W11.6) folds the losing candidates and the numbers away for a novice. It never folds
// away the fact that a span was ambiguous or that the plan overrode the ranking: those are
// warrant-bearing, so they render at every depth.
import { computed } from 'vue';
import {
  buildAnnotationOverlay,
  conceptLabel,
  type AnnotatedSpan,
} from '../../features/warrant/annotations';
import { depthPolicy, type Expertise } from '../../features/depth/expertise';
import { pct, type NodeProvenance, type PlanNode, type TokenAnnotation } from '../../features/warrant/types';

const props = withDefaults(
  defineProps<{
    question: string;
    annotations: readonly TokenAnnotation[];
    /** The SELECTED variant's provenance — node-level grounding. */
    provenance: readonly NodeProvenance[];
    /** The SELECTED variant's plan, so binding-level consumption is counted too. */
    plan?: PlanNode | null;
    level: Expertise;
  }>(),
  { plan: null },
);

const overlay = computed(() =>
  buildAnnotationOverlay(props.question, props.annotations, props.provenance, props.plan),
);
const policy = computed(() => depthPolicy(props.level));

/** Candidates to render: at novice depth, only the one the plan used (if any). */
function shown(s: AnnotatedSpan) {
  if (policy.value.showLosingCandidates) return s.candidates;
  const used = s.candidates.filter((c) => c.used);
  return used.length > 0 ? used : s.candidates.slice(0, 1);
}
function hiddenCount(s: AnnotatedSpan) {
  return s.candidates.length - shown(s).length;
}
function spanClass(s: AnnotatedSpan) {
  return {
    'sp-consumed': s.consumed,
    'sp-unconsumed': !s.consumed,
    'sp-ambiguous': s.ambiguous,
    'sp-overridden': s.overrodeTopConfidence,
  };
}
</script>

<template>
  <div class="ao">
    <!-- Counts first: the shape of the ambiguity, before the detail. -->
    <div class="ao-summary">
      <span class="ao-stat"
        ><b class="tnum">{{ overlay.spans.length }}</b> annotated span{{ overlay.spans.length === 1 ? '' : 's' }}</span
      >
      <span v-if="overlay.ambiguousCount" class="ao-stat s-amb"
        ><b class="tnum">{{ overlay.ambiguousCount }}</b> ambiguous</span
      >
      <span v-if="overlay.overriddenCount" class="ao-stat s-ovr"
        ><b class="tnum">{{ overlay.overriddenCount }}</b> plan overrode top confidence</span
      >
      <span v-if="overlay.unconsumedCount" class="ao-stat s-unc"
        ><b class="tnum">{{ overlay.unconsumedCount }}</b> annotated but unconsumed</span
      >
    </div>

    <!-- The question itself. -->
    <p class="ao-text">
      <template v-for="(seg, i) in overlay.segments" :key="i">
        <span v-if="!seg.annotated" class="ao-plain">{{ seg.text }}</span>
        <span v-else class="ao-span" :class="spanClass(seg.annotated)" tabindex="0" role="button"
          :aria-label="`${seg.text}: ${seg.annotated.candidates.length} candidate concept(s), ${seg.annotated.consumed ? 'consumed by the plan' : 'not consumed'}`"
        >
          <span class="ao-span-t">{{ seg.text }}</span>
          <span v-if="seg.annotated.ambiguous" class="ao-mark" aria-hidden="true">⑂</span>

          <!-- the competing-concepts popover -->
          <span class="ao-pop" role="tooltip">
            <span class="ao-pop-head">
              <b>“{{ seg.text }}”</b>
              <span v-if="policy.showSpanOffsets" class="ao-off tnum"
                >[{{ seg.annotated.span.start }},{{ seg.annotated.span.end }})</span
              >
              <span class="ao-pop-n"
                >{{ seg.annotated.candidates.length }} candidate{{ seg.annotated.candidates.length === 1 ? '' : 's' }}</span
              >
            </span>

            <!-- Warrant-bearing notices. Rendered at EVERY depth. -->
            <span v-if="seg.annotated.overrodeTopConfidence" class="ao-warn">
              The plan bound <b>{{ conceptLabel(seg.annotated.usedConceptRef ?? '') }}</b
              >, which is NOT the highest-confidence candidate
              (<b>{{ conceptLabel(seg.annotated.topConfidenceConceptRef ?? '') }}</b
              >). Ranking and choice disagree here.
            </span>
            <span v-else-if="!seg.annotated.consumed" class="ao-warn">
              No plan node consumed this span. It was annotated and then left on the floor —
              this is a coverage gap, not a resolved reading.
            </span>
            <span v-else-if="seg.annotated.ambiguous" class="ao-note">
              {{ seg.annotated.candidates.length }} readings competed; the plan took one.
            </span>

            <ul class="ao-cands">
              <li
                v-for="c in shown(seg.annotated)"
                :key="`${c.conceptRef}|${c.source}`"
                class="ao-cand"
                :class="{ used: c.used }"
              >
                <span class="ao-cand-top">
                  <span class="ao-cand-mark" aria-hidden="true">{{ c.used ? '●' : '○' }}</span>
                  <span class="ao-cand-c mono">{{ conceptLabel(c.conceptRef) }}</span>
                  <span v-if="c.used" class="ao-cand-used">used by the plan</span>
                  <span v-else class="ao-cand-lost">not used</span>
                </span>
                <span v-if="policy.showConfidence" class="ao-cand-meta">
                  <span class="tnum">{{ pct(c.confidence) }}</span> confidence · annotator
                  <span class="mono">{{ c.source }}</span>
                </span>
                <span v-if="policy.showRawRefs" class="ao-cand-ref mono">{{ c.conceptRef }}</span>
                <span v-if="c.used && c.usedBy.length" class="ao-cand-by">
                  bound by
                  <span v-for="(u, j) in c.usedBy" :key="`${u.nodeId}|${u.via}|${u.input ?? ''}`" class="mono"
                    >{{ u.actionName }}<span class="ao-nid">
                      ({{ u.nodeId }}<template v-if="u.via === 'binding'"> · {{ u.input }}</template
                      >)</span
                    ><span v-if="j < c.usedBy.length - 1">, </span></span
                  >
                </span>
              </li>
            </ul>

            <!-- Never let depth silently swallow competitors: say how many are folded. -->
            <span v-if="hiddenCount(seg.annotated) > 0" class="ao-hidden">
              {{ hiddenCount(seg.annotated) }} competing reading{{ hiddenCount(seg.annotated) === 1 ? '' : 's' }}
              hidden at this depth — raise depth to see {{ hiddenCount(seg.annotated) === 1 ? 'it' : 'them' }}.
            </span>
          </span>
        </span>
      </template>
    </p>

    <!-- Spans that could not be laid out inline because they overlap one that was. Shown, not
         dropped: a hidden competitor is the bug this surface exists to fix. -->
    <div v-if="overlay.overlapped.length" class="ao-overlap">
      <span class="ao-overlap-l">overlapping spans (not shown inline)</span>
      <span v-for="s in overlay.overlapped" :key="`${s.span.start}:${s.span.end}`" class="ao-overlap-i">
        “{{ s.span.text }}”
        <span v-if="policy.showSpanOffsets" class="ao-off tnum">[{{ s.span.start }},{{ s.span.end }})</span>
        →
        <span v-for="(c, j) in s.candidates" :key="c.conceptRef + c.source" class="mono">
          {{ conceptLabel(c.conceptRef) }}<span v-if="c.used" class="ao-cand-used"> ·used</span
          ><span v-if="j < s.candidates.length - 1">, </span>
        </span>
      </span>
    </div>

    <div class="ao-legend">
      <span><i class="lg lg-consumed" />consumed by the plan</span>
      <span><i class="lg lg-unconsumed" />annotated, unconsumed</span>
      <span><i class="lg lg-overridden" />plan overrode top confidence</span>
      <span>⑂ more than one concept competed</span>
    </div>
  </div>
</template>

<style scoped>
.ao {
  display: grid;
  gap: 0.7rem;
}
.ao-summary {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  align-items: center;
}
.ao-stat {
  font-size: 0.66rem;
  color: var(--muted);
  border: 1px solid var(--border-2);
  border-radius: var(--pill);
  padding: 1px 9px;
}
.ao-stat b {
  color: var(--ink);
}
.ao-stat.s-amb {
  color: var(--epi-derived);
  border-color: color-mix(in srgb, var(--epi-derived) 40%, transparent);
}
.ao-stat.s-amb b {
  color: var(--epi-derived);
}
.ao-stat.s-ovr {
  color: var(--warn);
  border-color: color-mix(in srgb, var(--warn) 44%, transparent);
  background: var(--warn-wash);
}
.ao-stat.s-ovr b {
  color: var(--warn);
}
.ao-stat.s-unc {
  color: var(--epi-hypothesis);
  border-color: color-mix(in srgb, var(--epi-hypothesis) 40%, transparent);
}
.ao-stat.s-unc b {
  color: var(--epi-hypothesis);
}

.ao-text {
  margin: 0;
  font-size: 1.02rem;
  line-height: 2.1;
  color: var(--ink-2);
  background: var(--sunken);
  border: 1px solid var(--hairline);
  border-radius: var(--r-2);
  padding: 0.7rem 0.8rem;
}
.ao-plain {
  color: var(--faint);
}

.ao-span {
  position: relative;
  display: inline-flex;
  align-items: baseline;
  gap: 2px;
  cursor: help;
  border-radius: var(--r-1);
  padding: 1px 4px;
  border-bottom: 2px solid var(--idle);
  color: var(--ink);
}
.ao-span:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}
/* Consumed = lit on the observed rung; unconsumed stays grey and dashed. */
.ao-span.sp-consumed {
  background: color-mix(in srgb, var(--epi-observed) 16%, transparent);
  border-bottom-color: var(--epi-observed);
}
.ao-span.sp-unconsumed {
  color: var(--muted);
  border-bottom-style: dashed;
  border-bottom-color: var(--epi-hypothesis);
}
.ao-span.sp-ambiguous {
  border-bottom-color: var(--epi-derived);
}
/* Override is the loudest state — warn, because ranking and choice disagreed. */
.ao-span.sp-overridden {
  background: var(--warn-wash);
  border-bottom-color: var(--warn);
}
.ao-mark {
  font-size: 0.7rem;
  color: var(--epi-derived);
  line-height: 1;
}
.sp-overridden .ao-mark {
  color: var(--warn);
}

.ao-pop {
  position: absolute;
  z-index: 60;
  bottom: calc(100% + 8px);
  left: 0;
  display: grid;
  gap: 0.35rem;
  width: max-content;
  max-width: 27rem;
  padding: 0.6rem 0.7rem;
  border-radius: var(--r-3);
  background: var(--surface);
  border: 1px solid var(--hairline-strong);
  box-shadow: var(--e-3);
  opacity: 0;
  visibility: hidden;
  transform: translateY(4px);
  transition: opacity 0.12s ease, transform 0.12s ease;
  font-size: 0.72rem;
  line-height: 1.45;
  text-align: left;
  white-space: normal;
  color: var(--ink-2);
}
.ao-span:hover .ao-pop,
.ao-span:focus-visible .ao-pop {
  opacity: 1;
  visibility: visible;
  transform: translateY(0);
}
.ao-pop-head {
  display: flex;
  align-items: baseline;
  gap: 0.4rem;
  flex-wrap: wrap;
  color: var(--ink);
  font-size: 0.74rem;
}
.ao-pop-n {
  margin-left: auto;
  color: var(--faint);
  font-size: 0.62rem;
}
.ao-off {
  color: var(--faint);
  font-size: 0.62rem;
}

.ao-warn {
  color: var(--warn);
  background: var(--warn-wash);
  border: 1px solid color-mix(in srgb, var(--warn) 34%, transparent);
  border-radius: var(--r-1);
  padding: 0.3rem 0.4rem;
  font-size: 0.66rem;
}
.ao-note {
  color: var(--epi-derived);
  font-size: 0.66rem;
}

.ao-cands {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.3rem;
}
.ao-cand {
  display: grid;
  gap: 1px;
  padding: 0.3rem 0.4rem;
  border-radius: var(--r-1);
  background: var(--sunken);
  border-left: 3px solid var(--idle);
}
.ao-cand.used {
  border-left-color: var(--epi-observed);
  background: var(--epi-observed-wash);
}
.ao-cand-top {
  display: flex;
  align-items: baseline;
  gap: 0.4rem;
}
.ao-cand-mark {
  color: var(--idle);
  font-size: 0.6rem;
}
.ao-cand.used .ao-cand-mark {
  color: var(--epi-observed);
}
.ao-cand-c {
  color: var(--ink);
  font-size: 0.7rem;
}
.ao-cand-used {
  margin-left: auto;
  color: var(--epi-observed);
  font-size: 0.6rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 700;
}
.ao-cand-lost {
  margin-left: auto;
  color: var(--faint);
  font-size: 0.6rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.ao-cand-meta,
.ao-cand-by {
  color: var(--faint);
  font-size: 0.62rem;
}
.ao-cand-ref {
  color: var(--muted);
  font-size: 0.6rem;
  overflow-wrap: anywhere;
}
.ao-nid {
  color: var(--faint);
}
.ao-hidden {
  color: var(--faint);
  font-size: 0.62rem;
  border-top: 1px solid var(--hairline);
  padding-top: 0.3rem;
}

.ao-overlap {
  display: grid;
  gap: 0.25rem;
  padding: 0.5rem 0.6rem;
  border: 1px dashed var(--border-2);
  border-radius: var(--r-2);
}
.ao-overlap-l {
  color: var(--faint);
  font-size: 0.6rem;
  text-transform: uppercase;
  letter-spacing: 0.07em;
}
.ao-overlap-i {
  color: var(--ink-2);
  font-size: 0.68rem;
}

.ao-legend {
  display: flex;
  gap: 0.9rem;
  flex-wrap: wrap;
  color: var(--faint);
  font-size: 0.62rem;
  align-items: center;
}
.lg {
  display: inline-block;
  width: 10px;
  height: 3px;
  border-radius: 2px;
  margin-right: 5px;
  vertical-align: middle;
}
.lg-consumed {
  background: var(--epi-observed);
}
.lg-unconsumed {
  background: var(--epi-hypothesis);
}
.lg-overridden {
  background: var(--warn);
}
.mono {
  font-family: var(--mono);
}
.tnum {
  font-variant-numeric: tabular-nums;
}
</style>
