/**
 * W11.4 — the annotation overlay model. Ambiguity is data, not noise.
 *
 * THE LESSON (EBA): one token routinely carries SEVERAL competing ontology annotations, and a
 * surface that renders only the one the plan bound has quietly deleted the most interesting
 * fact on the screen — that there was a choice, and that something chose.
 *
 * The engine does not hide this. `compileQuestion` (hellgraph `ts/src/nlq.ts` @ v0.4.45, line
 * ~1160) keeps the FULL annotation list on the compilation and hands the search a separate,
 * deduped view:
 *
 *     const annotations = raw.sort(…)                    // ← everything, kept for provenance
 *     const bySpanConcept = new Map<string, TokenAnnotation>()
 *     …                                                   // one per (span, concept), best confidence
 *     const searchAnnotations = [...bySpanConcept.values()]
 *
 * So `NlqCompilation.annotations` already carries every competitor, including several distinct
 * `conceptRef`s over the same characters and the same concept proposed by several annotators.
 * The cockpit's job is only to stop throwing that away.
 *
 * This module is PURE and framework-free so the honesty rules below are unit-testable:
 *
 *   1. Every candidate for a span is kept. Nothing is filtered by confidence.
 *   2. "Used" is read from the PLAN's provenance, never inferred from confidence rank. When the
 *      plan bound a lower-confidence concept, `overrodeTopConfidence` records exactly that.
 *   3. A span nothing consumed is `consumed: false` — reported as unconsumed, never as
 *      implicitly fine, and never silently omitted.
 *   4. Overlapping spans cannot be laid out in one linear run, so the ones that do not fit are
 *      surfaced in `overlapped` rather than dropped. Dropping them would re-commit the exact
 *      sin this surface exists to fix.
 */
import { planNodes, type NodeProvenance, type PlanNode, type TokenAnnotation, type TokenSpan } from './types';

/** How a plan took hold of a span. Both count as consumption — see `gatherConsumption`. */
export type ConsumptionVia = 'grounding' | 'binding';

export interface ConsumingNode {
  nodeId: string;
  actionName: string;
  via: ConsumptionVia;
  /** The declared input name, for `via: 'binding'`. */
  input?: string;
}

/** One ontology concept proposed for a span, and whether the plan actually took it. */
export interface ConceptCandidate {
  conceptRef: string;
  /** Which annotator proposed it (`lexicon`, `kko-semantic`, or a caller's own). */
  source: string;
  /** Annotator confidence in [0,1]. Carried through from the engine; does NOT gate the search. */
  confidence: number;
  /** True when the selected plan bound THIS concept for THIS span. Read from the plan, not guessed. */
  used: boolean;
  /** Plan nodes that consumed it, when used. */
  usedBy: ConsumingNode[];
}

/** A span of the question, with every concept that competed for it. */
export interface AnnotatedSpan {
  span: TokenSpan;
  /** Used first, then confidence descending, then conceptRef for determinism. */
  candidates: ConceptCandidate[];
  /** True when the plan consumed any candidate on this span. */
  consumed: boolean;
  /** The conceptRef the plan bound, when consumed. */
  usedConceptRef: string | null;
  /** True when more than one DISTINCT conceptRef competed here — the ambiguity flag. */
  ambiguous: boolean;
  /** The highest-confidence candidate, regardless of what the plan did. */
  topConfidenceConceptRef: string | null;
  /**
   * True when the plan bound a concept that was NOT the highest-confidence candidate. The single
   * most valuable thing this overlay can tell an operator: the ranking and the choice disagreed.
   */
  overrodeTopConfidence: boolean;
}

/** A run of question text: either plain, or an annotated span. */
export interface OverlaySegment {
  text: string;
  start: number;
  end: number;
  /** Null for the plain text between annotated spans. */
  annotated: AnnotatedSpan | null;
}

export interface AnnotationOverlay {
  question: string;
  segments: OverlaySegment[];
  /**
   * Annotated spans that overlap an already-laid-out span and so have no place in the linear
   * run. Kept and rendered separately — never discarded.
   */
  overlapped: AnnotatedSpan[];
  /** Every annotated span, laid out or overlapped, in document order. */
  spans: AnnotatedSpan[];
  /** Spans carrying more than one distinct concept. */
  ambiguousCount: number;
  /** Spans where the plan did not take the top-confidence candidate. */
  overriddenCount: number;
  /** Annotated spans the plan consumed nothing from. */
  unconsumedCount: number;
}

const spanKey = (s: TokenSpan) => `${s.start}:${s.end}`;

/**
 * (span, concept) → the plan nodes that took it.
 *
 * BOTH consumption routes are gathered, because the engine counts both. `scoreVariant`
 * (nlq.ts @ v0.4.45 :1065-1071) adds a node's grounding span AND every binding span to the
 * `consumed` set before computing coverage:
 *
 *     if (g.tokenSpan) { for (const i of g.tokenSpan.tokenIndices) consumed.add(i); … }
 *     for (const b of node.bindings) {
 *       if (b.tokenSpan) for (const i of b.tokenSpan.tokenIndices) consumed.add(i)
 *     }
 *
 * …but `provenance` only ever gets a row PER NODE. So a span consumed solely by a binding —
 * "Germany" filling a `region` input is the canonical case — is invisible in provenance while
 * still counting toward coverage. An overlay reading provenance alone would print "annotated
 * but unconsumed" next to a coverage figure of 100%, and one of the two would be lying.
 */
function gatherConsumption(
  provenance: readonly NodeProvenance[],
  plan: PlanNode | null,
): Map<string, ConsumingNode[]> {
  const consumedBy = new Map<string, ConsumingNode[]>();
  const add = (span: TokenSpan, conceptRef: string, entry: ConsumingNode) => {
    const k = `${spanKey(span)}|${conceptRef}`;
    const list = consumedBy.get(k) ?? [];
    // A node can appear once per route; don't double-count the same (node, route, input).
    if (!list.some((e) => e.nodeId === entry.nodeId && e.via === entry.via && e.input === entry.input)) {
      list.push(entry);
    }
    consumedBy.set(k, list);
  };

  for (const p of provenance) {
    if (p.tokenSpan && p.conceptRef) {
      add(p.tokenSpan, p.conceptRef, { nodeId: p.nodeId, actionName: p.actionName, via: 'grounding' });
    }
  }
  if (plan) {
    for (const node of planNodes(plan)) {
      for (const b of node.bindings) {
        if (b.tokenSpan && b.conceptRef) {
          add(b.tokenSpan, b.conceptRef, {
            nodeId: node.nodeId,
            actionName: node.actionName,
            via: 'binding',
            input: b.input,
          });
        }
      }
    }
  }
  return consumedBy;
}

/**
 * Build the overlay for one question + one plan variant.
 *
 * @param question    the compiled question — spans are character offsets into THIS string.
 * @param annotations `NlqCompilation.annotations` — the full, undeduped competitor list.
 * @param provenance  the SELECTED variant's `provenance` (node-level grounding).
 * @param plan        the SELECTED variant's plan, so binding-level consumption is seen too.
 */
export function buildAnnotationOverlay(
  question: string,
  annotations: readonly TokenAnnotation[],
  provenance: readonly NodeProvenance[],
  plan: PlanNode | null = null,
): AnnotationOverlay {
  const consumedBy = gatherConsumption(provenance, plan);

  // Group every annotation by the exact characters it covers.
  const groups = new Map<string, { span: TokenSpan; anns: TokenAnnotation[] }>();
  for (const a of annotations) {
    const k = spanKey(a.tokenSpan);
    const g = groups.get(k);
    if (g) g.anns.push(a);
    else groups.set(k, { span: a.tokenSpan, anns: [a] });
  }

  const spans: AnnotatedSpan[] = [...groups.values()]
    .map(({ span, anns }) => {
      const candidates: ConceptCandidate[] = anns.map((a) => {
        const usedBy = consumedBy.get(`${spanKey(span)}|${a.conceptRef}`) ?? [];
        return {
          conceptRef: a.conceptRef,
          source: a.source,
          confidence: a.confidence,
          used: usedBy.length > 0,
          usedBy,
        };
      });

      // Top confidence is computed over the candidates as proposed — deliberately NOT
      // influenced by what the plan did, so the two can be compared.
      const byConfidence = [...candidates].sort(
        (x, y) => y.confidence - x.confidence || x.conceptRef.localeCompare(y.conceptRef),
      );
      const top = byConfidence[0] ?? null;
      const used = candidates.find((c) => c.used) ?? null;
      const distinctConcepts = new Set(candidates.map((c) => c.conceptRef));

      candidates.sort(
        (x, y) =>
          Number(y.used) - Number(x.used) ||
          y.confidence - x.confidence ||
          x.conceptRef.localeCompare(y.conceptRef) ||
          x.source.localeCompare(y.source),
      );

      return {
        span,
        candidates,
        consumed: used !== null,
        usedConceptRef: used?.conceptRef ?? null,
        ambiguous: distinctConcepts.size > 1,
        topConfidenceConceptRef: top?.conceptRef ?? null,
        // Only meaningful when something WAS used: an unconsumed span did not override anything.
        overrodeTopConfidence:
          used !== null && top !== null && used.conceptRef !== top.conceptRef,
      } satisfies AnnotatedSpan;
    })
    // Document order; longer spans first so a container is laid out before anything inside it.
    .sort((a, b) => a.span.start - b.span.start || b.span.end - a.span.end);

  // Lay out the linear run. Anything that would overlap is set aside, not dropped.
  const segments: OverlaySegment[] = [];
  const overlapped: AnnotatedSpan[] = [];
  let cursor = 0;
  for (const s of spans) {
    if (s.span.start < cursor) {
      overlapped.push(s);
      continue;
    }
    if (s.span.start > cursor) {
      segments.push({
        text: question.slice(cursor, s.span.start),
        start: cursor,
        end: s.span.start,
        annotated: null,
      });
    }
    segments.push({
      text: question.slice(s.span.start, s.span.end),
      start: s.span.start,
      end: s.span.end,
      annotated: s,
    });
    cursor = s.span.end;
  }
  if (cursor < question.length) {
    segments.push({ text: question.slice(cursor), start: cursor, end: question.length, annotated: null });
  }

  return {
    question,
    segments,
    overlapped,
    spans,
    ambiguousCount: spans.filter((s) => s.ambiguous).length,
    overriddenCount: spans.filter((s) => s.overrodeTopConfidence).length,
    unconsumedCount: spans.filter((s) => !s.consumed).length,
  };
}

/** Short display form of a concept URN: the last segment, which is the readable part. */
export function conceptLabel(ref: string): string {
  const tail = ref.split(/[:/#]/).filter(Boolean).pop();
  return tail && tail.length > 0 ? tail : ref;
}
