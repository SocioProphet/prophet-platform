// The ingestion pipe — consume side. When GAIA's world_claim_ingest pipeline
// produces a governed claim bundle (the same GeoJSON + manifest our export emits),
// the cockpit reads it back in HERE: parse → verify the content fingerprint →
// hold the claims for the map to consume. This closes the loop (export ↔ ingest)
// and is the client half of the real pipeline; the server producer can be wired
// later without touching this. Verification is real: a tampered bundle fails.
import { fnv1a, type ClaimBundle, type ClaimFeature } from './exportClaims';

export interface IngestResult {
  ok: boolean;
  bundle?: ClaimBundle;
  count: number;
  admitted: number;
  sources: string[];
  fingerprintValid: boolean;
  error?: string;
}

// Parse + validate a claim bundle from raw JSON (a file, a fetch, or the pipeline).
// Returns ok:false with a reason rather than throwing.
export function ingestClaimBundle(raw: unknown): IngestResult {
  const empty: IngestResult = { ok: false, count: 0, admitted: 0, sources: [], fingerprintValid: false };
  const b = raw as Partial<ClaimBundle> | null;
  if (!b || typeof b !== 'object') return { ...empty, error: 'not an object' };
  if (b.schema !== 'gaia.world_claim.v1+geojson') return { ...empty, error: `unexpected schema: ${String(b.schema)}` };
  if (!Array.isArray(b.features)) return { ...empty, error: 'missing features[]' };
  // Every feature must carry the governed properties — reject an ordinary GeoJSON.
  const bad = (b.features as ClaimFeature[]).find((f) => !f?.properties || typeof f.properties.policy_status !== 'string' || typeof f.properties.omega !== 'string');
  if (bad) return { ...empty, error: 'a feature is not a governed world-claim (missing policy_status/omega)' };
  // Re-derive the content fingerprint and compare — tampered features won't match.
  const expected = `fnv1a:${fnv1a(JSON.stringify(b.features))}`;
  const fingerprintValid = b.content_fingerprint === expected;
  const admitted = (b.features as ClaimFeature[]).filter((f) => f.properties.policy_status === 'admitted').length;
  return {
    ok: true,
    bundle: b as ClaimBundle,
    count: b.features.length,
    admitted,
    sources: Array.isArray(b.sources) ? b.sources : [],
    fingerprintValid,
  };
}

// Index ingested claims by their H3 cell for the map to consume (only admitted +
// fingerprint-valid claims are eligible to paint as truth).
export function indexIngestedByCell(res: IngestResult): Map<string, ClaimFeature> {
  const m = new Map<string, ClaimFeature>();
  if (!res.ok || !res.bundle || !res.fingerprintValid) return m;
  for (const f of res.bundle.features) {
    const h3 = f.properties.h3;
    if (typeof h3 === 'string' && f.properties.policy_status === 'admitted') m.set(h3, f);
  }
  return m;
}
