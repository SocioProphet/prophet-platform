import { describe, it, expect } from 'vitest';
import { claimBundle, claimToFeature, fnv1a } from '../gaia/exportClaims';
import { realWorldClaim, syntheticWorldClaim, acsIncomeEvidence } from '../gaia/worldClaim';

const real = realWorldClaim({ cellId: 'a', lon: -73.98, lat: 40.75, claimType: 'observation_passthrough', value: { medianIncome: 82000 }, source: acsIncomeEvidence('a') });
const synth = syntheticWorldClaim({ cellId: 'b', lon: -73.9, lat: 40.7, claimType: 'feature_classification', value: { crimeRate: 40 }, metricLabel: 'crime' });

describe('governed world-claim export', () => {
  it('serializes a claim to a GeoJSON feature with policy + Ω + sources', () => {
    const f = claimToFeature(real);
    expect(f.type).toBe('Feature');
    expect(f.properties.policy_status).toBe('admitted');
    expect(f.properties.omega).toBe('ACTIONABLE');
    expect(f.properties.sources).toEqual(['census_acs:US Census Bureau ACS 5-year + TIGERweb']);
    expect(f.properties.h3).toBe('a');
  });

  it('builds a self-describing bundle with counts, sources, and a fingerprint', () => {
    const b = claimBundle([real, synth], '2026-07-08T00:00:00Z');
    expect(b.schema).toBe('gaia.world_claim.v1+geojson');
    expect(b.count).toBe(2);
    expect(b.admitted).toBe(1); // only the real claim is admitted
    expect(b.sources).toContain('US Census Bureau ACS 5-year + TIGERweb');
    expect(b.content_fingerprint).toMatch(/^fnv1a:[0-9a-f]{8}$/);
    expect(b.features).toHaveLength(2);
  });

  it('fingerprint is deterministic and change-sensitive', () => {
    expect(fnv1a('abc')).toBe(fnv1a('abc'));
    expect(fnv1a('abc')).not.toBe(fnv1a('abd'));
  });
});
