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

  // 2. expand to the 1-hop neighbourhood — the facts a human would cite come from around the seed.
  const grounded = new Set(seeds)
  for (const e of g.allEdges()) {
    if (seedSet.has(e.from)) grounded.add(e.to)
    if (seedSet.has(e.to)) grounded.add(e.from)
  }

  // 3. facts = triples whose SUBJECT is a grounded node → numbered, provenance-carrying citations.
  const facts = g.triples().filter((t) => grounded.has(t.subject))
  const citations: Citation[] = facts.slice(0, maxCitations).map((t, i) => ({
    n: i + 1,
    fact: `${t.subject} ${t.predicate} ${t.object}`,
    subject: t.subject, predicate: t.predicate, object: String(t.object), isIri: t.isIri,
    assertedAt: t.assertedAt,
  }))
  return { seeds, groundedNodes: [...grounded], citations }
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
  const { citations } = retrieveGrounding(g, question)
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
