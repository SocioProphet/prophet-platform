// Full-surface end-to-end smoke — hits every health-twin endpoint against a RUNNING engine and
// asserts basic shape. Unlike invariants.ts (pure, CI-enforced guardrails), this needs a live
// server, so it's a manual/integration check of the whole product on the CPU-only path:
//
//   npx tsx src/server.ts &            # the engine (optionally with NOETICA_AM_URL + _TOKEN for the brain)
//   npx tsx src/smoke.ts               # this sweep  (BASE overridable via HT_BASE)
//
// Grant reads are HOLDER-AUTHENTICATED (grantauth.ts): issuing a grant returns a one-time holder
// token, presented as `x-health-grant: <grant-id>.<secret>`; the id alone is not a credential and a
// grant that binds no holder is refused (fail-closed). Evidence + doctor-view read through that.
// Brain grounding lights up when the agent-machine is reachable with a matching embedder; otherwise
// retrieval degrades to the cited local KB — both are a PASS (every surface answers, degradation is graceful).
const BASE = process.env.HT_BASE ?? 'http://localhost:8097';
const HOLDER_HEADER = 'x-health-grant';
let passed = 0, failed = 0;

async function call(method: string, path: string, body?: unknown, headers: Record<string, string> = {}): Promise<{ st: number; d: any }> {
  try {
    const r = await fetch(`${BASE}${path}`, {
      method,
      headers: { 'content-type': 'application/json', accept: 'application/json', ...headers },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    let d: any = {};
    try { d = await r.json(); } catch { /* empty body */ }
    return { st: r.status, d };
  } catch (e) { return { st: 0, d: { _err: String(e) } }; }
}
function check(name: string, cond: boolean, detail = '') {
  console.log(`  ${cond ? '✓' : '✗'} ${name}${detail ? `  — ${detail}` : ''}`);
  cond ? passed++ : failed++;
}
// issue a grant and return its one-time holder token (x-health-grant value)
async function issue(agent: string, scope: string): Promise<{ id: string; token: string; summary: string }> {
  const r = await call('POST', '/api/health/grant', { agent, scope, ttlDays: 7 });
  return { id: r.d.grant?.id, token: r.d.holder?.token ?? '', summary: r.d.grant?.scopeSummary ?? '' };
}
const hdr = (token: string) => ({ [HOLDER_HEADER]: token });

async function main() {
  console.log('\n═══ HEALTH-TWIN FULL SURFACE SMOKE (CPU-only, holder-authenticated) ═══\n');

  // ── unauthenticated patient-owned surfaces ──────────────────────────────────────────────
  let r = await call('GET', '/api/health/twin');
  check('twin bundle', r.st === 200 && Array.isArray(r.d.systems), `${r.d.systems?.length ?? 0} systems`);

  r = await call('POST', '/api/health/ask', { q: 'what medications am I taking?' });
  check('ask recall', r.st === 200 && 'answer' in r.d, `${r.d.citations?.length ?? 0} citations, ${r.d.retrieval}`);

  r = await call('GET', '/api/health/guidance');
  check('guideline guidance', r.st === 200 && (r.d.items?.length ?? 0) > 0, `${r.d.items?.length} recs`);

  r = await call('GET', '/api/health/providers');
  check('providers + care team', r.st === 200 && (r.d.careTeam?.length ?? 0) > 0, `${r.d.careTeam?.length} care-team`);

  r = await call('POST', '/api/health/capture', { kind: 'note', by: 'clinician', caption: 'visit', text: 'BP 138/85, no chest pain, continue lisinopril' });
  check('capture → coded', r.st === 200 && 'captured' in r.d, `${r.d.captured?.coded?.length ?? 0} coded`);

  r = await call('POST', '/api/health/reading', { text: 'glucose 110 mg/dL', by: 'clinician', source: 'keyboard' });
  check('reading → observation', r.st === 200 && (r.d.count ?? 0) >= 1, `${r.d.count} created`);

  r = await call('POST', '/api/health/community/aggregate', { scope: { region: 'any', specialty: 'cardiology' } });
  check('community aggregate (enclave)', r.st === 200 && ('attestation' in r.d || 'receipt' in r.d || 'aggregate' in r.d), 'attestation' in r.d ? 'attested' : 'ok');

  r = await call('POST', '/api/health/consult', { scope: 'cardiovascular', disclosure: 'standard', agreed: true });
  check('consult open (blinded)', r.st === 200 && !!r.d.consult_id && 'slice' in r.d, 'de-identified slice');

  r = await call('GET', '/api/health/deident');
  check('deidentify', r.st === 200 && ('subject' in r.d || 'receipt' in r.d));

  r = await call('GET', '/api/health/connectors');
  check('connectors catalogue', r.st === 200 && (r.d.connectors?.length ?? 0) > 0, `${r.d.connectors?.length} connectors`);

  // triage — agentic OOD loop + red-flag safety floor + care routing
  r = await call('POST', '/api/health/triage', { complaint: 'crushing chest pain radiating to my left arm', route: true });
  check('triage: red flag → emergency + escalate', r.st === 200 && r.d.triage?.urgency === 'emergency' && r.d.triage?.disposition === 'escalate', `flags=${JSON.stringify((r.d.triage?.redFlags ?? []).map((f: any) => f.id))}`);
  check('triage: Perceive→Reason→Act→Verify traced', (r.d.triage?.loop ?? []).map((s: any) => s.step).join(',') === 'perceive,reason,act,verify');
  check('route: emergency → ED + specialty + pre-visit summary', r.d.route?.setting === 'emergency-department' && !!r.d.route?.specialty && !!r.d.route?.preVisitSummary, `${r.d.route?.specialty}`);
  r = await call('POST', '/api/health/triage', { complaint: 'i feel weird' });
  check('triage: thin input abstains', r.st === 200 && r.d.disposition === 'abstain' && (r.d.nextBestQuestions?.length ?? 0) > 0, `${r.d.nextBestQuestions?.length} next-best Q`);
  r = await call('POST', '/api/health/triage', { complaint: 'no chest pain, just a mild scrape on my knee' });
  check('triage: negation-safe, not over-escalated', r.st === 200 && r.d.urgency !== 'emergency', `urgency=${r.d.urgency}`);

  // longitudinal monitor — acuity bands + deterioration→escalate (fitness-fatigue generalization)
  r = await call('GET', '/api/health/monitor');
  check('monitor: acuity bands + escalate signal', r.st === 200 && Array.isArray(r.d.metrics) && r.d.metrics.length > 0 && typeof r.d.escalate === 'boolean', `overall=${r.d.overall}, deteriorating=${(r.d.deteriorating ?? []).length}`);

  // imaging & document agent — report text → plain-language + critical-finding floor
  r = await call('POST', '/api/health/interpret', { report: 'CT head: acute intraparenchymal hemorrhage in the right frontal lobe.' });
  check('interpret: critical finding floors + escalates', r.st === 200 && r.d.escalate === true && !!r.d.plainLanguage, `${r.d.modality}/${r.d.bodySite}, urgency=${r.d.urgency}`);
  r = await call('POST', '/api/health/interpret', { report: 'Chest X-ray: no acute process, no evidence of hemorrhage or mass. Unremarkable.' });
  check('interpret: negated report not over-flagged', r.st === 200 && r.d.escalate === false, `flags=${(r.d.criticalFlags ?? []).length}`);

  // multimodal vision — returns a VisionReading (real findings if LLaVA is up, else clean degradation)
  const tinyPng = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==';
  r = await call('POST', '/api/health/vision', { image: tinyPng });
  check('vision: returns a reading (degrades safely if no model)', r.st === 200 && typeof r.d.degraded === 'boolean' && !!r.d.receipt && /non-diagnostic/i.test(r.d.disclaimer ?? ''), r.d.degraded ? 'degraded (no model)' : `live: ${r.d.modelUsed}`);

  // patient identity plane — enroll → authenticate as owner → fail-closed
  r = await call('POST', '/api/health/patient/enroll', { displayName: 'Smoke Patient' });
  const ptoken = r.d.credential?.token;
  check('identity: enroll mints one-time credential', r.st === 200 && !!ptoken && r.d.credential?.shownOnce === true);
  r = await call('GET', '/api/health/patient/me', undefined, { 'x-health-patient': ptoken });
  check('identity: patient authenticates as owner', r.st === 200 && r.d.authenticated === true, r.d.profile?.displayName);
  r = await call('GET', '/api/health/patient/me', undefined, { 'x-health-patient': (ptoken ?? '').split('.')[0] });
  check('identity: bare id is not a credential (401)', r.st === 401 && r.d.authenticated === false);

  // FHIR R4 interop — export a valid de-identified Bundle, and round-trip it back
  r = await call('GET', '/api/health/fhir');
  const bundle = r.d;
  const pt = (bundle.entry ?? []).find((e: any) => e.resource?.resourceType === 'Patient')?.resource;
  check('fhir export: valid R4 Bundle, de-identified Patient', r.st === 200 && bundle.resourceType === 'Bundle' && !!pt && !pt.name && !pt.birthDate, `${(bundle.entry ?? []).length} resources`);
  r = await call('POST', '/api/health/fhir/import', bundle);
  check('fhir import: round-trips observations + conditions', r.st === 200 && (r.d.counts?.observations ?? 0) > 0 && (r.d.counts?.conditions ?? 0) > 0, `obs=${r.d.counts?.observations} cond=${r.d.counts?.conditions} skipped=${r.d.counts?.skipped}`);

  // professional reference — audience-rendered condition cards + med safety + guideline deltas
  const clin = (await call('GET', '/api/health/reference/condition/hypertension?audience=clinician')).d;
  const pat = (await call('GET', '/api/health/reference/condition/hypertension?audience=patient')).d;
  check('reference: audience renderers off one source', !!clin.citations && !pat.citations && clin.snomed === pat.snomed, `clin has citations, patient doesn't`);
  r = await call('POST', '/api/health/reference/med-check', { medications: [{ display: 'Simvastatin 40 MG' }, { display: 'Clarithromycin 500 MG' }, { display: 'Lisinopril 10 MG' }, { display: 'Losartan 50 MG' }], allergies: ['penicillin'] });
  check('reference: real drug safety (severity + dual-RAAS + class dup)', r.st === 200 && (r.d.interactions?.length ?? 0) >= 2 && !!r.d.highestSeverity, `${r.d.interactions?.length} interactions, worst=${r.d.highestSeverity}, dups=${(r.d.duplicates ?? []).length}`);
  r = await call('GET', '/api/health/reference/guideline-deltas');
  check('reference: guideline-delta engine', r.st === 200 && (r.d.deltas?.length ?? 0) > 0, `${r.d.deltas?.length} deltas`);
  // live FDA drug label (openFDA) — real data when online, clean degradation otherwise
  r = await call('GET', '/api/health/reference/drug-label?name=simvastatin');
  check('reference: live FDA drug label', r.st === 200 && typeof r.d.degraded === 'boolean' && /non-diagnostic/i.test(r.d.disclaimer ?? ''), r.d.degraded ? 'degraded (offline)' : `live: ${r.d.genericName} rxcui=${r.d.rxcui}`);

  // care-access booking (verb 6) — find slots + hold; fail-closed on unknown slot
  r = await call('GET', '/api/health/booking/slots?specialty=Cardiology&modality=telehealth');
  const slot0 = (r.d.slots ?? [])[0];
  check('booking: filtered bookable slots', r.st === 200 && !!slot0, `${(r.d.slots ?? []).length} slots`);
  r = await call('POST', '/api/health/booking/book', { slotId: slot0?.id, preVisitSummary: 'x' });
  check('booking: hold a real slot', r.st === 200 && r.d.status === 'held', r.d.providerName);
  r = await call('POST', '/api/health/booking/book', { slotId: 'nope' });
  check('booking: unknown slot fails closed', r.st === 404 && !!r.d.error);

  // data cooperative (verb 10) — consent fail-closed + de-id contribution + revoke + ledger
  r = await call('POST', '/api/health/contribution/join', { programId: 'cardio-eval', agreed: false });
  check('contribution: no consent → refused (fail-closed)', r.st === 422 && /consent/i.test(r.d.error ?? ''));
  r = await call('POST', '/api/health/contribution/join', { programId: 'cardio-eval', agreed: true });
  check('contribution: consented, de-identified, compensated', r.st === 200 && r.d.leakCheck === 'clean' && (r.d.compensation?.amount ?? 0) > 0, `+${r.d.compensation?.amount} ${r.d.compensation?.currency}`);
  r = await call('GET', '/api/health/contribution/ledger');
  check('contribution: transparent ledger', r.st === 200 && typeof r.d.totalAccrued === 'number');

  // terminology value sets bound to Ontogenesis/HDT
  r = await call('GET', '/api/health/terminology/valueset');
  check('terminology: multi-system value sets', r.st === 200 && (r.d.count ?? 0) >= 30 && (r.d.systems ?? []).length >= 3, `${r.d.count} concepts, ${(r.d.systems ?? []).length} systems`);
  r = await call('GET', '/api/health/terminology/lookup?system=LOINC&code=13457-7');
  check('terminology: lookup emits ontogenesis-typed node', r.st === 200 && !!r.d.ontogenesis?.classIri && !!r.d.ontogenesis?.organIri, `${r.d.concept?.display} → ${r.d.ontogenesis?.classIri?.split('#').pop()}`);
  r = await call('GET', '/api/health/terminology/crosswalk?system=SNOMED&code=38341003');
  check('terminology: SNOMED→ICD-10 crosswalk', r.st === 200 && (r.d.maps ?? []).some((m: any) => m.system === 'ICD-10'), (r.d.maps ?? []).map((m: any) => `${m.system} ${m.code}`).join(', '));

  // HIPAA audit trail — a doctor-view read/block should appear in the append-only log
  r = await call('GET', '/api/health/audit?action=doctor-view');
  check('audit: append-only access trail (HIPAA §164.312(b))', r.st === 200 && Array.isArray(r.d.events) && typeof r.d.total === 'number' && typeof r.d.droppedAtCap === 'number', `${r.d.total} doctor-view events logged`);

  // population & operations layer — cohort risk + early warnings, k-anonymity + aggregates only
  r = await call('GET', '/api/health/population');
  const wire = JSON.stringify(r.d);
  check('population: k-anonymity + aggregates only', r.st === 200 && Array.isArray(r.d.cohorts) && r.d.cohorts.every((c: any) => c.n >= r.d.kAnonymity) && !/"onStatin"|"ldlOverTarget"/.test(wire), `${r.d.cohorts?.length} cohorts, ${r.d.suppressedCohorts} suppressed, ${(r.d.earlyWarnings ?? []).length} warnings`);

  // ── holder-authenticated consent membrane ───────────────────────────────────────────────
  const full = await issue('Dr. Full', 'full-history');
  check('grant issue → one-time holder token', !!full.token && full.token.includes('.'), full.summary);

  // fail-closed: no credential is refused, not silently served
  r = await call('GET', '/api/health/doctor-view');
  check('doctor-view fail-closed (no header)', r.st === 401, `HTTP ${r.st}`);
  r = await call('GET', '/api/health/doctor-view', undefined, hdr(full.id)); // id without secret
  check('bare id is not a credential', r.st === 401 || r.d.blocked === true, `HTTP ${r.st}`);

  // authenticated scoped read + receipt
  r = await call('GET', '/api/health/doctor-view', undefined, hdr(full.token));
  check('doctor-view authenticated', r.st === 200 && 'view' in r.d && !!r.d.receipt, `${r.d.view?.systems?.length} systems, receipted`);

  // scope enforcement: cardiometabolic hides musculoskeletal as withheld COUNTS (content never crosses)
  const cardio = await issue('Dr. Cardio', 'cardiometabolic');
  r = await call('GET', '/api/health/doctor-view', undefined, hdr(cardio.token));
  const sys = (r.d.view?.systems ?? []).map((s: any) => s.id);
  check('scope: no out-of-scope system', r.st === 200 && !sys.includes('musculoskeletal') && (r.d.withheld?.total ?? 0) > 0, `systems=${JSON.stringify(sys)}, withheld=${r.d.withheld?.total}`);
  check('scope: withheld is counts not content', !JSON.stringify(r.d.view ?? {}).toLowerCase().includes('knee'), 'knee history never leaves the twin');

  // kinds scope: meds-allergies view carries no observations
  const meds = await issue('Dr. Meds', 'meds-allergies');
  r = await call('GET', '/api/health/doctor-view', undefined, hdr(meds.token));
  check('scope: kinds excluded', r.st === 200 && r.d.view?.counts?.observations === 0 && (r.d.view?.counts?.medications ?? 0) > 0, `obs=${r.d.view?.counts?.observations} meds=${r.d.view?.counts?.medications}`);

  // evidence grounding, read through the grant (brain when AM up, else cited KB)
  r = await call('GET', '/api/health/evidence', undefined, hdr(full.token));
  const rets = [...new Set((r.d.items ?? []).map((i: any) => i.retrieval))];
  check('evidence grounding (grant-read)', r.st === 200 && (r.d.items?.length ?? 0) > 0, `${r.d.items?.length} items, retrieval=${JSON.stringify(rets)}`);

  // revoke → the same credential is now blocked
  await call('POST', '/api/health/revoke', { grant: meds.id });
  r = await call('GET', '/api/health/doctor-view', undefined, hdr(meds.token));
  check('revoked grant blocks', (r.st === 403 || r.st === 401) && (r.d.blocked === true || r.d.reason), r.d.reason ?? `HTTP ${r.st}`);

  console.log(`\n═══ ${passed} passed, ${failed} failed ═══`);
  process.exit(failed ? 1 : 0);
}
main();
