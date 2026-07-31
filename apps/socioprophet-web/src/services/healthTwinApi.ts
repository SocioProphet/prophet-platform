// Digital Health Twin client (walking skeleton) → the health-twin engine (/svc/health). Reads the
// person's FHIR-lite record bundle (keyed to organ systems, so the anatomical diagram is the index)
// and drives governed consent grants — a designated agent gets a scoped, time-boxed, receipted,
// revocable read grant, and every access is a receipt or a block. In production the engine runs
// LOCAL-FIRST on the person's own node; this skeleton reads a synthetic subject. Non-diagnostic.
import { resolveBase } from '../config/cockpitRuntime';
import { HOLDER_HEADER, holderHeader } from './healthHolderToken';

const BASE = resolveBase('health', 'VITE_HEALTH_BASE', '/svc/health');

// ── reading THROUGH a consent grant: the holder credential ─────────────────────────────────────
// A grant id is no longer a credential. Every route that reads through a grant wants
// `x-health-grant: <grant-id>.<secret>`; the `?grant=<id>` form is refused with 401 by default
// because a query string is written to access logs, proxy logs, browser history and `Referer`.
// It is NOT kept here as a fallback — a fallback becomes the path of least resistance, and the leak
// it causes is silent. (`HEALTH_TWIN_LEGACY_GRANT_QUERY=1` exists server-side for synthetic-only
// deployments, warns on every use and refuses to boot in an authenticated one. It is a migration
// escape hatch, not something this cockpit is allowed to depend on.)
// The credential itself lives in healthHolderToken.ts — in memory, never persisted.

/**
 * What an authenticated read says about the authentication behind it (grantauth.ts:
 * HOLDER_AUTH_DISCLOSURE). Note `identityVerified: false` — this proves possession of a secret, not
 * that anyone is a clinician.
 */
export interface HolderAuthDisclosure {
  mechanism: string; binds: string; verifier?: string;
  identityVerified: boolean; channel: string; deprecated?: boolean;
}

/**
 * A 401 from the consent membrane — the CREDENTIAL failed, not the chart. Distinct from a generic
 * Error precisely so the UI can offer "enter your token" instead of a failure toast: one is
 * recoverable by the person looking at the screen, the other is not.
 *
 * `missing: true` = we never held one, so nothing was sent — no request, no failed read in the
 * engine's receipt trail. `missing: false` = the engine refused what we presented.
 *
 * Nothing derived from the token is ever put in this error. The server's `reason`/`detail` are fixed
 * strings that never echo the presented value, and its single uniform failure reason is deliberate:
 * a caller who has just failed to authenticate must not be able to use the response as an oracle for
 * which grant ids exist.
 */
export class HolderAuthError extends Error {
  readonly status = 401;
  constructor(readonly reason: string, readonly missing: boolean, readonly detail?: string) {
    super(reason);
    this.name = 'HolderAuthError';
  }
}

/**
 * Headers for a read that REQUIRES the grant credential. Throws before touching the network when
 * nothing is held, so "no token" costs zero unauthenticated requests.
 */
function holderHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const h = holderHeader();
  if (!h) {
    throw new HolderAuthError(
      'grant holder credential required', true,
      `present the grant as \`${HOLDER_HEADER}: <grant-id>.<secret>\` — the id on its own is not a credential`,
    );
  }
  return { ...extra, ...h };
}

/** Turn a 401 body into the recoverable error. Shared, so every grant-scoped route refuses alike. */
function refusal(payload: unknown): HolderAuthError {
  const b = (payload ?? {}) as { reason?: unknown; detail?: unknown };
  return new HolderAuthError(
    typeof b.reason === 'string' ? b.reason : 'grant holder authentication failed',
    false,
    typeof b.detail === 'string' ? b.detail : undefined,
  );
}

/** Parse defensively: a proxy can answer a 401 with html, and `.json()` would throw over the refusal. */
async function readBody(res: Response): Promise<any> {
  return await res.json().catch(() => ({}));
}

export type EpistemicMode = 'observed' | 'derived' | 'verified' | 'attested' | 'hypothesis';
// organ = the anatomical structure a record localises to (health:localizedTo); classIri/organIri = the
// HDT ontology class + organ IRIs the fact carries, so it types into HellGraph + reasons in Ontogenesis.
export interface Observation { id: string; system: string; organ?: string; classIri?: string; organIri?: string | null; code: string; codeSystem: string; display: string; value: number; unit: string; refLow?: number; refHigh?: number; effective: string; trend?: number[]; epistemic: EpistemicMode }
export interface Condition { id: string; system: string; organ?: string; classIri?: string; organIri?: string | null; code: string; codeSystem: string; display: string; onset: string; clinicalStatus: string; epistemic: EpistemicMode }
export interface Encounter { id: string; system: string; type: string; date: string; provider: string; note: string }
export interface ImagingStudy { id: string; system: string; modality: string; bodySite: string; date: string; description: string; epistemic: EpistemicMode }
export interface SystemBundle { id: string; label: string; organs: string[]; iri?: string; compartment?: string; observations: Observation[]; conditions: Condition[]; encounters: Encounter[]; imaging: ImagingStudy[] }
export interface Grant { id: string; agent: string; scope: string; granted_at: string; expires_at: string; revoked: boolean; reads: number; receipt: string; active?: boolean }
export interface Medication { id: string; system: string; organ: string; code: string; codeSystem: string; display: string; dose: string; status: string; started: string; epistemic: string }
export interface Allergy { id: string; code: string; codeSystem: string; display: string; reaction: string; criticality: string; epistemic: string }
export interface Immunization { id: string; code: string; codeSystem: string; display: string; date: string; epistemic: string }
export interface CareTeamMember { id: string; name: string; specialty: string; role: string; credentials: string; org: string; location: string; npi?: string; verified: boolean; yearsInPractice: number; visits: number; lastSeen: string; firstSeen: string }
export interface Reading { id: string; system: string; organ: string; code: string; codeSystem: string; display: string; value: number; unit: string; effective: string; epistemic: string; by: string; source: string }
export interface TwinBundle {
  subject: { id: string; label: string; note: string; ageBand?: string; sex?: string };
  systems: (SystemBundle & { medications?: Medication[] })[];
  medications?: Medication[]; allergies?: Allergy[]; immunizations?: Immunization[];
  careTeam?: CareTeamMember[]; readings?: Reading[];
  timeline: Encounter[];
  counts: { observations: number; conditions: number; encounters: number; imaging: number };
  grants: Grant[];
  ontology?: { health: string; hdt: string; subjectClass: string; note: string };
  disclaimer: string;
}
export async function addReading(text: string, by = 'clinician', source = 'keyboard'): Promise<{ created: Reading[]; count: number }> {
  const res = await fetch(`${BASE}/api/health/reading`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ text, by, source }) });
  if (!res.ok) throw new Error(`reading failed (${res.status})`);
  return await res.json();
}
// evidence grounded ON the twin — contextual (patient-specific query) + evidentiary (bound to a record).
// Present the grant credential and the engine scopes evidence SERVER-SIDE to records inside the
// grant, so withheld findings can't leak to a clinician through the evidence side door.
export interface TwinEvidence { recordId: string; finding: string; query: string; evidence: string; citations: { source: string; tier: string }[]; retrieval: string }
/**
 * Requires the holder credential even though the ENGINE treats the grant as optional here (no grant
 * offered = evidence is not narrowed at all). That default is right for the engine and wrong for a
 * clinician surface: an unauthenticated call would quietly return evidence over records the consent
 * scope withholds, which is the side door this scoping exists to close. So the chart either reads
 * evidence through the grant or does not read it.
 */
export async function groundEvidence(): Promise<{ context: string; items: TwinEvidence[]; authentication?: HolderAuthDisclosure }> {
  const res = await fetch(`${BASE}/api/health/evidence`, { headers: holderHeaders({ accept: 'application/json' }) });
  const b = await readBody(res);
  if (res.status === 401) throw refusal(b);
  if (!res.ok) throw new Error(`evidence failed (${res.status})`);
  return b;
}

// ── grant-scoped clinician access: the doctor chart reads THROUGH a consent grant ─────────────────
// The engine returns exactly the granted slice plus withheld COUNTS (never content); revoked/expired
// grants return an explicit receipted block. Every read increments the grant's receipt trail.
/**
 * `holderBound` = this grant carries a holder digest, so it can authenticate someone. A grant issued
 * before holder binding existed is `false`: it still looks active and unexpired, but it authenticates
 * nobody and every read through it is refused. Rendering the two identically would mean showing an
 * "active" grant that cannot be used, and leaving the patient to discover it from a clinician's
 * failed login — so the UI has to tell them apart.
 */
export interface GrantSummary { id: string; agent: string; scope: string; scopeSummary: string; active: boolean; holderBound: boolean; expires_at: string; reads: number }
/** Unauthenticated by design: this is the patient's control panel, not a credential store. */
export async function listGrants(): Promise<{ grants: GrantSummary[]; presets: Record<string, string>; authentication?: HolderAuthDisclosure }> {
  const res = await fetch(`${BASE}/api/health/grants`, { headers: { accept: 'application/json' } });
  if (!res.ok) throw new Error(`grants unreachable (${res.status})`);
  return await res.json();
}
export type WithheldCounts = { total: number } & Partial<Record<'observations' | 'conditions' | 'encounters' | 'imaging' | 'medications' | 'allergies' | 'immunizations' | 'readings', number>>;
export interface DoctorView {
  blocked?: boolean; reason?: string; authenticated?: boolean;
  grant?: { id: string; agent: string; scope: string; scopeSummary: string; expires_at: string; reads: number };
  view?: Omit<TwinBundle, 'grants'>; withheld?: WithheldCounts;
  authentication?: HolderAuthDisclosure;
  receipt?: { id: string };
}
/**
 * No grant-id argument any more, and that is the point rather than a tidy-up: WHICH grant is read is
 * now decided by the credential presented, not by a parameter the caller picks. Asking for a grant
 * you cannot authenticate is not a thing that can be expressed.
 *
 * A 401 throws (the credential is wrong — recoverable by entering the right one). A 403 returns
 * normally carrying `{ blocked, reason, receipt }`: the grant is revoked or expired, the holder is
 * proven, and the block IS the answer.
 */
export async function doctorView(): Promise<DoctorView> {
  const res = await fetch(`${BASE}/api/health/doctor-view`, { headers: holderHeaders({ accept: 'application/json' }) });
  const b = await readBody(res);
  if (res.status === 401) throw refusal(b);
  return b;
}

export async function loadTwin(): Promise<TwinBundle> {
  const res = await fetch(`${BASE}/api/health/twin`, { headers: { accept: 'application/json' } });
  if (!res.ok) throw new Error(`health twin unreachable (${res.status})`);
  return (await res.json()) as TwinBundle;
}
/**
 * Issuing a grant now mints a holder secret, and `holder.token` is the ONE time it exists outside
 * the holder — only its sha256 digest is stored, so lost means re-issue, never look up. The caller
 * has to hand it to the clinician there and then; nothing in this app writes it down.
 */
export interface IssuedGrant {
  grant: Grant & { scopeSummary?: string };
  holder: { token: string; shownOnce: boolean; present: string; note: string };
  authentication?: HolderAuthDisclosure;
  grantorAuth?: { authenticatedAs: string | null; isThePatient: boolean; note: string };
  receipt?: { id: string };
}
export async function grantAccess(agent: string, scope: string, ttlDays: number): Promise<IssuedGrant> {
  const res = await fetch(`${BASE}/api/health/grant`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ agent, scope, ttlDays }) });
  if (!res.ok) throw new Error(`grant failed (${res.status})`);
  return await res.json();
}
/**
 * Still id-only, and deliberately NOT converted to the holder credential. Revocation is the patient
 * shutting a door on someone else's grant, and the patient does not hold the clinician's secret —
 * requiring it here would mean only the person being revoked could revoke themselves. Slamming the
 * door must never be harder than opening it. (Server-side reasoning: server.ts, /api/health/revoke.)
 */
export async function revokeAccess(grant: string): Promise<unknown> {
  const res = await fetch(`${BASE}/api/health/revoke`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ grant }) });
  if (!res.ok) throw new Error(`revoke failed (${res.status})`);
  return await res.json();
}
/**
 * Exercising a grant, on the holder credential — the id is NOT sent in the body. It used to be, and
 * a bare id in a JSON body is the same bearer capability as one in a query string, just on a channel
 * that happens not to be logged; the engine refuses it for that reason. The grant being exercised is
 * whichever one the presented credential authenticates.
 */
export interface AgentRead {
  agent?: string; scope?: string; reads?: number;
  blocked?: boolean; reason?: string; authenticated?: boolean;
  authentication?: HolderAuthDisclosure; receipt?: { id: string };
}
export async function agentRead(): Promise<AgentRead> {
  const res = await fetch(`${BASE}/api/health/agent-read`, { method: 'POST', headers: holderHeaders({ 'content-type': 'application/json' }), body: '{}' });
  const b = await readBody(res);
  if (res.status === 401) throw refusal(b);
  return b;
}

// ── ingestion + reconciliation surface (the connector plane + the estate services it orchestrates) ──
export interface ConnectorMeta { id: string; name: string; kind: string; authModel: string; sourceShape: string; uscdiClasses: string[]; modes: string[] }
export interface IngestSummary { counts: { total: number } & Record<string, number>; sources: { source: string; connector: string; mode: string; count: number }[]; uscdiCoverage: string[] }
export interface ServiceHealth { service: string; up: boolean; url: string }
export interface GoldenRecord { entity_id: string; name: string; size: number; members: string[]; contributingSources: string[] }
export interface ReconcileReport { service: string; reason?: string; before: number; after: number; merged: number; golden: GoldenRecord[]; receipt?: { id: string } }

export async function listConnectors(): Promise<{ connectors: ConnectorMeta[]; summary: IngestSummary }> {
  const res = await fetch(`${BASE}/api/health/connectors`, { headers: { accept: 'application/json' } });
  if (!res.ok) throw new Error(`connectors unreachable (${res.status})`);
  return await res.json();
}
export async function ingestConnector(connector: string, mode = 'fixture'): Promise<{ added: { total: number }; summary: IngestSummary; receipt: { id: string } }> {
  const res = await fetch(`${BASE}/api/health/ingest`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ connector, mode }) });
  if (!res.ok) throw new Error(`ingest failed (${res.status})`);
  return await res.json();
}
export async function reconcile(): Promise<ReconcileReport> {
  const res = await fetch(`${BASE}/api/health/reconcile`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: '{}' });
  if (!res.ok) throw new Error(`reconcile failed (${res.status})`);
  return await res.json();
}
export async function serviceHealth(): Promise<{ services: ServiceHealth[] }> {
  const res = await fetch(`${BASE}/api/health/services`, { headers: { accept: 'application/json' } });
  if (!res.ok) throw new Error(`services unreachable (${res.status})`);
  return await res.json();
}

// ── blinded second opinions (wall 4): consent-scoped, double-blind, non-diagnostic ─────────────────
export interface DeidView { subject: { pseudonym: string; ageBand?: string; sex?: string }; systems: { id: string; label: string; observations: { code: string; codeSystem: string; display: string; value: number; unit: string; refLow?: number; refHigh?: number; effective: string; trend?: number[]; epistemic: string }[]; conditions: { display: string; clinicalStatus: string; epistemic: string }[] }[]; receipt: { pseudonym: string; scope: string; dateShiftDays: number; identifiersRemoved: string[] } }
export interface OpenConsult { consult_id?: string; slice?: DeidView; consent?: { agreed: boolean; disclosure: string; receipt: string }; error?: string }
export interface OpinionOut { reviewer: string; assessment: string; confidence: string; tier: string; receipt: string }
export interface Concordance { n: number; verdict: 'insufficient' | 'unanimous' | 'majority' | 'split'; agreement: number; groups: { assessment: string; count: number; reviewers: string[] }[]; flag: string }
export interface ConsultAgg { consult_id: string; scope: string; blind: boolean; opinions: OpinionOut[]; concordance: Concordance; disclaimer: string; error?: string }

// `agreed` defaults to FALSE for the same reason it does server-side: a consent parameter
// that defaults to granted means any caller who forgets it opens a consult. The server
// refuses an un-agreed consult, so the honest client default is the one that makes a
// forgetful caller get refused rather than quietly succeed.
export async function openConsult(scope: string, disclosure = 'standard', agreed = false): Promise<OpenConsult> {
  const res = await fetch(`${BASE}/api/health/consult`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ scope, disclosure, agreed }) });
  return await res.json();
}
export async function consultResult(id: string): Promise<ConsultAgg> {
  const res = await fetch(`${BASE}/api/health/consult/${encodeURIComponent(id)}`, { headers: { accept: 'application/json' } });
  return await res.json();
}
export async function reviewerSlice(id: string): Promise<{ scope: string; slice: DeidView } | { error: string }> {
  const res = await fetch(`${BASE}/api/health/consult/${encodeURIComponent(id)}/review`, { headers: { accept: 'application/json' } });
  return await res.json();
}
export async function submitOpinion(id: string, reviewer: string, assessment: string, confidence: string): Promise<OpinionOut | { error: string }> {
  const res = await fetch(`${BASE}/api/health/consult/${encodeURIComponent(id)}/opinion`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ reviewer, assessment, confidence }) });
  return await res.json();
}

// ── Ask-my-agent (patient magic): conversational recall over the twin, cited + non-diagnostic ──────
export interface AskCitation { id: string; kind: string; text: string; date?: string; tier?: string; system?: string }
export interface AskAnswer { question: string; answer: string; citations: AskCitation[]; retrieval: string }
export async function askTwin(q: string): Promise<AskAnswer> {
  const res = await fetch(`${BASE}/api/health/ask`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ q }) });
  if (!res.ok) throw new Error(`ask failed (${res.status})`);
  return await res.json();
}

// guideline-grounded, cited, non-diagnostic guidance over the twin's own numbers
export interface GuidanceItem { finding: string; says: string; source: string; strength: 'screen' | 'discuss' | 'monitor' | 'confirm'; cites: string[] }
export async function guidance(): Promise<{ items: GuidanceItem[]; disclaimer: string }> {
  const res = await fetch(`${BASE}/api/health/guidance`, { headers: { accept: 'application/json' } });
  if (!res.ok) throw new Error(`guidance failed (${res.status})`);
  return await res.json();
}

// ── Capture surface: voice notes / photos / documents → the twin, hash-sealed + tier-tagged ────────
export interface CodedEntity { text: string; category: string; code: string; codeSystem: string; display: string; negated: boolean }
export interface Captured { id: string; kind: 'note' | 'photo' | 'document'; caption: string; text?: string; tier: string; by: string; contentHash: string; organ?: string; system?: string; capturedAt: string; receipt: string; coded?: CodedEntity[] }
export async function capture(payload: { kind: string; by: string; caption?: string; text?: string; system?: string; organ?: string; contentHash?: string }): Promise<{ captured: Captured; count: number }> {
  const res = await fetch(`${BASE}/api/health/capture`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(payload) });
  if (!res.ok) throw new Error(`capture failed (${res.status})`);
  return await res.json();
}
