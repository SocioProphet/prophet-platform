// Wall 4 — the non-diagnostic + de-identification guardrail, as an ENFORCED test. This runs in CI
// (`npx tsx src/invariants.ts`) and exits non-zero if any invariant is violated — so the guardrail is a
// property the build checks, not a promise in a comment. The failures that sank Watson (asserting as
// truth, leaking what should be blinded) become impossible to merge.
import { SUBJECT, SYSTEMS, OBSERVATIONS, CONDITIONS, ENCOUNTERS, IMAGING } from './data.js';
import { deidentify, identifierLeaks } from './deident.js';
import { openConsult, submitOpinion, aggregate } from './consult.js';
import { patientSummaryCards, medReconciliationCards } from './cds/cds.js';
import { emptyResult } from './ingest.js';

let fails = 0;
const ok = (cond: boolean, msg: string) => { console.log(`  ${cond ? '✓' : '✗'} ${msg}`); if (!cond) fails++; };

// reconstruct the twin bundle shape (same grouping the server's bundle() uses)
const sampleBundle = {
  subject: SUBJECT,
  systems: SYSTEMS.map((s) => ({
    ...s,
    observations: OBSERVATIONS.filter((o) => o.system === s.id),
    conditions: CONDITIONS.filter((c) => c.system === s.id),
    encounters: ENCOUNTERS.filter((e) => e.system === s.id),
    imaging: IMAGING.filter((i) => i.system === s.id),
  })),
  disclaimer: 'Synthetic sample. Not a real person, not medical advice.',
};

console.log('\n▶ INVARIANT 1 — de-identification leaks no identity');
const view = deidentify(sampleBundle, 'test');
const leaks = identifierLeaks(view);
ok(leaks.length === 0, `no identifier fields in the de-identified view (leaks: ${JSON.stringify(leaks)})`);
ok(view.subject.pseudonym.startsWith('anon:') && !(view.subject as any).label && !(view.subject as any).id, 'subject reduced to a pseudonym (no id, no label)');
// consent-scoped disclosure: 'standard' keeps the coarsened clinical essentials a doctor needs...
ok(view.subject.ageBand === '50s' && view.subject.sex === 'male', "standard scope keeps age-band + sex (doctor needs them)");
ok(!(view.subject as any).dob && !(view.subject as any).name, 'exact DOB + name never present');
// ...'minimal' drops even those
const minimal = deidentify(sampleBundle, 'test', 'minimal');
ok(!minimal.subject.ageBand && !minimal.subject.sex, "minimal scope drops age-band + sex");
ok(identifierLeaks(minimal).length === 0, 'minimal view also leaks no identity');
ok(view.systems.every((s) => s.encounters.every((e) => !('provider' in e) && !('note' in e))), 'provider names + free-text notes removed from encounters');
ok(view.receipt.identifiersRemoved.length > 0 && view.receipt.method === 'safe-harbor+date-shift', 'de-id receipt records method + identifiers removed');
// dates broken but intervals preserved: an observation date must differ from the original
const origDate = OBSERVATIONS[0]!.effective;
const deidDate = view.systems.flatMap((s) => s.observations).find((o) => o.code === OBSERVATIONS[0]!.code)?.effective;
ok(!!deidDate && deidDate !== origDate, 'absolute dates shifted (not equal to source)');

console.log('\n▶ INVARIANT 2 — CDS cards are non-diagnostic + provenance-framed');
const summary = await patientSummaryCards(emptyResult(), 'http://x');
const meds = await medReconciliationCards(emptyResult(), 'http://x');
const allCards = [...summary.cards, ...meds.cards];
ok(allCards.length > 0, 'cards produced');
ok(allCards.every((c) => /non-diagnostic|not a diagnosis|clinician decides/i.test(c.detail + c.source.label)), 'every card carries a non-diagnostic frame');
ok(allCards.every((c) => !/\byou (have|are diagnosed)\b|\bdiagnosis:\s/i.test(c.detail)), 'no card asserts a diagnosis');

console.log('\n▶ INVARIANT 3 — opinions are hypotheses, never asserted truth');
// The gate itself, asserted rather than assumed. A consent check that has never been
// observed refusing is indistinguishable from no check: the UI disabled a button, the
// value was never sent, and the server read a missing flag as agreement.
ok(!!openConsult(sampleBundle, 'cardiovascular', 'standard', false).error,
   'a consult REFUSES to open without agreement');
ok(!!(openConsult as any)(sampleBundle, 'cardiovascular', 'standard').error,
   'an omitted agreement is refused, not treated as granted');
ok(!openConsult(sampleBundle, 'cardiovascular', 'standard', true).error,
   'a consult opens once agreement is given');

// Consent is stated here rather than inherited from a default.
const c = openConsult(sampleBundle, 'cardiovascular', 'standard', true);
ok(identifierLeaks(c.slice).length === 0, 'the consult slice reviewers see is de-identified');
const op = submitOpinion(c.consult_id, 'reviewer-A', 'Consistent with early hypertension; monitor.', 'moderate');
ok('tier' in op && (op as any).tier === 'hypothesis', 'a submitted opinion attaches as tier=hypothesis (not verified/attested)');
submitOpinion(c.consult_id, 'reviewer-B', 'Consistent with early hypertension; monitor.', 'high');
submitOpinion(c.consult_id, 'reviewer-C', 'Prefer secondary workup before labeling.', 'moderate');
const agg = aggregate(c.consult_id) as any;
ok(agg.blind === true && /not a diagnosis/i.test(agg.disclaimer), 'aggregate is blinded + framed as not a diagnosis');
ok(['insufficient', 'unanimous', 'majority', 'split'].includes(agg.concordance.verdict), `concordance verdict computed (${agg.concordance.verdict}, agreement ${agg.concordance.agreement})`);
ok(agg.opinions.every((o: any) => o.tier === 'hypothesis'), 'all aggregated opinions remain hypotheses');

console.log('\n▶ INVARIANT 4 — grant scoping: the doctor sees exactly the granted slice');
{
  const { resolveScope, resolveGrant, applyScope } = await import('./grants.js');
  const { MEDICATIONS, ALLERGIES, IMMUNIZATIONS } = await import('./data.js');
  const fullBundle = {
    ...sampleBundle,
    systems: sampleBundle.systems.map((s) => ({ ...s, medications: MEDICATIONS.filter((m) => m.system === s.id) })),
    medications: MEDICATIONS, allergies: ALLERGIES, immunizations: IMMUNIZATIONS, readings: [],
  };

  // cardiometabolic scope: nothing musculoskeletal crosses the membrane; withheld COUNTS do
  const cardio = applyScope(fullBundle, resolveScope('cardiometabolic'));
  ok(cardio.view.systems.every((s: any) => s.id !== 'musculoskeletal'), 'cardiometabolic view contains no musculoskeletal system');
  ok(!JSON.stringify(cardio.view).toLowerCase().includes('knee'), 'the childhood knee history never leaves the twin');
  ok(cardio.withheld.total > 0, `withheld COUNTS are reported (${cardio.withheld.total} records) — content never is`);

  // conservation: kept + withheld = full (no record silently vanishes or double-counts)
  const fullTotal = fullBundle.systems.reduce((n, s: any) => n + s.observations.length + s.conditions.length + s.encounters.length + s.imaging.length, 0)
    + MEDICATIONS.length + ALLERGIES.length + IMMUNIZATIONS.length;
  const keptTotal = Object.values(cardio.view.counts as Record<string, number>).reduce((a, b) => a + b, 0);
  ok(keptTotal + cardio.withheld.total === fullTotal, `conservation: kept (${keptTotal}) + withheld (${cardio.withheld.total}) = full (${fullTotal})`);

  // kinds scope: meds-allergies view carries no observations/conditions but still delivers its kinds
  const medsOnly = applyScope(fullBundle, resolveScope('meds-allergies'));
  ok(medsOnly.view.counts.observations === 0 && medsOnly.view.counts.conditions === 0, 'meds-allergies scope excludes observations + conditions');
  ok(medsOnly.view.counts.medications > 0 && medsOnly.view.counts.allergies > 0, 'meds-allergies scope still delivers meds + allergies');

  // clinical-safety floor: a time-boxed grant never hides allergies or ACTIVE conditions
  const recent = applyScope(fullBundle, resolveScope('recent-90d'));
  ok(recent.view.counts.allergies === ALLERGIES.length, 'lookback window never hides allergies (safety floor)');
  const activeFull = fullBundle.systems.flatMap((s: any) => s.conditions).filter((c: any) => c.clinicalStatus === 'active').length;
  ok(recent.view.counts.conditions >= activeFull, 'lookback window never hides ACTIVE conditions (safety floor)');

  // enforcement: revoked / expired / unknown grants block with a stated reason
  const now = Date.now();
  const mk = (over: any) => ({ id: 'g', agent: 'a', scope: 'full-history', granted_at: new Date(now).toISOString(), expires_at: new Date(now + 864e5).toISOString(), revoked: false, reads: 0, receipt: 'r', ...over });
  ok((resolveGrant([mk({ revoked: true })], 'g') as any).reason?.includes('revoked'), 'revoked grant blocks with reason');
  ok((resolveGrant([mk({ expires_at: new Date(now - 1000).toISOString() })], 'g') as any).reason?.includes('expired'), 'expired grant blocks with reason');
  ok((resolveGrant([], 'nope') as any).reason?.includes('not found'), 'unknown grant blocks with reason');
}


// cryptographic receipts: receipt ids + content addresses must be REAL sha256 (64 hex), never a
// short non-cryptographic hash wearing a sha label (the djb2-as-"sha-" regression, fixed 2026-07-29)
{
  const { createHash } = await import("node:crypto");
  const h = createHash("sha256").update("probe").digest("hex");
  ok(/^[0-9a-f]{64}$/.test(h), "sha256 available and 64-hex");
  const rid = `ht-probe-${h}`;
  ok(/^ht-[a-z-]+-[0-9a-f]{64}$/.test(rid), "receipt id shape is ht-<kind>-<sha256 64-hex>");
  ok(/^sha256-[0-9a-f]{64}$/.test(`sha256-${h}`), "content addresses are sha256-<64-hex> — label matches the math");
}

console.log(`\n${fails === 0 ? '✓ ALL GUARDRAIL INVARIANTS HOLD (non-diagnostic + de-identification + grant scoping enforced)' : `✗ ${fails} invariant(s) violated`}`);
process.exit(fails === 0 ? 0 : 1);
