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
const c = openConsult(sampleBundle, 'cardiovascular');
ok(identifierLeaks(c.slice).length === 0, 'the consult slice reviewers see is de-identified');
const op = submitOpinion(c.consult_id, 'reviewer-A', 'Consistent with early hypertension; monitor.', 'moderate');
ok('tier' in op && (op as any).tier === 'hypothesis', 'a submitted opinion attaches as tier=hypothesis (not verified/attested)');
submitOpinion(c.consult_id, 'reviewer-B', 'Consistent with early hypertension; monitor.', 'high');
submitOpinion(c.consult_id, 'reviewer-C', 'Prefer secondary workup before labeling.', 'moderate');
const agg = aggregate(c.consult_id) as any;
ok(agg.blind === true && /not a diagnosis/i.test(agg.disclaimer), 'aggregate is blinded + framed as not a diagnosis');
ok(['insufficient', 'unanimous', 'majority', 'split'].includes(agg.concordance.verdict), `concordance verdict computed (${agg.concordance.verdict}, agreement ${agg.concordance.agreement})`);
ok(agg.opinions.every((o: any) => o.tier === 'hypothesis'), 'all aggregated opinions remain hypotheses');

console.log(`\n${fails === 0 ? '✓ ALL GUARDRAIL INVARIANTS HOLD (non-diagnostic + de-identification enforced)' : `✗ ${fails} invariant(s) violated`}`);
process.exit(fails === 0 ? 0 : 1);
