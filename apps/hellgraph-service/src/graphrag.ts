/**
 * graphrag.ts — GraphRAG-for-LLMs, provenance-cited (the moat over MS GraphRAG / Cognee / LlamaIndex).
 *
 * "Ask a question, get an answer grounded in the graph" is the dominant 2026 buying motive. Everyone
 * ships it; nobody ships it with RECEIPTS. This does: graph-native retrieval (seed nodes by lexical
 * match → 1-hop neighbourhood → the grounded facts) turned into NUMBERED, provenance-carrying citations,
 * then a sovereign-LLM answer that may only cite those facts — so it cannot hallucinate past what the
 * graph actually asserts, and every claim traces to a node/edge with its assertion time.
 *
 * Opt-in + fail-open: no GRAPHRAG_LLM_URL → returns the grounded facts with no synthesized prose (an
 * honest extractive answer), and any LLM error degrades the same way. Read-only; never throws.
 */
import type { Triple } from '@socioprophet/hellgraph'
// WO-2: the built-but-dark hybrid retrieval primitives — HNSW dense index, BM25 lexical index, and the
// RRF fusion entrypoint — now ON the retrieval path (they were exported but never wired).
import { HnswIndex, BM25Index, hybridRetrieve } from '@socioprophet/hellgraph'

export interface GraphNodeLite { id: string; labels: string[]; properties: Record<string, unknown> }
export interface GraphSource {
  triples(): Triple[]
  allNodes(): GraphNodeLite[]
  allEdges(): { id: string; label: string; from: string; to: string }[]
}

export interface Citation {
  n: number
  fact: string          // human-readable "subject predicate object"
  subject: string
  predicate: string
  object: string
  isIri: boolean
  assertedAt: string    // provenance: when the graph asserted this — the receipt
}

export interface Grounding {
  seeds: string[]       // node ids that matched the question
  groundedNodes: string[]
  citations: Citation[]
}

export interface AskResult {
  question: string
  answer: string
  citations: Citation[]
  synthesized: boolean  // false → no LLM configured/failed; the citations ARE the (extractive) answer
  grounded: boolean     // false → nothing in the graph matched the question
}

const STOP = new Set(['the', 'a', 'an', 'of', 'is', 'are', 'was', 'to', 'in', 'on', 'and', 'or', 'what', 'who',
  'where', 'when', 'how', 'why', 'which', 'does', 'do', 'did', 'for', 'with', 'about', 'me', 'tell', 'give'])

function terms(q: string): string[] {
  return [...new Set(q.toLowerCase().split(/[^a-z0-9]+/).filter((t) => t.length > 2 && !STOP.has(t)))]
}

function nodeText(n: GraphNodeLite): string {
  return `${n.id} ${n.labels.join(' ')} ${Object.values(n.properties).join(' ')}`.toLowerCase()
}

const MAX_SEEDS = 12
const MAX_CITATIONS = 24

/** Retrieve the grounding: seed nodes matching the question, their 1-hop neighbourhood, and the facts within. */
export function retrieveGrounding(g: GraphSource, question: string, maxCitations = MAX_CITATIONS): Grounding {
  const qterms = terms(question)
  const nodes = g.allNodes()

  // 1. seed nodes: score by how many query terms appear in the node's text; keep the top matches.
  const scored = qterms.length === 0 ? [] : nodes
    .map((n) => { const t = nodeText(n); return { id: n.id, score: qterms.filter((q) => t.includes(q)).length } })
    .filter((s) => s.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, MAX_SEEDS)
  const seeds = scored.map((s) => s.id)
  const seedSet = new Set(seeds)

  return groundingFromSeeds(g, seeds, 1, maxCitations)
}

/** From seed node ids: expand `hops` neighbourhood, then emit the grounded facts as numbered citations. */
function groundingFromSeeds(g: GraphSource, seeds: string[], hops: number, maxCitations: number): Grounding {
  const grounded = new Set(seeds)
  const edges = g.allEdges()
  let frontier = new Set(seeds)
  for (let h = 0; h < Math.max(1, hops); h++) {
    const next = new Set<string>()
    for (const e of edges) {
      if (frontier.has(e.from) && !grounded.has(e.to)) { grounded.add(e.to); next.add(e.to) }
      if (frontier.has(e.to) && !grounded.has(e.from)) { grounded.add(e.from); next.add(e.from) }
    }
    if (next.size === 0) break
    frontier = next
  }
  const facts = g.triples().filter((t) => grounded.has(t.subject))
  const citations: Citation[] = facts.slice(0, maxCitations).map((t, i) => ({
    n: i + 1,
    fact: `${t.subject} ${t.predicate} ${t.object}`,
    subject: t.subject, predicate: t.predicate, object: String(t.object), isIri: t.isIri,
    assertedAt: t.assertedAt,
  }))
  return { seeds, groundedNodes: [...grounded], citations }
}

// ── Semantic retrieval over a sovereign embeddings endpoint (opt-in) ────────────────────────────────
interface EmbedConfig { url: string; model: string; key: string }
function embedConfig(): EmbedConfig | null {
  const url = (process.env['EMBEDDINGS_URL'] ?? '').trim()
  if (!url) return null
  return { url, model: process.env['EMBEDDINGS_MODEL'] ?? 'nomic-embed-text', key: process.env['EMBEDDINGS_API_KEY'] ?? '' }
}
export function semanticEnabled(): boolean { return embedConfig() !== null }

const embedCache = new Map<string, number[]>()
async function embed(text: string, cfg: EmbedConfig, fetchImpl: typeof fetch): Promise<number[] | null> {
  const cached = embedCache.get(text); if (cached) return cached
  try {
    const headers: Record<string, string> = { 'content-type': 'application/json' }
    if (cfg.key) headers['authorization'] = `Bearer ${cfg.key}`
    const res = await fetchImpl(cfg.url, { method: 'POST', headers, body: JSON.stringify({ model: cfg.model, input: text }), signal: AbortSignal.timeout(10_000) })
    if (!res.ok) return null
    const body = await res.json() as any
    const v: number[] = body?.embedding ?? body?.embeddings?.[0] ?? body?.data?.[0]?.embedding ?? []
    if (!Array.isArray(v) || v.length === 0) return null
    if (embedCache.size < 50_000) embedCache.set(text, v)
    return v
  } catch { return null }
}

function cosine(a: number[], b: number[]): number {
  let dot = 0, na = 0, nb = 0
  const n = Math.min(a.length, b.length)
  for (let i = 0; i < n; i++) { dot += a[i] * b[i]; na += a[i] * a[i]; nb += b[i] * b[i] }
  return na && nb ? dot / (Math.sqrt(na) * Math.sqrt(nb)) : 0
}

/** Auto retrieval: SEMANTIC (embedding cosine) seeding when EMBEDDINGS_URL is configured + reachable, else the
 * lexical substring path. `hops` configurable (default 1). Fixes the audit's "substring + fixed-1-hop" finding. */
// ── WO-2 hybrid retrieval index: HNSW dense ⊕ BM25 lexical, built ONCE over the node corpus and cached
// (rebuilt only when the node count changes). A query then embeds the QUERY alone + does one ANN + one
// BM25 lookup — instead of the old path that re-embedded EVERY node on EVERY query (O(n) embeds/query).
// Rebuilds reuse embedCache, so they're near-free after the first pass. vecOf keeps the node vectors so
// seeds can still be cosine-gated for grounding quality.
let hybridIndex: { hnsw: HnswIndex; bm25: BM25Index; vecOf: Map<string, number[]>; signature: string } | null = null

async function getHybridIndex(g: GraphSource, cfg: EmbedConfig, fetchImpl: typeof fetch) {
  const nodes = g.allNodes()
  // signature = count + a cheap rolling hash of node ids, so a different corpus (added/removed nodes)
  // rebuilds — count alone would collide two distinct same-size graphs (and break test isolation).
  let h = 0
  for (const nd of nodes) for (let i = 0; i < nd.id.length; i++) h = (Math.imul(h, 31) + nd.id.charCodeAt(i)) | 0
  const signature = `${nodes.length}:${h >>> 0}`
  if (hybridIndex && hybridIndex.signature === signature) return hybridIndex
  const hnsw = new HnswIndex()
  const bm25 = new BM25Index()
  const vecOf = new Map<string, number[]>()
  for (const nd of nodes) {
    const text = nodeText(nd)
    bm25.add(nd.id, text)
    const nv = await embed(text, cfg, fetchImpl)
    if (nv) { hnsw.add(nd.id, nv); vecOf.set(nd.id, nv) }
  }
  hybridIndex = { hnsw, bm25, vecOf, signature }
  return hybridIndex
}

export async function retrieveGroundingAuto(g: GraphSource, question: string, hops = 1, maxCitations = MAX_CITATIONS, fetchImpl: typeof fetch = fetch): Promise<Grounding & { retrieval: string }> {
  const cfg = embedConfig()
  if (cfg) {
    const qv = await embed(question, cfg, fetchImpl)
    if (qv) {
      const idx = await getHybridIndex(g, cfg, fetchImpl)
      // dense (HNSW ANN) ⊕ lexical (BM25), fused with Reciprocal Rank Fusion — one ANN + one BM25 lookup.
      const fused = hybridRetrieve({ dense: idx.hnsw, bm25: idx.bm25 }, { vector: qv, text: question, topK: MAX_SEEDS })
      // Keep grounding honest: a seed WITH an embedding must clear the cosine relevance bar; BM25-only
      // (unembedded) hits pass on their lexical match. Empty → fall through to the lexical path.
      const seeds = fused.map((s) => s.id).filter((id) => { const v = idx.vecOf.get(id); return v ? cosine(qv, v) > 0.2 : true })
      if (seeds.length) {
        return { ...groundingFromSeeds(g, seeds, hops, maxCitations), retrieval: `hybrid HNSW+BM25 RRF (${cfg.model})` }
      }
    }
  }
  return { ...groundingFromSeeds(g, retrieveGrounding(g, question, maxCitations).seeds, hops, maxCitations), retrieval: 'lexical (substring)' }
}

interface LlmConfig { url: string; model: string; key: string }
function llmConfig(): LlmConfig | null {
  const url = (process.env['GRAPHRAG_LLM_URL'] ?? '').replace(/\/$/, '')
  const model = process.env['GRAPHRAG_LLM_MODEL'] ?? ''
  if (!url || !model) return null   // sovereign LLM not configured → extractive (facts-only) mode
  return { url, model, key: process.env['GRAPHRAG_LLM_KEY'] ?? '' }
}
export function synthesisEnabled(): boolean { return llmConfig() !== null }

/** Ask a question over the graph: retrieve grounding, then synthesize a cited answer (opt-in, fail-open). */
export async function askGraph(g: GraphSource, question: string, fetchImpl: typeof fetch = fetch): Promise<AskResult> {
  const { citations } = await retrieveGroundingAuto(g, question, 1, MAX_CITATIONS, fetchImpl)
  const grounded = citations.length > 0
  const cfg = llmConfig()
  if (!cfg || !grounded) return { question, answer: '', citations, synthesized: false, grounded }

  const facts = citations.map((c) => `[${c.n}] ${c.fact}`).join('\n')
  const prompt =
    `You are a sovereign knowledge-graph assistant. Answer the question using ONLY the numbered graph facts below. ` +
    `Cite every claim inline as [n] using those numbers. If the facts do not answer it, say so plainly — never use outside knowledge.\n\n` +
    `Question: ${question}\n\nGraph facts:\n${facts}\n\nAnswer (with [n] citations):`
  try {
    const headers: Record<string, string> = { 'content-type': 'application/json' }
    if (cfg.key) headers['authorization'] = `Bearer ${cfg.key}`
    const res = await fetchImpl(`${cfg.url}/chat/completions`, {
      method: 'POST', headers,
      body: JSON.stringify({ model: cfg.model, temperature: 0.1, max_tokens: 600, messages: [{ role: 'user', content: prompt }] }),
      signal: AbortSignal.timeout(30_000),
    })
    if (!res.ok) return { question, answer: '', citations, synthesized: false, grounded }
    const data = (await res.json()) as { choices?: Array<{ message?: { content?: string } }> }
    const answer = data.choices?.[0]?.message?.content?.trim() ?? ''
    return { question, answer, citations, synthesized: answer.length > 0, grounded }
  } catch {
    return { question, answer: '', citations, synthesized: false, grounded }
  }
}
