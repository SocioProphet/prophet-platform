// Wall 4 — the blinded, n-ary opinion plane. The moat: because the twin is sovereign, consent-scoped,
// and DE-IDENTIFIABLE, N clinicians each give an INDEPENDENT read on the same de-identified slice —
// blind to the patient's identity, blind to each other, blind to prior labels. The aggregate is a
// CONCORDANCE / DISSENT signal that removes anchoring, identity, and diagnostic-cascade bias.
//
// Each opinion attaches to the consult as a TIER=hypothesis claim (an opinion, never asserted truth —
// the anti-Watson rule). The aggregate is a signal, NOT a diagnosis; a clinician still decides.
import { deidentify, type DeidView, type DeidReceipt } from './deident.js';

function djb2(s: string): string { let h = 5381; for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) & 0xffffffff; return (h >>> 0).toString(16).padStart(8, '0'); }
const receipt = (kind: string, parts: string[]) => ({ id: `ht-${kind}-${djb2(parts.join('|'))}`, verifier: 'health-twin', at: new Date().toISOString() });

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
export interface Consult {
  id: string;
  createdAt: string;
  scope: string;
  slice: DeidView;        // the de-identified view every reviewer sees (no identity)
  blind: true;
  opinions: Opinion[];
}

// in-memory consult ledger (local-first store in production)
const consults = new Map<string, Consult>();

// Open a blinded consult over the twin (optionally scoped to a system). Returns the consult id + the
// de-identified slice reviewers will see — identity is already gone before anyone reads it.
export function openConsult(bundle: any, scope = 'whole twin'): { consult_id: string; slice: DeidView; receipt: { id: string } } {
  const salt = `${Date.now()}-${scope}`;
  const slice = deidentify(bundle, salt);
  const id = `consult-${djb2([slice.receipt.pseudonym, scope, salt].join('|'))}`;
  consults.set(id, { id, createdAt: new Date().toISOString(), scope, slice, blind: true, opinions: [] });
  return { consult_id: id, slice, receipt: receipt('consult-open', [id, scope]) };
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
    id: `op-${djb2([consultId, rv, a, String(Date.now())].join('|'))}`,
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
