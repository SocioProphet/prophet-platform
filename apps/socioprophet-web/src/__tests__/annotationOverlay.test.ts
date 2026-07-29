/**
 * W11.4 — the annotation overlay. Ambiguity is data, not noise.
 *
 * The contract under test is that NOTHING the compiler saw gets silently deleted:
 *   1. every competing concept for a span survives to the model;
 *   2. "used" comes from the PLAN, never from confidence rank — which is the only way the
 *      override case (plan took the lower-confidence reading) can be detected at all;
 *   3. a span consumed only by a BINDING still counts as consumed, because the engine's own
 *      coverage arithmetic counts it;
 *   4. overlapping spans are surfaced, not dropped;
 *   5. depth may fold competitors away, but must say how many it folded.
 */
import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import AnnotationOverlay from '../components/warrant/AnnotationOverlay.vue';
import { buildAnnotationOverlay, conceptLabel } from '../features/warrant/annotations';
import { FIXTURE_COMPILATION, FIXTURE_QUESTION } from '../data/warrantFixture';

const V1 = FIXTURE_COMPILATION.variants[0]!;
const V2 = FIXTURE_COMPILATION.variants[1]!;
const ANN = FIXTURE_COMPILATION.annotations;

const build = (v = V1) => buildAnnotationOverlay(FIXTURE_QUESTION, ANN, v.provenance, v.plan);
const spanAt = (start: number, o = build()) => o.spans.find((s) => s.span.start === start)!;

describe('annotation overlay — the model', () => {
  it('keeps every competing concept for a span', () => {
    const delayed = spanAt(34);
    expect(delayed.candidates.map((c) => c.conceptRef).sort()).toEqual([
      'urn:srcos:concept:DelayedStatus',
      'urn:srcos:concept:LateShipment',
    ]);
    expect(delayed.ambiguous).toBe(true);
  });

  it('reads "used" from the plan, NOT from confidence order', () => {
    const delayed = spanAt(34);
    // LateShipment scores higher (0.91 vs 0.88) but the plan bound DelayedStatus.
    expect(delayed.topConfidenceConceptRef).toBe('urn:srcos:concept:LateShipment');
    expect(delayed.usedConceptRef).toBe('urn:srcos:concept:DelayedStatus');
    expect(delayed.overrodeTopConfidence).toBe(true);

    const used = delayed.candidates.find((c) => c.used)!;
    const lost = delayed.candidates.find((c) => !c.used)!;
    expect(used.conceptRef).toBe('urn:srcos:concept:DelayedStatus');
    expect(lost.confidence).toBeGreaterThan(used.confidence);
  });

  it('does not flag an override when the plan took the top candidate', () => {
    const suppliers = spanAt(9);
    expect(suppliers.ambiguous).toBe(true);
    expect(suppliers.usedConceptRef).toBe('urn:srcos:type:Supplier');
    expect(suppliers.topConfidenceConceptRef).toBe('urn:srcos:type:Supplier');
    expect(suppliers.overrodeTopConfidence).toBe(false);
  });

  it('counts a span consumed only by a BINDING as consumed', () => {
    // "Germany" fills the `region` input; it never appears in node-level provenance.
    const inProvenance = V1.provenance.some((p) => p.tokenSpan?.start === 22);
    expect(inProvenance).toBe(false);

    const germany = spanAt(22);
    expect(germany.consumed).toBe(true);
    expect(germany.usedConceptRef).toBe('urn:srcos:concept:Germany');
    const via = germany.candidates.find((c) => c.used)!.usedBy[0]!;
    expect(via.via).toBe('binding');
    expect(via.input).toBe('region');
  });

  it('agrees with the engine: consumed spans reconcile with the variant coverage', () => {
    // V1 reports 5/5 content tokens consumed, so no CONTENT span may read as unconsumed.
    expect(V1.senseMetric.consumedContentTokens).toBe(5);
    const o = build();
    const unconsumedContent = o.spans
      .filter((s) => !s.consumed)
      // "many" is a sub-span of the already-consumed "how many"; its tokens are covered.
      .filter((s) => s.span.text !== 'many');
    expect(unconsumedContent).toEqual([]);
  });

  it('reports an unconsumed span when the selected variant ignores it', () => {
    // V2 never consumes "delayed" — that is exactly why it lost on coverage.
    const o = build(V2);
    const delayed = o.spans.find((s) => s.span.start === 34)!;
    expect(delayed.consumed).toBe(false);
    expect(delayed.usedConceptRef).toBeNull();
    // An unconsumed span cannot have "overridden" anything.
    expect(delayed.overrodeTopConfidence).toBe(false);
  });

  it('keeps overlapping spans instead of dropping them', () => {
    const o = build();
    expect(o.overlapped.map((s) => s.span.text)).toEqual(['many']);
    // …and it is still counted in the totals, not quietly excluded.
    expect(o.spans.some((s) => s.span.text === 'many')).toBe(true);
    expect(o.unconsumedCount).toBe(1);
  });

  it('lays the question out losslessly', () => {
    const o = build();
    expect(o.segments.map((s) => s.text).join('')).toBe(FIXTURE_QUESTION);
    for (const s of o.segments) expect(FIXTURE_QUESTION.slice(s.start, s.end)).toBe(s.text);
  });

  it('summarizes the ambiguity', () => {
    const o = build();
    expect(o.spans.length).toBe(5);
    expect(o.ambiguousCount).toBe(3); // suppliers, Germany, delayed
    expect(o.overriddenCount).toBe(1); // delayed
  });

  it('shortens concept URNs to their readable tail', () => {
    expect(conceptLabel('urn:srcos:concept:DelayedStatus')).toBe('DelayedStatus');
    expect(conceptLabel('http://kbpedia.org/ontologies/kko#Quantity')).toBe('Quantity');
  });
});

describe('annotation overlay — the surface', () => {
  const mountAt = (level: 'novice' | 'journeyman' | 'expert', variant = V1) =>
    mount(AnnotationOverlay, {
      props: {
        question: FIXTURE_QUESTION,
        annotations: ANN,
        provenance: variant.provenance,
        plan: variant.plan,
        level,
      },
    });

  it('lights consumed spans and marks unconsumed ones differently', () => {
    const w = mountAt('expert');
    const consumed = w.findAll('.ao-span.sp-consumed');
    expect(consumed.length).toBeGreaterThan(0);
    // The override span wears the loud class.
    expect(w.find('.ao-span.sp-overridden').exists()).toBe(true);
  });

  it('names the override in plain words, with both concepts', () => {
    const w = mountAt('expert');
    const warn = w.find('.ao-span.sp-overridden .ao-warn');
    expect(warn.exists()).toBe(true);
    expect(warn.text()).toContain('DelayedStatus');
    expect(warn.text()).toContain('LateShipment');
    expect(warn.text()).toContain('NOT the highest-confidence');
  });

  it('shows every competing candidate at journeyman and above', () => {
    const w = mountAt('journeyman');
    const delayed = w.findAll('.ao-span').find((s) => s.text().includes('delayed'))!;
    expect(delayed.findAll('.ao-cand').length).toBe(2);
    expect(delayed.text()).toContain('used by the plan');
    expect(delayed.text()).toContain('not used');
  });

  it('folds competitors away at novice depth — but DISCLOSES how many', () => {
    const w = mountAt('novice');
    const delayed = w.findAll('.ao-span').find((s) => s.text().includes('delayed'))!;
    expect(delayed.findAll('.ao-cand').length).toBe(1);
    expect(delayed.find('.ao-hidden').text()).toContain('1 competing reading');
  });

  it('still warns about the override at NOVICE depth — ambiguity is warrant-bearing', () => {
    const w = mountAt('novice');
    const warn = w.find('.ao-span.sp-overridden .ao-warn');
    expect(warn.exists()).toBe(true);
    expect(warn.text()).toContain('NOT the highest-confidence');
  });

  it('renders overlapping spans in their own strip rather than hiding them', () => {
    const w = mountAt('expert');
    const strip = w.find('.ao-overlap');
    expect(strip.exists()).toBe(true);
    expect(strip.text()).toContain('many');
    expect(strip.text()).toContain('Quantity');
  });

  it('says a span was annotated and left unconsumed', () => {
    const w = mountAt('expert', V2);
    const delayed = w.findAll('.ao-span').find((s) => s.text().includes('delayed'))!;
    expect(delayed.classes()).toContain('sp-unconsumed');
    expect(delayed.find('.ao-warn').text()).toContain('No plan node consumed this span');
  });
});
