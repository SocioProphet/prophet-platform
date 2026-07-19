import { describe, it, expect } from 'vitest';
import { ingestClaimBundle, indexIngestedByCell } from '../gaia/claimStore';
import { claimBundle } from '../gaia/exportClaims';
import { realWorldClaim, syntheticWorldClaim, acsIncomeEvidence } from '../gaia/worldClaim';

const real = realWorldClaim({ cellId: '8a1', lon: -73.98, lat: 40.75, claimType: 'observation_passthrough', value: { medianIncome: 82000 }, source: acsIncomeEvidence('8a1') });
const synth = syntheticWorldClaim({ cellId: '8a2', lon: -73.9, lat: 40.7, claimType: 'feature_classification', value: { crimeRate: 40 }, metricLabel: 'crime' });
const bundle = claimBundle([real, synth], '2026-07-08T00:00:00Z');

describe('GAIA ingestion pipe (export ↔ ingest round-trip)', () => {
  it('ingests our own exported bundle and validates its fingerprint', () => {
    const r = ingestClaimBundle(JSON.parse(JSON.stringify(bundle)));
    expect(r.ok).toBe(true);
    expect(r.count).toBe(2);
    expect(r.admitted).toBe(1);
    expect(r.fingerprintValid).toBe(true);
  });

  it('detects tampering — a mutated feature fails the fingerprint check', () => {
    const tampered = JSON.parse(JSON.stringify(bundle));
    tampered.features[0].properties.value = { medianIncome: 999999 }; // someone edited a real claim
    const r = ingestClaimBundle(tampered);
    expect(r.ok).toBe(true);           // still parses
    expect(r.fingerprintValid).toBe(false); // but integrity fails
  });

  it('rejects a plain GeoJSON that is not a governed bundle', () => {
    expect(ingestClaimBundle({ type: 'FeatureCollection', features: [{ type: 'Feature', geometry: null, properties: { name: 'x' } }] }).ok).toBe(false);
    expect(ingestClaimBundle({ schema: 'gaia.world_claim.v1+geojson', features: 'x' }).ok).toBe(false);
    expect(ingestClaimBundle(null).ok).toBe(false);
  });

  it('indexes only admitted + fingerprint-valid claims by H3', () => {
    const r = ingestClaimBundle(JSON.parse(JSON.stringify(bundle)));
    const idx = indexIngestedByCell(r);
    expect(idx.has('8a1')).toBe(true);   // admitted real
    expect(idx.has('8a2')).toBe(false);  // synthetic/proposed — not truth
  });
});
