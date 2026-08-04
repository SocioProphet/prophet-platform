// Wall 4 — the non-diagnostic + de-identification guardrail, as an ENFORCED test. This runs in CI
// (`npx tsx src/invariants.ts`) and exits non-zero if any invariant is violated — so the guardrail is a
// property the build checks, not a promise in a comment. The failures that sank Watson (asserting as
// truth, leaking what should be blinded) become impossible to merge.
import { SUBJECT, SYSTEMS, OBSERVATIONS, CONDITIONS, ENCOUNTERS, IMAGING } from './data.js';
import { deidentify, identifierLeaks } from './deident.js';
import { openConsult, submitOpinion, aggregate, requestMore } from './consult.js';
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
// No cast needed: every parameter after `bundle` has a default, so omitting `agreed` is
// type-legal and exercises exactly the path a forgetful caller takes.
ok(!!openConsult(sampleBundle, 'cardiovascular', 'standard').error,
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


console.log('\n▶ INVARIANT 5 — receipts EMITTED by the real code paths are cryptographic');
// Receipt ids must be REAL sha256 (64 hex), never a short non-cryptographic hash wearing a
// sha label.
//
// The previous version of this block computed its OWN sha256, built its OWN string, and
// asserted that the string it had just built matched a regex. It proved that node can hash,
// and touched not one receipt this service emits — which is why it passed for the whole
// period consult.ts was still minting 8-hex djb2 ids under the same comment claiming the
// regression was fixed. An invariant that constructs its own subject cannot fail.
//
// These read the ids the code actually produces: openConsult, submitOpinion, aggregate.
{
  const consult = openConsult(sampleBundle, 'receipt-probe', 'standard', true);
  ok(/^consult-[0-9a-f]{64}$/.test(consult.consult_id ?? ''),
     `consult id is a real sha256 (${(consult.consult_id ?? '').slice(0, 24)}…)`);
  ok(/^ht-[a-z-]+-[0-9a-f]{64}$/.test(consult.receipt?.id ?? ''),
     'consult-open receipt id is ht-<kind>-<sha256 64-hex>');
  ok(/^ht-[a-z-]+-[0-9a-f]{64}$/.test(consult.consent?.receipt ?? ''),
     'consent receipt id is ht-<kind>-<sha256 64-hex>');

  const opinion = submitOpinion(consult.consult_id!, 'reviewer-probe', 'a read', 'moderate') as any;
  ok(/^op-[0-9a-f]{64}$/.test(opinion.id ?? ''), 'opinion id is a real sha256');
  ok(/^ht-[a-z-]+-[0-9a-f]{64}$/.test(opinion.receipt?.id ?? ''), 'opinion receipt id is a real sha256');

  const more = requestMore(consult.consult_id!, 'medication list', 'need the full list') as any;
  ok(/^more-[0-9a-f]{64}$/.test(more.id ?? ''), 'more-request id is a real sha256');

  // aggregate() mints its own receipt and re-publishes every opinion's receipt id; both are checked
  // on the value the function returns, not on a reconstruction of it.
  const probeAgg = aggregate(consult.consult_id!) as any;
  ok(/^ht-[a-z-]+-[0-9a-f]{64}$/.test(probeAgg.receipt?.id ?? ''),
     'consult-aggregate receipt id is a real sha256');
  ok(probeAgg.opinions.length > 0 && probeAgg.opinions.every((o: any) => /^ht-[a-z-]+-[0-9a-f]{64}$/.test(o.receipt)),
     'every opinion receipt republished by aggregate is a real sha256');

  // No id anywhere may be the old 8-hex djb2 shape. This is the check that would have caught
  // the miss: it runs over EMITTED ids, so a djb2 call site cannot hide behind a passing suite.
  const ids = [
    consult.consult_id, consult.receipt?.id, consult.consent?.receipt,
    opinion.id, opinion.receipt?.id, more.id, probeAgg.receipt?.id,
    ...probeAgg.opinions.map((o: any) => o.receipt),
  ];
  ok(ids.every((i) => !/-[0-9a-f]{8}$/.test(String(i))), 'no emitted id ends in an 8-hex (djb2) digest');
  ok(ids.every((i) => /-[0-9a-f]{64}$/.test(String(i))), `all ${ids.length} emitted ids carry a full 64-hex digest`);
}

console.log('\n▶ INVARIANT 6 — the record bundle is not served open once real records exist');
{
  const { exposureDenial, exposureFromEnv } = await import('./exposure.js');
  const open = { mode: 'synthetic-only' as const, token: '', authorization: '' };

  // The safety of the open endpoint rests entirely on the data being synthetic, so that is
  // the condition enforced. A twin holding real records must stop serving them openly on its
  // own, not when someone remembers to change a setting.
  ok(exposureDenial({ ...open, ingestedRecords: 0 }) === null,
     'synthetic twin (0 ingested records) serves the bundle');
  const withRecords = exposureDenial({ ...open, ingestedRecords: 1 });
  ok(withRecords?.code === 403,
     'ONE real ingested record stops the open bundle (403)');
  ok(String(JSON.stringify(withRecords?.body)).includes('remedy'),
     'the refusal states how to serve records legitimately, not just that it refused');

  // authenticated mode: the permissive state must be asserted, and asserting it without a
  // secret must fail closed rather than silently serving.
  const auth = { mode: 'authenticated' as const, ingestedRecords: 0 };
  ok(exposureDenial({ ...auth, token: '', authorization: 'Bearer anything' })?.code === 503,
     'authenticated mode with no token configured fails CLOSED (503), it does not serve');
  ok(exposureDenial({ ...auth, token: 's3cret', authorization: '' })?.code === 401,
     'no Authorization header is refused');
  ok(exposureDenial({ ...auth, token: 's3cret', authorization: 'Bearer wrong' })?.code === 401,
     'a wrong token is refused');
  ok(exposureDenial({ ...auth, token: 's3cret', authorization: 'Bearer s3cret' }) === null,
     'the configured token is accepted');
  ok(exposureDenial({ ...auth, token: 's3cret', authorization: 'Bearer  s3cret  ' }) === null,
     'surrounding whitespace does not defeat a correct token');
  // The back-ported hardening (platform #1086/#1109): the scheme is REQUIRED, not stripped when it
  // happens to be there, and the compare is constant-time. These pin the teeth so the canonical cannot
  // silently regress to the old `replace(/^Bearer\s+/i,'')` that authenticated a schemeless secret.
  ok(exposureDenial({ ...auth, token: 's3cret', authorization: 's3cret' })?.code === 401,
     'a schemeless credential is NOT a bearer credential — the strip-if-present defect is closed');
  ok(exposureDenial({ ...auth, token: 's3cret', authorization: 'Basic s3cret' })?.code === 401,
     'a non-Bearer scheme carrying the secret is refused, not compared as the string "Basic s3cret"');
  ok(exposureDenial({ ...auth, token: 's3cret', authorization: 'Bearer' })?.code === 401,
     'the scheme with no credential is refused');
  // and a real deployment still serves records under a token, which synthetic-only would refuse
  ok(exposureDenial({ mode: 'authenticated', token: 's3cret', authorization: 'Bearer s3cret', ingestedRecords: 500 }) === null,
     'authenticated mode serves real records — the gate is about governance, not about refusing work');

  // default is the safe one: anything but the explicit opt-in is synthetic-only
  ok(exposureFromEnv({} as NodeJS.ProcessEnv) === 'synthetic-only', 'default exposure is synthetic-only');
  ok(exposureFromEnv({ HEALTH_TWIN_EXPOSURE: 'yes' } as any) === 'synthetic-only', 'an unrecognised value is NOT treated as authenticated');
  ok(exposureFromEnv({ HEALTH_TWIN_EXPOSURE: 'authenticated' } as any) === 'authenticated', 'the explicit opt-in is honoured');
}

console.log('\n▶ INVARIANT 7 — twin dynamics: physics disposes, and a refusal is never silent');
{
  const { predict, COMPARTMENT_SYSTEM } = await import('./dynamics/predict.js');
  const { rejectionLedger, _clearLedger, RANGE, REJECTION_REASONS } = await import('./dynamics/gate.js');
  const { resolveGrant: resolveGrantDyn } = await import('./grants.js');

  // 7a. the learned term is a RESIDUAL: zero it and the physics comes back, bit for bit
  const zeroed = predict({ overrideDelta: () => 0 });
  ok(zeroed.organs.every((o) => o.emitted.every((v, i) => v === o.mechanistic[i])),
    'a zero learned correction leaves the mechanistic trajectory untouched (the surrogate is a residual, not a replacement)');

  // 7b. an inadmissible proposal is REJECTED — and the emitted value is the PHYSICS, not the bound.
  // A clamp would emit RANGE.cardio.lo here and look perfectly plausible. That is the silent-wrong
  // class this repo keeps finding, so it is an invariant, not a unit test.
  _clearLedger();
  const forced = predict({ compartments: ['cardio'], overrideDelta: () => -100 });
  const dec = forced.organs[0]!.decisions[0]!;
  ok(dec.verdict === 'rejected' && !!dec.reason, `an out-of-bounds proposal is rejected with a typed reason (${dec.reason})`);
  ok(REJECTION_REASONS.includes(dec.reason!), 'the rejection reason is from the declared taxonomy, never a bare string');
  ok(dec.emitted === dec.mechanistic, 'the emitted value is the mechanistic value');
  ok(dec.emitted !== RANGE.cardio.lo, `the emitted value is NOT the boundary (${RANGE.cardio.lo}) — no silent clamp`);
  ok(dec.clamped === false && !!dec.law && !!dec.bound, 'the decision records clamped:false plus the law and bound it broke');
  ok(forced.organs.every((o) => o.emissionAudit === 'ok'), 'the anti-clamp audit passes (every emitted value is the physics or the whole proposal)');
  ok(rejectionLedger().count === forced.gate.rejected && forced.gate.rejections.length === forced.gate.rejected,
    `every refusal is recorded — ledger ${rejectionLedger().count}, response ${forced.gate.rejections.length}`);

  // 7b-bis. divergence fails CLOSED. The body-state schema says a 'divergent' forward model must not
  // drive human actuation and cannot be promoted past TRUSTED; the gate emits that consequence itself.
  ok(forced.reconciliation.verdict === 'divergent', `a refused proposal makes the run 'divergent' (got '${forced.reconciliation.verdict}')`);
  ok(forced.reconciliation.executionDecision === 'deny' && forced.reconciliation.humanActuation === 'blocked' && forced.reconciliation.omegaCeiling === 'TRUSTED',
    'divergent denies actuation and caps omega at TRUSTED (body-state schema safety invariant)');

  // 7b-ter. THE VERDICT IS ONLY WORTH COMPUTING IF SOMETHING CONSULTS IT.
  // It was computed correctly, proven correctly, and never read on the request path: /api/health/predict
  // sent a 'deny' with 200 OK in a body shaped exactly like an allowed prediction. Two things are
  // invariants now — that the deny is reachable from ORDINARY CALLER INPUT (so this is a live path, not
  // a hypothetical), and that the verdict is BOUND INTO THE SEAL (so it cannot be flipped after the
  // fact). The HTTP status/shape half is asserted in the ci.yml boot smoke, against a real server.
  const { verifyPrediction } = await import('./dynamics/predict.js');
  const viaCovariates = predict({ covariates: { adherencePdc: 50, reninIndex: 50, bmi: 28.4, uacr: 0.18 } });
  ok(viaCovariates.reconciliation.executionDecision === 'deny',
    'caller-supplied covariates alone can drive the run to deny — the divergent path is reachable over HTTP, not just from the harness');
  ok(predict().reconciliation.executionDecision === 'allow',
    'teeth the other way: default covariates still produce an allowed prediction');
  const flipped = structuredClone(viaCovariates);
  flipped.reconciliation = { ...flipped.reconciliation, executionDecision: 'allow', humanActuation: 'permitted' };
  ok(!verifyPrediction(flipped), 'flipping deny→allow breaks the receipt — the safety verdict is sealed, not decorative');

  // 7b-quater. the anti-clamp audit is INSIDE the seal and predict() refuses rather than serving a clamp
  const clean = predict();
  ok(verifyPrediction(clean), 'a clean prediction verifies against its own receipt');
  const clampTampered = structuredClone(clean);
  (clampTampered.organs[0] as { emissionAudit: unknown }).emissionAudit = { violated: 'clamp', law: 'x', violations: [] };
  ok(!verifyPrediction(clampTampered),
    'a clamp violation perturbs the seal — "never clamps" is provable from the receipt, not just asserted in a comment');
  const { EmissionLawViolation } = await import('./dynamics/predict.js');
  let refusedClamp = false;
  try {
    predict({ compartments: ['cardio'], overrideDelta: () => -100, overrideDecisions: (_k, ds) => ds.map((d) => ({ ...d, emitted: RANGE.cardio.lo })) });
  } catch (e) { refusedClamp = e instanceof EmissionLawViolation; }
  ok(refusedClamp, 'a gate that clamps makes predict() fail CLOSED — the clamped number is never returned to a caller');

  // 7c. a prediction that can reach a patient-facing surface is PROVABLE and framed non-diagnostically
  const pred = predict();
  ok(/^ht-prediction-[0-9a-f]{64}$/.test(pred.receipt.id), 'a prediction carries a sha256 receipt id of the estate shape');
  ok(/^sha256-[0-9a-f]{64}$/.test(pred.receipt.snapshotDigest), 'the snapshot digest is sha256-<64 hex> (label matches the math)');
  ok(!!pred.provenance.mechanistic.model && !!pred.provenance.surrogate.coefficientsDigest && !!pred.provenance.gate.admissibilityDigest,
    'the receipt names WHICH mechanistic model, WHICH surrogate weights and WHICH gate policy produced it');
  ok(pred.provenance.surrogate.residualOnly === true && (pred.provenance.surrogate.fittedOn as any).synthetic === true,
    'the receipt declares the surrogate residual-only and its cohort synthetic');
  ok(/not a diagnosis/i.test(pred.disclaimer) && /not a medical device/i.test(pred.disclaimer), 'a prediction is framed non-diagnostically');
  ok(!/\byou (have|will develop|are diagnosed)\b/i.test(pred.disclaimer), 'the prediction frame asserts nothing about the person');

  // 7d. the prediction surface honours the SAME consent membrane as the record — a compartment outside
  // the grant is not reachable through the forecast side door.
  const cardioOnly = { systems: ['cardiovascular'], kinds: 'all' as const, lookbackDays: null };
  const gDyn = { id: 'g-dyn', agent: 'a', scope: 'custom', granted_at: new Date().toISOString(), expires_at: new Date(Date.now() + 864e5).toISOString(), revoked: false, reads: 0, receipt: 'r', scopeSpec: cardioOnly };
  const resolvedDyn = resolveGrantDyn([gDyn as any], 'g-dyn');
  const allowedDyn = (['cardio', 'hepatic', 'renal'] as const).filter((k) => cardioOnly.systems.includes(COMPARTMENT_SYSTEM[k]));
  ok(resolvedDyn.ok === true && allowedDyn.length === 1 && allowedDyn[0] === 'cardio',
    'a cardiovascular-only grant admits exactly the cardio compartment (hepatic + renal stay outside)');

  // 7e. THE REJECTION LEDGER IS RECORD CONTENT, AND IT IS SCOPED LIKE ONE.
  // Every entry carries mechanistic / proposed / delta / emitted — the person's own trajectory in
  // mmHg, % and mL/min. The endpoint shipped ungated and unscoped, so a clinician refused the renal
  // forecast at /predict could have reconstructed it by reading the refusals instead. Scoping the
  // ledger closes that side door, and the count and histogram are recomputed over the scoped set —
  // a total taken across the whole ledger would itself disclose that out-of-scope refusals happened.
  _clearLedger();
  predict({ overrideDelta: () => -100 });               // force refusals in ALL THREE compartments
  const full = rejectionLedger(500);
  const scoped = rejectionLedger(500, ['cardio']);
  ok(full.rejections.some((r) => r.compartment === 'renal') && full.rejections.some((r) => r.compartment === 'hepatic'),
    `the unscoped ledger holds every compartment (${full.count} refusals across ${new Set(full.rejections.map((r) => r.compartment)).size} organs)`);
  ok(scoped.rejections.every((r) => r.compartment === 'cardio'),
    'a cardio-scoped ledger read returns cardio entries ONLY — the renal trajectory is not readable through the refusals');
  ok(scoped.count === scoped.rejections.length && scoped.count < full.count,
    `the scoped count is recomputed over the scoped set (${scoped.count} of ${full.count}), not leaked as a whole-ledger total`);
  ok(Object.values(scoped.byReason).reduce((a, b) => a + b, 0) === scoped.count,
    'the scoped reason histogram sums to the scoped count — no out-of-scope refusal is counted');
  // and the values really are record content, so the scoping is load-bearing rather than tidy
  ok(full.rejections.every((r) => typeof r.mechanistic === 'number' && typeof r.emitted === 'number'),
    'a ledger entry does carry physiological values (which is WHY it is gated and scoped)');
  _clearLedger();

  // 7f. DECLARED == ENFORCED. RULES is served verbatim at GET /api/health/dynamics as inspectable
  // policy, so a rule whose text names a different quantity than the code reads is a documented lie
  // on a PHI surface. The renal bound said `previousAccepted` while the gate read `previousEmitted`.
  const { RULES } = await import('./dynamics/gate.js');
  const renalMono = RULES.find((r) => r.reason === 'monotonicity' && r.compartments.includes('renal'))!;
  ok(/previousEmitted/.test(renalMono.bound) && !/previousAccepted/.test(renalMono.bound),
    `the renal monotonicity bound names the quantity the gate actually reads (${renalMono.bound})`);
  ok(RULES.every((r) => !/previousAccepted/.test(r.bound)),
    'no published rule bound names a quantity the gate does not read');
}

console.log('\n▶ INVARIANT 8 — the de-identification boundary is cryptographic AND honestly labelled');
// deident.ts derived the pseudonym over PHI with 32-bit djb2. That is a re-identification risk,
// not merely a receipt-integrity one, so the derivation is asserted on real deidentify() output.
{
  const v = deidentify(sampleBundle, 'deid-probe');
  ok(/^anon:[0-9a-f]{32}$/.test(v.receipt.pseudonym),
     `pseudonym is anon: + 32 hex / 128 bits (${v.receipt.pseudonym})`);
  ok(!/^anon:[0-9a-f]{8}$/.test(v.receipt.pseudonym), 'pseudonym is NOT the old 8-hex djb2 token');
  ok(v.subject.pseudonym === v.receipt.pseudonym, 'the view and its receipt carry the same pseudonym');

  // deterministic within a scope, unlinkable across scopes — both on real output
  ok(deidentify(sampleBundle, 'deid-probe').receipt.pseudonym === v.receipt.pseudonym,
     'same subject + same salt → same pseudonym (stable within a consult)');
  ok(deidentify(sampleBundle, 'other-scope').receipt.pseudonym !== v.receipt.pseudonym,
     'a different salt → a different pseudonym (consults stay unlinkable)');

  // date shift: in range, and exercising enough salts that a BigInt-precision regression shows up.
  // parseInt over >13 hex digits silently rounds past 2^53 and collapses the low bits, so a broken
  // derivation reaches only a few distinct values instead of spreading across the window.
  const shifts = Array.from({ length: 400 }, (_, i) => deidentify(sampleBundle, `s${i}`).receipt.dateShiftDays);
  ok(shifts.every((d) => Number.isInteger(d) && d >= -183 && d <= 182), 'every date shift is an integer in [-183, +182]');
  ok(new Set(shifts).size > 200, `date shift spreads across the window (${new Set(shifts).size} distinct over 400 salts — a parseInt precision loss collapses this)`);

  // domain separation: the shift must not be recoverable from the pseudonym. If both derivations
  // shared one digest, deriving the shift FROM the pseudonym would reproduce it every time; with
  // separation, all 8 agreeing is a (1/366)^8 event.
  const allMatch = Array.from({ length: 8 }, (_, i) => `sep${i}`).every((salt) => {
    const view = deidentify(sampleBundle, salt);
    const fromPseudonym = Number(BigInt(`0x${view.receipt.pseudonym.slice(5, 21)}`) % 366n) - 183;
    return fromPseudonym === view.receipt.dateShiftDays;
  });
  ok(!allMatch, 'date shift is domain-separated from the pseudonym (not derivable from it)');

  // The receipt must not claim a protection the run did not have. Both branches are exercised so
  // a receipt hard-coded to keyed:true — the failure mode that matters — cannot pass.
  const KEY = 'HEALTH_TWIN_DEID_KEY';
  const saved = process.env[KEY];
  // try/finally: this block mutates a process-wide variable that changes how PHI is de-identified.
  // Restoring it only on the happy path would leave every later invariant running under a key state
  // it did not choose, and a de-id failure would then be attributed to the wrong cause.
  try {
    delete process.env[KEY];
    const unkeyed = deidentify(sampleBundle, 'deid-probe');
    ok(unkeyed.receipt.keyed === false && unkeyed.receipt.derivation === 'sha256',
       'with no key configured the receipt declares keyed:false / sha256 — it does not overstate');
    process.env[KEY] = 'invariant-test-key-32-bytes-long';
    const keyed = deidentify(sampleBundle, 'deid-probe');
    ok(keyed.receipt.keyed === true && keyed.receipt.derivation === 'hmac-sha256',
       'with a key configured the receipt declares keyed:true / hmac-sha256');
    ok(keyed.receipt.pseudonym !== unkeyed.receipt.pseudonym,
       'the key actually enters the derivation (keyed pseudonym ≠ unkeyed pseudonym)');

    // A DEGENERATE KEY MUST NOT BUY THE keyed:true LABEL.
    // The receipt's only job is to never overstate protection. The key is there to close the
    // guessing attack; a one-character or whitespace key does not close it, so stamping
    // keyed:true / hmac-sha256 for one would tell a reader the view is protected when it is not.
    // Such a key is refused and the run falls back to the honest unkeyed path.
    for (const weak of [' ', 'x', 'short', '\t\n', 'fifteen-bytes!']) {
      process.env[KEY] = weak;
      const r = deidentify(sampleBundle, 'deid-probe').receipt;
      ok(r.keyed === false && r.derivation === 'sha256',
         `a ${Buffer.byteLength(weak)}-byte key is refused, not reported as protection (${JSON.stringify(weak)} → keyed:${r.keyed})`);
      ok(r.pseudonym === unkeyed.receipt.pseudonym,
         `a refused key really is unused — the pseudonym is the unkeyed one (${JSON.stringify(weak)})`);
    }
    // and the boundary is where it says it is: 16 bytes is accepted
    process.env[KEY] = 'sixteen-bytes-16';
    const atMin = deidentify(sampleBundle, 'deid-probe').receipt;
    ok(Buffer.byteLength('sixteen-bytes-16') === 16 && atMin.keyed === true && atMin.derivation === 'hmac-sha256',
       'a key at the 16-byte minimum IS accepted (the floor is a floor, not a moving refusal)');
  } finally {
    if (saved === undefined) delete process.env[KEY]; else process.env[KEY] = saved;
  }

  // ── THE DATE SHIFT FAILS CLOSED ───────────────────────────────────────────────────────────────
  // shiftDate() returned anything it could not parse UNCHANGED, so a malformed-but-meaningful date
  // ('2024-13-45') survived UNSHIFTED into a view whose receipt claims 'safe-harbor+date-shift'.
  // Asserted on real deidentify() OUTPUT: calling the helper directly, or checking a hand-built
  // string, would leave the actual data path unproven — which is exactly how consult.ts went on
  // shipping 8-hex ids underneath a passing invariant.
  const WELL_FORMED = ['2024-01-15', '2024-01', '2024-01-15T10:30:00Z'];
  const YEAR_ONLY = ['2024'];
  // Same Copilot-round-2 finding as prophet-platform#1095: the absent branch admits
  // three shapes — '', undefined, and null — and the invariant probe must exercise
  // each; a probe that only asserts '' and undefined leaves the null path unverified
  // even though the branch handles it.
  const ABSENT: (string | undefined | null)[] = ['', undefined, null];
  // malformed, and none of it a date: month 13 / day 45, a real-looking impossible day, a
  // non-ISO ordering, prose, whitespace, and all-zeroes.
  const GARBAGE = ['not-a-date', '2024-13-45', '2024-02-30', '15/01/2024', 'yesterday', '   ', '0000-00-00'];
  const ALL = [...WELL_FORMED, ...YEAR_ONLY, ...ABSENT, ...GARBAGE];
  const dateBundle = {
    subject: { id: 'date-probe' },
    systems: [{
      id: 'sys', label: 'Sys', organs: [],
      observations: ALL.map((d, i) => ({
        code: `C${i}`, codeSystem: 'LOINC', display: `case ${i}`, value: 1, unit: 'x',
        effective: d, epistemic: 'measured',
      })),
      conditions: [], encounters: [], imaging: [],
    }],
  };
  const dv = deidentify(dateBundle, 'date-probe');
  const emitted = dv.systems[0].observations.map((o: any) => o.effective);

  // THE INVARIANT: no unparseable input survives as itself.
  const survivors = GARBAGE.filter((g) => emitted.includes(g));
  ok(survivors.length === 0,
     `no unparseable date survives as itself through deidentify() (survivors: ${JSON.stringify(survivors)})`);
  // and what replaced it is the sentinel. The LITERAL, not the imported constant: this string is a
  // wire contract a reader matches on, so a change to the constant's VALUE must fail here.
  const garbageOut = emitted.slice(WELL_FORMED.length + YEAR_ONLY.length + ABSENT.length);
  ok(garbageOut.every((v: unknown) => v === 'date-unshiftable'),
     `every unparseable date is replaced by the sentinel (${JSON.stringify(garbageOut)})`);

  // A bare year is an EXPLICIT ALLOW — Safe Harbor permits year granularity — not a parse failure.
  ok(emitted[WELL_FORMED.length] === '2024', 'a bare year passes through unshifted (Safe Harbor permits it)');
  ok(WELL_FORMED.every((_, i) => /^\d{4}-\d{2}-\d{2}$/.test(emitted[i]) && emitted[i] !== WELL_FORMED[i]),
     `every well-formed date was actually shifted (${JSON.stringify(emitted.slice(0, WELL_FORMED.length))})`);

  // The receipt must not overstate what was de-identified: every date field is counted in exactly
  // one branch, and the branches sum to the number of fields that went in.
  const dc = dv.receipt.dates;
  ok(dc.shifted === WELL_FORMED.length && dc.yearOnly === YEAR_ONLY.length
     && dc.absent === ABSENT.length && dc.unshiftable === GARBAGE.length,
     `receipt counts each branch exactly (${JSON.stringify(dc)})`);
  ok(dc.shifted + dc.yearOnly + dc.absent + dc.unshiftable === ALL.length,
     `receipt accounts for all ${ALL.length} date fields — none silently uncounted`);
  ok(dc.unshiftable > 0,
     'a view containing unshiftable dates says so on its receipt rather than claiming a clean shift');

  // TIMEZONE STABILITY. The shift is whole days on a UTC instant, so the same input must give the
  // same output in every zone. The previous implementation parsed date-only strings as UTC midnight
  // and then advanced them with LOCAL-time setDate: the two offsets cancel only when none of the
  // shift crosses a DST transition, so under America/Los_Angeles '2024-01-15' +88d came out a day
  // early. Several salts are exercised precisely so that some shifts DO cross a transition.
  const ZONES = ['UTC', 'America/Los_Angeles', 'Pacific/Kiritimati', 'Asia/Kolkata'];
  const savedTZ = process.env.TZ;
  // try/finally for the same reason the key block uses one: TZ is process-wide, and leaving it set
  // would silently re-time every invariant that runs after this.
  try {
    const perZone = ZONES.map((tz) => {
      process.env.TZ = tz;
      return JSON.stringify(Array.from({ length: 12 }, (_, i) => {
        const v = deidentify(dateBundle, `tz-salt-${i}`);
        return [v.receipt.dateShiftDays, v.systems[0].observations.map((o: any) => o.effective)];
      }));
    });
    ok(new Set(perZone).size === 1,
       `the de-identified dates are identical in ${ZONES.join(', ')} (a local-time shift diverges across a DST edge)`);
  } finally {
    if (savedTZ === undefined) delete process.env.TZ; else process.env.TZ = savedTZ;
  }

  // INTERVALS SURVIVE — the property the whole date-shift exists to preserve. The local-time bug
  // broke this too: only the endpoint on the far side of a DST edge moved, so a real 152-day gap
  // came back as 153 under LA.
  const gapBundle = (id: string) => ({
    subject: { id }, systems: [{ id: 'sys', label: 'Sys', organs: [],
      observations: ['2024-01-15', '2024-06-15'].map((d, i) => ({
        code: `G${i}`, codeSystem: 'LOINC', display: `g${i}`, value: 1, unit: 'x', effective: d, epistemic: 'measured' })),
      conditions: [], encounters: [], imaging: [] }],
  });
  const gapsHold = Array.from({ length: 12 }, (_, i) => {
    const o = deidentify(gapBundle('gap'), `gap-${i}`).systems[0].observations;
    return Math.round((Date.parse(o[1].effective) - Date.parse(o[0].effective)) / 86_400_000);
  }).every((g) => g === 152);
  ok(gapsHold, 'a 152-day interval is still 152 days after shifting (intervals are what the shift must preserve)');
}

console.log('\n▶ INVARIANT 9 — a grant id is not a credential: the holder is authenticated, both ways');
{
  const {
    authenticateHolder, holderDigest, holderToken, mintHolderSecret, parseHolderToken,
    presentedHolderToken, seedGrantDecision, legacyQueryDecision,
    HOLDER_AUTH_DISCLOSURE, HOLDER_FAILED, HOLDER_HEADER, HOLDER_REQUIRED,
  } = await import('./grantauth.js');

  const secret = mintHolderSecret();
  const bound = { id: 'grant-bound', holderDigest: holderDigest(secret) };
  const unbound = { id: 'grant-legacy' }; // minted before holder binding existed
  const find = (id: string) => [bound, unbound].find((g) => g.id === id);

  // ── THE DEFECT: possession of the id must not be enough ────────────────────────────────────────
  const leakedIdOnly = authenticateHolder({ presented: bound.id, find });
  ok(leakedIdOnly.ok === false, 'a leaked grant id ALONE does not authenticate (the id is not a credential)');
  const wrongSecret = authenticateHolder({ presented: holderToken(bound.id, mintHolderSecret()), find });
  ok(wrongSecret.ok === false, 'the right id with the wrong secret is refused');
  const noCredential = authenticateHolder({ presented: '', find });
  ok(noCredential.ok === false && (noCredential as any).reason === HOLDER_REQUIRED && (noCredential as any).reason !== HOLDER_FAILED,
     'presenting nothing at all is refused, and told how to present (a usage error, not a failed attempt)');
  ok(authenticateHolder({ presented: holderToken(unbound.id, secret), find }).ok === false,
     'a grant carrying NO holder binding authenticates nobody — it fails closed, it does not get a legacy pass');

  // ── AND THE OTHER WAY: the real holder still gets in ───────────────────────────────────────────
  const good = authenticateHolder({ presented: holderToken(bound.id, secret), find });
  ok(good.ok === true && good.holderDigest === bound.holderDigest,
     'the holder of the minted secret IS authenticated (a gate that refuses everyone is equally broken)');

  // no enumeration oracle: "wrong secret" and "no such grant" are indistinguishable to a caller who
  // has just failed to authenticate. Otherwise this endpoint answers "which grant ids are real?".
  const unknownId = authenticateHolder({ presented: holderToken('grant-does-not-exist', secret), find });
  ok(unknownId.ok === false && (unknownId as any).reason === (wrongSecret as any).reason
     && (unknownId as any).detail === undefined && (wrongSecret as any).detail === undefined,
     `unknown id and wrong secret give the identical refusal ("${(unknownId as any).reason}") — no id-enumeration oracle`);

  // the secret is never written down, and the digest is not the secret
  ok(!Object.values(bound).includes(secret) && bound.holderDigest !== secret, 'the grant stores a digest, never the secret');
  ok(/^sha256-[0-9a-f]{64}$/.test(bound.holderDigest), 'the holder verifier is sha256-<64 hex> — the label matches the math');
  ok(mintHolderSecret() !== mintHolderSecret() && Buffer.from(mintHolderSecret(), 'base64url').length === 32,
     'each minted secret is 256 fresh CSPRNG bits (not derived from the id, not guessable from another grant)');

  // token plumbing: ids contain dashes, secrets contain base64url — the split must survive both
  const parsed = parseHolderToken(holderToken('grant-abc-123', secret));
  ok(parsed?.grantId === 'grant-abc-123' && parsed?.secret === secret, 'a token round-trips through parse (split on the LAST dot)');
  ok(parseHolderToken('no-separator') === null && parseHolderToken('') === null && parseHolderToken('.x') === null,
     'a malformed token parses to null rather than to a half-credential');
  ok(presentedHolderToken({ [HOLDER_HEADER]: `  ${holderToken(bound.id, secret)}  ` }) === holderToken(bound.id, secret),
     'the header is read and trimmed');

  // the disclosure never overstates: this binds a secret-holder, NOT a verified identity
  ok(HOLDER_AUTH_DISCLOSURE.identityVerified === false,
     'the disclosure states identityVerified:false — it authenticates the holder of a secret, not a person');
  ok(!/\bverified (clinician|identity|person)\b/i.test(JSON.stringify(HOLDER_AUTH_DISCLOSURE)),
     'nothing in the disclosure claims a verified person');

  // ── the seed grant cannot exist in a production configuration ──────────────────────────────────
  ok(seedGrantDecision({} as NodeJS.ProcessEnv, 'synthetic-only').seed === false,
     'no demo grant is seeded by default (the hard-coded grant-seed-rivera is gone)');
  const fatal = seedGrantDecision({ HEALTH_TWIN_SEED_GRANT: '1' } as any, 'authenticated');
  ok(fatal.seed === false && !!fatal.fatal,
     'asking for the demo grant on an authenticated deployment is FATAL — the server refuses to boot, it does not warn');
  const seeded = seedGrantDecision({ HEALTH_TWIN_SEED_GRANT: '1' } as any, 'synthetic-only');
  ok(seeded.seed === true && !!seeded.secret && seeded.minted === true && !fatal.secret,
     'the demo grant on a synthetic deployment gets a secret MINTED at boot (never a literal in source)');
  ok(seedGrantDecision({ HEALTH_TWIN_SEED_GRANT: '1', HEALTH_TWIN_SEED_GRANT_SECRET: 'operator-supplied' } as any, 'synthetic-only').secret === 'operator-supplied',
     'an operator may supply the seed secret out of band (so CI can prove the positive case without scraping stdout)');

  // ── and the leak channel itself is off unless someone turns it on, and cannot be turned on in prod
  ok(legacyQueryDecision({} as NodeJS.ProcessEnv, 'synthetic-only').allowed === false,
     '?grant=<id> is refused by default — the credential does not travel in the request line');
  const legacyFatal = legacyQueryDecision({ HEALTH_TWIN_LEGACY_GRANT_QUERY: '1' } as any, 'authenticated');
  ok(legacyFatal.allowed === false && !!legacyFatal.fatal,
     'the legacy query form cannot be enabled on an authenticated deployment — that is also FATAL at boot');
  ok(legacyQueryDecision({ HEALTH_TWIN_LEGACY_GRANT_QUERY: '1' } as any, 'synthetic-only').allowed === true,
     'the synthetic demo may opt back in (deprecated, warned on every use)');

  // ── the source itself no longer carries a usable grant ─────────────────────────────────────────
  const { readFileSync } = await import('node:fs');
  const serverSrc = readFileSync(new URL('./server.ts', import.meta.url), 'utf8');
  ok(!serverSrc.includes('grant-seed-rivera'), 'the hard-coded grant-seed-rivera id is gone from server.ts');
  ok(!/holderDigest:\s*['"`]/.test(serverSrc) && !/HEALTH_TWIN_SEED_GRANT_SECRET\s*=\s*['"`][^'"`]/.test(serverSrc),
     'no holder secret or digest is a literal in server.ts');
}

console.log('\n▶ INVARIANT 10 — the credential is not usable from anywhere: origins, ids, and the bare-id rule');
{
  const { corsHeaders, corsPolicyFromEnv, isOrigin, originAllowed, DEV_ORIGINS } = await import('./cors.js');
  const { mintId, ID_PATTERN } = await import('./ids.js');
  const {
    bareIdPolicy, authenticateHolder, holderDigest, holderToken, mintHolderSecret,
    LEGACY_QUERY_REFUSAL, BODY_ID_REFUSAL, BOTH_FORMS_REFUSAL,
  } = await import('./grantauth.js');

  // ── CORS: `*` is not a value this service emits, and not one an operator can ask for ────────────
  // `access-control-allow-origin: *` alongside an allowed `x-health-grant` header let ANY page mint a
  // grant and read the chart cross-origin — the PR that introduced the credential also made it
  // usable by an attacker page. The allowlist is the fix; these prove it BOTH ways.
  const allowed = new Set(['https://cockpit.example']);
  const hit = corsHeaders('https://cockpit.example', allowed);
  const miss = corsHeaders('https://evil.example', allowed);
  const none = corsHeaders(undefined, allowed);
  ok(hit['access-control-allow-origin'] === 'https://cockpit.example',
     'an allowlisted origin is echoed EXACTLY (a gate that refuses everyone is equally broken)');
  ok(miss['access-control-allow-origin'] === undefined && none['access-control-allow-origin'] === undefined,
     'a foreign origin — and a caller with no Origin at all — gets no access-control-allow-origin');
  ok(!Object.values({ ...hit, ...miss, ...none }).includes('*'),
     'no response carries a wildcard origin, on a hit or a miss');
  ok(hit['vary'] === 'origin' && miss['vary'] === 'origin' && none['vary'] === 'origin',
     'every response varies on Origin — the reply depends on it, and a cache that does not know that leaks one origin’s allowance to another');
  ok(hit['access-control-allow-credentials'] === undefined,
     'credentials mode is never enabled: the holder credential is an explicit header, never ambient browser authority');
  ok(miss['access-control-allow-headers'] === undefined,
     `a refused origin is not even told it could have set the credential header`);
  ok(originAllowed('https://cockpit.example', allowed) && !originAllowed('', allowed) && !originAllowed('https://evil.example', allowed),
     'originAllowed() is true only for a named origin — an absent Origin is not a browser and is not "allowed"');

  const wildcard = corsPolicyFromEnv({ HEALTH_TWIN_ALLOWED_ORIGINS: 'https://ok.example,*' } as any, 'synthetic-only');
  ok(wildcard.origins.length === 0 && !!wildcard.fatal,
     'asking for `*` in HEALTH_TWIN_ALLOWED_ORIGINS is FATAL at boot — the defect cannot move from a line of code to a line of YAML');
  ok(!!corsPolicyFromEnv({ HEALTH_TWIN_ALLOWED_ORIGINS: 'https://ok.example/path' } as any, 'synthetic-only').fatal,
     'a value that is not an origin is fatal too — an allowlist entry that can never match is a silent outage');
  ok(corsPolicyFromEnv({} as NodeJS.ProcessEnv, 'authenticated').origins.length === 0,
     'an authenticated deployment allows NO browser origin unless one is named (the cockpit reaches it same-origin through nginx)');
  ok(corsPolicyFromEnv({} as NodeJS.ProcessEnv, 'synthetic-only').origins.every((o) => DEV_ORIGINS.includes(o)),
     'the synthetic-only default is the loopback dev origins and nothing wider');
  ok(corsPolicyFromEnv({ HEALTH_TWIN_ALLOWED_ORIGINS: 'https://a.example, https://b.example' } as any, 'authenticated').origins.length === 2,
     'a named allowlist is authoritative, in either mode');
  ok(corsPolicyFromEnv({ HEALTH_TWIN_ALLOWED_ORIGINS: '' } as any, 'synthetic-only').origins.length === 0,
     'an EMPTY HEALTH_TWIN_ALLOWED_ORIGINS means none — "no browser at all" has to be sayable, or the dev defaults come back on the deployment that just asked for none');
  ok(isOrigin('https://a.example') && isOrigin('http://127.0.0.1:5174')
     && !isOrigin('*') && !isOrigin('https://a.example/') && !isOrigin('a.example') && !isOrigin('https://*.example'),
     'an origin is `scheme://host[:port]` — no wildcard, no path, no trailing slash, no bare hostname');

  // ── ids are MINTED, not derived from their own published inputs ────────────────────────────────
  const ids = Array.from({ length: 5_000 }, () => mintId('grant'));
  ok(new Set(ids).size === ids.length,
     '5,000 ids minted in one tight loop are all distinct — the old sha256(agent|scope|ms) collided on 79% of 200 concurrent issues');
  ok(ids.every((i) => ID_PATTERN.test(i)) && ids[0]!.length === 'grant-'.length + 64,
     'every id is <prefix>-<64 hex> — 256 CSPRNG bits, the width the estate’s no-djb2 id ratchet already demands');
  {
    // The whole point: the published fields no longer determine the id.
    const { createHash } = await import('node:crypto');
    // Every millisecond a mint could plausibly have happened in, derived both ways the old code
    // might have joined its parts. None of them may hit a minted id. (The widths now match — a
    // 256-bit mint is 64 hex, same as a sha256 — so this compares VALUES, which is the actual claim.)
    const now = Date.now();
    const derived = new Set<string>();
    for (let t = now - 5_000; t <= now + 5_000; t++) {
      const parts = ['Dr. X', 'cardiometabolic', String(t)];
      derived.add(`grant-${createHash('sha256').update(parts.join('|')).digest('hex')}`);
      derived.add(`grant-${createHash('sha256').update(JSON.stringify(parts)).digest('hex')}`);
    }
    ok(ids.every((i) => !derived.has(i)),
       `an id is not recomputable from (agent, scope, granted_at) — ${derived.size.toLocaleString()} candidate derivations over a 10s window hit none of ${ids.length.toLocaleString()} minted ids; a grant listing is no longer a way to derive every id in it`);
  }

  // ── a bare id is refused wherever it arrives, and whatever else the request carries ────────────
  ok(bareIdPolicy({ channel: 'query', presented: false, legacyAllowed: false }).reason === LEGACY_QUERY_REFUSAL,
     '?grant=<id> alone is refused');
  ok(bareIdPolicy({ channel: 'query', presented: true, legacyAllowed: false }).refuse === true,
     '🔴 ?grant=<id> is refused EVEN WITH a valid holder credential — `bareId !== null && !presented` served those 200, left the id in the URL, and suppressed the deprecation warning');
  ok(bareIdPolicy({ channel: 'body', presented: false, legacyAllowed: false }).reason === BODY_ID_REFUSAL,
     'a bare id in the JSON body is refused too, and told why in its own words (a body is not logged; possession is still the whole authorization)');
  ok(bareIdPolicy({ channel: 'body', presented: true, legacyAllowed: false }).refuse === true,
     'a bare body id plus a credential is refused as well — one request, one answer to "which grant is this"');
  ok(bareIdPolicy({ channel: 'query', presented: false, legacyAllowed: true }).refuse === false
     && bareIdPolicy({ channel: 'query', presented: false, legacyAllowed: true }).warn === true,
     'the synthetic-only opt-in still works, and is warned on every use (a gate that refuses everyone is equally broken)');
  ok(bareIdPolicy({ channel: 'query', presented: true, legacyAllowed: true }).reason === BOTH_FORMS_REFUSAL,
     'even with the opt-in on, presenting BOTH forms is refused rather than silently preferring one');

  // ── the refusal costs the same whether or not the id exists ────────────────────────────────────
  // The body was already uniform; the CLOCK was the remaining oracle. Both halves are asserted: the
  // ledger is indexed (no scan) and the compare runs on every path (no early return on a miss).
  {
    // The two ids are the SAME LENGTH on purpose: an attacker picks the id, so a length difference
    // measures strlen on their own input and tells them nothing about the ledger. What must not vary
    // is the cost of the LOOKUP and the COMPARE. Interleaved runs, minimum taken — the minimum is the
    // run least disturbed by the scheduler, and a real oracle survives it.
    const KNOWN = 'grant-known-000000000000000000000000';
    const UNKNOWN = 'grant-nope--000000000000000000000000';
    const index = new Map([[KNOWN, { id: KNOWN, holderDigest: holderDigest(mintHolderSecret()) }]]);
    const find = (id: string) => index.get(id);
    const bench = (id: string, iters: number) => {
      for (let i = 0; i < 5_000; i++) authenticateHolder({ presented: `${id}.wrong-secret`, find });
      const t0 = process.hrtime.bigint();
      for (let i = 0; i < iters; i++) authenticateHolder({ presented: `${id}.wrong-secret`, find });
      return Number(process.hrtime.bigint() - t0);
    };
    //
    // SELF-CALIBRATING, because a shared CI runner's noise floor is not knowable in advance and a
    // fixed threshold is either flaky or meaningless. The same workload is benched twice to measure
    // what this machine's repeat-measurement error IS, and the known-vs-unknown difference then has
    // to sit inside that. This detects an ORDER-OF-MAGNITUDE tell — the array scan was 3,682% — and
    // is not claimed as a formal constant-time proof, which a JIT and a shared runner cannot give.
    const a: number[] = [], b: number[] = [], c: number[] = [];
    for (let r = 0; r < 5; r++) {
      a.push(bench(KNOWN, 20_000)); b.push(bench(UNKNOWN, 20_000)); c.push(bench(KNOWN, 20_000));
    }
    const exists = Math.min(...a), unknown = Math.min(...b), again = Math.min(...c);
    const rel = (x: number, y: number) => Math.abs(x - y) / Math.max(x, y);
    const noise = rel(exists, again);           // the same work, twice — pure measurement error
    const skew = rel(exists, unknown);          // the signal an attacker would be reading
    const budget = Math.max(0.25, noise * 2);
    ok(skew <= budget,
       `refusing a KNOWN id and an UNKNOWN id cost the same to within this machine's own noise ` +
       `(skew ${(skew * 100).toFixed(1)}%, noise floor ${(noise * 100).toFixed(1)}%, budget ${(budget * 100).toFixed(1)}%) — ` +
       `the response time is not an id-enumeration oracle (the ledger scan it replaced measured 3,682%)`);

    // Both halves of that, asserted in the source so a refactor cannot quietly reinstate either.
    // Comments are stripped first: this file's own prose names the thing it is forbidding.
    const src = (await import('node:fs')).readFileSync(new URL('./server.ts', import.meta.url), 'utf8')
      .replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
    ok(!/grants\.find\(/.test(src) && /grantIndex\.get\(/.test(src),
       'server.ts looks a grant up by index, not by walking the ledger (a scan costs a full pass on a miss and one comparison on a head hit: 54µs vs 1.4µs over 2,000 grants)');
    ok(!/['"`]access-control-allow-origin['"`]/.test(src),
       'server.ts sets no access-control-allow-origin of its own — cors.ts holds the only copy of the policy');
  }
}

console.log('\n▶ INVARIANT 11 — triage safety floor: a red flag never resolves to self-care');
{
  const { triage, URGENCY_RANK } = await import('./triage.js');

  // a classic emergency presentation escalates, regardless of anything reassuring in the text
  const cardiac = await triage('crushing chest pain radiating to my left arm, but I think I feel ok');
  ok(cardiac.urgency === 'emergency' && cardiac.disposition === 'escalate', 'chest pain radiating to arm → emergency + escalate');
  ok(cardiac.redFlags.some((r) => r.id === 'cardiac'), 'the cardiac red flag is surfaced');
  ok(/emergency/i.test(cardiac.care), 'the care line sends the person to emergency care');
  ok(cardiac.urgency !== 'self-care' && cardiac.urgency !== 'monitor', 'a red flag can NEVER band as self-care/monitor (the anti-Watson floor)');

  // negation must not trip the flag: "no chest pain" is not a cardiac emergency
  const negated = await triage('no chest pain, just a mild cough for a day');
  ok(!negated.redFlags.some((r) => r.id === 'cardiac'), 'negated chest pain does NOT trip the cardiac flag');
  ok(URGENCY_RANK[negated.urgency] < URGENCY_RANK['emergency'], 'a negated red flag is not an emergency');

  // stroke FAST signs escalate
  const stroke = await triage('sudden face drooping and slurred speech since an hour ago');
  ok(stroke.urgency === 'emergency' && stroke.redFlags.some((r) => r.id === 'stroke'), 'FAST stroke signs → emergency');

  // thin input abstains and asks the next-best question rather than guessing
  const thin = await triage('something feels off');
  ok(thin.disposition === 'abstain' && thin.nextBestQuestions.length > 0, 'a thin complaint abstains + asks the next-best question');

  // a minor complaint does not over-escalate
  const minor = await triage('small scrape on my knee from yesterday, mild, cleaned it');
  ok(minor.urgency === 'self-care' || minor.urgency === 'monitor', 'a minor injury bands self-care/monitor, not emergency');

  // every triage result is non-diagnostic and carries the disclaimer + an auditable loop trace
  ok(/not a diagnosis/i.test(cardiac.disclaimer), 'triage result is framed as not a diagnosis');
  ok(cardiac.loop.map((s) => s.step).join(',') === 'perceive,reason,act,verify', 'the Perceive→Reason→Act→Verify loop is traced');
}

console.log('\n▶ INVARIANT 12 — longitudinal monitor: deterioration is flagged, recovery is not');
{
  const { acuity, monitorTwin } = await import('./monitor.js');

  // out of range and moving further out → worsening/critical + escalate
  const worsening = acuity({ id: 'm', display: 'LDL cholesterol', value: 190, unit: 'mg/dL', refLow: 0, refHigh: 100, trend: [150, 165, 178, 190] });
  ok((worsening.band === 'worsening' || worsening.band === 'critical') && worsening.escalate, 'a metric moving further out of range → worsening/critical + escalate');

  // out of range but moving back toward it → improving, NOT escalated
  const improving = acuity({ id: 'm', display: 'LDL cholesterol', value: 130, unit: 'mg/dL', refLow: 0, refHigh: 100, trend: [190, 170, 150, 130] });
  ok(improving.band === 'improving' && !improving.escalate, 'a metric recovering toward range → improving, not escalated');

  // in range and flat → stable, not escalated
  const stable = acuity({ id: 'm', display: 'eGFR', value: 100, unit: 'mL/min', refLow: 90, refHigh: 120, trend: [101, 100, 100, 100] });
  ok(stable.band === 'stable' && !stable.escalate, 'an in-range flat metric → stable, not escalated');

  // low-adverse direction: eGFR falling below range → worsening (falling is bad for a high-is-good metric)
  const renalDrop = acuity({ id: 'm', display: 'eGFR', value: 55, unit: 'mL/min', refLow: 60, refHigh: 120, trend: [75, 68, 61, 55] });
  ok(renalDrop.escalate && renalDrop.adverse === 'low', 'falling eGFR below range is adverse-low and escalates (direction-aware)');

  const report = monitorTwin();
  ok(report.escalate === (report.deteriorating.length > 0), 'the report escalate flag agrees with its deteriorating list');
  ok(/non-diagnostic/i.test(report.disclaimer), 'the monitor report is framed as non-diagnostic');
}

console.log('\n▶ INVARIANT 13 — imaging report interpretation: critical-finding floor + non-diagnostic');
{
  const { interpretReport } = await import('./imaging.js');

  const acute = await interpretReport('CT head without contrast. Findings: acute intraparenchymal hemorrhage in the right frontal lobe.');
  ok(acute.escalate && (acute.urgency === 'emergency' || acute.urgency === 'urgent'), 'an acute hemorrhage finding floors urgency + escalates');
  ok(acute.modality === 'CT' && acute.bodySite === 'head', 'modality + body site are detected');
  ok(!/\byou (have|are diagnosed)\b|\bdiagnosis is\b/i.test(acute.plainLanguage) && /non-diagnostic/i.test(acute.disclaimer), 'the explanation asserts no diagnosis + carries a non-diagnostic disclaimer');

  const clean = await interpretReport('Chest X-ray PA and lateral. No acute cardiopulmonary process. No evidence of hemorrhage or mass. Impression: unremarkable.');
  ok(!clean.escalate && clean.criticalFlags.length === 0, 'a negated report ("no acute", "no evidence of hemorrhage/mass") does NOT trip the critical floor');

  ok((await interpretReport('MRI left knee: findings suspicious for a mass.')).escalate, 'a suspicious mass escalates');
}

console.log('\n▶ INVARIANT 14 — FHIR interop: valid R4, round-trips, and de-identified at the Patient level');
{
  const { toFhirBundle, fromFhirBundle } = await import('./fhir.js');
  const bundle = toFhirBundle();
  ok(bundle.resourceType === 'Bundle' && bundle.type === 'collection' && Array.isArray(bundle.entry), 'export is a valid FHIR R4 collection Bundle');
  ok(bundle.entry.every((e: any) => typeof e.resource?.resourceType === 'string'), 'every entry carries a resource with a resourceType');
  const patient = bundle.entry.find((e: any) => e.resource.resourceType === 'Patient')?.resource;
  ok(!!patient && !patient.name && !patient.birthDate, 'the Patient resource carries NO name and NO birthDate (de-identified)');
  const anObs = bundle.entry.find((e: any) => e.resource.resourceType === 'Observation')?.resource;
  ok(anObs?.code?.coding?.[0]?.system === 'http://loinc.org', 'observations carry the real LOINC code-system URI');

  // round-trip: export → import preserves observation + condition codes/values (no silent loss)
  const parsed = fromFhirBundle(bundle);
  ok(parsed.counts.observations === OBSERVATIONS.length && parsed.counts.conditions === CONDITIONS.length, 'export→import round-trips all observations + conditions');
  const ldl = parsed.observations.find((o) => o.code === OBSERVATIONS[0]!.code);
  ok(!!ldl && ldl.value === OBSERVATIONS[0]!.value && ldl.codeSystem === 'LOINC', 'a round-tripped observation preserves its value + code system');

  // foreign/partial bundles are tolerated: unmappable entries are counted, never silently dropped
  const foreign = fromFhirBundle({ resourceType: 'Bundle', entry: [{ resource: { resourceType: 'Practitioner', id: 'x' } }] });
  ok(foreign.counts.skipped === 1 && foreign.counts.observations === 0, 'an unmappable resource is counted as skipped, not dropped');
}

console.log('\n▶ INVARIANT 15 — professional reference: audience renderers + medication safety off one source');
{
  const { conditionCard, checkMeds } = await import('./reference.js');

  // audience rendering off the SAME source of truth: clinician gets citations + workup; patient does not
  const clin = conditionCard('hypertension', 'clinician') as any;
  const pat = conditionCard('hypertension', 'patient') as any;
  ok(!!clin.citations && !!clin.workup, 'the clinician card carries citations + workup');
  ok(!pat.citations && !pat.workup, 'the patient card omits citations/workup jargon (audience renderer)');
  ok(clin.snomed === pat.snomed && clin.name === pat.name, 'both renderers derive from one source of truth (same SNOMED + name)');
  ok(/non-diagnostic/i.test(pat.disclaimer) && /non-diagnostic/i.test(clin.disclaimer), 'cards are non-diagnostic');
  const trainee = conditionCard('hypertension', 'trainee') as any;
  ok(!!trainee.teaching, 'the trainee card adds a teaching overlay');

  // medication safety: a known interaction, an allergy conflict, and a duplicate are each flagged
  const interact = checkMeds([{ display: 'Lisinopril 10 MG' }, { display: 'Ibuprofen 400 MG' }]);
  ok(interact.interactions.some((i) => i.severity && /NSAID|ACEi/i.test(i.mechanism)), 'a lisinopril↔ibuprofen interaction is flagged');
  const allergyHit = checkMeds([{ display: 'Penicillin 500 MG' }], ['penicillin']);
  ok(allergyHit.allergyConflicts.length === 1, 'a med matching a documented allergy is flagged as a conflict');
  const dup = checkMeds([{ display: 'Lisinopril 10 MG' }, { display: 'Lisinopril 20 MG' }]);
  ok(dup.duplicates.length === 1, 'duplicate therapy (same ingredient twice) is flagged');
  ok(/non-diagnostic/i.test(interact.disclaimer), 'the med check is framed as non-diagnostic decision support');
}

console.log('\n▶ INVARIANT 16 — access + data economics: booking + contribution fail closed, only de-id data leaves');
{
  const { findSlots, book } = await import('./booking.js');
  const { contribute, revokeContribution } = await import('./contribution.js');
  const { identifierLeaks } = await import('./deident.js');

  // booking fails closed: an unknown slot never yields a booking (no silent success)
  ok('error' in book('nope'), 'booking an unknown slot is refused, not silently succeeded');
  const someSlot = findSlots().slots[0];
  ok(!!someSlot && !('error' in (book(someSlot.id) as any)), 'a real slot books');

  // contribution consent fails closed: no agreement → refused
  const refused = contribute('cardio-eval', sampleBundle, false) as any;
  ok(!!refused.error && /consent/i.test(refused.error), 'contribution without explicit consent is refused (fail-closed)');
  const missing = contribute('cardio-eval', sampleBundle) as any; // agreed omitted
  ok(!!missing.error, 'an omitted agreement is refused, not treated as consent');

  // a consented contribution ships only DE-IDENTIFIED data (leak check clean) + is revocable + accrues comp
  const joined = contribute('cardio-eval', sampleBundle, true) as any;
  ok(!joined.error && joined.consented === true && joined.leakCheck === 'clean', 'a consented contribution is accepted + leak-clean');
  ok(joined.compensation?.amount > 0 && joined.compensation?.status === 'accrued', 'compensation is transparently accrued');
  ok(revokeContribution(joined.id).revoked === true, 'a contribution is revocable');
  // the de-id boundary itself: minimal-scope contribution leaks no identifiers
  const { deidentify } = await import('./deident.js');
  ok(identifierLeaks(deidentify(sampleBundle, 'contrib|cardio-eval', 'minimal')).length === 0, 'the contributed slice leaks no identifiers');
}

console.log('\n▶ INVARIANT 17 — population layer: k-anonymity + aggregates only, never an individual record');
{
  const { populationRisk } = await import('./population.js');
  const report = populationRisk();

  // k-anonymity: every REPORTED cohort meets the floor; smaller cells are suppressed, not shown
  ok(report.cohorts.every((c: any) => c.n >= report.kAnonymity), 'every reported cohort has n ≥ the k-anonymity floor');
  ok(typeof report.suppressedCohorts === 'number', 'cohorts below the floor are counted as suppressed');

  // aggregates only: the wire shape carries counts/rates, NOT member records (no conditions[]/acuity per person)
  const wire = JSON.stringify(report);
  ok(!/"onStatin"|"ldlOverTarget"|"sex":/.test(wire), 'no per-member fields leak — the report is aggregates only');
  ok(report.cohorts.every((c: any) => typeof c.risingAcuityRate === 'number' && typeof c.statinCareGapRate === 'number'), 'cohorts carry rates, not rows');

  ok(/de-identified|aggregates only/i.test(report.disclaimer) && /not surveillance/i.test(report.disclaimer), 'the report is framed as de-identified aggregates, not surveillance');
  ok(!!report.receipt, 'the population read is receipted');
}

console.log('\n▶ INVARIANT 18 — triage is safe by MEASUREMENT: no missed emergency on the labeled corpus');
{
  const { evaluateTriage } = await import('./triage-eval.js');
  const r = await evaluateTriage();
  ok(r.emergencyRecall === 1, `emergency recall (sensitivity) is 100% — every labeled emergency escalates (got ${(r.emergencyRecall * 100).toFixed(1)}%)`);
  ok(r.emergencyUnderTriage === 0, `zero emergency under-triage — no emergency is banded below emergency (got ${r.emergencyUnderTriage})`);
  ok(r.overTriageRate <= 0.15, `over-triage stays low (safe-but-costly ≤15%; got ${(r.overTriageRate * 100).toFixed(1)}%)`);
}

console.log('\n▶ INVARIANT 19 — terminology value sets are bound UPWARD into Ontogenesis + HDT');
{
  const { VALUE_SETS, lookup, crosswalk, valueSetTtl, toOntogenesisNode } = await import('./terminology.js');
  const { HDT_NS, HEALTH_NS } = await import('./data.js');

  // every concept carries a real code + system + an ontogenesis/HDT class IRI (the upward bind)
  ok(VALUE_SETS.length >= 30 && VALUE_SETS.every((c: any) => c.code && c.system && c.classIri), `every concept carries a code + system + HDT class IRI (${VALUE_SETS.length} concepts)`);
  ok(VALUE_SETS.every((c: any) => c.classIri.startsWith(HDT_NS) || c.classIri.startsWith(HEALTH_NS)), 'every class IRI is an hdt:/health: ontology class (not a bare string)');
  ok(new Set(VALUE_SETS.map((c: any) => c.system)).size >= 3, 'value sets span multiple code systems (SNOMED/LOINC/RxNorm/ICD-10)');

  // observations bind to an organ (localizedTo) — they type onto anatomy in the twin
  const ldl = lookup({ system: 'LOINC', code: '13457-7' })!;
  ok(!!ldl && !!ldl.organ, 'a LOINC observation binds to an organ (localizedTo the twin anatomy)');
  const node = toOntogenesisNode(ldl);
  ok(!!node.iri && !!node.classIri && !!node.organIri && !!node.systemIri, 'a concept emits a typed Ontogenesis node with class + organ + system IRIs');

  // cross-terminology crosswalk resolves (SNOMED hypertension → ICD-10 I10)
  const cw = crosswalk('SNOMED', '38341003');
  ok(cw.maps.some((m: any) => m.system === 'ICD-10' && m.code === 'I10'), 'SNOMED essential hypertension crosswalks to ICD-10 I10');

  // the TTL is ontogenesis-consumable: SKOS concepts TYPED as their HDT class, with exactMatch links
  const ttl = valueSetTtl();
  ok(/a skos:Concept, <https?:[^>]+(Observation|Condition|Medication)>/.test(ttl), 'TTL types each concept as skos:Concept AND its HDT class');
  ok(/skos:exactMatch/.test(ttl) && /health:localizedTo/.test(ttl) && /health:inSystem/.test(ttl), 'TTL carries cross-maps + organ + system bindings for Ontogenesis/HellGraph');
}

console.log('\n▶ INVARIANT 20 — drug safety: a real interaction dataset with severity, classes, and cross-reactivity');
{
  const { INTERACTIONS, checkDrugSafety } = await import('./drugsafety.js');

  ok(INTERACTIONS.length >= 30, `the interaction dataset is substantial (${INTERACTIONS.length} pairs), not a 6-row demo`);
  ok(INTERACTIONS.every((i: any) => i.severity && i.mechanism && i.management), 'every interaction carries severity + mechanism + management');

  // a contraindicated pair is surfaced as contraindicated (nitrate + PDE5 inhibitor)
  const cx = checkDrugSafety([{ display: 'Sildenafil 50 MG' }, { display: 'Nitroglycerin 0.4 MG' }]);
  ok(cx.interactions.some((i: any) => i.severity === 'contraindicated') && cx.highestSeverity === 'contraindicated', 'nitrate + PDE5 inhibitor is flagged contraindicated');

  // order-insensitivity: the same pair flags regardless of listing order
  const ab = checkDrugSafety([{ display: 'Warfarin 5 MG' }, { display: 'Ibuprofen 400 MG' }]);
  const ba = checkDrugSafety([{ display: 'Ibuprofen 400 MG' }, { display: 'Warfarin 5 MG' }]);
  ok(ab.interactions.length === 1 && ba.interactions.length === 1, 'interaction matching is order-insensitive (and not double-counted)');

  // duplicate therapy by CLASS (two ACE inhibitors), and allergy CROSS-reactivity (penicillin→amoxicillin)
  ok(checkDrugSafety([{ display: 'Lisinopril 10 MG' }, { display: 'Enalapril 5 MG' }]).duplicates.some((d: any) => d.class === 'ACE inhibitor'), 'two drugs of the same class flag as duplicate therapy');
  const cross = checkDrugSafety([{ display: 'Amoxicillin 500 MG' }], ['penicillin']);
  ok(cross.allergyConflicts.some((c: any) => /cross-reactivity/.test(c.via)), 'a documented penicillin allergy cross-flags amoxicillin (class cross-reactivity)');
  ok(/non-diagnostic/i.test(cx.disclaimer) && /not a complete/i.test(cx.disclaimer), 'honest: framed as non-diagnostic + not a complete database');
}

console.log('\n▶ INVARIANT 21 — vision: degrades to SILENCE, never a fabricated finding, never a diagnosis');
{
  // point at a guaranteed-dead vision endpoint so the model is unreachable — the degradation path
  const prev = process.env.NOETICA_OLLAMA_URL;
  process.env.NOETICA_OLLAMA_URL = 'http://127.0.0.1:9'; // nothing listens here
  const { assessImage } = await import(`./vision.js?nocache=${Date.now()}`);
  const tinyPng = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==';
  const r = await assessImage(tinyPng);
  ok(r.degraded === true && r.ok === false, 'no vision model → degraded (does not pretend to have seen the image)');
  ok(r.visibleFindings === '' && r.visualRedFlags.length === 0 && r.escalate === false, 'a degraded reading fabricates NO findings and raises NO red flag (anti-Watson floor for images)');
  ok(/non-diagnostic/i.test(r.disclaimer) && !!r.receipt, 'the reading is non-diagnostic + receipted even when degraded');
  const empty = await assessImage('');
  ok(empty.degraded === true, 'an empty image degrades cleanly, not throws');
  if (prev === undefined) delete process.env.NOETICA_OLLAMA_URL; else process.env.NOETICA_OLLAMA_URL = prev;
}

console.log('\n▶ INVARIANT 22 — patient identity plane: one-time credential, fail-closed, id ≠ credential');
{
  const { enrollPatient, authenticatePatient, patientProfile, revokePatient, PATIENT_HEADER } = await import('./identity.js');

  const e = enrollPatient('Alex Demo');
  ok(!!e.patient.id && e.credential.token.includes('.') && e.credential.shownOnce === true, 'enroll mints a one-time patient credential (id.secret)');
  // the stored profile never exposes the holder digest (secret-equivalent verifier)
  ok(!JSON.stringify(patientProfile(e.patient.id)).includes('sha256-'), 'the patient profile never exposes the holder digest');

  const hdr = (v: string) => ({ [PATIENT_HEADER]: v });
  ok(authenticatePatient(hdr(e.credential.token)).ok === true, 'the full credential authenticates the patient');
  ok(authenticatePatient(hdr(e.patient.id)).ok === false, 'the bare patient id is NOT a credential (fail-closed)');
  ok(authenticatePatient(hdr(`${e.patient.id}.wrong-secret`)).ok === false, 'a wrong secret is refused');
  ok(authenticatePatient({}).ok === false, 'a missing credential is refused, not treated as the patient');

  // revocation: the patient revokes their own credential → future auth denies
  revokePatient(e.patient.id);
  const after = authenticatePatient(hdr(e.credential.token));
  ok(after.ok === false && /revoked/.test((after as any).reason), 'a revoked credential no longer authenticates');
}

console.log(`\n${fails === 0 ? '✓ ALL 22 GUARDRAIL INVARIANTS HOLD (…+ patient identity plane)' : `✗ ${fails} invariant(s) violated`}`);
process.exit(fails === 0 ? 0 : 1);
