/**
 * analytics.ts — graph analytics over the SHIPPING service, running the BENCHMARKED Rust kernel.
 *
 * hellgraph-bench measured a Rust CSR kernel (hg_analytics: PreparedGraph + parallel PageRank / WCC), but the
 * service historically had no analytics route at all — so the "3–35× vs Neo4j" numbers described code the
 * product didn't run. This wires that exact kernel in via an N-API addon (native/hg_napi.node, built in the
 * Docker Rust stage). If the addon isn't present (local dev without the native build), it degrades to a small
 * TS power-iteration so the endpoint still works — and REPORTS which backend served the result, no silent swap.
 */
import * as path from 'node:path'

export interface NodeLite { id: string }
export interface EdgeLite { from: string; to: string }
export interface GraphSource { allNodes(): NodeLite[]; allEdges(): EdgeLite[] }

/** Node shape needed for label-scoping (the store's GraphNode satisfies it). */
export interface LabeledNodeLite extends NodeLite { labels?: string[] }
export interface LabeledGraphSource { allNodes(): LabeledNodeLite[]; allEdges(): EdgeLite[] }

/** Labels that carry the ONTOLOGY (KKO upper classes + KBpedia reference concepts), not domain data. */
export const ONTOLOGY_LABELS = ['KkoClass', 'KkoReferenceConcept'] as const

/**
 * A GraphSource view with ontology nodes (and their incident edges) filtered out — so analytics and
 * exploration rank DOMAIN data, not the type system. The ontology stays fully queryable (SPARQL/Cypher/
 * kko endpoints are unaffected); this only scopes the analytics projection. Lazily materialized per call.
 */
export function dataScope(g: LabeledGraphSource): GraphSource {
  const isOntology = (n: LabeledNodeLite): boolean =>
    (n.labels ?? []).some((l) => (ONTOLOGY_LABELS as readonly string[]).includes(l))
  return {
    allNodes(): NodeLite[] { return g.allNodes().filter((n) => !isOntology(n)) },
    allEdges(): EdgeLite[] {
      const keep = new Set(this.allNodes().map((n) => n.id))
      return g.allEdges().filter((e) => keep.has(e.from) && keep.has(e.to))
    },
  }
}

interface NativeKernel {
  pagerank(n: number, from: number[], to: number[], damping: number, iters: number, tol: number): number[]
  connectedComponents(n: number, from: number[], to: number[]): number[]
  bfs(n: number, from: number[], to: number[], src: number): number[]
  sssp(n: number, from: number[], to: number[], weights: number[], src: number): number[]
  cdlp(n: number, from: number[], to: number[], iters: number): number[]
  lcc(n: number, from: number[], to: number[]): number[]
  backend(): string
}

// Load the native addon once (CommonJS require). Candidate paths cover the Docker layout (/app/native)
// and local dev (../native relative to this module).
let NATIVE: NativeKernel | null = null
{
  const candidates = [
    path.resolve(process.cwd(), 'native/hg_napi.node'),
    path.resolve(__dirname, '../native/hg_napi.node'),
    path.resolve(__dirname, '../../native/hg_napi.node'),
  ]
  for (const p of candidates) {
    try { NATIVE = require(p) as NativeKernel; break } catch { /* try next */ }
  }
}

export function analyticsBackend(): string {
  return NATIVE ? NATIVE.backend() : 'ts-fallback (power iteration)'
}

/** Dense-index the graph: node id ↔ 0..n, edges as parallel from/to index arrays. */
function indexGraph(g: GraphSource): { ids: string[]; idx: Map<string, number>; from: number[]; to: number[] } {
  const nodes = g.allNodes()
  const idx = new Map<string, number>()
  const ids: string[] = []
  for (const n of nodes) { idx.set(n.id, ids.length); ids.push(n.id) }
  const from: number[] = [], to: number[] = []
  for (const e of g.allEdges()) {
    const a = idx.get(e.from), b = idx.get(e.to)
    if (a !== undefined && b !== undefined) { from.push(a); to.push(b) }
  }
  return { ids, idx, from, to }
}

/** The fast traversal/community kernels are native-only — no silent TS fallback (that's the whole
 *  point: the SHIPPING product runs the benchmarked Rust kernel, or it tells you it can't). */
function requireNative(metric: string): NativeKernel {
  if (!NATIVE) throw new Error(`analytics: metric '${metric}' needs the native hg_analytics kernel (native/hg_napi.node), which is not loaded — build the Rust addon (the Docker native stage does this).`)
  return NATIVE
}

/** TS fallback PageRank (power iteration over the same directed CSR semantics as the Rust kernel). */
function tsPagerank(n: number, from: number[], to: number[], damping: number, iters: number): number[] {
  if (n === 0) return []
  const outDeg = new Array(n).fill(0)
  for (const a of from) outDeg[a]++
  let rank = new Array(n).fill(1 / n)
  for (let it = 0; it < iters; it++) {
    const next = new Array(n).fill((1 - damping) / n)
    let dangling = 0
    for (let i = 0; i < n; i++) if (outDeg[i] === 0) dangling += rank[i]
    const danglingShare = damping * dangling / n
    for (let i = 0; i < n; i++) next[i] += danglingShare
    for (let e = 0; e < from.length; e++) next[to[e]] += damping * rank[from[e]] / outDeg[from[e]]
    rank = next
  }
  return rank
}

export interface PageRankResult { backend: string; nodes: number; edges: number; top: { id: string; score: number }[] }

export function pagerank(g: GraphSource, limit = 20, damping = 0.85, iters = 50, tol = 1e-9): PageRankResult {
  const { ids, from, to } = indexGraph(g)
  const scores = NATIVE
    ? NATIVE.pagerank(ids.length, from, to, damping, iters, tol)
    : tsPagerank(ids.length, from, to, damping, iters)
  const top = ids.map((id, i) => ({ id, score: Math.round((scores[i] ?? 0) * 1e6) / 1e6 }))
    .sort((a, b) => b.score - a.score).slice(0, limit)
  return { backend: analyticsBackend(), nodes: ids.length, edges: from.length, top }
}

export interface ComponentsResult { backend: string; nodes: number; edges: number; components: number; largest: number }

export function connectedComponents(g: GraphSource): ComponentsResult {
  const { ids, from, to } = indexGraph(g)
  let comp: number[]
  if (NATIVE) comp = NATIVE.connectedComponents(ids.length, from, to)
  else {
    // TS fallback: union-find over undirected edges.
    const parent = Array.from({ length: ids.length }, (_, i) => i)
    const find = (x: number): number => { while (parent[x] !== x) { parent[x] = parent[parent[x]]; x = parent[x] } return x }
    for (let e = 0; e < from.length; e++) parent[find(from[e])] = find(to[e])
    comp = ids.map((_, i) => find(i))
  }
  const sizes = new Map<number, number>()
  for (const c of comp) sizes.set(c, (sizes.get(c) ?? 0) + 1)
  return { backend: analyticsBackend(), nodes: ids.length, edges: from.length,
    components: sizes.size, largest: sizes.size ? Math.max(...sizes.values()) : 0 }
}

const UNREACHED = 0xffffffff

export interface TraversalResult { backend: string; nodes: number; edges: number; source: string; reached: number; maxDistance: number }

/** BFS hop-distance from `source` — benchmarked parallel kernel (native-only). */
export function bfs(g: GraphSource, source: string): TraversalResult {
  const K = requireNative('bfs')
  const { ids, idx, from, to } = indexGraph(g)
  const s = idx.get(source)
  if (s === undefined) throw new Error(`bfs: source node '${source}' is not in the graph`)
  const dist = K.bfs(ids.length, from, to, s)
  let reached = 0, maxD = 0
  for (const d of dist) if (d !== UNREACHED) { reached++; if (d > maxD) maxD = d }
  return { backend: analyticsBackend(), nodes: ids.length, edges: from.length, source, reached, maxDistance: maxD }
}

/** Single-source shortest paths from `source` (unit edge weights) — benchmarked parallel kernel (native-only). */
export function sssp(g: GraphSource, source: string): TraversalResult {
  const K = requireNative('sssp')
  const { ids, idx, from, to } = indexGraph(g)
  const s = idx.get(source)
  if (s === undefined) throw new Error(`sssp: source node '${source}' is not in the graph`)
  const weights = new Array<number>(from.length).fill(1) // unit weights; extend to edge-property weights later
  const dist = K.sssp(ids.length, from, to, weights, s)
  let reached = 0, maxD = 0
  for (const d of dist) if (Number.isFinite(d)) { reached++; if (d > maxD) maxD = d }
  return { backend: analyticsBackend(), nodes: ids.length, edges: from.length, source, reached, maxDistance: maxD }
}

export interface CommunitiesResult { backend: string; nodes: number; edges: number; communities: number; largest: number }

/** CDLP community detection (LDBC in∪out label propagation) — benchmarked parallel kernel (native-only). */
export function cdlp(g: GraphSource, iters = 10): CommunitiesResult {
  const K = requireNative('cdlp')
  const { ids, from, to } = indexGraph(g)
  const label = K.cdlp(ids.length, from, to, iters)
  const sizes = new Map<number, number>()
  for (const l of label) sizes.set(l, (sizes.get(l) ?? 0) + 1)
  return { backend: analyticsBackend(), nodes: ids.length, edges: from.length,
    communities: sizes.size, largest: sizes.size ? Math.max(...sizes.values()) : 0 }
}

export interface LccResult { backend: string; nodes: number; edges: number; averageCoefficient: number }

/** LCC — average local clustering coefficient (simple undirected graph) — benchmarked parallel kernel (native-only). */
export function lcc(g: GraphSource): LccResult {
  const K = requireNative('lcc')
  const { ids, from, to } = indexGraph(g)
  const coeff = K.lcc(ids.length, from, to)
  const avg = coeff.length ? coeff.reduce((s, c) => s + c, 0) / coeff.length : 0
  return { backend: analyticsBackend(), nodes: ids.length, edges: from.length, averageCoefficient: Math.round(avg * 1e6) / 1e6 }
}
