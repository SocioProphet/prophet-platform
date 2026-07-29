/**
 * Smoke tests for <SenseMetricBadge> (W11.3) — three legible axes, not one opaque number.
 *
 * Covers:
 *   1. coverage / groundedness / similarity each render as their own labelled axis, with
 *      the weight and the actual weighted contribution.
 *   2. Creativity is presented as the MECHANISM — `1 − groundedness`, produced by the
 *      admissibility discount — with the offending nodes named.
 *   3. A fully grounded plan reads as clean, not as "0% creative".
 *   4. Deltas against a reference metric render signed, and colour-code direction.
 */
import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import SenseMetricBadge from '../components/warrant/SenseMetricBadge.vue';
import { FIXTURE_COMPILATION } from '../data/warrantFixture';

const winner = FIXTURE_COMPILATION.variants[0].senseMetric;
const invented = FIXTURE_COMPILATION.variants[2].senseMetric;

describe('<SenseMetricBadge> (three-axis score)', () => {
  it('renders the three axes as separate, labelled tracks', () => {
    const w = mount(SenseMetricBadge, { props: { metric: winner } });
    expect(w.findAll('.sm-axis-name').map((a) => a.text())).toEqual([
      'coverage',
      'groundedness',
      'similarity',
    ]);
    expect(w.findAll('.sm-bar').length).toBe(3);
  });

  it('shows each axis value, its weight and its weighted contribution', () => {
    const w = mount(SenseMetricBadge, { props: { metric: winner } });
    expect(w.findAll('.sm-axis-val').map((v) => v.text())).toEqual(['100%', '100%', '50%']);
    expect(w.findAll('.sm-w').map((v) => v.text())).toEqual(['w 0.50', 'w 0.30', 'w 0.20']);
    expect(w.findAll('.sm-contrib').map((v) => v.text())).toEqual([
      'contributes 0.500',
      'contributes 0.300',
      'contributes 0.100',
    ]);
  });

  it('renders the composite', () => {
    const w = mount(SenseMetricBadge, { props: { metric: winner } });
    expect(w.find('.sm-comp-v').text()).toBe('0.900');
  });

  it('states creativity as 1 − groundedness and names every node that cost it', () => {
    const w = mount(SenseMetricBadge, { props: { metric: invented } });
    const cr = w.find('.sm-creativity');
    expect(cr.text()).toContain('75%');
    expect(cr.text()).toContain('1 − groundedness');
    expect(cr.text()).toContain('2 of 2 nodes invented');
    const rows = w.findAll('.sm-adm-row');
    expect(rows.length).toBe(2);
    expect(rows[0].text()).toContain('n0');
    expect(rows[0].text()).toContain('no token span');
    expect(rows[0].text()).toContain('×0.00');
    expect(rows[1].text()).toContain('a required input never bound');
    expect(rows[1].text()).toContain('×0.50');
  });

  it('reads a fully grounded plan as clean rather than as a penalty', () => {
    const w = mount(SenseMetricBadge, { props: { metric: winner } });
    const cr = w.find('.sm-creativity');
    expect(cr.classes()).toContain('sm-clean');
    expect(cr.text()).toContain('no invention');
    expect(w.findAll('.sm-adm-row').length).toBe(0);
  });

  it('renders signed, direction-coded deltas against a reference', () => {
    const w = mount(SenseMetricBadge, { props: { metric: invented, reference: winner } });
    const deltas = w.findAll('.sm-delta');
    // coverage −0.2, groundedness −0.75, similarity +0.5, composite −0.225
    expect(deltas.map((d) => d.text())).toEqual(['−0.200', '−0.750', '+0.500', '−0.225']);
    expect(deltas[0].classes()).toContain('d-down');
    expect(deltas[2].classes()).toContain('d-up');
  });

  it('omits deltas entirely when there is no reference', () => {
    const w = mount(SenseMetricBadge, { props: { metric: winner } });
    expect(w.findAll('.sm-delta').length).toBe(0);
  });

  it('drops the per-axis detail in compact mode but keeps the axes and composite', () => {
    const w = mount(SenseMetricBadge, { props: { metric: winner, compact: true } });
    expect(w.findAll('.sm-bar').length).toBe(3);
    expect(w.find('.sm-comp-v').exists()).toBe(true);
    expect(w.findAll('.sm-w').length).toBe(0);
    expect(w.find('.sm-creativity').exists()).toBe(false);
  });
});
