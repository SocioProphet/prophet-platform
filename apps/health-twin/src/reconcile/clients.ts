// Thin clients to EXISTING estate services — the twin orchestrates, it does not re-implement NLP / ER /
// vector / verification. Every call degrades gracefully: if a service is unreachable the twin keeps
// working (local-first) and records the degradation in provenance — a down service never fails an ingest.
//   • ie-engine          POST /extract          free-text → entities/relations/claims (spaCy)
//   • entity-resolution  POST /resolve          records → proof-carrying golden records + decision ledger
//   • embeddings         POST /v1/embeddings    text → 768-dim L2-normalized vectors (nomic; cosine=dot)
//   • holmes             POST /verify           claims → verdicts grounded in HellGraph (anti-Watson guard)
// Base URLs come from env (in-cluster DNS in prod; localhost in dev). Same server-to-server pattern the
// rest of the estate uses (EMBEDDINGS_URL etc.).

const ENV = process.env;
export const SERVICES = {
  ie: ENV.HT_IE_URL ?? 'http://127.0.0.1:8086',           // free-text → facts (spaCy)
  er: ENV.HT_ER_URL ?? 'http://127.0.0.1:8082',           // records → golden records (proof-carrying)
  embeddings: ENV.HT_EMBEDDINGS_URL ?? 'http://127.0.0.1:8080/v1/embeddings', // 768-dim vectors
  holmes: ENV.HT_HOLMES_URL ?? 'http://127.0.0.1:8091',   // claims → verdicts (anti-Watson guard)
  hellgraph: ENV.HT_HELLGRAPH_URL ?? 'http://127.0.0.1:8090', // graph landing + hybrid semantic search
  owl: ENV.HT_OWL_URL ?? 'http://127.0.0.1:8081',         // TTL → entailments (RDFS/OWL-RL)
} as const;

export type Ok<T> = { ok: true; data: T; service: string };
export type Degraded = { ok: false; service: string; reason: string };
export type Call<T> = Ok<T> | Degraded;

async function callJson<T>(service: string, url: string, body: unknown, timeoutMs = 4000): Promise<Call<T>> {
  const ac = new AbortController();
  const t = setTimeout(() => ac.abort(), timeoutMs);
  try {
    const r = await fetch(url, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body), signal: ac.signal });
    if (!r.ok) return { ok: false, service, reason: `HTTP ${r.status}` };
    return { ok: true, data: (await r.json()) as T, service };
  } catch (e) {
    return { ok: false, service, reason: (e as Error).name === 'AbortError' ? 'timeout' : (e as Error).message };
  } finally { clearTimeout(t); }
}

async function probe(service: string, base: string): Promise<{ service: string; up: boolean; url: string }> {
  // health endpoints are GET /healthz (strip any /v1/... path from embeddings url first)
  const root = base.replace(/\/v1\/.*/, '');
  const ac = new AbortController(); const t = setTimeout(() => ac.abort(), 1500);
  try { const r = await fetch(`${root}/healthz`, { signal: ac.signal }); return { service, up: r.ok, url: root }; }
  catch { return { service, up: false, url: root }; }
  finally { clearTimeout(t); }
}

// ── ie-engine: free text → structured facts ──────────────────────────────────────────────────────
export interface IeEntity { text: string; type: string; spacy_label: string; mentions: number }
export interface IeClaim { type: 'ASSERT' | 'HEDGE'; text: string; verifiable: boolean }
export interface IeExtract { entities: IeEntity[]; relations: { from: string; relation: string; to: string }[]; claims: IeClaim[]; topics: { text: string }[]; counts: Record<string, number>; provenance: { model: string; extractor: string; real: boolean } }
export const extractText = (text: string) => callJson<IeExtract>('ie-engine', `${SERVICES.ie}/extract`, { text });

// ── entity-resolution: records → golden records + proof-carrying ledger ───────────────────────────
export interface ErRecordIn { id: string; name: string; attributes?: Record<string, string>; scope?: string; primes?: string[] }
export interface ErResult {
  replay_key: Record<string, string>; records: number; merged: number;
  entities: { entity_id: string; members: string[]; size: number; canonical: { survivor: string; name: string; attributes: Record<string, string> } }[];
  golden_records: Record<string, { survivor: string; name: string; attributes: Record<string, string>; members: string[] }>;
  concordance: { record_id: string; entity_id: string; survivor: string }[];
  decision_ledger: { a: string; b: string; decision: string; score: number; name_sim: number; attr_sim: number; evidence: Record<string, unknown> }[];
  epistemic_edges: { subject: string; predicate: string; object: string; confidence_score: number }[];
}
export const resolveRecords = (records: ErRecordIn[]) => callJson<ErResult>('entity-resolution', `${SERVICES.er}/resolve`, { records });

// ── embeddings: text → 768-dim normalized vectors (cosine = dot) ──────────────────────────────────
export interface EmbedResult { object: string; data: { index: number; embedding: number[] }[]; model: string }
export const embed = (input: string[]) => callJson<EmbedResult>('embeddings', SERVICES.embeddings, { input });

// ── holmes: claims → verdicts grounded in HellGraph ───────────────────────────────────────────────
export interface HolmesVerdict { claim: string; verdict: string; matched_terms: string[]; evidence_count: number }
export const verifyClaims = (claims: string[]) => callJson<{ results: HolmesVerdict[] }>('holmes', `${SERVICES.holmes}/verify`, { claims });

// ── hellgraph-service: land records as typed nodes/edges, then hybrid (HNSW⊕BM25 RRF) cited search ─
export const graphNode = (id: string, labels: string[], properties: Record<string, unknown>) =>
  callJson<{ ok: boolean }>('hellgraph', `${SERVICES.hellgraph}/api/graph/node`, { id, labels, properties });
export interface GroundResult { question: string; semanticEnabled: boolean; groundedNodes: unknown[]; citations: { n: number; fact: string }[]; retrieval: string }
export const graphGround = async (q: string, hops = 2): Promise<Call<GroundResult>> => {
  const ac = new AbortController(); const t = setTimeout(() => ac.abort(), 4000);
  try {
    const r = await fetch(`${SERVICES.hellgraph}/api/graph/ground?q=${encodeURIComponent(q)}&hops=${hops}`, { signal: ac.signal });
    if (!r.ok) return { ok: false, service: 'hellgraph', reason: `HTTP ${r.status}` };
    return { ok: true, data: (await r.json()) as GroundResult, service: 'hellgraph' };
  } catch (e) { return { ok: false, service: 'hellgraph', reason: (e as Error).name === 'AbortError' ? 'timeout' : (e as Error).message }; }
  finally { clearTimeout(t); }
};

// ── owl-reasoner: TTL → RDFS/OWL-RL entailments (drives correspondence promotion + FHIRResource typing)
export interface ReasonResult { input_triples: number; entailed_triples: number; inference: string; profile: string; entailments: string[] }
export const reasonTurtle = (turtle: string, inference = 'rdfs') =>
  callJson<ReasonResult>('owl-reasoner', `${SERVICES.owl}/reason`, { turtle, inference }, 8000);

// ── service health (for the surface: "what's connected") ──────────────────────────────────────────
export async function serviceHealth() {
  return Promise.all([
    probe('ie-engine', SERVICES.ie), probe('entity-resolution', SERVICES.er),
    probe('embeddings', SERVICES.embeddings), probe('holmes', SERVICES.holmes),
    probe('hellgraph', SERVICES.hellgraph), probe('owl-reasoner', SERVICES.owl),
  ]);
}
