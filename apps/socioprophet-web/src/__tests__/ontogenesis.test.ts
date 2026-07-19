import { describe, it, expect } from 'vitest';
import { omegaForClaim, omegaConformance, OMEGA_LADDER, notationOf } from '../ontology/ontogenesis';
import { realWorldClaim, syntheticWorldClaim, acsIncomeEvidence, type WorldClaim } from '../gaia/worldClaim';

const real = realWorldClaim({ cellId: 'c', lon: 0, lat: 0, claimType: 'observation_passthrough', value: { medianIncome: 80000 }, source: acsIncomeEvidence('c') });
const synth = syntheticWorldClaim({ cellId: 'c', lon: 0, lat: 0, claimType: 'feature_classification', value: { crimeRate: 3 }, metricLabel: 'crime' });

describe('ontogenesis Ω-ladder governance', () => {
  it('exposes the canonical 7-rung Ω scheme (verbatim from omega.ttl)', () => {
    expect(OMEGA_LADDER.map((x) => x.id)).toEqual(['ABSENT', 'SEEDED', 'NORMALIZED', 'LINKED', 'TRUSTED', 'ACTIONABLE', 'DELIVERED']);
    expect(notationOf('TRUSTED')).toBe(4);
  });

  it('grades real admitted low-uncertainty data as ACTIONABLE', () => {
    expect(omegaForClaim(real)).toBe('ACTIONABLE'); // confidence 0.9 ≥ 0.85
  });

  it('grades synthetic data no higher than SEEDED', () => {
    expect(omegaForClaim(synth)).toBe('SEEDED');
    expect(omegaConformance(synth).stepsToActionable).toBe(4); // 5 - 1
  });

  it('conformance passes for consistent claims', () => {
    expect(omegaConformance(real).conformant).toBe(true);
    expect(omegaConformance(synth).conformant).toBe(true);
  });

  it('conformance TRIPS when synthetic data is force-graded ACTIONABLE (the lie guard)', () => {
    const bad = omegaConformance(synth, 'ACTIONABLE');
    expect(bad.conformant).toBe(false);
    expect(bad.violations.join(' ')).toMatch(/synthetic-only evidence graded above SEEDED/);
  });

  it('conformance TRIPS when an admitted claim is force-graded below TRUSTED', () => {
    const bad = omegaConformance(real, 'SEEDED');
    expect(bad.conformant).toBe(false);
    expect(bad.violations.join(' ')).toMatch(/admitted GAIA claim graded below TRUSTED/);
  });
});
