// Wall 4 — the blinded, n-ary opinion plane. The moat: because the twin is sovereign, consent-scoped,
// and DE-IDENTIFIABLE, N clinicians each give an INDEPENDENT read on the same de-identified slice —
// blind to the patient's identity, blind to each other, blind to prior labels. The aggregate is a
// CONCORDANCE / DISSENT signal that removes anchoring, identity, and diagnostic-cascade bias.
//
// Each opinion attaches to the consult as a TIER=hypothesis claim (an opinion, never asserted truth —
// the anti-Watson rule). The aggregate is a signal, NOT a diagnosis; a clinician still decides.
import { createHash } from 'node:crypto';
import { deidentify, type DeidView, type DisclosureScope } from './deident.js';

// server.ts replaced djb2 with real SHA-256 and said so; this file was missed, so consult
// ids and consult receipts stayed 32-bit djb2 — trivially collidable, and guessable enough
// that an id which can be fetched and posted to is an enumeration surface.
//
// Parts are JSON-encoded rather than joined on '|'. A separator that can occur inside a part
// is not a separator: ['a|b','c'] and ['a','b|c'] joined that way produce the same string and
// therefore the same digest, so a stronger hash over an ambiguous encoding still collides.
function sha256(parts: string[]): string {
  return createHash('sha256').update(JSON.stringify(parts)).digest('hex');
}
const receipt = (kind: string, parts: string[]) => ({ id: `ht-${kind}-${sha256(parts)}`, verifier: 'health-twin', at: new Date().toISOString() });

export type Confidence = 'low' | 'moderate' | 'high';
export interface Opinion {
  id: string;
  reviewer: string;       // pseudonymous reviewer handle (blinded to identity + to other reviewers at submit time)
  assessment: string;     // the reviewer's read
  confidence: Confidence;
  tier: 'hypothesis';     // an opinion is a hypothesis, never verified/attested truth
  at: string;
  receipt: { id: string };
}
// The patient's agreement is the gate: a consult only exists because the patient consented to a
// disclosure scope. Anonymous by default; anything beyond the agreed scope is a request they must approve.
export interface Consent { agreed: boolean; disclosure: DisclosureScope; at: string; receipt: string }
export interface MoreRequest { id: string; field: string; reason: string; status: 'pending' | 'approved' | 'declined'; at: string }
export interface Consult {
  id: string;
  createdAt: string;
  scope: string;
  consent: Consent;       // the patient agreed to these terms before anyone was asked
  slice: DeidView;        // the de-identified view every reviewer sees (no identity)
  blind: true;
  opinions: Opinion[];
  moreRequests: MoreRequest[];
}

// in-memory consult ledger (local-first store in production)
const consults = new Map<string, Consult>();

// Open a blinded consult over the twin. Requires the patient's agreement (anonymous by default); the
// agreed `disclosure` scope decides what the de-identified slice keeps. Returns the consult id + the
// slice reviewers will see — identity is already gone before anyone reads it.
export function openConsult(bundle: any, scope = 'whole twin', disclosure: DisclosureScope = 'standard', agreed = true): { consult_id?: string; slice?: DeidView; consent?: Consent; receipt?: { id: string }; error?: string } {
  if (!agreed) return { error: 'patient must agree to the disclosure terms before a consult can open' };
  const salt = `${Date.now()}-${scope}`;
  const slice = deidentify(bundle, salt, disclosure);
  const id = `consult-${sha256([slice.receipt.pseudonym, scope, salt])}`;
  const consent: Consent = { agreed: true, disclosure, at: new Date().toISOString(), receipt: receipt('consent', [id, disclosure]).id };
  consults.set(id, { id, createdAt: new Date().toISOString(), scope, consent, slice, blind: true, opinions: [], moreRequests: [] });
  return { consult_id: id, slice, consent, receipt: receipt('consult-open', [id, scope]) };
}

// A reviewer asks to see something beyond the agreed scope → a request the PATIENT decides on (it is
// NOT granted here). Anonymous-by-default means more disclosure is always the patient's explicit call.
export function requestMore(consultId: string, field: string, reason: string): MoreRequest | { error: string } {
  const c = consults.get(consultId);
  if (!c) return { error: 'consult not found' };
  const r: MoreRequest = { id: `more-${sha256([consultId, field, String(Date.now())])}`, field: field.trim(), reason: reason.trim(), status: 'pending', at: new Date().toISOString() };
  c.moreRequests.push(r);
  return r;
}

// The de-identified slice a reviewer opens (blind read — no identity, no other opinions shown here).
export function reviewerView(consultId: string): { scope: string; slice: DeidView } | null {
  const c = consults.get(consultId);
  return c ? { scope: c.scope, slice: c.slice } : null;
}

// A reviewer submits an INDEPENDENT opinion — blind to identity and to other reviewers. Attaches as a
// tier=hypothesis claim.
export function submitOpinion(consultId: string, reviewer: string, assessment: string, confidence: Confidence): Opinion | { error: string } {
  const c = consults.get(consultId);
  if (!c) return { error: 'consult not found' };
  const rv = reviewer.trim(); const a = assessment.trim();
  if (!rv || !a) return { error: 'reviewer and assessment required' };
  const op: Opinion = {
    id: `op-${sha256([consultId, rv, a, String(Date.now())])}`,
    reviewer: rv, assessment: a, confidence, tier: 'hypothesis',
    at: new Date().toISOString(), receipt: receipt('opinion', [consultId, rv]),
  };
  c.opinions.push(op);
  return op;
}

const CONF_W: Record<Confidence, number> = { low: 1, moderate: 2, high: 3 };
const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9 ]/g, '').replace(/\s+/g, ' ').trim();

// Aggregate the independent opinions into a concordance/dissent signal. NOT a diagnosis — a signal that
// concordance is reassurance and dissent is a flag worth more looking.
export function aggregate(consultId: string) {
  const c = consults.get(consultId);
  if (!c) return { error: 'consult not found' };
  const ops = c.opinions;
  const n = ops.length;
  // group by normalized assessment; weight by confidence
  const groups = new Map<string, { assessment: string; reviewers: string[]; count: number; weight: number }>();
  for (const o of ops) {
    const k = norm(o.assessment);
    const g = groups.get(k) ?? { assessment: o.assessment, reviewers: [], count: 0, weight: 0 };
    g.reviewers.push(o.reviewer); g.count += 1; g.weight += CONF_W[o.confidence]; groups.set(k, g);
  }
  const ranked = [...groups.values()].sort((a, b) => b.weight - a.weight || b.count - a.count);
  const top = ranked[0];
  const agreement = n ? (top?.count ?? 0) / n : 0;
  let verdict: 'insufficient' | 'unanimous' | 'majority' | 'split';
  if (n < 2) verdict = 'insufficient';
  else if (ranked.length === 1) verdict = 'unanimous';
  else if ((top?.count ?? 0) > n / 2) verdict = 'majority';
  else verdict = 'split';

  return {
    consult_id: consultId, scope: c.scope, blind: true,
    opinions: ops.map((o) => ({ reviewer: o.reviewer, assessment: o.assessment, confidence: o.confidence, tier: o.tier, receipt: o.receipt.id })),
    concordance: {
      n, verdict, agreement: Math.round(agreement * 100) / 100,
      groups: ranked.map((g) => ({ assessment: g.assessment, count: g.count, reviewers: g.reviewers })),
      // dissent is the product's value: a split flags a case that deserves more looking
      flag: verdict === 'split' ? 'discordant — warrants further review' : verdict === 'unanimous' ? 'concordant' : verdict === 'majority' ? 'mostly concordant' : 'need ≥2 independent opinions',
    },
    disclaimer: 'Independent, blinded opinions aggregated into a concordance signal. This is not a diagnosis; a clinician decides.',
    receipt: receipt('consult-aggregate', [consultId, String(n)]),
  };
}
