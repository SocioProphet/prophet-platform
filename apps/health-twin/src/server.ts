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
import { serviceHealth, reasonTurtle, graphGround, SERVICES } from './reconcile/clients.js';
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
import { exposureDenial, exposureFromEnv } from './exposure.js';
import {
  HOLDER_HEADER, HOLDER_AUTH_DISCLOSURE, LEGACY_QUERY_WARNING,
  authenticateHolder, bareIdPolicy, holderDigest, holderToken, legacyQueryDecision, mintHolderSecret,
  presentedHolderToken, seedGrantDecision,
} from './grantauth.js';
import { corsHeaders, corsPolicyFromEnv, originAllowed } from './cors.js';
import { mintId } from './ids.js';
import { triage } from './triage.js';
import { route } from './routing.js';
import { monitorTwin } from './monitor.js';
import { interpretReport } from './imaging.js';
import { toFhirBundle, fromFhirBundle } from './fhir.js';
import { proveFhirWriteBack } from './fhir-live.js';
import { assessImage } from './vision.js';
import { enrollPatient, authenticatePatient, patientProfile, revokePatient } from './identity.js';
import { conditionList, conditionCard, checkMeds, guidelineDeltas, type Audience } from './reference.js';
import { fdaLabel } from './drugsafety-live.js';
import { audit, auditQuery } from './audit.js';
import { findSlots, book } from './booking.js';
import { programs as contributionPrograms, contribute, revokeContribution, ledger as contributionLedger } from './contribution.js';
import { populationRisk } from './population.js';
import { valueSet, lookup, crosswalk, valueSetTtl, toOntogenesisNode, type CodeSystem, type ConceptCategory } from './terminology.js';
import { predict, EmissionLawViolation, COMPARTMENTS, COMPARTMENT_SYSTEM, currentObservations, type Covariates } from './dynamics/predict.js';
import { gatePolicy, rejectionLedger } from './dynamics/gate.js';
import { fitSurrogate } from './dynamics/surrogate.js';
import { OBSERVABLE, type Compartment } from './dynamics/mechanistic.js';

const PORT = Number(process.env.PORT ?? 8097);

// Real SHA-256 (node:crypto, no deps). Receipts and content addresses on a governance surface must be
// cryptographic: the previous djb2 (32-bit, trivially collidable) was labeled "sha-", which made
// "tamper-evident" a false claim. Now the label and the math agree.
function sha256(s: string): string {
  return createHash('sha256').update(s).digest('hex');
}
// Parts are JSON-encoded, not joined on '|'. A separator that can appear inside a part is
// not a separator: ['a|b','c'] and ['a','b|c'] join to the same string and so hash to the
// same digest. A stronger hash over an ambiguous encoding is still ambiguous — two
// different fact-sets producing one receipt id is exactly what tamper-evidence must exclude.
function receipt(kind: string, parts: string[]): { id: string; verifier: 'health-twin'; at: string } {
  return { id: `ht-${kind}-${sha256(JSON.stringify(parts))}`, verifier: 'health-twin', at: new Date().toISOString() };
}

// Exposure gate — see exposure.ts for why the condition is "is the data synthetic" rather
// than a bearer token the browser would have to hold.
const EXPOSURE = exposureFromEnv();

function denyExposure(req: http.IncomingMessage) {
  return exposureDenial({
    mode: EXPOSURE,
    token: process.env.HEALTH_TWIN_TOKEN ?? '',
    authorization: String(req.headers['authorization'] ?? ''),
    ingestedRecords: resultCounts(ingested).total,
  });
}

// In-memory grant ledger (skeleton). Local-first store in production.
//
// Indexed by id, and the index is not a micro-optimisation. `grants.find((g) => g.id === id)` walks
// the ledger, so a MISS costs a full scan and a HIT near the head costs one comparison — which makes
// the response time an answer to "does this grant id exist?" for a caller who has, by definition,
// just failed to authenticate. Measured over a 2,000-grant ledger: an unknown id took 54µs against
// 1.4µs for a known one, a 37× tell through a refusal body that is otherwise byte-identical.
// grantauth.ts closes the rest of the gap by doing the same digest work on every refusal.
//
// The array stays: it is the ORDER the patient's control panel is listed in. The two are written
// together in addGrant(), which is the only way a grant enters the ledger.
const grants: Grant[] = [];
const grantIndex = new Map<string, Grant>();
const findGrant = (id: string) => grantIndex.get(id);
function addGrant(g: Grant, where: 'head' | 'tail' = 'head') {
  if (where === 'head') grants.unshift(g); else grants.push(g);
  grantIndex.set(g.id, g);
}

// ── the demo cardiologist grant, and the two boot-time policies around it ───────────────────────
//
// This used to be an unconditional array literal right here: a fixed, well-known id (the invariants
// assert that string is gone, so it is not repeated even in this comment), active for 30 days, on
// every boot of every deployment. Since a grant id was the whole credential, that made a
// live consent grant whose secret was a string committed to a public repository — presentable by
// anyone who read the source, a log line or a `Referer`. It is now: absent by default, refused
// outright in a deployment that serves real records, and bound to a secret that is never in source.
//
// Both policies REFUSE TO BOOT rather than warn. A production configuration that cannot exist cannot
// be the thing nobody remembered to turn off.
const SEED = seedGrantDecision(process.env, EXPOSURE);
const LEGACY_QUERY = legacyQueryDecision(process.env, EXPOSURE);
// Which browser origins may drive this engine. `*` is neither emitted nor configurable — see cors.ts
// for why a wildcard stopped being survivable in the same change that made a credential presentable.
const CORS = corsPolicyFromEnv(process.env, EXPOSURE);
const ALLOWED_ORIGINS: ReadonlySet<string> = new Set(CORS.origins);
for (const fatal of [SEED.fatal, LEGACY_QUERY.fatal, CORS.fatal]) {
  if (fatal) { console.error(`health-twin: ${fatal}`); process.exit(1); }
}
console.log(`health-twin: CORS — ${CORS.why}${CORS.origins.length ? ` [${CORS.origins.join(' ')}]` : ''}`);
if (SEED.seed) {
  // The scope is the cardiometabolic wedge, so the doctor chart still demos scoping on a fresh boot
  // (the childhood knee history is OUTSIDE it — it shows up as withheld counts).
  addGrant({
    id: 'grant-dev-seed-cardiology',
    agent: 'Dr. A. Rivera (Cardiology) — DEV SEED, synthetic subject only',
    scope: 'cardiometabolic',
    scopeSpec: resolveScope('cardiometabolic'),
    granted_at: new Date().toISOString(),
    expires_at: new Date(Date.now() + 30 * 86_400_000).toISOString(),
    revoked: false, reads: 0, receipt: 'ht-grant-dev-seed',
    holderDigest: holderDigest(SEED.secret!),
  }, 'tail');
  console.log(`health-twin: DEV SEED GRANT active (${SEED.why}). Synthetic subject only.`);
  // The seed grant's holder SECRET is never written to a log. A credential in a log is precisely the
  // leak channel this PR closes (access logs, proxy logs, browser history, `Referer`), so the seed is
  // no exception: printing `grant-dev-seed-cardiology.<secret>` here would re-open it on the operator's
  // stdout. CI proves the positive path by supplying the secret out of band
  // (HEALTH_TWIN_SEED_GRANT_SECRET), never by scraping this line — see the invariant on seedGrantDecision.
  if (SEED.minted) {
    console.log(
      `health-twin: DEV SEED GRANT holder secret was minted this boot and is NOT logged (a credential in a ` +
      `log is the defect this service refuses). It is unrecoverable; to drive the seed grant set ` +
      `HEALTH_TWIN_SEED_GRANT_SECRET to a holder secret you choose and reboot — the id alone is not a credential.`);
  } else {
    console.log(`health-twin: seed holder secret taken from HEALTH_TWIN_SEED_GRANT_SECRET (not printed)`);
  }
} else if (SEED.why) {
  console.log(`health-twin: no demo grant — ${SEED.why}`);
}
if (LEGACY_QUERY.allowed) {
  console.warn(`health-twin: DEPRECATED — ${LEGACY_QUERY.why}. ?grant=<id> authenticates nobody and leaks the id into every log in the path.`);
}

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
    // `holderDigest` is the verifier for a live credential. It is not secret-equivalent (sha256 of
    // 256 random bits), but there is no reason for it to be readable, and publishing verifiers is how
    // an offline guessing target gets handed out for free.
    grants: grants.map((g) => publicGrant(g)),
    // records pulled through the connector plane (provenance + epistemic tier on every one).
    ingested: { ...ingested, summary: ingestedSummary() },
    // captured media (voice notes, photos, documents) — hash-sealed, tier-tagged.
    captured,
    // the twin speaks the estate's ontology: every fact carries a class IRI from the HDT ontology.
    ontology: { health: HEALTH_NS, hdt: HDT_NS, subjectClass: `${HDT_NS}HumanDigitalTwin`, note: 'Facts carry health:/hdt: class IRIs so they type into HellGraph + reason in Ontogenesis.' },
    disclaimer: 'Synthetic sample. Not a real person, not medical advice. This tool organises records; it does not diagnose.',
  };
}

// Emit the twin as typed RDF (Turtle) the sophos-reasoner can consume: the subject is a
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

/**
 * 🔴 THIS IS THE SHARED CORS SURFACE. Every route answers through here, so the wildcard that used to
 * sit on this line was on every response the service made — including the ones that accept and act
 * on the holder credential. `access-control-allow-origin: *` plus `access-control-allow-headers:
 * … x-health-grant` is an invitation: any page in any tab may call this engine, set the credential,
 * and read the reply. Minting is ungated on a synthetic-only deployment, so a page could issue itself
 * a grant, take the one-shot secret from a response it was allowed to read, and pull the chart —
 * cross-origin, with no leaked id at all. The credential this PR introduced was usable by an attacker
 * page the moment it existed.
 *
 * Now the origin is matched against an explicit allowlist (cors.ts) and echoed only on a hit; a
 * caller with no `Origin` — same-origin browser requests through the nginx /svc/health proxy, curl,
 * every server-to-server client — gets no CORS headers, because it never looks at them. `res.req` is
 * the request this response belongs to, so no call site had to change: a per-route flag would have
 * been the thing someone forgets on the one route that matters.
 */
function send(res: http.ServerResponse, code: number, body: unknown, extra: Record<string, string> = {}) {
  res.writeHead(code, {
    'content-type': 'application/json',
    ...corsHeaders(res.req?.headers?.origin as string | undefined, ALLOWED_ORIGINS),
    ...extra,
  });
  res.end(JSON.stringify(body));
}

// The grant as anyone but the ledger may see it: never the holder verifier.
const publicGrant = (g: Grant) => {
  const { holderDigest: _verifier, ...rest } = g;
  return { ...rest, active: !g.revoked && new Date(g.expires_at) > new Date() };
};
function readJson(req: http.IncomingMessage): Promise<any> {
  return new Promise((resolve, reject) => {
    let raw = ''; req.on('data', (c) => { raw += c; if (raw.length > 2_000_000) req.destroy(); });
    req.on('end', () => { try { resolve(raw ? JSON.parse(raw) : {}); } catch (e) { reject(e); } });
    req.on('error', reject);
  });
}

// ── the consent membrane's front door ───────────────────────────────────────────────────────────
//
// Every route that reads THROUGH a grant comes through here, so there is one answer to "who may
// exercise this consent" rather than five copies that drift. The order is deliberate:
//
//   1. the query-string form is refused before anything is looked up — accepting a credential on a
//      channel that logs it is the defect, and answering it at all normalises the channel;
//   2. the HOLDER is authenticated (constant-time digest compare) with ONE uniform failure, so a
//      caller who cannot authenticate cannot use the endpoint to discover which grant ids exist;
//   3. only then is grant STATE consulted, so revoked/expired keep their stated reasons — reported
//      to someone who has proved they hold the grant.
//
// Every refusal carries a receipt, for the same reason every read does: a block nobody can point at
// afterwards is indistinguishable from a block that never happened.
type GrantAuthz =
  | { ok: true; grant: Grant; holder: string; legacy: boolean }
  | { ok: false; code: number; body: Record<string, unknown>; headers?: Record<string, string> };

/**
 * `who` names the surface being read, so the receipt says WHAT was presented against WHICH subject
 * on WHICH route. `required` is false for routes where a grant narrows an otherwise-permitted read
 * (evidence, predict, the rejection ledger): no grant at all means "no narrowing", a presented grant
 * means "authenticate it".
 */
function authorizeGrant(req: http.IncomingMessage, url: URL, who: string, required: boolean, legacyBodyId?: string): GrantAuthz | null {
  // The two channels a bare id used to arrive on: `?grant=` (logged everywhere) and a JSON body
  // field (not logged, but still possession-is-authorization). Neither is a credential.
  const queryId = url.searchParams.get('grant');
  const bodyId = legacyBodyId != null && String(legacyBodyId).trim() ? String(legacyBodyId) : null;
  const channel: 'query' | 'body' | null = queryId !== null ? 'query' : bodyId !== null ? 'body' : null;
  const bareId = queryId ?? bodyId;
  const presented = presentedHolderToken(req.headers as Record<string, string | string[] | undefined>);

  // 🔴 THE GUARD USED TO BE `bareId !== null && !presented`, which meant a request carrying BOTH a
  // `?grant=<id>` and a valid header skipped the refusal and was served 200: the id still landed in
  // the access log, the proxy log, the history and the `Referer`, and the deprecation `Warning` was
  // suppressed on precisely the requests that were teaching callers the channel still works. What
  // leaks the id is the URL, not the absence of a better credential. So the bare form is refused
  // WHENEVER IT IS PRESENT — see bareIdPolicy(), which is pure and covered by the invariants.
  if (channel !== null) {
    const policy = bareIdPolicy({ channel, presented: !!presented, legacyAllowed: LEGACY_QUERY.allowed });
    if (policy.refuse) {
      return {
        ok: false, code: 401,
        body: {
          blocked: true, authenticated: false,
          reason: policy.reason, detail: policy.detail,
          receipt: grantUseReceipt('grant-auth-denied', [who, policy.reason!], { route: who, authenticated: false }),
        },
        headers: { warning: LEGACY_QUERY_WARNING },
      };
    }
    // Enabled only on a synthetic-only deployment, and loud on every single use.
    const r = resolveGrant(grantIndex, bareId!);
    if (!r.ok) {
      return {
        ok: false, code: 403,
        body: { blocked: true, authenticated: false, reason: r.reason, receipt: grantUseReceipt(`${who}-blocked`, [bareId!, r.reason], { route: who, authenticated: false }) },
        headers: { warning: LEGACY_QUERY_WARNING },
      };
    }
    // `bareId` is caller-supplied; strip CR/LF before it reaches the log so a crafted id cannot forge
    // or split log lines (log-injection). `who` is a fixed route name, not user input.
    console.warn(`health-twin: DEPRECATED unauthenticated bare-id read on ${who} (${String(bareId).replace(/[\r\n]/g, ' ')})`);
    return { ok: true, grant: r.grant, holder: 'unauthenticated:legacy-bare-id', legacy: true };
  }

  if (!presented && !required) return null; // no grant offered, and this route does not demand one

  const auth = authenticateHolder({
    presented,
    find: findGrant,
    onUnbound: (id) => console.warn(`health-twin: grant ${id} carries no holder binding — refused (fail-closed)`),
  });
  if (!auth.ok) {
    return {
      ok: false, code: auth.code,
      body: { blocked: true, authenticated: false, reason: auth.reason, detail: auth.detail, receipt: grantUseReceipt('grant-auth-denied', [who, auth.reason], { route: who, authenticated: false }) },
    };
  }
  // The holder is proved. Now, and only now, the grant's own state answers.
  const r = resolveGrant(grantIndex, auth.grantId);
  if (!r.ok) {
    return {
      ok: false, code: 403,
      body: { blocked: true, authenticated: true, reason: r.reason, receipt: grantUseReceipt(`${who}-blocked`, [auth.grantId, auth.holderDigest, r.reason], { route: who, grant: auth.grantId, presentedBy: auth.holderDigest }) },
    };
  }
  return { ok: true, grant: r.grant, holder: auth.holderDigest, legacy: false };
}

/**
 * A grant-use receipt names WHO presented WHAT against WHICH subject — the three things an audit
 * after the fact has to answer. Same `ht-<kind>-<sha256>` shape and same `verifier`/`at` fields as
 * every other receipt this service emits; the holder appears as the stored digest, never the secret.
 */
function grantUseReceipt(kind: string, parts: string[], extra: Record<string, unknown> = {}) {
  return { ...receipt(kind, [...parts, SUBJECT.id]), subject: SUBJECT.id, ...extra };
}

/** What an authenticated read says about the authentication behind it. Claims nothing more. */
const authenticatedAs = (a: Extract<GrantAuthz, { ok: true }>) => (a.legacy
  ? { ...HOLDER_AUTH_DISCLOSURE, mechanism: 'none (deprecated ?grant= query form)', binds: 'nobody — possession of an id that travels in logs', channel: 'query string', deprecated: true }
  : HOLDER_AUTH_DISCLOSURE);

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url ?? '/', `http://${req.headers.host}`);
  // The preflight is where a browser asks whether it may send `x-health-grant` from this origin. An
  // origin that is not on the list is told no, out loud, rather than being handed a 204 with no
  // allowance in it — the browser blocks either way, but only one of them is debuggable.
  if (req.method === 'OPTIONS') {
    const o = String(req.headers.origin ?? '');
    return o && !originAllowed(o, ALLOWED_ORIGINS)
      ? send(res, 403, { error: 'origin not allowed', detail: 'name it in HEALTH_TWIN_ALLOWED_ORIGINS' })
      : send(res, 204, {});
  }
  if (req.method === 'GET' && url.pathname === '/healthz') return send(res, 200, { ok: true, service: 'health-twin' });

  // The twin bundle (the surface's one read).
  if (req.method === 'GET' && url.pathname === '/api/health/twin') {
    const denied = denyExposure(req);
    return denied ? send(res, denied.code, denied.body) : send(res, 200, bundle());
  }

  // the twin as reasoner-ready RDF (Turtle) — typed with the HDT ontology, imports the TBox.
  //
  // 🔴 This is the SAME BUNDLE /api/health/twin serves, in another serialisation, and it was ungated
  // while that route was not — so the exposure membrane could be walked around by asking for Turtle.
  // A serialisation is not a permission boundary: the RDF carries the subject label, the coded
  // observations and their values. Found while auditing the dynamics surfaces; same membrane, same
  // condition, same refusal.
  if (req.method === 'GET' && url.pathname === '/api/health/twin.ttl') {
    const denied = denyExposure(req);
    if (denied) return send(res, denied.code, denied.body);
    // Turtle, so it does not go through send() — and so it had its own hand-rolled `*`. Same policy,
    // written once: a second CORS surface is a second thing to forget.
    res.writeHead(200, {
      'content-type': 'text/turtle; charset=utf-8',
      ...corsHeaders(req.headers.origin, ALLOWED_ORIGINS),
    });
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
  // ie-engine, holmes, hellgraph-service, sophos-reasoner). Every route degrades gracefully: a down
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

  // Reason over the twin's typed RDF via sophos-reasoner → RDFS/OWL-RL entailments (conditions ⊑
  // hdt:FHIRResource, drives correspondence promotion). Reuses the same twin.ttl the reasoner consumes.
  //
  // 🔴 THIS IS AN EGRESS OF RECORD CONTENT TO ANOTHER SERVICE. `twinTtl()` is the whole twin — subject,
  // coded observations, values — and it is POSTed out of this process to the reasoner at HT_OWL_URL.
  // Two things follow, and neither was true before:
  //
  //   • It is exposure-gated. Sending the bundle somewhere is at least as consequential as serving it,
  //     so the route that ships it cannot be more permissive than the route that returns it. /twin
  //     refuses once real records land; so does this.
  //
  //   • It emits a RECEIPT, because this was the largest unrecorded action in the twin. Everything else
  //     consequential here leaves one, and an egress of PHI that left none meant nobody could answer
  //     "what went out, and where did it go?" after the fact. The receipt names the DESTINATION (the
  //     resolved URL, not the word "reasoner" — the default is localhost but HT_OWL_URL can point
  //     anywhere, and which one it was is the whole question), the CONTENT CLASS, and a sha256 of the
  //     exact bytes that left, so the claim is checkable rather than asserted. It is recorded whether
  //     the call succeeds or fails: the bundle leaves this process either way.
  if (req.method === 'POST' && url.pathname === '/api/health/reason') {
    const denied = denyExposure(req);
    if (denied) return send(res, denied.code, denied.body);
    const ttl = twinTtl();
    const egress = {
      ...receipt('egress-reason', [SERVICES.owl, 'twin-rdf', sha256(ttl)]),
      destination: `${SERVICES.owl}/reason`,
      contentClass: 'twin-rdf-turtle (full record bundle: subject, coded observations, values)',
      bytes: Buffer.byteLength(ttl, 'utf8'),
      contentDigest: `sha256-${sha256(ttl)}`,
      inference: 'rdfs',
    };
    const r = await reasonTurtle(ttl, 'rdfs');
    return send(res, 200, r.ok
      ? { ...r.data, egress }
      : { service: 'degraded', reason: r.reason, entailed_triples: 0, entailments: [], egress });
  }

  // ── CDS Hooks (HL7 CDS Hooks 2.0) — the twin as a decision-moment service inside the EHR. Cards are
  // cited, epistemic-tiered, holmes-verified, and framed non-diagnostically. ────────────────────────
  if (req.method === 'GET' && url.pathname === '/cds-services') return send(res, 200, discovery());
  if (req.method === 'POST' && url.pathname.startsWith('/cds-services/')) {
    try {
      await readJson(req); // hook context (patientId, prefetch) — skeleton reads the local twin
      const id = url.pathname.slice('/cds-services/'.length);
      // SMART launch links go into CDS cards a clinician clicks. Falling back to
      // req.headers.host let a caller choose that destination: Host is attacker-supplied
      // on most deployments, so a crafted header pointed the "launch the twin" link at a
      // domain of their choosing, inside a card the EHR presents as ours.
      // Configured value only — no configuration means relative links, which resolve
      // against whatever origin actually served the card rather than a claimed one.
      const base = process.env.SMART_APP_BASE ?? '';
      if (id === 'health-twin-patient-summary') return send(res, 200, await patientSummaryCards(ingested, base));
      if (id === 'health-twin-medication-reconciliation') return send(res, 200, await medReconciliationCards(ingested, base));
      return send(res, 404, { error: `unknown cds-service: ${id}` });
    } catch (e) { return send(res, 400, { error: (e as Error).message || 'cds failed' }); }
  }

  // ── Wall 4: de-identification + blinded n-ary consults (the moat). Non-diagnostic; the aggregate is a
  // concordance signal, a clinician decides. ────────────────────────────────────────────────────────

  // Guideline-grounded guidance — the twin's own numbers → cited, non-diagnostic recommendations
  // grounded in real clinical guidelines (ACC/AHA, ADA, USPSTF, KDIGO).
  // 🔴 guidance() reads the twin's own labs, vitals, conditions and medications: each item names the
  // `finding` that triggered it and `cites` the record ids it is grounded on. Guideline TEXT is public;
  // which guidelines fire on THIS person is not. Gated on the same condition as the record itself.
  if (req.method === 'GET' && url.pathname === '/api/health/guidance') {
    const denied = denyExposure(req);
    return denied ? send(res, denied.code, denied.body) : send(res, 200, guidance());
  }

  // Triage — the agentic OOD loop (Perceive→Reason→Act→Verify) over a described complaint: structures
  // symptoms, detects red flags, bands urgency, asks the next-best question, and routes disposition
  // (act/abstain/escalate). Non-diagnostic; a red flag can never resolve below emergency (invariant).
  if (req.method === 'POST' && url.pathname === '/api/health/triage') {
    const denied = denyExposure(req);
    if (denied) return send(res, denied.code, denied.body);
    try {
      const b = await readJson(req);
      const t = await triage(String(b.complaint ?? b.text ?? b.q ?? ''));
      // `route=1` (or POST includes it) also returns the care route + pre-visit summary in one call.
      const withRoute = b.route === true || b.route === 1 || url.searchParams.get('route') === '1';
      return send(res, 200, withRoute ? { triage: t, route: route(t) } : t);
    } catch (e) { return send(res, 400, { error: (e as Error).message || 'triage failed' }); }
  }

  // Care routing — turn a triage result into action: setting, specialty, modality, timing, candidate
  // providers, and a clinician-facing pre-visit summary (Zocdoc pattern; verbs Route + Prepare).
  if (req.method === 'POST' && url.pathname === '/api/health/route') {
    const denied = denyExposure(req);
    if (denied) return send(res, denied.code, denied.body);
    try {
      const b = await readJson(req);
      // accept either a full triage result or a raw complaint (triage it first)
      const t = (b && typeof b === 'object' && 'urgency' in b && 'disposition' in b)
        ? (b as any) : await triage(String(b.complaint ?? b.text ?? ''));
      return send(res, 200, { route: route(t), triage: t });
    } catch (e) { return send(res, 400, { error: (e as Error).message || 'route failed' }); }
  }

  // Terminology value sets (SNOMED/LOINC/RxNorm/ICD-10) bound to Ontogenesis + HDT — each concept
  // carries its hdt:/health: class IRI + organ/system + cross-maps, so codes are typed world-model
  // nodes, not a flat lexicon. /ttl emits the SKOS/RDF the owl-reasoner + Ontogenesis consume.
  if (req.method === 'GET' && url.pathname === '/api/health/terminology/valueset') {
    return send(res, 200, valueSet((url.searchParams.get('category') as ConceptCategory) ?? undefined));
  }
  if (req.method === 'GET' && url.pathname === '/api/health/terminology/lookup') {
    const p = url.searchParams;
    const c = lookup({ system: (p.get('system') as CodeSystem) ?? undefined, code: p.get('code') ?? undefined, q: p.get('q') ?? undefined });
    return send(res, c ? 200 : 404, c ? { concept: c, ontogenesis: toOntogenesisNode(c) } : { error: 'concept not found' });
  }
  if (req.method === 'GET' && url.pathname === '/api/health/terminology/crosswalk') {
    const p = url.searchParams;
    return send(res, 200, crosswalk((p.get('system') as CodeSystem) ?? 'SNOMED', p.get('code') ?? ''));
  }
  if (req.method === 'GET' && url.pathname === '/api/health/terminology/ttl') {
    res.writeHead(200, { 'content-type': 'text/turtle; charset=utf-8', ...corsHeaders(req.headers.origin, ALLOWED_ORIGINS) });
    return res.end(valueSetTtl());
  }

  // Audit trail (HIPAA §164.312(b)) — the append-only access log for compliance review. Exposure-gated
  // (this is the record-access history); filterable by actor/action/outcome. Read-only; append-only.
  if (req.method === 'GET' && url.pathname === '/api/health/audit') {
    const denied = denyExposure(req);
    if (denied) return send(res, denied.code, denied.body);
    const p = url.searchParams;
    return send(res, 200, auditQuery({ actor: p.get('actor') ?? undefined, action: p.get('action') ?? undefined, outcome: (p.get('outcome') as any) ?? undefined, limit: p.get('limit') ? Number(p.get('limit')) : undefined }));
  }

  // Population & operations layer (surface 5) — cohort risk + care gaps + early warnings over
  // DE-IDENTIFIED aggregates, with a k-anonymity floor. Aggregates only; non-diagnostic; not surveillance.
  if (req.method === 'GET' && url.pathname === '/api/health/population') {
    const denied = denyExposure(req);
    return denied ? send(res, denied.code, denied.body) : send(res, 200, populationRisk());
  }

  // Care-access marketplace (verb 6 Book) — find bookable slots (specialty/modality/insurance/timing)
  // and hold one, carrying the pre-visit summary forward. Non-diagnostic; arranges access.
  if (req.method === 'GET' && url.pathname === '/api/health/booking/slots') {
    const p = url.searchParams;
    return send(res, 200, findSlots({
      specialty: p.get('specialty') ?? undefined,
      modality: (p.get('modality') as any) ?? undefined,
      insurance: p.get('insurance') ?? undefined,
      withinHours: p.get('withinHours') ? Number(p.get('withinHours')) : undefined,
    }));
  }
  if (req.method === 'POST' && url.pathname === '/api/health/booking/book') {
    try { const b = await readJson(req); const r = book(String(b.slotId ?? ''), { preVisitSummary: b.preVisitSummary }); return send(res, 'error' in r ? 404 : 200, r); }
    catch (e) { return send(res, 400, { error: (e as Error).message || 'book failed' }); }
  }

  // Data cooperative (verb 10 Learn; Segmed pattern) — programs, consented de-identified contribution,
  // revoke, and the transparent compensation ledger. Consent fails closed; only de-id data leaves.
  if (req.method === 'GET' && url.pathname === '/api/health/contribution/programs') return send(res, 200, contributionPrograms());
  if (req.method === 'POST' && url.pathname === '/api/health/contribution/join') {
    try { const b = await readJson(req); const r = contribute(String(b.programId ?? ''), bundle(), b.agreed === true); return send(res, 'error' in r ? 422 : 200, r); }
    catch (e) { return send(res, 400, { error: (e as Error).message || 'join failed' }); }
  }
  if (req.method === 'POST' && url.pathname === '/api/health/contribution/revoke') {
    try { const b = await readJson(req); return send(res, 200, revokeContribution(String(b.id ?? ''))); }
    catch (e) { return send(res, 400, { error: (e as Error).message || 'revoke failed' }); }
  }
  if (req.method === 'GET' && url.pathname === '/api/health/contribution/ledger') return send(res, 200, contributionLedger());

  // Professional reference layer — condition cards rendered by audience, medication safety check, and
  // the guideline-delta engine. Task-first, non-diagnostic; one source of truth, many renderers.
  if (req.method === 'GET' && url.pathname === '/api/health/reference/conditions') {
    return send(res, 200, { conditions: conditionList() });
  }
  if (req.method === 'GET' && url.pathname.startsWith('/api/health/reference/condition/')) {
    const id = url.pathname.slice('/api/health/reference/condition/'.length);
    const audience = (url.searchParams.get('audience') ?? 'patient') as Audience;
    const card = conditionCard(id, ['patient', 'clinician', 'trainee'].includes(audience) ? audience : 'patient');
    return send(res, card ? 200 : 404, card ?? { error: 'condition not found' });
  }
  if (req.method === 'POST' && url.pathname === '/api/health/reference/med-check') {
    try { const b = await readJson(req); return send(res, 200, checkMeds(b?.medications, b?.allergies)); }
    catch (e) { return send(res, 400, { error: (e as Error).message || 'med-check failed' }); }
  }
  // Live FDA drug label (openFDA + RxNorm) — real boxed warnings, contraindications, interactions.
  if (req.method === 'GET' && url.pathname === '/api/health/reference/drug-label') {
    return send(res, 200, await fdaLabel(url.searchParams.get('name') ?? ''));
  }
  if (req.method === 'GET' && url.pathname === '/api/health/reference/guideline-deltas') {
    return send(res, 200, guidelineDeltas(url.searchParams.get('area') ?? undefined));
  }

  // FHIR interop plane — export the twin as an HL7 FHIR R4 Bundle (de-identified Patient), or import
  // a FHIR Bundle → twin records. How we read/write the real healthcare system (beats NEPHRO-DIGITAL).
  if (req.method === 'GET' && url.pathname === '/api/health/fhir') {
    const denied = denyExposure(req);
    return denied ? send(res, denied.code, denied.body) : send(res, 200, toFhirBundle());
  }
  if (req.method === 'POST' && url.pathname === '/api/health/fhir/import') {
    try { const b = await readJson(req); return send(res, 200, fromFhirBundle(b)); }
    catch (e) { return send(res, 400, { error: (e as Error).message || 'fhir import failed' }); }
  }
  // LIVE write-back proof — writes a DE-IDENTIFIED SYNTHETIC Observation to a real FHIR server and
  // reads it back (closed-loop interop). Opt-in outbound; only synthetic data ever leaves.
  if (req.method === 'POST' && url.pathname === '/api/health/fhir/push') {
    try { const b = await readJson(req).catch(() => ({})); return send(res, 200, await proveFhirWriteBack(b?.target)); }
    catch (e) { return send(res, 400, { error: (e as Error).message || 'fhir push failed' }); }
  }

  // Patient identity plane — a real person enrolls + owns their twin (the third actor, distinct from
  // the operator and clinician grant-holders). Enroll mints a one-time credential; auth fails closed.
  if (req.method === 'POST' && url.pathname === '/api/health/patient/enroll') {
    try { const b = await readJson(req).catch(() => ({})); return send(res, 200, enrollPatient(String(b?.displayName ?? 'Patient'), b?.twinSubject ?? null)); }
    catch (e) { return send(res, 400, { error: (e as Error).message || 'enroll failed' }); }
  }
  if (req.method === 'GET' && url.pathname === '/api/health/patient/me') {
    const a = authenticatePatient(req.headers as any);
    if (!a.ok) return send(res, 401, { authenticated: false, reason: a.reason });
    return send(res, 200, { authenticated: true, profile: patientProfile(a.patientId) });
  }
  if (req.method === 'POST' && url.pathname === '/api/health/patient/revoke') {
    const a = authenticatePatient(req.headers as any); // only the patient may revoke their own credential
    if (!a.ok) return send(res, 401, { authenticated: false, reason: a.reason });
    return send(res, 200, revokePatient(a.patientId));
  }

  // Multimodal image intake — routes an image to a vision model (LLaVA) for a NON-DIAGNOSTIC visual
  // observation + danger-sign detection. Graceful: no model → degraded, fabricates nothing.
  if (req.method === 'POST' && url.pathname === '/api/health/vision') {
    const denied = denyExposure(req);
    if (denied) return send(res, denied.code, denied.body);
    try { const b = await readJson(req); return send(res, 200, await assessImage(String(b.image ?? b.imageBase64 ?? ''))); }
    catch (e) { return send(res, 400, { error: (e as Error).message || 'vision failed' }); }
  }

  // Imaging & document agent — plain-language explanation of a radiology/pathology/discharge report
  // TEXT, with a critical-finding floor. Non-diagnostic; explains a report, does not read pixels.
  if (req.method === 'POST' && url.pathname === '/api/health/interpret') {
    const denied = denyExposure(req);
    if (denied) return send(res, denied.code, denied.body);
    try {
      const b = await readJson(req);
      return send(res, 200, await interpretReport(String(b.report ?? b.text ?? '')));
    } catch (e) { return send(res, 400, { error: (e as Error).message || 'interpret failed' }); }
  }

  // Longitudinal monitor — acuity band per tracked metric (fitness-fatigue generalization): stable /
  // improving / watch / worsening / critical, with a deterioration→escalate signal. Non-diagnostic.
  if (req.method === 'GET' && url.pathname === '/api/health/monitor') {
    const denied = denyExposure(req);
    return denied ? send(res, denied.code, denied.body) : send(res, 200, monitorTwin());
  }

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
  // The evidence is scoped SERVER-SIDE to records inside the grant, so withheld findings can't leak
  // to the clinician through the evidence side door. Enforced here, not in the client. A blocked
  // grant blocks evidence too.
  if (req.method === 'GET' && url.pathname === '/api/health/evidence') {
    // 🔴 Every item carries `recordId` and `finding` — the person's own out-of-range labs and active
    // conditions. With a grant it was scoped; with NO grant it returned everything, ungated. The
    // exposure gate applies for the same reason it applies to /twin.
    const denied = denyExposure(req);
    if (denied) return send(res, denied.code, denied.body);
    // 🔴 …and the GRANT is required as well, which it was not. Both membranes, because they answer
    // different questions: exposure says whether this deployment may serve records at all, the grant
    // says how much of them THIS reader may see. `required: false` meant a caller past the exposure
    // gate and holding no grant got the widest read the service can perform — every out-of-range
    // observation and every condition with its value, unit and reference range, plus the patient's
    // age band, sex and comorbidity list as retrieval context. That is the content a scope withholds.
    // The cockpit (prophet-platform#1083) already assumes the 401 and only calls this after a
    // clinician has entered a token.
    const a = authorizeGrant(req, url, 'evidence', true)!;
    if (!a.ok) return send(res, a.code, a.body, a.headers);
    const grounded = await groundTwin();
    const scope = a.grant.scopeSpec ?? resolveScope(a.grant.scope);
    const { view } = applyScope(bundle(), scope);
    const keptIds = new Set<string>([
      ...view.systems.flatMap((s: any) => [...s.observations, ...s.conditions].map((x: any) => x.id)),
    ]);
    return send(res, 200, {
      ...grounded,
      items: grounded.items.filter((i) => keptIds.has(i.recordId)),
      authentication: authenticatedAs(a),
      receipt: grantUseReceipt('evidence-read', [a.grant.id, a.holder], { grant: a.grant.id, presentedBy: a.holder }),
    }, a.legacy ? { warning: LEGACY_QUERY_WARNING } : {});
  }

  // ── W10 TWIN DYNAMICS — the twin PREDICTS, under a gate. "Learned proposes, physics disposes."
  // A mechanistic organ model runs first; a learned residual proposes a correction; the reconciliation
  // gate accepts it only inside physiologically admissible bounds and otherwise REJECTS it with a typed
  // reason, emitting the physics and recording the refusal. Every prediction is sealed with the model,
  // the surrogate version and the gate policy it came from. Non-diagnostic; synthetic data. ──────────

  // What the twin can predict, and the exact rules a learned correction has to satisfy. A surface shows
  // this next to a prediction so "why was that refused?" is answerable without reading the code.
  //
  // The POLICY half is genuinely not record content — compartment definitions, the rule table, the
  // surrogate's version and weight digest — and it stays readable ungated, because a UI that cannot
  // read the rules cannot explain a refusal, and an unexplainable refusal is the thing this wave exists
  // to prevent.
  //
  // `anchoredTo` is NOT policy. It is the person's own latest recorded systolic pressure, HbA1c and
  // eGFR — record content, and it was being served through an ungated endpoint with CORS `*`, which is
  // precisely the leak the exposure membrane exists to stop. It is now behind `denyExposure`, on the
  // same condition as /twin, /deident and /predict. When it is withheld the response SAYS SO and names
  // the reason rather than silently omitting the field: a surface must be able to tell "this twin has
  // no anchor" from "you may not see this twin's anchor".
  if (req.method === 'GET' && url.pathname === '/api/health/dynamics') {
    const sur = fitSurrogate();
    const denied = denyExposure(req);
    return send(res, 200, {
      compartments: COMPARTMENTS.map((k) => ({ compartment: k, ...OBSERVABLE[k], system: COMPARTMENT_SYSTEM[k] })),
      anchoredTo: denied ? null : currentObservations(),
      ...(denied ? { anchorWithheld: { reason: 'exposure', code: denied.code, ...denied.body } } : {}),
      surrogate: { id: sur.id, version: sur.version, coefficientsDigest: sur.coefficientsDigest, fittedOn: sur.fittedOn, residualOnly: true, organs: sur.organs },
      gate: gatePolicy(),
      disclaimer: 'Synthetic sample. A trajectory projection, not a diagnosis or a prognosis. A clinician decides.',
    });
  }

  // Run the twin forward.
  // Two membranes apply, for two different reasons:
  //   • the EXPOSURE gate, because a trajectory is derived from the records and starts at the person's
  //     actual measured values — the same reason /deident is gated, so the forecast is not the way real
  //     records leave an openly-served twin;
  //   • the GRANT scope, because a clinician holding a cardiovascular grant must not learn the renal
  //     trajectory. Enforced SERVER-SIDE, so a prediction cannot become a side door around consent.
  if (req.method === 'POST' && url.pathname === '/api/health/predict') {
    try {
      const denied = denyExposure(req);
      if (denied) return send(res, denied.code, denied.body);
      const b = await readJson(req);
      // Fields are read one by one and never spread: the TEST-ONLY overrideDelta hook must stay
      // unreachable from the network, or the gate could be steered by its own caller.
      const horizonDays = b.horizonDays != null ? Number(b.horizonDays) : undefined;
      const stepDays = b.stepDays != null ? Number(b.stepDays) : undefined;
      let compartments = Array.isArray(b.compartments)
        ? (b.compartments as unknown[]).map(String).filter((k): k is Compartment => (COMPARTMENTS as string[]).includes(k))
        : COMPARTMENTS;
      const covariates = b.covariates && typeof b.covariates === 'object' ? (b.covariates as Covariates) : undefined;

      const a = authorizeGrant(req, url, 'predict', false);
      if (a && !a.ok) return send(res, a.code, a.body, a.headers);
      let withheldSystems: string[] = [];
      if (a) {
        const scope = a.grant.scopeSpec ?? resolveScope(a.grant.scope);
        const allowed = compartments.filter((k) => scope.systems === 'all' || scope.systems.includes(COMPARTMENT_SYSTEM[k]));
        withheldSystems = compartments.filter((k) => !allowed.includes(k)).map((k) => COMPARTMENT_SYSTEM[k]);
        compartments = allowed;
      }
      if (compartments.length === 0) return send(res, 403, { blocked: true, reason: 'no compartment is inside this grant\u2019s scope' });

      const p = predict({ horizonDays, stepDays, compartments, covariates });
      // #8 holder-auth: the success body carries the authenticated grant + use-receipt; #9's verdict
      // gate below is applied to exactly this body (auth first, then the physics verdict).
      const body = a
        ? { ...p, grant: { id: a.grant.id, withheldSystems }, authentication: authenticatedAs(a), grantReceipt: grantUseReceipt('predict-read', [a.grant.id, a.holder], { grant: a.grant.id, presentedBy: a.holder }) }
        : p;
      const extra = a?.legacy ? { warning: LEGACY_QUERY_WARNING } : {};
      const rec = p.reconciliation;

      // ── THE GATE VERDICT IS CONSULTED HERE, NOT JUST COMPUTED ────────────────────────────────
      // The body-state schema's safety invariant is that a 'divergent' forward model MUST NOT drive
      // human actuation. gate.ts emits exactly that — executionDecision 'deny', humanActuation
      // 'blocked', omegaCeiling 'TRUSTED' — and this endpoint used to send it with `200 OK` in a body
      // shaped identically to an allowed prediction. The verdict was serialised and inert: a caller
      // doing the ordinary `if (res.ok) render(body.organs)` could not tell a denied forward model
      // from a permitted one. And this is NOT a theoretical path — `covariates` is caller-supplied,
      // so an unprivileged POST can drive the surrogate across the admissibility bounds and make the
      // run divergent. It was reachable, it was live, and it read as success.
      //
      // Why 409 and not 200: a naive client keys off `res.ok`, so the refusal has to be non-2xx or it
      // is not a refusal. Why 409 and not 403: in this engine 403 means "you may not SEE this" — the
      // exposure membrane and the grant scope both use it — and that is a different thing. Here the
      // caller may see the trajectory in full; what is withdrawn is its standing to drive an action.
      // Conflating the two would render "access denied" over data the caller is entitled to read, and
      // would make a consent refusal and a physics refusal indistinguishable in any log or dashboard.
      // 409 Conflict is the accurate one: the learned proposal conflicts with the mechanistic law.
      //
      // Why the prediction moves under `prediction`: the SHAPE has to differ too. A denied response
      // that still answers `body.organs[i].emitted` is one careless `res.ok` away from being rendered
      // as an ordinary forecast. Nested, a client that never considered divergence gets `undefined`
      // and fails loudly instead of quietly. The trajectory itself is still served in full and is
      // still the mechanistic one, exactly as the gate's own reason text promises.
      if (rec.executionDecision === 'deny') {
        return send(res, 409, {
          blocked: true,
          reason: rec.reason,
          // hoisted, not merely nested: these three ARE the safety invariant, and a reader that has to
          // walk into `.reconciliation` to find them is a reader that can miss them
          executionDecision: rec.executionDecision,
          humanActuation: rec.humanActuation,
          omegaCeiling: rec.omegaCeiling,
          verdict: rec.verdict,
          schema: rec.schema,
          reconciliation: rec,
          // the trajectory is READABLE — it is the physics — but it is advisory, never actuation-grade
          advisory: true,
          prediction: body,
          receipt: p.receipt,
        }, extra);
      }
      return send(res, 200, body, extra);
    } catch (e) {
      // The anti-clamp law failing is NOT a bad request — it means the gate itself emitted a value
      // that is neither the physics nor the whole proposal. Nothing is served, and the receipt that
      // binds the violation is returned so the failure is provable rather than merely logged.
      if (e instanceof EmissionLawViolation) {
        return send(res, 500, {
          error: 'emission-law-violation',
          law: e.law, violations: e.violations, receipt: e.receipt,
          detail: 'the reconciliation gate emitted a clamped value; the prediction was sealed and then refused rather than served',
        });
      }
      return send(res, 400, { error: (e as Error).message || 'predict failed' });
    }
  }

  // The rejection ledger. A refusal nobody can see may as well have been a silent clamp, so the refusals
  // are a first-class readable surface — not a log line.
  //
  // 🔴 A ledger entry IS record content. An earlier comment here claimed "decisions and bounds only,
  // never record content" and that was simply false: every entry carries the mechanistic value, the
  // proposal, the delta and the emitted value — the person's own trajectory in mmHg, % and mL/min. So
  // the SAME TWO MEMBRANES that guard /predict guard this, for the same two reasons:
  //   • EXPOSURE, because these are record-derived numbers and this endpoint is reachable cross-origin;
  //   • the GRANT scope, because a clinician holding a cardiovascular grant must not learn the renal
  //     trajectory — and would have, by reading the refusals instead of asking for the prediction.
  // Without both, a caller refused at /predict could reconstruct what it was refused, one rejection at
  // a time, which is exactly the bypass the grant scope exists to prevent.
  if (req.method === 'GET' && url.pathname === '/api/health/dynamics/rejections') {
    const denied = denyExposure(req);
    if (denied) return send(res, denied.code, denied.body);
    const limit = Math.max(1, Math.min(500, Number(url.searchParams.get('limit') ?? 100)));

    const a = authorizeGrant(req, url, 'rejections', false);
    if (a && !a.ok) return send(res, a.code, a.body, a.headers);
    let only: Compartment[] | undefined;
    let withheldSystems: string[] = [];
    if (a) {
      const scope = a.grant.scopeSpec ?? resolveScope(a.grant.scope);
      only = COMPARTMENTS.filter((k) => scope.systems === 'all' || scope.systems.includes(COMPARTMENT_SYSTEM[k]));
      withheldSystems = COMPARTMENTS.filter((k) => !only!.includes(k)).map((k) => COMPARTMENT_SYSTEM[k]);
      if (only.length === 0) return send(res, 403, { blocked: true, reason: 'no compartment is inside this grant’s scope' });
    }
    return send(res, 200, {
      ...rejectionLedger(limit, only),
      law: gatePolicy().doctrine,
      ...(a ? { grant: { id: a.grant.id, withheldSystems }, authentication: authenticatedAs(a), grantReceipt: grantUseReceipt('rejections-read', [a.grant.id, a.holder], { grant: a.grant.id, presentedBy: a.holder }) } : {}),
    }, a?.legacy ? { warning: LEGACY_QUERY_WARNING } : {});
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
  if (req.method === 'GET' && url.pathname === '/api/health/deident') {
    // De-identified, but still derived from the same records — gated on the same condition.
    const denied = denyExposure(req);
    return denied ? send(res, denied.code, denied.body) : send(res, 200, deidentify(bundle()));
  }

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

  // Grant a designated agent a scoped, time-boxed read grant — receipted, and now HOLDER-BOUND.
  //
  // 🔴 Minting is exposure-gated, and that is not decoration: an OPEN mint endpoint makes holder
  // authentication theatre, because anyone refused at /doctor-view could simply issue themselves a
  // full-history grant and read with a credential of their own choosing. Whether this deployment may
  // hand out consent at all is the same question exposure.ts already answers for serving records.
  //
  // Be plain about what the grantor authentication IS: on a synthetic-only deployment, none — the
  // data being synthetic is the whole protection, exactly as exposure.ts says. On an `authenticated`
  // deployment it is the DEPLOYMENT secret, i.e. "whoever operates this node", NOT the patient. There
  // is no patient identity plane in this skeleton, so consent cannot be attributed to the person
  // whose records it discloses. That is recorded in the response rather than implied away.
  if (req.method === 'POST' && url.pathname === '/api/health/grant') {
    try {
      const denied = denyExposure(req);
      if (denied) return send(res, denied.code, denied.body);
      const b = await readJson(req);
      const agent = String(b.agent ?? '').trim();
      const scope = String(b.scope ?? 'all systems').trim() || 'all systems';
      const ttlDays = Math.max(1, Math.min(365, Number(b.ttlDays ?? 30)));
      if (!agent) return send(res, 422, { error: 'agent required' });
      const now = new Date();
      // Minted here, hashed immediately, returned once, never stored and never logged.
      const secret = mintHolderSecret();
      const g: Grant = {
        // 🔴 WAS `grant-<sha256(agent|scope|ms)>` — a hash of its own published inputs. Two grants to
        // the same agent with the same scope in the same millisecond collided (measured: 79% over 200
        // concurrent issues), which puts two rows in the ledger under one identity: one holder stops
        // authenticating with no error, revoking the id revokes one of them, and every receipt naming
        // it is ambiguous about which grant it recorded. And `granted_at` is published at millisecond
        // precision beside the agent and the scope, so anyone with a grant listing could recompute
        // every id in it offline. Minted from the CSPRNG now — see ids.ts for why not a salted hash.
        id: mintId('grant'),
        agent, scope, granted_at: now.toISOString(),
        expires_at: new Date(now.getTime() + ttlDays * 86400000).toISOString(),
        revoked: false, reads: 0, receipt: receipt('grant', [agent, scope, String(ttlDays)]).id,
        // structured scope: explicit spec > preset name > the scope label if it names a preset > full history
        scopeSpec: resolveScope(String(b.preset ?? scope), b.scopeSpec),
        holderDigest: holderDigest(secret),
      };
      addGrant(g);
      return send(res, 200, {
        grant: { ...publicGrant(g), scopeSummary: scopeSummary(g.scopeSpec!) },
        holder: {
          token: holderToken(g.id, secret),
          shownOnce: true,
          present: `${HOLDER_HEADER}: ${holderToken(g.id, secret)}`,
          note: 'This is the only time the secret exists outside the holder. It is not recoverable — ' +
            'only its sha256 digest is stored. Lost means re-issue, never look up.',
        },
        authentication: HOLDER_AUTH_DISCLOSURE,
        grantorAuth: EXPOSURE === 'authenticated'
          ? { authenticatedAs: 'deployment operator (HEALTH_TWIN_TOKEN)', isThePatient: false, note: 'no patient identity plane exists here — consent is issued by whoever operates the node' }
          : { authenticatedAs: null, isThePatient: false, note: 'synthetic-only deployment: minting is ungated because the data is synthetic, and refuses the moment real records land' },
        // `boundTo: true`, not the digest itself. The holder verifier binds the receipt via the hashed
        // parts above, but must not appear verbatim in a response: every other surface strips it, and
        // publishing a verifier hands out an offline guessing target for free.
        receipt: grantUseReceipt('grant-issued', [g.id, g.holderDigest!, agent, scope], { grant: g.id, boundTo: true }),
      });
    } catch { return send(res, 400, { error: 'bad json' }); }
  }

  // Grant summaries for the clinician surface (id + label + active — never the record itself, and
  // never the holder verifier: this list is the patient's control panel, not a credential store.
  // `holderBound` says whether the grant can authenticate anyone at all, so an unbound legacy grant
  // is visible as such rather than looking active and silently refusing.)
  if (req.method === 'GET' && url.pathname === '/api/health/grants') {
    return send(res, 200, {
      grants: grants.map((g) => ({
        id: g.id, agent: g.agent, scope: g.scope,
        scopeSummary: scopeSummary(g.scopeSpec ?? resolveScope(g.scope)),
        active: !g.revoked && new Date(g.expires_at) > new Date(),
        holderBound: !!g.holderDigest,
        expires_at: g.expires_at, reads: g.reads,
      })),
      presets: Object.fromEntries(Object.entries(SCOPE_PRESETS).map(([k, v]) => [k, scopeSummary(v)])),
      authentication: HOLDER_AUTH_DISCLOSURE,
    });
  }

  // The doctor chart's data source: exercise a grant → the SCOPED bundle. The subject stays
  // identified (the clinician is authorized); the slice is exactly what the consent covers, with
  // withheld COUNTS (never content) so the doctor can see more history exists and request it.
  // Every read is a receipt; revoked/expired/unknown grants get an explicit receipted block.
  // BOTH membranes apply here, and the grant is not a substitute for the other one.
  //
  // A grant answers WHO may read and how much. Exposure answers WHETHER THIS DEPLOYMENT may serve
  // records at all over the path it is reachable on. They are different questions, and this route was
  // answering only the first.
  //
  // The distinction was not theoretical. `resolveGrant` checks that the id exists, is unrevoked and is
  // unexpired — nothing else — and the id arrived in a QUERY STRING, so it was a bearer capability with
  // no holder authentication, logged by every proxy in the path and leaked in `Referer`; one of them
  // was hard-coded in this file. Anyone who read the source, a log, or a referrer could present it.
  //
  // Now the grant BINDS A HOLDER: `x-health-grant: <grant-id>.<secret>`, verified against a sha256
  // digest stored at issue time. A leaked id is no longer a chart. See grantauth.ts — including what
  // this deliberately does NOT claim: it authenticates the holder of a secret, not a person.
  if (req.method === 'GET' && url.pathname === '/api/health/doctor-view') {
    const denied = denyExposure(req);
    if (denied) return send(res, denied.code, denied.body);
    const a = authorizeGrant(req, url, 'doctor-read', true)!;
    if (!a.ok) { audit({ actor: 'clinician', action: 'doctor-view', resource: 'twin', outcome: 'blocked', reason: (a.body as any)?.reason ?? 'unauthorized' }); return send(res, a.code, a.body, a.headers); }
    const g = a.grant;
    g.reads += 1;
    const scope = g.scopeSpec ?? resolveScope(g.scope);
    const { view, withheld } = applyScope(bundle(), scope);
    const readReceipt = grantUseReceipt('doctor-read', [g.id, a.holder, String(g.reads)], { grant: g.id, presentedBy: a.holder });
    audit({ actor: a.holder, action: 'doctor-view', resource: g.id, outcome: 'ok', receipt: (readReceipt as any).id });
    return send(res, 200, {
      grant: { id: g.id, agent: g.agent, scope: g.scope, scopeSummary: scopeSummary(scope), expires_at: g.expires_at, reads: g.reads },
      view, withheld,
      authentication: authenticatedAs(a),
      receipt: readReceipt,
    }, a.legacy ? { warning: LEGACY_QUERY_WARNING } : {});
  }

  // Revoke a grant — read-enforced: future reads by that agent are blocked.
  //
  // DELIBERATELY still id-only, and the honest reason is written into the response. Revocation is the
  // PATIENT shutting a door on someone else's grant; the patient does not hold the clinician's secret,
  // so requiring the holder credential here would mean only the person being revoked could revoke
  // themselves. Slamming the door must never be harder than opening it.
  //
  // What that leaves unprotected, stated rather than implied: on a synthetic-only deployment anyone
  // who learns a grant id can revoke it. That is a denial-of-ACCESS, not a disclosure — the failure
  // direction is a clinician locked out, not a stranger reading a chart — but it is real, and it is
  // unfixable here without a patient identity plane this estate does not have. On an `authenticated`
  // deployment the exposure membrane at least requires the deployment secret.
  if (req.method === 'POST' && url.pathname === '/api/health/revoke') {
    try {
      const denied = denyExposure(req);
      if (denied) return send(res, denied.code, denied.body);
      const b = await readJson(req);
      const g = findGrant(String(b.grant));
      if (!g) return send(res, 404, { error: 'grant not found' });
      g.revoked = true;
      return send(res, 200, {
        grant: publicGrant(g),
        revokerAuth: {
          authenticatedAs: EXPOSURE === 'authenticated' ? 'deployment operator (HEALTH_TWIN_TOKEN)' : null,
          isThePatient: false,
          note: 'revocation is id-only by design (the patient does not hold the clinician secret); ' +
            'no patient identity plane exists here, so the revoker is not authenticated as the subject',
        },
        receipt: grantUseReceipt('revoke', [g.id], { grant: g.id }),
      });
    } catch { return send(res, 400, { error: 'bad json' }); }
  }

  // An agent exercises a grant to read a slice — the access itself is a receipt (or a block).
  // Same holder credential as /doctor-view: this route counted a read and named the agent on the
  // strength of an id in a JSON body, which is the same bearer capability by another channel.
  if (req.method === 'POST' && url.pathname === '/api/health/agent-read') {
    try {
      const denied = denyExposure(req);
      if (denied) return send(res, denied.code, denied.body);
      const b = await readJson(req);
      const a = authorizeGrant(req, url, 'agent-read', true, b.grant ? String(b.grant) : undefined)!;
      if (!a.ok) return send(res, a.code, a.body, a.headers);
      const g = a.grant;
      g.reads += 1;
      return send(res, 200, {
        agent: g.agent, scope: g.scope, reads: g.reads,
        authentication: authenticatedAs(a),
        receipt: grantUseReceipt('read', [g.id, a.holder, String(g.reads)], { grant: g.id, presentedBy: a.holder }),
      });
    } catch { return send(res, 400, { error: 'bad json' }); }
  }

  send(res, 404, { error: 'not found' });
});

server.listen(PORT, () => { console.log(`health-twin listening on :${PORT}`); });
