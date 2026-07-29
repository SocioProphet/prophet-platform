/**
 * The fixture is a stand-in for the hellgraph NLQ compiler, so it has one job beyond
 * existing: it must not tell a story the engine's own arithmetic would refuse.
 *
 * These tests RE-DERIVE the fixture rather than assert its literals:
 *   1. composite = coverage·0.5 + groundedness·0.3 + similarity·0.2 (DEFAULT_SENSE_WEIGHTS).
 *   2. creativity = 1 − groundedness.
 *   3. groundedness = mean admissibility-discounted node weight, from `provenance`.
 *   4. node counts, grounded/ungrounded splits and the admissibility ledger agree with the tree.
 *   5. every token span slices back to its own `text` at its own offsets in the question.
 *   6. variants are ranked best-first, ranks are 1-based and dense, winner === variants[0].
 *
 * Also pins the resolveSeal() decision table, which is the honest-degradation contract in
 * pure form.
 */
import { describe, expect, it } from 'vitest';
import {
  FIXTURE_COMPILATION,
  FIXTURE_QUESTION,
  FIXTURE_SEAL_DEGRADED,
  FIXTURE_SEAL_OK,
  FIXTURE_TOKENS,
  FIXTURE_WALK_TAMPERED,
  FIXTURE_WALK_VALID,
} from '../data/warrantFixture';
import {
  DEFAULT_SENSE_WEIGHTS,
  planNodes,
  RECEIPT_WALK_STEPS,
  resolveSeal,
  warrantView,
} from '../features/warrant/types';

const variants = FIXTURE_COMPILATION.variants;

describe('warrant fixture — the arithmetic re-derives', () => {
  it.each(variants.map((v) => [v.rank, v] as const))('variant #%i composite is the weighted sum', (_r, v) => {
    const m = v.senseMetric;
    const expected =
      m.coverage * m.weights.coverage +
      m.groundedness * m.weights.groundedness +
      m.similarity * m.weights.similarity;
    expect(m.composite).toBeCloseTo(expected, 6);
  });

  it.each(variants.map((v) => [v.rank, v] as const))('variant #%i creativity is 1 − groundedness', (_r, v) => {
    expect(v.senseMetric.creativity).toBeCloseTo(1 - v.senseMetric.groundedness, 6);
  });

  it.each(variants.map((v) => [v.rank, v] as const))(
    'variant #%i groundedness is the mean discounted node weight',
    (_r, v) => {
      const mean = v.provenance.reduce((a, p) => a + p.weight, 0) / v.provenance.length;
      expect(v.senseMetric.groundedness).toBeCloseTo(mean, 6);
    },
  );

  it.each(variants.map((v) => [v.rank, v] as const))('variant #%i node accounting matches its tree', (_r, v) => {
    const nodes = planNodes(v.plan);
    const m = v.senseMetric;
    expect(m.nodes).toBe(nodes.length);
    expect(v.provenance.length).toBe(nodes.length);
    expect(m.groundedNodes + m.ungroundedNodes).toBe(m.nodes);
    expect(m.groundedNodes).toBe(v.provenance.filter((p) => p.grounded).length);
    expect(m.ungroundedNodes).toBe(nodes.filter((n) => n.grounding.kind === 'ungrounded').length);
    // the ledger has exactly one entry per ungrounded node, and its weight is the discount
    expect(m.admissibility.length).toBe(m.ungroundedNodes);
    for (const entry of m.admissibility) {
      const prov = v.provenance.find((p) => p.nodeId === entry.nodeId);
      expect(prov?.weight).toBeCloseTo(entry.weight, 6);
      const node = nodes.find((n) => n.nodeId === entry.nodeId);
      expect(node?.grounding.admissibility?.weight).toBeCloseTo(entry.weight, 6);
      expect(node?.grounding.reason).toBe(entry.reason);
    }
  });

  it('uses the engine default weights everywhere', () => {
    for (const v of variants) expect(v.senseMetric.weights).toEqual(DEFAULT_SENSE_WEIGHTS);
    expect(FIXTURE_COMPILATION.weights).toEqual(DEFAULT_SENSE_WEIGHTS);
  });

  it('coverage is consumed content tokens over content tokens', () => {
    const content = FIXTURE_TOKENS.filter((t) => !t.stop).length;
    for (const v of variants) {
      expect(v.senseMetric.contentTokens).toBe(content);
      expect(v.senseMetric.coverage).toBeCloseTo(v.senseMetric.consumedContentTokens / content, 6);
    }
  });
});

describe('warrant fixture — spans point back at the question', () => {
  it('every token offset slices back to its own text', () => {
    for (const t of FIXTURE_TOKENS) {
      expect(FIXTURE_QUESTION.slice(t.start, t.end)).toBe(t.text);
      expect(t.norm).toBe(t.text.toLowerCase());
    }
  });

  it('every plan and annotation span slices back to its own text', () => {
    const spans = [
      ...FIXTURE_COMPILATION.annotations.map((a) => a.tokenSpan),
      ...variants.flatMap((v) => v.provenance.map((p) => p.tokenSpan)),
      ...variants.flatMap((v) => planNodes(v.plan).flatMap((n) => n.bindings.map((b) => b.tokenSpan))),
    ].filter((s): s is NonNullable<typeof s> => !!s);
    expect(spans.length).toBeGreaterThan(0);
    for (const s of spans) expect(FIXTURE_QUESTION.slice(s.start, s.end)).toBe(s.text);
  });
});

describe('warrant fixture — ranking', () => {
  it('is ordered best-first with dense 1-based ranks', () => {
    expect(variants.map((v) => v.rank)).toEqual([1, 2, 3]);
    const composites = variants.map((v) => v.senseMetric.composite);
    expect([...composites].sort((a, b) => b - a)).toEqual(composites);
  });

  it('winner is variants[0]', () => {
    expect(FIXTURE_COMPILATION.winner).toBe(variants[0]);
  });
});

describe('receipt walk fixtures match the gateway contract', () => {
  it('always carries all three steps, in the pinned order', () => {
    for (const walk of [FIXTURE_WALK_VALID, FIXTURE_WALK_TAMPERED]) {
      expect(walk.steps.map((s) => s.step)).toEqual([...RECEIPT_WALK_STEPS]);
    }
  });

  it('stops at the first failure and marks the rest skipped — never ok', () => {
    const statuses = FIXTURE_WALK_TAMPERED.steps.map((s) => s.status);
    expect(statuses).toEqual(['ok', 'fail', 'skipped']);
    expect(FIXTURE_WALK_TAMPERED.valid).toBe(false);
  });

  it('a valid walk is all ok', () => {
    expect(FIXTURE_WALK_VALID.steps.every((s) => s.status === 'ok')).toBe(true);
    expect(FIXTURE_WALK_VALID.valid).toBe(true);
  });
});

describe('resolveSeal — the honest-degradation decision table', () => {
  const claim = 'c';

  it('nothing to go on → unknown, not sealed', () => {
    expect(resolveSeal({ claim })).toEqual({ state: 'unknown', detail: null });
  });

  it('sealed:false → unsealed, carrying the sealError', () => {
    const r = resolveSeal({ claim, seal: FIXTURE_SEAL_DEGRADED });
    expect(r.state).toBe('unsealed');
    expect(r.detail).toBe('gateway_unconfigured');
  });

  it('sealed:true with no walk → sealed', () => {
    expect(resolveSeal({ claim, seal: FIXTURE_SEAL_OK }).state).toBe('sealed');
  });

  it('a failing walk beats a sealed:true claim', () => {
    const r = resolveSeal({ claim, seal: FIXTURE_SEAL_OK, walk: FIXTURE_WALK_TAMPERED });
    expect(r.state).toBe('unsealed');
    expect(r.detail).toContain('engine-seal-hash');
  });

  it('a valid walk → sealed', () => {
    expect(resolveSeal({ claim, walk: FIXTURE_WALK_VALID }).state).toBe('sealed');
  });
});

describe('warrantView — the ramp degrades with the seal', () => {
  it('keeps the grounded ramp mode while sealed', () => {
    const v = warrantView({
      claim: 'c',
      grounding: variants[0].plan.grounding,
      walk: FIXTURE_WALK_VALID,
    });
    expect(v.epistemic).toBe('observed');
    expect(v.kindLabel).toBe('token span');
  });

  it('falls to unknown once unsealed, so the colour cannot outrank the proof', () => {
    const v = warrantView({
      claim: 'c',
      grounding: variants[0].plan.grounding,
      seal: FIXTURE_SEAL_DEGRADED,
    });
    expect(v.epistemic).toBe('unknown');
    expect(v.sealDetail).toBe('gateway_unconfigured');
  });

  it('labels an ungrounded claim model-generated and surfaces its admissibility', () => {
    const v = warrantView({ claim: 'c', grounding: variants[2].plan.grounding });
    expect(v.kindLabel).toBe('model-generated');
    expect(v.span).toBeNull();
    expect(v.admissibility?.admitted).toBe(false);
    expect(v.admissibility?.excludedAt).toBe('relevance');
  });
});
