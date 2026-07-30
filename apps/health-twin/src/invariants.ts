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


// cryptographic receipts: receipt ids + content addresses must be REAL sha256 (64 hex), never a
// short non-cryptographic hash wearing a sha label.
//
// The previous version of this block computed its OWN sha256, built its OWN string, and
// asserted that the string it had just built matched a regex. It proved that node can hash,
// and touched not one receipt this service emits — which is why it passed for the whole
// period consult.ts was still minting 8-hex djb2 ids under the same comment claiming the
// regression was fixed. An invariant that constructs its own subject cannot fail.
//
// These read the ids the code actually produces.
console.log('\n▶ INVARIANT 5 — receipts EMITTED by the real code paths are cryptographic');
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

console.log('\n▶ INVARIANT 8 — the de-identification boundary is cryptographic AND honestly labelled');
// deident.ts derived the pseudonym over PHI with 32-bit djb2 — the same regression as the consult
// receipts, but a re-identification risk rather than a receipt-integrity one, and it survived the
// sweep because this file never wore a "sha-" label. Asserted on real deidentify() output.
{
  const v = deidentify(sampleBundle, 'deid-probe');
  ok(/^anon:[0-9a-f]{32}$/.test(v.receipt.pseudonym),
     `pseudonym is anon: + 32 hex / 128 bits (${v.receipt.pseudonym})`);
  ok(!/^anon:[0-9a-f]{8}$/.test(v.receipt.pseudonym), 'pseudonym is NOT the old 8-hex djb2 token');
  ok(v.subject.pseudonym === v.receipt.pseudonym, 'the view and its receipt carry the same pseudonym');

  ok(deidentify(sampleBundle, 'deid-probe').receipt.pseudonym === v.receipt.pseudonym,
     'same subject + same salt → same pseudonym (stable within a consult)');
  ok(deidentify(sampleBundle, 'other-scope').receipt.pseudonym !== v.receipt.pseudonym,
     'a different salt → a different pseudonym (consults stay unlinkable)');

  // parseInt over >13 hex digits silently rounds past 2^53 and collapses the low bits the modulus
  // consumes, so a broken derivation reaches only a few distinct values instead of the window.
  const shifts = Array.from({ length: 400 }, (_, i) => deidentify(sampleBundle, `s${i}`).receipt.dateShiftDays);
  ok(shifts.every((d) => Number.isInteger(d) && d >= -183 && d <= 182), 'every date shift is an integer in [-183, +182]');
  ok(new Set(shifts).size > 200, `date shift spreads across the window (${new Set(shifts).size} distinct over 400 salts — a parseInt precision loss collapses this)`);

  // domain separation: if both derivations shared one digest, deriving the shift FROM the pseudonym
  // would reproduce it every time; with separation, all 8 agreeing is a (1/366)^8 event.
  const allMatch = Array.from({ length: 8 }, (_, i) => `sep${i}`).every((salt) => {
    const view = deidentify(sampleBundle, salt);
    const fromPseudonym = Number(BigInt(`0x${view.receipt.pseudonym.slice(5, 21)}`) % 366n) - 183;
    return fromPseudonym === view.receipt.dateShiftDays;
  });
  ok(!allMatch, 'date shift is domain-separated from the pseudonym (not derivable from it)');

  // The receipt must not claim a protection the run did not have. Both branches are exercised so a
  // receipt hard-coded to keyed:true — the failure mode that matters — cannot pass.
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
  // Copilot #1074: the absent branch admits three shapes — '', undefined, and null —
  // and the invariant probe must exercise each; a probe that only asserts '' and
  // undefined leaves the null path unverified even though the branch handles it.
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
}

console.log('\n▶ INVARIANT 8 — a grant id is not a credential: the holder is authenticated, both ways');
{
  const {
    authenticateHolder, holderDigest, holderToken, mintHolderSecret, parseHolderToken,
    presentedHolderToken, seedGrantDecision, legacyQueryDecision,
    HOLDER_AUTH_DISCLOSURE, HOLDER_FAILED, HOLDER_HEADER,
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
  ok(noCredential.ok === false && (noCredential as any).reason !== HOLDER_FAILED,
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

console.log(`\n${fails === 0 ? '✓ ALL GUARDRAIL INVARIANTS HOLD (non-diagnostic + de-identification + grant scoping enforced)' : `✗ ${fails} invariant(s) violated`}`);
process.exit(fails === 0 ? 0 : 1);
