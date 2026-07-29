// health-twin — the Digital Health Twin engine (walking skeleton). Serves the person's records as a
// FHIR-lite bundle keyed to organ systems (so the anatomical diagram is the index), plus GOVERNED
// consent grants: a designated agent gets a scoped, time-boxed, receipted, revocable read grant, and
// every access is a receipt. In production this runs LOCAL-FIRST on the person's own node — never a
// shared cloud. Here it holds one clearly-synthetic subject. Node http, binds 0.0.0.0.
//
// NOT a medical device. NOT diagnostic. Organises + retrieves + governs sharing of a person's own
// records. Synthetic data only in this skeleton — no real PHI.
import http from 'node:http';
import { createHash } from 'node:crypto';
import { SUBJECT, SYSTEMS, OBSERVATIONS, CONDITIONS, ENCOUNTERS, IMAGING, MEDICATIONS, ALLERGIES, IMMUNIZATIONS, ORGAN_IRI, OBSERVATION_CLASS, CONDITION_CLASS, HEALTH_NS, HDT_NS, type Grant, type Observation, type Condition } from './data.js';
import { connectorCatalogue, runConnector } from './connectors/index.js';
import { mergeResults, resultCounts, emptyResult, type IngestResult, type IngestMode, type SourceId } from './ingest.js';
import { dedupeIngested, extractNarrative, landInGraph } from './reconcile/reconcile.js';
import { serviceHealth, reasonTurtle, graphGround } from './reconcile/clients.js';
import { discovery, patientSummaryCards, medReconciliationCards } from './cds/cds.js';
import { deidentify } from './deident.js';
import { ask } from './ask.js';
import { ground, groundFromBrain } from './knowledge.js';
import { communityAggregate, communityScopes, type Scope } from './enclave.js';
import { directory, provider, careTeam } from './providers.js';
import { parseReadings, type Reading } from './readings.js';
import { groundTwin } from './evidence.js';
import { codeText, type CodedEntity } from './clinical.js';
import { guidance } from './guidelines.js';
import { openConsult, reviewerView, submitOpinion, aggregate, requestMore, type Confidence } from './consult.js';
import { resolveScope, resolveGrant, applyScope, scopeSummary, SCOPE_PRESETS } from './grants.js';

const PORT = Number(process.env.PORT ?? 8097);

// Real SHA-256 (node:crypto, no deps). Receipts and content addresses on a governance surface must be
// cryptographic: the previous djb2 (32-bit, trivially collidable) was labeled "sha-", which made
// "tamper-evident" a false claim. Now the label and the math agree.
function sha256(s: string): string {
  return createHash('sha256').update(s).digest('hex');
}
function receipt(kind: string, parts: string[]): { id: string; verifier: 'health-twin'; at: string } {
  return { id: `ht-${kind}-${sha256(parts.join('|'))}`, verifier: 'health-twin', at: new Date().toISOString() };
}

// In-memory grant ledger (skeleton). Local-first store in production. Seeded with one active
// cardiometabolic grant for the care-team cardiologist so the doctor chart demos scoping on a
// fresh boot (the childhood knee history is OUTSIDE this scope — it shows up as withheld counts).
const grants: Grant[] = [{
  id: 'grant-seed-rivera',
  agent: 'Dr. A. Rivera (Cardiology)',
  scope: 'cardiometabolic',
  scopeSpec: resolveScope('cardiometabolic'),
  granted_at: new Date().toISOString(),
  expires_at: new Date(Date.now() + 30 * 86_400_000).toISOString(),
  revoked: false, reads: 0, receipt: 'ht-grant-seed',
}];

// Entered readings — device / voice / keyboard vitals that became coded observations. Local-first store.
const readings: Reading[] = [];

// Capture surface — voice notes, photos, documents captured across devices land here, each hash-sealed
// with provenance + an epistemic tier. A clinician's dictated note is 'attested'; a patient photo is
// 'observed' (self-reported). Content-addressed (hash) so media is tamper-evident. Local-first store.
interface Captured { id: string; kind: 'note' | 'photo' | 'document'; caption: string; text?: string; system?: string; organ?: string; contentHash: string; tier: string; by: 'clinician' | 'patient'; capturedAt: string; receipt: string; coded?: CodedEntity[] }
const captured: Captured[] = [];

// In-memory ingested store — records pulled through the connector plane (fixture mode here). Every
// record carries provenance + an epistemic tier (the lineage Watson Health never had). Local-first in
// production; this accumulates across ingest calls so the twin reflects what's been connected.
let ingested: IngestResult = emptyResult();

// A compact summary of what's been ingested: which sources, and which USCDI classes are now covered.
function ingestedSummary() {
  const all = [
    ...ingested.observations, ...ingested.conditions, ...ingested.medications,
    ...ingested.immunizations, ...ingested.allergies, ...ingested.imaging, ...ingested.coverage,
  ];
  const sources = new Map<string, { source: string; connector: string; mode: string; count: number }>();
  const uscdi = new Set<string>();
  for (const r of all as any[]) {
    const p = r.provenance; if (!p) continue;
    uscdi.add(p.uscdi);
    const k = p.source;
    const s = sources.get(k) ?? { source: p.source, connector: p.connector, mode: p.mode, count: 0 };
    s.count += 1; sources.set(k, s);
  }
  return { counts: resultCounts(ingested), sources: [...sources.values()], uscdiCoverage: [...uscdi].sort() };
}

// enrich a record with its ontology IRIs so it lands in HellGraph as a typed node, not a label string.
const obsView = (o: Observation) => ({ ...o, classIri: OBSERVATION_CLASS, organIri: ORGAN_IRI[o.organ] ?? null });
const condView = (c: Condition) => ({ ...c, classIri: CONDITION_CLASS, organIri: ORGAN_IRI[c.organ] ?? null });

function bundle() {
  // group records per system for the anatomical index
  const bySystem = SYSTEMS.map((s) => ({
    ...s,
    observations: OBSERVATIONS.filter((o) => o.system === s.id).map(obsView),
    conditions: CONDITIONS.filter((c) => c.system === s.id).map(condView),
    encounters: ENCOUNTERS.filter((e) => e.system === s.id),
    imaging: IMAGING.filter((i) => i.system === s.id),
    medications: MEDICATIONS.filter((m) => m.system === s.id),
  }));
  return {
    subject: SUBJECT,
    systems: bySystem,
    medications: MEDICATIONS, allergies: ALLERGIES, immunizations: IMMUNIZATIONS,
    careTeam: careTeam(), readings,
    timeline: [...ENCOUNTERS].sort((a, b) => (a.date < b.date ? 1 : -1)),
    counts: { observations: OBSERVATIONS.length, conditions: CONDITIONS.length, encounters: ENCOUNTERS.length, imaging: IMAGING.length, medications: MEDICATIONS.length, allergies: ALLERGIES.length, immunizations: IMMUNIZATIONS.length },
    grants: grants.map((g) => ({ ...g, active: !g.revoked && new Date(g.expires_at) > new Date() })),
    // records pulled through the connector plane (provenance + epistemic tier on every one).
    ingested: { ...ingested, summary: ingestedSummary() },
    // captured media (voice notes, photos, documents) — hash-sealed, tier-tagged.
    captured,
    // the twin speaks the estate's ontology: every fact carries a class IRI from the HDT ontology.
    ontology: { health: HEALTH_NS, hdt: HDT_NS, subjectClass: `${HDT_NS}HumanDigitalTwin`, note: 'Facts carry health:/hdt: class IRIs so they type into HellGraph + reason in Ontogenesis.' },
    disclaimer: 'Synthetic sample. Not a real person, not medical advice. This tool organises records; it does not diagnose.',
  };
}

// Emit the twin as typed RDF (Turtle) the owl-reasoner can consume: the subject is a
// hdt:HumanDigitalTwin, each observation a hdt:Observation, each condition a health:Condition, each
// localised to a health:Organ — importing the HDT health ontology (socioprophet.md). Loading this
// alongside the ontology TBox lets a reasoner entail (e.g. conditions ⊑ hdt:FHIRResource) and drive
// the correspondence promotion membrane. Synthetic data only.
function ttlEsc(s: string): string { return s.replace(/\\/g, '\\\\').replace(/"/g, '\\"'); }
function twinTtl(): string {
  const head = [
    '@prefix health: <https://socioprophet.md/ont/health#> .',
    '@prefix hdt: <https://socioprophet.dev/ont/ontogenesis#> .',
    '@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .',
    '@prefix owl: <http://www.w3.org/2002/07/owl#> .',
    '@prefix sp: <https://socioprophet.ai/kg#> .',
    '',
    '<urn:health-twin:graph> a owl:Ontology ; owl:imports <https://socioprophet.md/ont/health#> .',
  ];
  const S = `<urn:health-twin:${SUBJECT.id}>`;
  const out = [`${S} a hdt:HumanDigitalTwin ; rdfs:label "${ttlEsc(SUBJECT.label)}" .`];
  for (const s of SYSTEMS) out.push(`<${s.iri}> a health:OrganSystem ; rdfs:label "${ttlEsc(s.label)}" .`);
  for (const o of OBSERVATIONS) {
    const oi = ORGAN_IRI[o.organ];
    out.push(`<urn:health-twin:${o.id}> a hdt:Observation ; rdfs:label "${ttlEsc(o.display)}" ; sp:epistemicMode "${o.epistemic}" ; health:code "${o.code}" ; health:codeSystem "${o.codeSystem}"${oi ? ` ; health:localizedTo <${oi}>` : ''} .`);
  }
  for (const c of CONDITIONS) {
    const oi = ORGAN_IRI[c.organ];
    out.push(`<urn:health-twin:${c.id}> a health:Condition ; rdfs:label "${ttlEsc(c.display)}" ; sp:epistemicMode "${c.epistemic}" ; health:code "${c.code}" ; health:codeSystem "${c.codeSystem}"${oi ? ` ; health:localizedTo <${oi}>` : ''} .`);
  }
  return head.concat(out).join('\n') + '\n';
}

function send(res: http.ServerResponse, code: number, body: unknown) {
  res.writeHead(code, { 'content-type': 'application/json', 'access-control-allow-origin': '*', 'access-control-allow-headers': 'content-type', 'access-control-allow-methods': 'POST, GET, OPTIONS' });
  res.end(JSON.stringify(body));
}
function readJson(req: http.IncomingMessage): Promise<any> {
  return new Promise((resolve, reject) => {
    let raw = ''; req.on('data', (c) => { raw += c; if (raw.length > 2_000_000) req.destroy(); });
    req.on('end', () => { try { resolve(raw ? JSON.parse(raw) : {}); } catch (e) { reject(e); } });
    req.on('error', reject);
  });
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url ?? '/', `http://${req.headers.host}`);
  if (req.method === 'OPTIONS') return send(res, 204, {});
  if (req.method === 'GET' && url.pathname === '/healthz') return send(res, 200, { ok: true, service: 'health-twin' });

  // The twin bundle (the surface's one read).
  if (req.method === 'GET' && url.pathname === '/api/health/twin') return send(res, 200, bundle());

  // the twin as reasoner-ready RDF (Turtle) — typed with the HDT ontology, imports the TBox.
  if (req.method === 'GET' && url.pathname === '/api/health/twin.ttl') {
    res.writeHead(200, { 'content-type': 'text/turtle; charset=utf-8', 'access-control-allow-origin': '*' });
    return res.end(twinTtl());
  }

  // The connector catalogue — "connect a source". Each proves out on a real-schema fixture and flips
  // to live with a credential (no downstream change).
  if (req.method === 'GET' && url.pathname === '/api/health/connectors') {
    return send(res, 200, { connectors: connectorCatalogue(), summary: ingestedSummary() });
  }

  // Ingest from a connector: fetch(mode) → normalize() → merge into the twin. fixture mode proves the
  // live path (normalize is mode-invariant). Every landed record carries provenance + an epistemic tier.
  if (req.method === 'POST' && url.pathname === '/api/health/ingest') {
    try {
      const b = await readJson(req);
      const connector = String(b.connector ?? '').trim() as SourceId;
      const mode = (String(b.mode ?? 'fixture').trim() || 'fixture') as IngestMode;
      if (!connector) return send(res, 422, { error: 'connector required' });
      const delta = await runConnector(connector, mode);
      ingested = mergeResults([ingested, delta]);
      const added = resultCounts(delta);
      const sample = [...delta.observations, ...delta.conditions, ...delta.medications, ...delta.imaging][0] as any;
      return send(res, 200, {
        connector, mode, added, added_result: delta,
        provenanceSample: sample?.provenance ?? null,
        summary: ingestedSummary(),
        receipt: receipt('ingest', [connector, mode, String(added.total)]),
      });
    } catch (e) { return send(res, 400, { error: (e as Error).message || 'ingest failed' }); }
  }

  // ── Reconciliation + reasoning plane — ORCHESTRATES existing estate services (entity-resolution,
  // ie-engine, holmes, hellgraph-service, owl-reasoner). Every route degrades gracefully: a down
  // service never breaks the twin, it reports 'degraded'. Non-diagnostic throughout. ────────────────

  // What's connected — health of every estate service the twin reuses.
  if (req.method === 'GET' && url.pathname === '/api/health/services') {
    return send(res, 200, { services: await serviceHealth() });
  }

  // Cross-source dedup via entity-resolution → proof-carrying golden records (the aggregator feature,
  // but auditable): each golden record shows the union of sources that saw it + the decision ledger.
  if (req.method === 'POST' && url.pathname === '/api/health/reconcile') {
    const report = await dedupeIngested(ingested);
    return send(res, 200, { ...report, receipt: receipt('reconcile', [String(report.before), String(report.after), report.service]) });
  }

  // Unstructured narrative → candidate facts (ie-engine spaCy) + claim verification (holmes). Candidates
  // are TIER=hypothesis, never promoted without clinician attestation.
  if (req.method === 'POST' && url.pathname === '/api/health/extract') {
    try {
      const b = await readJson(req);
      const text = String(b.text ?? '').trim();
      if (!text) return send(res, 422, { error: 'text required' });
      return send(res, 200, await extractNarrative(text));
    } catch (e) { return send(res, 400, { error: (e as Error).message || 'extract failed' }); }
  }

  // Land ingested records as typed nodes in HellGraph (enables hybrid semantic search + PLN reason).
  if (req.method === 'POST' && url.pathname === '/api/health/graph/sync') {
    return send(res, 200, await landInGraph(ingested));
  }

  // Hybrid (HNSW⊕BM25 RRF) cited semantic search over the record graph, via hellgraph-service.
  if (req.method === 'GET' && url.pathname === '/api/health/search') {
    const q = url.searchParams.get('q') ?? '';
    if (!q) return send(res, 422, { error: 'q required' });
    const r = await graphGround(q);
    return send(res, r.ok ? 200 : 200, r.ok ? r.data : { service: 'degraded', reason: r.reason, groundedNodes: [], citations: [] });
  }

  // Reason over the twin's typed RDF via owl-reasoner → RDFS/OWL-RL entailments (conditions ⊑
  // hdt:FHIRResource, drives correspondence promotion). Reuses the same twin.ttl the reasoner consumes.
  if (req.method === 'POST' && url.pathname === '/api/health/reason') {
    const r = await reasonTurtle(twinTtl(), 'rdfs');
    return send(res, 200, r.ok ? r.data : { service: 'degraded', reason: r.reason, entailed_triples: 0, entailments: [] });
  }

  // ── CDS Hooks (HL7 CDS Hooks 2.0) — the twin as a decision-moment service inside the EHR. Cards are
  // cited, epistemic-tiered, holmes-verified, and framed non-diagnostically. ────────────────────────
  if (req.method === 'GET' && url.pathname === '/cds-services') return send(res, 200, discovery());
  if (req.method === 'POST' && url.pathname.startsWith('/cds-services/')) {
    try {
      await readJson(req); // hook context (patientId, prefetch) — skeleton reads the local twin
      const id = url.pathname.slice('/cds-services/'.length);
      const base = process.env.SMART_APP_BASE ?? `http://${req.headers.host}`;
      if (id === 'health-twin-patient-summary') return send(res, 200, await patientSummaryCards(ingested, base));
      if (id === 'health-twin-medication-reconciliation') return send(res, 200, await medReconciliationCards(ingested, base));
      return send(res, 404, { error: `unknown cds-service: ${id}` });
    } catch (e) { return send(res, 400, { error: (e as Error).message || 'cds failed' }); }
  }

  // ── Wall 4: de-identification + blinded n-ary consults (the moat). Non-diagnostic; the aggregate is a
  // concordance signal, a clinician decides. ────────────────────────────────────────────────────────

  // Guideline-grounded guidance — the twin's own numbers → cited, non-diagnostic recommendations
  // grounded in real clinical guidelines (ACC/AHA, ADA, USPSTF, KDIGO).
  if (req.method === 'GET' && url.pathname === '/api/health/guidance') return send(res, 200, guidance());

  // Clinical coder — free text → coded facts (conditions→SNOMED, meds→RxNorm, labs→LOINC) + negation.
  // Clinical-terminology extraction for the cardiometabolic wedge; non-diagnostic (labels, not diagnoses).
  if (req.method === 'POST' && url.pathname === '/api/health/code') {
    try { const b = await readJson(req); return send(res, 200, codeText(String(b.text ?? ''))); }
    catch (e) { return send(res, 400, { error: (e as Error).message || 'code failed' }); }
  }

  // Ask-my-agent — conversational recall over the twin, cited + non-diagnostic. Local-first (sovereign):
  // answers on the person's own node; hellgraph semantic grounding is additive when reachable.
  if (req.method === 'POST' && url.pathname === '/api/health/ask') {
    try {
      const b = await readJson(req); const q = String(b.q ?? b.question ?? '');
      const a = ask(q);
      const brain = await groundFromBrain(q); // prefer the estate's brain corpus when wired; else local KB
      if (brain && brain.grounded) a.grounded = brain;
      return send(res, 200, a);
    } catch (e) { return send(res, 400, { error: (e as Error).message || 'ask failed' }); }
  }

  // Explain — a clinical-knowledge question grounded in authoritative medical sources (cited, tiered).
  // Uses the estate's brain corpus when wired (HT_BRAIN_URL), else the local sourced knowledge base.
  if (req.method === 'POST' && url.pathname === '/api/health/explain') {
    try {
      const b = await readJson(req); const q = String(b.q ?? b.question ?? '');
      const brain = await groundFromBrain(q);
      return send(res, 200, brain && brain.grounded ? brain : ground(q));
    } catch (e) { return send(res, 400, { error: (e as Error).message || 'explain failed' }); }
  }

  // Capture — a voice note / photo / document lands in the twin, hash-sealed + tier-tagged. The doctor's
  // "talk, it writes the note and pulls the films" and the patient's "snap a record" both flow here.
  if (req.method === 'POST' && url.pathname === '/api/health/capture') {
    try {
      const b = await readJson(req);
      const kind = (['note', 'photo', 'document'].includes(b.kind) ? b.kind : 'note') as Captured['kind'];
      const caption = String(b.caption ?? '').trim() || (kind === 'note' ? 'Note' : 'Capture');
      const text = b.text ? String(b.text) : undefined;
      const by = b.by === 'clinician' ? 'clinician' : 'patient';
      // content-addressed with REAL sha256 — tamper-evident is now a true claim, not a label
      const contentHash = sha256([kind, caption, text ?? '', String(b.contentHash ?? '')].join('|'));
      const rec: Captured = {
        id: `cap-${contentHash.slice(0, 16)}`, kind, caption, text,
        system: b.system ? String(b.system) : undefined, organ: b.organ ? String(b.organ) : undefined,
        contentHash: `sha256-${contentHash}`, tier: kind === 'note' && by === 'clinician' ? 'attested' : 'observed',
        by, capturedAt: new Date().toISOString(), receipt: receipt('capture', [kind, caption, contentHash]).id,
        // clinically code the note text (conditions→SNOMED, meds→RxNorm, labs→LOINC) with negation
        coded: text ? codeText(text).entities : undefined,
      };
      captured.unshift(rec);
      return send(res, 200, { captured: rec, count: captured.length });
    } catch (e) { return send(res, 400, { error: (e as Error).message || 'capture failed' }); }
  }

  // ── Doctor community over confidential compute (first slice): blinded-consult aggregation run INSIDE
  // an attested enclave over a SCOPED community pool. The enclave sees de-identified inputs only and
  // emits digests + a result — never raw data. Skeleton attestation; real deployment = Nitro/SGX/SEV. ──
  if (req.method === 'GET' && url.pathname === '/api/health/community/scopes') return send(res, 200, communityScopes());
  if (req.method === 'POST' && url.pathname === '/api/health/community/aggregate') {
    try { const b = await readJson(req); return send(res, 200, communityAggregate((b.scope ?? {}) as Scope)); }
    catch (e) { return send(res, 400, { error: (e as Error).message || 'aggregate failed' }); }
  }

  // Evidence grounded ON the twin — the brain lookup contextualized by the patient's own record and
  // bound evidentiarily to each finding. The clinician chart shows the literature behind each number.
  // Grant-aware: with ?grant=<id> the evidence is scoped SERVER-SIDE to records inside the grant, so
  // withheld findings can't leak to the clinician through the evidence side door. Enforced here, not
  // in the client. A blocked grant blocks evidence too.
  if (req.method === 'GET' && url.pathname === '/api/health/evidence') {
    const gid = url.searchParams.get('grant');
    const grounded = await groundTwin();
    if (!gid) return send(res, 200, grounded);
    const r = resolveGrant(grants, String(gid));
    if (!r.ok) return send(res, 403, { blocked: true, reason: r.reason, receipt: receipt('evidence-blocked', [String(gid), r.reason]) });
    const scope = r.grant.scopeSpec ?? resolveScope(r.grant.scope);
    const { view } = applyScope(bundle(), scope);
    const keptIds = new Set<string>([
      ...view.systems.flatMap((s: any) => [...s.observations, ...s.conditions].map((x: any) => x.id)),
    ]);
    return send(res, 200, { ...grounded, items: grounded.items.filter((i) => keptIds.has(i.recordId)) });
  }

  // Provider directory + a provider's profile (the patient reviews who their doctors are).
  if (req.method === 'GET' && url.pathname === '/api/health/providers') return send(res, 200, { providers: directory(), careTeam: careTeam() });
  if (req.method === 'GET' && url.pathname.startsWith('/api/health/provider/')) {
    const p = provider(url.pathname.slice('/api/health/provider/'.length));
    return send(res, p ? 200 : 404, p ?? { error: 'provider not found' });
  }

  // Easy entry — a device reading / spoken phrase / typed line → coded vital+lab observations.
  if (req.method === 'POST' && url.pathname === '/api/health/reading') {
    try {
      const b = await readJson(req);
      const created = parseReadings(String(b.text ?? ''), b.by === 'clinician' ? 'clinician' : 'patient', String(b.source ?? 'manual'));
      readings.unshift(...created);
      return send(res, 200, { created, count: readings.length, receipt: receipt('reading', [String(created.length), String(Date.now())]) });
    } catch (e) { return send(res, 400, { error: (e as Error).message || 'reading failed' }); }
  }

  // A de-identified view of the twin (Safe-Harbor + date-shift) — proof identity is gone.
  if (req.method === 'GET' && url.pathname === '/api/health/deident') return send(res, 200, deidentify(bundle()));

  // Open a blinded consult: requires the patient's agreement (anonymous by default). `disclosure` =
  // the agreed scope ('standard' keeps age-band + sex a doctor needs; 'minimal' = facts only).
  if (req.method === 'POST' && url.pathname === '/api/health/consult') {
    try {
      const b = await readJson(req);
      const disclosure = b.disclosure === 'minimal' ? 'minimal' : 'standard';
      // Must be EXPLICIT. `b.agreed !== false` read a missing flag as agreement, so a
      // caller that never mentioned consent got a consult — which is the opposite of a
      // gate. The comment beside it already said "must explicitly agree"; now it does.
      const agreed = b.agreed === true;
      const r = openConsult(bundle(), String(b.scope ?? 'whole twin').trim() || 'whole twin', disclosure, agreed);
      return send(res, (r as any).error ? 422 : 200, r);
    } catch (e) { return send(res, 400, { error: (e as Error).message || 'consult failed' }); }
  }

  // Consult sub-routes: /api/health/consult/{id}[/review|/opinion]
  if (url.pathname.startsWith('/api/health/consult/')) {
    const rest = url.pathname.slice('/api/health/consult/'.length);
    const [id, sub] = rest.split('/');
    // A reviewer opens the blinded slice (no identity, no other opinions shown).
    if (req.method === 'GET' && !sub) { const a = aggregate(id!); return send(res, (a as any).error ? 404 : 200, a); }
    if (req.method === 'GET' && sub === 'review') { const v = reviewerView(id!); return send(res, v ? 200 : 404, v ?? { error: 'consult not found' }); }
    // A reviewer submits an independent opinion (blind).
    if (req.method === 'POST' && sub === 'opinion') {
      try {
        const b = await readJson(req);
        const r = submitOpinion(id!, String(b.reviewer ?? ''), String(b.assessment ?? ''), (['low', 'moderate', 'high'].includes(b.confidence) ? b.confidence : 'moderate') as Confidence);
        return send(res, (r as any).error ? 400 : 200, r);
      } catch (e) { return send(res, 400, { error: (e as Error).message || 'opinion failed' }); }
    }
    // A reviewer asks to see more than the agreed scope → a request the PATIENT decides on (not granted here).
    if (req.method === 'POST' && sub === 'request-more') {
      try {
        const b = await readJson(req);
        const r = requestMore(id!, String(b.field ?? ''), String(b.reason ?? ''));
        return send(res, (r as any).error ? 404 : 200, r);
      } catch (e) { return send(res, 400, { error: (e as Error).message || 'request failed' }); }
    }
  }

  // Grant a designated agent a scoped, time-boxed read grant — receipted.
  if (req.method === 'POST' && url.pathname === '/api/health/grant') {
    try {
      const b = await readJson(req);
      const agent = String(b.agent ?? '').trim();
      const scope = String(b.scope ?? 'all systems').trim() || 'all systems';
      const ttlDays = Math.max(1, Math.min(365, Number(b.ttlDays ?? 30)));
      if (!agent) return send(res, 422, { error: 'agent required' });
      const now = new Date();
      const g: Grant = {
        id: `grant-${sha256([agent, scope, String(now.getTime())].join('|'))}`,
        agent, scope, granted_at: now.toISOString(),
        expires_at: new Date(now.getTime() + ttlDays * 86400000).toISOString(),
        revoked: false, reads: 0, receipt: receipt('grant', [agent, scope, String(ttlDays)]).id,
        // structured scope: explicit spec > preset name > the scope label if it names a preset > full history
        scopeSpec: resolveScope(String(b.preset ?? scope), b.scopeSpec),
      };
      grants.unshift(g);
      return send(res, 200, { grant: { ...g, scopeSummary: scopeSummary(g.scopeSpec!) } });
    } catch { return send(res, 400, { error: 'bad json' }); }
  }

  // Grant summaries for the clinician surface (id + label + active — never the record itself).
  if (req.method === 'GET' && url.pathname === '/api/health/grants') {
    return send(res, 200, {
      grants: grants.map((g) => ({
        id: g.id, agent: g.agent, scope: g.scope,
        scopeSummary: scopeSummary(g.scopeSpec ?? resolveScope(g.scope)),
        active: !g.revoked && new Date(g.expires_at) > new Date(),
        expires_at: g.expires_at, reads: g.reads,
      })),
      presets: Object.fromEntries(Object.entries(SCOPE_PRESETS).map(([k, v]) => [k, scopeSummary(v)])),
    });
  }

  // The doctor chart's data source: exercise a grant → the SCOPED bundle. The subject stays
  // identified (the clinician is authorized); the slice is exactly what the consent covers, with
  // withheld COUNTS (never content) so the doctor can see more history exists and request it.
  // Every read is a receipt; revoked/expired/unknown grants get an explicit receipted block.
  if (req.method === 'GET' && url.pathname === '/api/health/doctor-view') {
    const id = String(url.searchParams.get('grant') ?? '');
    const r = resolveGrant(grants, id);
    if (!r.ok) return send(res, 403, { blocked: true, reason: r.reason, receipt: receipt('doctor-read-blocked', [id, r.reason]) });
    const g = r.grant;
    g.reads += 1;
    const scope = g.scopeSpec ?? resolveScope(g.scope);
    const { view, withheld } = applyScope(bundle(), scope);
    return send(res, 200, {
      grant: { id: g.id, agent: g.agent, scope: g.scope, scopeSummary: scopeSummary(scope), expires_at: g.expires_at, reads: g.reads },
      view, withheld,
      receipt: receipt('doctor-read', [g.id, String(g.reads)]),
    });
  }

  // Revoke a grant — read-enforced: future reads by that agent are blocked.
  if (req.method === 'POST' && url.pathname === '/api/health/revoke') {
    try {
      const b = await readJson(req);
      const g = grants.find((x) => x.id === String(b.grant));
      if (!g) return send(res, 404, { error: 'grant not found' });
      g.revoked = true;
      return send(res, 200, { grant: g, receipt: receipt('revoke', [g.id]) });
    } catch { return send(res, 400, { error: 'bad json' }); }
  }

  // An agent exercises a grant to read a slice — the access itself is a receipt (or a block).
  if (req.method === 'POST' && url.pathname === '/api/health/agent-read') {
    try {
      const b = await readJson(req);
      const g = grants.find((x) => x.id === String(b.grant));
      if (!g) return send(res, 404, { error: 'grant not found' });
      if (g.revoked) return send(res, 403, { blocked: true, reason: 'grant revoked — read denied' });
      if (new Date(g.expires_at) <= new Date()) return send(res, 403, { blocked: true, reason: 'grant expired — read denied' });
      g.reads += 1;
      return send(res, 200, { agent: g.agent, scope: g.scope, reads: g.reads, receipt: receipt('read', [g.id, String(g.reads)]) });
    } catch { return send(res, 400, { error: 'bad json' }); }
  }

  send(res, 404, { error: 'not found' });
});

server.listen(PORT, () => { console.log(`health-twin listening on :${PORT}`); });
