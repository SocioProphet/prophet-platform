// Pure predicates for the connector proof harness (verify.ts) — split out so they're unit-testable
// without executing verify.ts itself (which runs every connector and calls process.exit()).
//
// Copilot #938: verify.ts asserted `!!(r.epistemic || r.provenance)`, two lines after already
// asserting `!!r.provenance` unconditionally. Since every record that reaches that point has
// ALREADY been proven to carry provenance, the `|| r.provenance` branch is always true — the
// assertion could never fail, regardless of whether `r.epistemic` (a REQUIRED field per data.ts:
// Observation/Condition/Medication/... all declare `epistemic: EpistemicMode`) was actually set.
// It read as a real gate on the epistemic tier and gated nothing.
//
// `epistemic` tracks HOW a record was normalized (verified/attested/observed) — a different axis
// from `provenance`, which tracks WHERE it came from. A connector that stamps provenance but
// forgets to set epistemic is exactly the regression this check exists to catch.
export function carriesEpistemicTier(r: { epistemic?: unknown }): boolean {
  return typeof r.epistemic === 'string' && r.epistemic.length > 0;
}
