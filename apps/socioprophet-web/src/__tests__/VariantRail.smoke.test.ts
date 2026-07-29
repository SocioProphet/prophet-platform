/**
 * Smoke tests for <VariantRail> (W11.2) — the alternatives that LOST.
 *
 * Covers:
 *   1. Every ranked variant renders, best-first, with its composite.
 *   2. The winner is marked; the selected one is marked separately.
 *   3. Selecting and re-running emit the variant the user picked.
 *   4. "Why it lost" names the axis that cost the most COMPOSITE POINTS (deficit × weight),
 *      not the biggest raw gap — the two differ, and only one of them is true.
 *   5. An empty variant list says nothing type-checked rather than rendering blank.
 */
import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import VariantRail from '../components/warrant/VariantRail.vue';
import { FIXTURE_COMPILATION } from '../data/warrantFixture';

const variants = FIXTURE_COMPILATION.variants;

describe('<VariantRail> (ranked alternatives)', () => {
  it('renders every variant with its rank and composite', () => {
    const w = mount(VariantRail, { props: { variants } });
    const items = w.findAll('.vr-item');
    expect(items.length).toBe(3);
    expect(w.findAll('.vr-rank').map((r) => r.text())).toEqual(['#1', '#2', '#3']);
    expect(w.findAll('.vr-comp').map((c) => c.text())).toEqual(['0.900', '0.825', '0.675']);
  });

  it('marks the winner and the selection independently', () => {
    const w = mount(VariantRail, { props: { variants, selectedRank: 2 } });
    const items = w.findAll('.vr-item');
    expect(items[0].classes()).toContain('vr-winner');
    expect(items[1].classes()).toContain('vr-on');
    expect(items[0].classes()).not.toContain('vr-on');
    expect(w.find('.vr-crown').text()).toBe('won');
  });

  it('emits select with the picked rank', async () => {
    const w = mount(VariantRail, { props: { variants } });
    await w.findAll('.vr-pick')[2].trigger('click');
    expect(w.emitted('select')?.[0]).toEqual([3]);
  });

  it('emits rerun with the whole variant', async () => {
    const w = mount(VariantRail, { props: { variants } });
    await w.findAll('.vr-rerun')[1].trigger('click');
    const payload = w.emitted('rerun')?.[0]?.[0] as { rank: number };
    expect(payload.rank).toBe(2);
  });

  it('names the axis that actually cost each loser the win', () => {
    const w = mount(VariantRail, { props: { variants } });
    const whys = w.findAll('.vr-why').map((p) => p.text());
    expect(whys.length).toBe(2); // the winner has no "why it lost"
    // #2 ignored "delayed": coverage deficit 0.2 × w0.5 = 0.10, the largest weighted loss
    expect(whys[0]).toContain('coverage');
    // #3 invented its root: groundedness deficit 0.75 × w0.3 = 0.225, larger than its
    // coverage loss of 0.2 × 0.5 = 0.10 — so groundedness, not coverage.
    expect(whys[1]).toContain('groundedness');
  });

  it('shows per-axis deltas against the winner for losers only', () => {
    const w = mount(VariantRail, { props: { variants } });
    const items = w.findAll('.vr-item');
    expect(items[0].findAll('.sm-delta').length).toBe(0);
    expect(items[1].findAll('.sm-delta').length).toBeGreaterThan(0);
  });

  it('says nothing type-checked when there are no variants', () => {
    const w = mount(VariantRail, { props: { variants: [] } });
    expect(w.find('.vr-empty').text()).toContain('Nothing type-checked');
    expect(w.findAll('.vr-item').length).toBe(0);
  });
});
