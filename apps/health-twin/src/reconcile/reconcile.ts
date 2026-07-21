// Wall 2 — reconciliation + extraction, done by ORCHESTRATING the estate (not re-implementing it):
//   • cross-source dedup / golden records  → entity-resolution  (proof-carrying merges)
//   • unstructured narrative → candidate facts → ie-engine (spaCy) + holmes (verify the claims)
//   • land records as typed graph nodes    → hellgraph-service (then hybrid semantic search / PLN)
// Everything degrades gracefully and preserves provenance. Nothing here diagnoses.
import type { IngestResult } from '../ingest.js';
import { resolveRecords, extractText, verifyClaims, graphNode, type ErRecordIn, type Call } from './clients.js';

// ── every ingested record → an entity-resolution input (name + coded attributes + source) ──────────
type AnyRec = { id: string; display?: string; code?: string; codeSystem?: string; system?: string; provenance?: { source?: string } };
function recordsForEr(store: IngestResult): { input: ErRecordIn[]; provById: Map<string, string> } {
  const provById = new Map<string, string>();
  const push = (arr: AnyRec[], kind: string, input: ErRecordIn[]) => {
    for (const r of arr) {
      provById.set(r.id, r.provenance?.source ?? 'unknown');
      // Match on the CANONICAL name: strip source-specific suffixes (" — fill ×90") so the same drug/
      // analyte named slightly differently across sources still aligns on name similarity.
      const name = (r.display ?? r.id).split(' — ')[0].trim();
      input.push({
        id: r.id, name,
        // Identity attributes only: the clinical CODE (so same-code records agree, attr_sim ↑ and
        // cross-source dupes merge) + kind (keeps meds from clustering with labs). The internal `system`
        // routing field is deliberately NOT an identity attribute — it varies by source and would create
        // false disagreement.
        attributes: { code: r.code ?? '', codeSystem: r.codeSystem ?? '', kind },
        scope: kind,
      });
    }
  };
  const input: ErRecordIn[] = [];
  push(store.medications as AnyRec[], 'medication', input);
  push(store.observations as AnyRec[], 'observation', input);
  push(store.conditions as AnyRec[], 'condition', input);
  return { input, provById };
}

export interface DedupeReport {
  service: 'entity-resolution' | 'degraded';
  reason?: string;
  before: number; after: number; merged: number;
  golden: { entity_id: string; name: string; size: number; members: string[]; contributingSources: string[] }[];
  decision_ledger?: unknown[];
}

// Dedup the ingested records across sources via entity-resolution. The merges are proof-carrying (the
// decision ledger); each golden record is annotated with the UNION of its members' source provenance —
// so "one medication, seen by Epic + Blue Button" is explicit and auditable.
export async function dedupeIngested(store: IngestResult): Promise<DedupeReport> {
  const { input, provById } = recordsForEr(store);
  if (input.length === 0) return { service: 'degraded', reason: 'no records to reconcile', before: 0, after: 0, merged: 0, golden: [] };
  const res = await resolveRecords(input);
  if (!res.ok) return { service: 'degraded', reason: res.reason, before: input.length, after: input.length, merged: 0, golden: [] };
  const golden = res.data.entities.map((e) => ({
    entity_id: e.entity_id, name: e.canonical.name, size: e.size, members: e.members,
    contributingSources: [...new Set(e.members.map((m) => provById.get(m) ?? 'unknown'))].sort(),
  }));
  return {
    service: 'entity-resolution', before: input.length, after: res.data.entities.length,
    merged: res.data.merged, golden, decision_ledger: res.data.decision_ledger,
  };
}

// ── unstructured narrative (discharge summary / C-CDA text / OCR'd PDF) → candidate facts ──────────
export interface ExtractReport {
  service: 'ie-engine' | 'degraded';
  reason?: string;
  candidates: { text: string; type: string; tier: 'hypothesis' }[];  // NOT diagnostic; pending attestation
  claims: { text: string; verifiable: boolean; verdict?: string; evidence_count?: number }[];
  model?: string;
}

// Pipe narrative text through ie-engine (spaCy NER), surface candidate facts as TIER=hypothesis (never
// promoted without clinician attestation), and verify each assertive claim against HellGraph via holmes.
export async function extractNarrative(text: string): Promise<ExtractReport> {
  const ex = await extractText(text);
  if (!ex.ok) return { service: 'degraded', reason: ex.reason, candidates: [], claims: [] };
  const candidates = ex.data.entities.map((e) => ({ text: e.text, type: e.type, tier: 'hypothesis' as const }));
  const assertions = ex.data.claims.filter((c) => c.type === 'ASSERT');
  let verdicts: Record<string, { verdict: string; evidence_count: number }> = {};
  if (assertions.length) {
    const v = await verifyClaims(assertions.map((c) => c.text));
    if (v.ok) for (const r of v.data.results) verdicts[r.claim] = { verdict: r.verdict, evidence_count: r.evidence_count };
  }
  const claims = ex.data.claims.map((c) => ({ text: c.text, verifiable: c.verifiable, ...(verdicts[c.text] ?? {}) }));
  return { service: 'ie-engine', candidates, claims, model: ex.data.provenance?.model };
}

// ── land ingested records as typed nodes in HellGraph (enables hybrid semantic search + PLN reason) ─
export async function landInGraph(store: IngestResult): Promise<{ service: 'hellgraph' | 'degraded'; landed: number; attempted: number; reason?: string }> {
  const recs: { id: string; kind: string; r: AnyRec }[] = [
    ...store.observations.map((r) => ({ id: r.id, kind: 'Observation', r: r as AnyRec })),
    ...store.conditions.map((r) => ({ id: r.id, kind: 'Condition', r: r as AnyRec })),
    ...store.medications.map((r) => ({ id: r.id, kind: 'Medication', r: r as AnyRec })),
  ];
  if (recs.length === 0) return { service: 'degraded', landed: 0, attempted: 0, reason: 'no records' };
  let landed = 0; let firstFail: string | undefined;
  const results = await Promise.all(recs.map(({ id, kind, r }) =>
    graphNode(id, ['HealthRecord', kind], { display: r.display, code: r.code, codeSystem: r.codeSystem, system: r.system, source: r.provenance?.source })));
  for (const res of results as Call<unknown>[]) { if (res.ok) landed++; else firstFail ??= res.reason; }
  return landed > 0
    ? { service: 'hellgraph', landed, attempted: recs.length }
    : { service: 'degraded', landed: 0, attempted: recs.length, reason: firstFail };
}
