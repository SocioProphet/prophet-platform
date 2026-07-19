import { describe, it, expect } from 'vitest';
import { realWorldClaim, syntheticWorldClaim, acsIncomeEvidence, claimToProvenance, isAdmitted, GAIA_V1_SOURCE_TYPES } from '../gaia/worldClaim';
import { tierOf } from '../features/provenance/types';

describe('GAIA WorldClaim contract', () => {
  const real = realWorldClaim({
    cellId: '8a2a', lon: -73.98, lat: 40.75, claimType: 'observation_passthrough',
    value: { medianIncome: 82000 }, source: acsIncomeEvidence('8a2a'),
  });
  const synth = syntheticWorldClaim({
    cellId: '8a2a', lon: -73.98, lat: 40.75, claimType: 'feature_classification',
    value: { crimeRate: 3.1 }, metricLabel: 'crime rate',
  });

  it('every claim satisfies the admissibility invariant shape (anchor + >=1 evidence + uncertainty + policy)', () => {
    for (const c of [real, synth]) {
      expect(c.geo_anchor.anchor_id).toBeTruthy();
      expect(c.source_evidence_refs.length).toBeGreaterThanOrEqual(1);
      expect(c.uncertainty.uncertainty_class).toBeTruthy();
      expect(c.policy_status.status).toBeTruthy();
      expect(c.attribution.license_refs.length).toBeGreaterThanOrEqual(1);
    }
  });

  it('real ACS income is admitted, low-uncertainty, and a truth layer', () => {
    expect(real.policy_status.status).toBe('admitted');
    expect(real.uncertainty.uncertainty_class).toBe('low');
    expect(isAdmitted(real)).toBe(true);
    expect(real.map_display?.display_layer).toBe('admitted_world_state');
  });

  it('synthetic data is proposed, high-uncertainty, display-advisory-only — never truth', () => {
    expect(synth.policy_status.status).toBe('proposed');
    expect(synth.uncertainty.uncertainty_class).toBe('high');
    expect(synth.policy_status.constraints).toContain('display-advisory-only');
    expect(isAdmitted(synth)).toBe(false);
    expect(synth.source_evidence[0]!.source_type).toBe('synthetic_fixture');
  });

  it('claimToProvenance projects admitted-real → grounded, synthetic → unassayed', () => {
    expect(tierOf(claimToProvenance(real)).verdict).toBe('grounded');   // retrieved → grounded
    expect(tierOf(claimToProvenance(synth)).verdict).toBe('unassayed'); // fixture → unassayed
  });

  it('flags census_acs as a local extension beyond the GAIA v1 source enum', () => {
    // Honesty guard: if a future dev thinks census is already canonical, this fails.
    expect(GAIA_V1_SOURCE_TYPES).not.toContain('census_acs');
    expect(acsIncomeEvidence('x').source_type).toBe('census_acs');
  });
});
