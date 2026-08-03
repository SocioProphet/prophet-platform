/**
 * connectors/verify.ts's per-record epistemic-tier check (Copilot #938).
 *
 * The bug this pins: verify.ts asserted `!!(r.epistemic || r.provenance)` two lines after
 * already asserting `!!r.provenance` unconditionally on the same record. Since every record
 * that reaches that line has ALREADY been proven to carry provenance, the `|| r.provenance`
 * branch is always true — the assertion could never fail no matter what `r.epistemic` was,
 * including missing entirely. `carriesEpistemicTier()` is the extracted, pure predicate now
 * used in its place: it must depend on `epistemic` alone.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { carriesEpistemicTier } from './connectors/recordProof.js';

test('a record with a real epistemic tier passes', () => {
  assert.equal(carriesEpistemicTier({ epistemic: 'verified' }), true);
});

test('a record missing epistemic fails even though it carries provenance — the exact regression', () => {
  // This is the case the pre-fix predicate `!!(r.epistemic || r.provenance)` could never catch:
  // r.epistemic is undefined, but r.provenance is truthy, so the OR made the whole thing truthy.
  const r = { provenance: { source: 'oura', uscdi: 'Observation', sourceShape: 'oura-v2' } };
  assert.equal(carriesEpistemicTier(r as { epistemic?: unknown }), false);
});

test('an empty-string epistemic also fails (a connector that sets the field to "" is still not tiered)', () => {
  assert.equal(carriesEpistemicTier({ epistemic: '' }), false);
});

test('a non-string epistemic fails', () => {
  assert.equal(carriesEpistemicTier({ epistemic: null }), false);
  assert.equal(carriesEpistemicTier({ epistemic: undefined }), false);
});
