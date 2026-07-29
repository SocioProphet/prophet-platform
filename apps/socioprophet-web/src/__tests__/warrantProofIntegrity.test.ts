/**
 * W11 — the two integrity properties that outrank every other behaviour of this surface.
 *
 *  1. FIXTURE DATA MAY NEVER BACK A PROOF RESULT.
 *     Fixture plans are fine — the surface says so in a banner. A fixture *seal* or a
 *     fixture *walk* standing in for a live check that did not succeed is not: it renders a
 *     real verification that failed as a green "sealed". A live check that failed must read
 *     as unavailable/unknown.
 *
 *  2. COLOUR MAY NEVER OUTRANK PROOF.
 *     `unknown` ("could not check") must not keep a confident epistemic ramp colour, and
 *     must stay visually distinct from `unsealed` ("checked, and it failed").
 */
import { flushPromises, mount } from '@vue/test-utils';
import { afterEach, describe, expect, it, vi } from 'vitest';
import StudioWarrant from '../pages/studio/StudioWarrant.vue';
import Warrant from '../components/warrant/Warrant.vue';
import { warrantView, type PlanGrounding } from '../features/warrant/types';
import { FIXTURE_RECEIPT_ID, FIXTURE_SEAL_DEGRADED, FIXTURE_WALK_VALID } from '../data/warrantFixture';

/** Swappable live-verify outcome; defaults to the real (unconfigured ⇒ unavailable) door. */
const h = vi.hoisted(() => ({
  verify: null as null | ((id: string, project?: string) => Promise<unknown>),
}));

vi.mock('../services/warrantApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/warrantApi')>();
  return {
    ...actual,
    verifyReceipt: (id: string, project?: string) =>
      h.verify ? h.verify(id, project) : actual.verifyReceipt(id, project),
  };
});

afterEach(() => {
  h.verify = null;
});

async function mountSurface() {
  const w = mount(StudioWarrant);
  await flushPromises();
  return w;
}

const runBadge = (w: ReturnType<typeof mount>) => w.find('.wsurf-runhead .wr');
const liveButton = (w: ReturnType<typeof mount>) => w.find('.wsurf-live');
const stateButtons = (w: ReturnType<typeof mount>) => w.findAll('.wsurf-state');

const GROUNDED: PlanGrounding = {
  kind: 'token-span',
  tokenSpan: { start: 9, end: 18, text: 'suppliers', tokenIndices: [2] },
  conceptRef: 'urn:srcos:type:Supplier',
  source: 'lexicon',
  confidence: 0.97,
};

// ─── 1. a failed live walk must not fall back to fixture proof ─────────────────

describe('StudioWarrant — a live check that failed is never backfilled with fixture proof', () => {
  it('offers an explicit live-verify door', async () => {
    const w = await mountSurface();
    expect(liveButton(w).exists()).toBe(true);
  });

  it('drops the fixture SEAL and the fixture WALK when the live walk is unavailable', async () => {
    const w = await mountSurface();
    // Baseline: the sealed fixture state reads sealed, off fixture data, and says it is fixture.
    expect(runBadge(w).classes()).toContain('wr-sealed');

    // Ask the gateway for real. Nothing is configured, so the attempt fails.
    await liveButton(w).trigger('click');
    await flushPromises();

    // The badge must NOT still read sealed off the fixture.
    expect(runBadge(w).classes()).not.toContain('wr-sealed');
    expect(runBadge(w).classes()).toContain('wr-unknown');
    expect(w.find('.err').text()).toMatch(/no compute-gateway base configured/);

    // …and the fixture's three green steps must be gone from the receipt walk.
    await runBadge(w).find('.wr-badge').trigger('click');
    expect(w.find('.wr-steps').exists()).toBe(false);
  });

  it('does the same from the tampered fixture state — no fixture verdict either way', async () => {
    const w = await mountSurface();
    await stateButtons(w)[1].trigger('click');
    expect(runBadge(w).classes()).toContain('wr-unsealed');

    await liveButton(w).trigger('click');
    await flushPromises();

    // "could not check" — not the fixture's INVALID verdict, which is also a claim about proof.
    expect(runBadge(w).classes()).toContain('wr-unknown');
    expect(runBadge(w).classes()).not.toContain('wr-unsealed');
  });

  it('renders a live walk that SUCCEEDS, and marks the surface live', async () => {
    h.verify = async () => ({ data: FIXTURE_WALK_VALID, mode: 'live' as const });
    const w = await mountSurface();
    await liveButton(w).trigger('click');
    await flushPromises();

    expect(runBadge(w).classes()).toContain('wr-sealed');
    expect(w.find('.err').exists()).toBe(false);
  });

  it('lets a live walk that FAILS its verification read as unsealed — a real check, a real verdict', async () => {
    h.verify = async () => ({
      data: {
        valid: false,
        receipt_id: FIXTURE_RECEIPT_ID,
        project: 'default',
        steps: [
          { step: 'gateway-signature', status: 'ok', detail: null },
          { step: 'engine-seal-hash', status: 'fail', detail: 'hash mismatch' },
          { step: 'snapshot-seq-binding', status: 'skipped', detail: 'prior step failed' },
        ],
      },
      mode: 'live' as const,
    });
    const w = await mountSurface();
    await liveButton(w).trigger('click');
    await flushPromises();

    expect(runBadge(w).classes()).toContain('wr-unsealed');
    expect(runBadge(w).find('.wr-why').text()).toContain('engine-seal-hash');
  });

  it('never shows a live-failure error next to a sealed badge', async () => {
    const w = await mountSurface();
    await liveButton(w).trigger('click');
    await flushPromises();

    // Whatever the surface chooses to do next, these two may never be on screen together.
    const erroring = w.find('.err').exists();
    expect(erroring && runBadge(w).classes().includes('wr-sealed')).toBe(false);
  });

  it('lets the user go back to the fixture demo explicitly, and clears the live failure with it', async () => {
    const w = await mountSurface();
    await liveButton(w).trigger('click');
    await flushPromises();
    expect(w.find('.err').exists()).toBe(true);

    // Switching the fixture proof-state is a deliberate "show me the fixture story" action.
    await stateButtons(w)[0].trigger('click');
    expect(w.find('.err').exists()).toBe(false);
    expect(runBadge(w).classes()).toContain('wr-sealed');
  });
});

// ─── 4. the degraded state has nothing to walk, and the code must agree ────────

describe('StudioWarrant — "nothing to walk" means the code offers nothing to walk', () => {
  it('carries no receiptRef in the degraded state, so the badge cannot ask for a walk', async () => {
    const w = await mountSurface();
    await stateButtons(w)[2].trigger('click');

    await runBadge(w).find('.wr-badge').trigger('click');
    await flushPromises();

    // The copy says the claim was never sealed, so there is nothing to walk …
    expect(w.find('.wr-nowalk').text()).toContain('never sealed');
    // … and no walk was requested behind the user's back.
    expect(w.find('.wr-hash').exists()).toBe(false);
  });

  it('carries the receiptRef the SEAL actually reports in the sealed state', async () => {
    const w = await mountSurface();
    await runBadge(w).find('.wr-badge').trigger('click');
    expect(w.find('.wr-walk-head .wr-hash').text()).toBe(FIXTURE_RECEIPT_ID);
  });
});

// ─── 3. colour may never outrank proof ─────────────────────────────────────────

describe('warrantView — the epistemic ramp degrades for unknown as well as unsealed', () => {
  it('refuses an unknown claim a confident ramp mode', () => {
    const v = warrantView({ claim: 'c', grounding: GROUNDED });
    expect(v.seal).toBe('unknown');
    // 'observed' is the confident mode for a token-span grounding. Not while unproven.
    expect(v.epistemic).toBe('unknown');
  });

  it('degrades every warrant kind that is not sealed', () => {
    for (const kind of ['token-span', 'registry-default', 'ungrounded'] as const) {
      const g = { ...GROUNDED, kind } as PlanGrounding;
      expect(warrantView({ claim: 'c', grounding: g }).epistemic).toBe('unknown');
    }
  });

  it('still lets a SEALED claim keep its confident ramp mode', () => {
    const v = warrantView({ claim: 'c', grounding: GROUNDED, walk: FIXTURE_WALK_VALID });
    expect(v.seal).toBe('sealed');
    expect(v.epistemic).toBe('observed');
  });
});

describe('<Warrant> — unknown and unsealed are both unconfident, and still distinguishable', () => {
  const styleOf = (w: ReturnType<typeof mount>) => w.find('.wr').attributes('style') ?? '';

  it('gives an unknown claim no confident colour', () => {
    const unknown = mount(Warrant, { props: { w: { claim: 'c', grounding: GROUNDED } } });
    expect(styleOf(unknown)).not.toContain('--epi-observed');
    expect(styleOf(unknown)).toContain('--epi-unknown');
  });

  it('keeps "could not check" visually distinct from "checked, and it failed"', () => {
    const unknown = mount(Warrant, { props: { w: { claim: 'c', grounding: GROUNDED } } });
    const unsealed = mount(Warrant, {
      props: { w: { claim: 'c', grounding: GROUNDED, seal: FIXTURE_SEAL_DEGRADED } },
    });
    expect(styleOf(unsealed)).toContain('--fail');
    expect(styleOf(unknown)).not.toContain('--fail');
    expect(styleOf(unknown)).not.toBe(styleOf(unsealed));
    // and the labels stay different too
    expect(unknown.find('.wr-seal').text()).toBe('unknown');
    expect(unsealed.find('.wr-seal').text()).toBe('UNSEALED');
  });
});
