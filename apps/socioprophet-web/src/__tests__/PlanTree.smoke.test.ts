/**
 * Smoke tests for <PlanTree> (W11.1) — the PLAN, not just the answer.
 *
 * Covers:
 *   1. The typed action tree renders every node of the winning plan, nested.
 *   2. Each node carries its own <Warrant>, and inherits the compilation's seal state —
 *      a node cannot be more proven than the run that produced it.
 *   3. Collapsing a node hides its subtree.
 *   4. Bindings render their type, kind, literal and subsumption witness.
 *   5. An effect-request leaf is flagged as a PROPOSAL, never as something that ran.
 *   6. The question strip lights up exactly the spans the plan consumed (= coverage, literally).
 */
import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import PlanTree from '../components/warrant/PlanTree.vue';
import {
  FIXTURE_COMPILATION,
  FIXTURE_QUESTION,
  FIXTURE_SEAL_DEGRADED,
  FIXTURE_WALK_VALID,
} from '../data/warrantFixture';

const winner = FIXTURE_COMPILATION.variants[0];
const invented = FIXTURE_COMPILATION.variants[2];

function mountWinner(extra: Record<string, unknown> = {}) {
  return mount(PlanTree, {
    props: {
      plan: winner.plan,
      provenance: winner.provenance,
      question: FIXTURE_QUESTION,
      walk: FIXTURE_WALK_VALID,
      ...extra,
    },
  });
}

describe('<PlanTree> (typed action tree)', () => {
  it('renders every node of the winning plan', () => {
    const w = mountWinner();
    const names = w.findAll('.pt-name').map((n) => n.text());
    expect(names).toEqual(['Count', 'FilterByStatus', 'SuppliersInRegion']);
    expect(w.findAll('.pt-node').length).toBe(3);
  });

  it('shows each node id and its output type', () => {
    const w = mountWinner();
    expect(w.findAll('.pt-id').map((n) => n.text())).toEqual(['n0', 'n0.items', 'n0.items.source']);
    expect(w.find('.pt-type').text()).toContain('Cardinal');
  });

  it('gives every node its own Warrant badge', () => {
    const w = mountWinner();
    expect(w.findAll('.pt-warrant').length).toBe(3);
  });

  it('propagates an UNSEALED compilation down to every node', () => {
    const w = mountWinner({ walk: null, seal: FIXTURE_SEAL_DEGRADED });
    const badges = w.findAll('.pt-warrant');
    expect(badges.length).toBe(3);
    for (const b of badges) expect(b.classes()).toContain('wr-unsealed');
  });

  it('collapses a subtree when the twisty is clicked', async () => {
    const w = mountWinner();
    expect(w.findAll('.pt-node').length).toBe(3);
    await w.find('.pt-twist').trigger('click');
    expect(w.findAll('.pt-node').length).toBe(1);
  });

  it('renders bindings with type, kind and the literal lifted from the question', () => {
    const w = mountWinner();
    const kinds = w.findAll('.pt-bind-kind').map((k) => k.text());
    expect(kinds).toContain('action');
    expect(kinds).toContain('annotation');
    // the literal must come from the BINDING, not merely from the question strip above it
    const literals = w.findAll('.pt-bind-val mark').map((m) => m.text());
    expect(literals).toContain('Germany');
    expect(literals).toContain('delayed');
  });

  it('shows the subsumption witness when a bind was licensed by polymorphism', () => {
    const w = mountWinner();
    const sub = w.find('.pt-subsume');
    expect(sub.exists()).toBe(true);
    expect(sub.text()).toContain('Region');
  });

  it('flags an effect-request leaf as a proposal', () => {
    const w = mount(PlanTree, {
      props: { plan: invented.plan, provenance: invented.provenance, question: FIXTURE_QUESTION },
    });
    expect(w.find('.pt-effect').text()).toBe('effect-request');
  });

  it('lights up exactly the consumed spans in the question strip', () => {
    const w = mountWinner();
    const hits = w.findAll('.pt-q-hit').map((h) => h.text());
    expect(hits).toEqual(['how many', 'suppliers', 'delayed']);
    // and the untouched text is still there, just not lit
    expect(w.find('.pt-q-text').text().replace(/\s+/g, ' ')).toContain('Germany');
  });
});
