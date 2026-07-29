/**
 * Smoke tests for the Studio "Warrant" surface — the W11 composition.
 *
 * Covers:
 *   1. It declares its own provenance FIRST: the plan is fixture-backed, and the banner
 *      says so above everything it renders.
 *   2. Plan tree, variant rail and three-axis score all mount over one compilation.
 *   3. Selecting a losing variant swaps the plan tree and turns on the winner deltas.
 *   4. The proof-state switch drives the run warrant through sealed → tampered → degraded,
 *      and the degraded state is visibly unsealed.
 */
import { flushPromises, mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import StudioWarrant from '../pages/studio/StudioWarrant.vue';

async function mountSurface() {
  const w = mount(StudioWarrant);
  await flushPromises();
  return w;
}

describe('Studio Warrant surface (W11)', () => {
  it('declares up front that the plan is fixture-backed, and why', async () => {
    const w = await mountSurface();
    const banner = w.find('.wsurf-mode');
    expect(banner.classes()).toContain('m-fixture');
    expect(banner.find('.wsurf-mode-tag').text()).toBe('fixture');
    expect(banner.text()).toContain('ts/src/nlq.ts');
    expect(banner.text()).toContain('No service in this repo exposes it over HTTP yet');
  });

  it('mounts the plan tree, the variant rail and the three-axis score together', async () => {
    const w = await mountSurface();
    expect(w.find('.pt-root').exists()).toBe(true);
    expect(w.findAll('.vr-item').length).toBe(3);
    expect(w.findAll('.sm-axis-name').length).toBeGreaterThanOrEqual(3);
  });

  it('opens on the winning variant', async () => {
    const w = await mountSurface();
    expect(w.text()).toContain('Plan · variant #1');
    expect(w.findAll('.pt-name').map((n) => n.text())).toEqual([
      'Count',
      'FilterByStatus',
      'SuppliersInRegion',
    ]);
  });

  it('swaps the plan tree when a losing variant is selected', async () => {
    const w = await mountSurface();
    await w.findAll('.vr-pick')[2].trigger('click');
    expect(w.text()).toContain('Plan · variant #3');
    expect(w.findAll('.pt-name').map((n) => n.text())).toEqual(['Summarize', 'DescribeRegion']);
  });

  it('re-runs on the variant the user picked', async () => {
    const w = await mountSurface();
    await w.findAll('.vr-rerun')[1].trigger('click');
    expect(w.text()).toContain('Plan · variant #2');
  });

  it('refuses to relabel the fixture with a question it never compiled', async () => {
    const w = await mountSurface();
    await w.find('input').setValue('which customers churned last quarter');
    await w.find('.btn').trigger('click');
    await flushPromises();

    // it says the compiler did not run …
    expect(w.find('.wsurf-note').text()).toContain('No compiler ran');
    // … and the plan still points at the question whose spans it actually holds,
    // rather than highlighting characters of a question that produced nothing.
    expect(w.find('.pt-q-text').text()).toContain('suppliers');
    expect(w.find('.pt-q-text').text()).not.toContain('churned');
    expect(w.findAll('.pt-q-hit').map((h) => h.text())).toEqual(['how many', 'suppliers', 'delayed']);
  });

  it('drives the run warrant through all three proof states, degrading honestly', async () => {
    const w = await mountSurface();
    const states = w.findAll('.wsurf-state');
    expect(states.map((s) => s.text())).toEqual(['sealed', 'tampered', 'degraded']);

    const runBadge = () => w.find('.wsurf-runhead .wr');
    expect(runBadge().classes()).toContain('wr-sealed');

    await states[1].trigger('click');
    expect(runBadge().classes()).toContain('wr-unsealed');
    expect(runBadge().find('.wr-why').text()).toContain('engine-seal-hash');

    await states[2].trigger('click');
    expect(runBadge().classes()).toContain('wr-unsealed');
    expect(runBadge().find('.wr-why').text()).toContain('gateway_unconfigured');
  });
});
