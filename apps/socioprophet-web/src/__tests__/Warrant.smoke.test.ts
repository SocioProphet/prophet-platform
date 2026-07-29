/**
 * Smoke tests for <Warrant> (W11.0) — the keystone proof primitive.
 *
 * The contract under test is HONEST DEGRADATION. A warrant may only read as sealed when
 * something actually proved it, so these cases pin:
 *   1. sealed / unsealed / unknown badge states, and that they are distinguishable.
 *   2. `sealed: false` + a `sealError` renders VISIBLY unsealed, with the error shown.
 *   3. A failing verify walk beats a `sealed: true` claim — a seal is a claim, a walk is a check.
 *   4. The three-step receipt walk renders every step, including `skipped` ones.
 *   5. An unsealed warrant never keeps a reassuring epistemic-ramp colour.
 *   6. Depth 2 (popover) carries the claim, the warrant type, and the source span —
 *      or says "model-generated" when there is no span.
 */
import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import Warrant from '../components/warrant/Warrant.vue';
import {
  FIXTURE_RECEIPT_ID,
  FIXTURE_SEAL_DEGRADED,
  FIXTURE_SEAL_OK,
  FIXTURE_WALK_TAMPERED,
  FIXTURE_WALK_VALID,
} from '../data/warrantFixture';
import type { PlanGrounding } from '../features/warrant/types';

const GROUNDED: PlanGrounding = {
  kind: 'token-span',
  tokenSpan: { start: 9, end: 18, text: 'suppliers', tokenIndices: [2] },
  conceptRef: 'urn:srcos:type:Supplier',
  source: 'lexicon',
  confidence: 0.97,
};

const INVENTED: PlanGrounding = {
  kind: 'ungrounded',
  reason: 'no-token-span',
  admissibility: {
    admitted: true,
    weight: 0.5,
    steps: [{ gate: 'opinion', passed: true, reason: 'model-generated: opinion discount' }],
  },
};

describe('<Warrant> — badge states', () => {
  it('renders sealed when the verify walk is valid', () => {
    const w = mount(Warrant, {
      props: { w: { claim: 'c', grounding: GROUNDED, walk: FIXTURE_WALK_VALID } },
    });
    expect(w.find('.wr').classes()).toContain('wr-sealed');
    expect(w.find('.wr-seal').text()).toBe('sealed');
  });

  it('renders unknown — not sealed — when there is nothing to go on', () => {
    const w = mount(Warrant, { props: { w: { claim: 'c', grounding: GROUNDED } } });
    expect(w.find('.wr').classes()).toContain('wr-unknown');
    expect(w.find('.wr').classes()).not.toContain('wr-sealed');
    expect(w.find('.wr-seal').text()).toBe('unknown');
  });

  it('renders UNSEALED and SHOWS the sealError when sealed:false', () => {
    const w = mount(Warrant, {
      props: { w: { claim: 'c', grounding: GROUNDED, seal: FIXTURE_SEAL_DEGRADED } },
    });
    expect(w.find('.wr').classes()).toContain('wr-unsealed');
    expect(w.find('.wr-seal').text()).toBe('UNSEALED');
    // The reason must be on screen, not swallowed.
    const why = w.find('.wr-why');
    expect(why.exists()).toBe(true);
    expect(why.text()).toContain('gateway_unconfigured');
  });

  it('never silently passes a sealed:false with no sealError', () => {
    const w = mount(Warrant, {
      props: {
        w: { claim: 'c', grounding: GROUNDED, seal: { sealed: false, receiptRef: null, sealError: null } },
      },
    });
    expect(w.find('.wr').classes()).toContain('wr-unsealed');
    expect(w.find('.wr-why').text()).toContain('sealed:false with no sealError');
  });

  it('lets a FAILING walk override a sealed:true claim — a walk is a check, a seal is a claim', () => {
    const w = mount(Warrant, {
      props: { w: { claim: 'c', grounding: GROUNDED, seal: FIXTURE_SEAL_OK, walk: FIXTURE_WALK_TAMPERED } },
    });
    expect(w.find('.wr').classes()).toContain('wr-unsealed');
    // and it names the step that owns the failure
    expect(w.find('.wr-why').text()).toContain('engine-seal-hash');
  });

  it('drops the reassuring ramp colour when unsealed', () => {
    const sealed = mount(Warrant, {
      props: { w: { claim: 'c', grounding: GROUNDED, walk: FIXTURE_WALK_VALID } },
    });
    const unsealed = mount(Warrant, {
      props: { w: { claim: 'c', grounding: GROUNDED, seal: FIXTURE_SEAL_DEGRADED } },
    });
    expect(sealed.find('.wr').attributes('style')).toContain('--epi-observed');
    expect(unsealed.find('.wr').attributes('style')).toContain('--fail');
    expect(unsealed.find('.wr').attributes('style')).not.toContain('--epi-observed');
  });
});

describe('<Warrant> — depth 2, the popover', () => {
  it('carries the claim, the warrant type and the source span', () => {
    const w = mount(Warrant, {
      props: { w: { claim: 'Count produces Cardinal', grounding: GROUNDED, walk: FIXTURE_WALK_VALID } },
    });
    const pop = w.find('.wr-pop');
    expect(pop.text()).toContain('Count produces Cardinal');
    expect(pop.text()).toContain('token span');
    expect(pop.find('mark').text()).toBe('suppliers');
    expect(pop.text()).toContain('[9,18)');
  });

  it('says "model-generated" when a claim has no span, and shows the admissibility ruling', () => {
    const w = mount(Warrant, { props: { w: { claim: 'invented', grounding: INVENTED } } });
    const pop = w.find('.wr-pop');
    expect(pop.find('.wr-nospan').text()).toContain('model-generated');
    expect(pop.text()).toContain('admitted');
    expect(pop.text()).toContain('0.50');
  });
});

describe('<Warrant> — depth 3, the receipt walk', () => {
  it('is closed until asked for, then renders all three steps in order', async () => {
    const w = mount(Warrant, {
      props: { w: { claim: 'c', grounding: GROUNDED, walk: FIXTURE_WALK_VALID } },
    });
    expect(w.find('.wr-walk').exists()).toBe(false);

    await w.find('.wr-badge').trigger('click');
    const steps = w.findAll('.wr-step');
    expect(steps.length).toBe(3);
    expect(steps.map((s) => s.find('.wr-step-name').text())).toEqual([
      'gateway-signature',
      'engine-seal-hash',
      'snapshot-seq-binding',
    ]);
    expect(w.find('.wr-walk-verdict').text()).toBe('valid');
  });

  it('renders a tampered walk as INVALID and marks the skipped step as skipped, not passed', async () => {
    const w = mount(Warrant, {
      props: { w: { claim: 'c', grounding: GROUNDED, walk: FIXTURE_WALK_TAMPERED } },
    });
    await w.find('.wr-badge').trigger('click');
    expect(w.find('.wr-walk-verdict').text()).toBe('INVALID');
    const steps = w.findAll('.wr-step');
    expect(steps[0].classes()).toContain('s-ok');
    expect(steps[1].classes()).toContain('s-fail');
    expect(steps[2].classes()).toContain('s-skipped');
    expect(steps[2].text()).toContain('prior step failed');
  });

  it('says plainly that an unsealed claim has nothing to walk', async () => {
    const w = mount(Warrant, {
      props: { w: { claim: 'c', grounding: GROUNDED, seal: FIXTURE_SEAL_DEGRADED } },
    });
    await w.find('.wr-badge').trigger('click');
    expect(w.find('.wr-steps').exists()).toBe(false);
    expect(w.find('.wr-nowalk').text()).toContain('never sealed');
  });

  it('emits walk with the receipt ref when opened without a walk in hand', async () => {
    const w = mount(Warrant, {
      props: { w: { claim: 'c', grounding: GROUNDED, seal: FIXTURE_SEAL_OK } },
    });
    await w.find('.wr-badge').trigger('click');
    expect(w.emitted('walk')?.[0]).toEqual([FIXTURE_RECEIPT_ID]);
  });
});
