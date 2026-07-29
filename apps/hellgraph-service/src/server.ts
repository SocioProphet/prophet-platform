/**
 * HellGraph service — exposes the shared @socioprophet/hellgraph AtomSpace engine
 * over HTTP so other prophet-platform services (Go, Python, the browser app) can
 * use the metagraph without embedding a TS engine. Zero web-framework deps:
 * Node's built-in http server is enough.
 *
 * Routes:
 *   GET  /healthz                  liveness + engine export count
 *   GET  /api/graph/stats          node / edge counts
 *   GET  /api/graph/analytics?metric=pagerank|components  the BENCHMARKED Rust CSR kernel (native, TS fallback)
 *   POST /api/graph/node           { id, labels[], properties? } → upsert node
 *   POST /api/graph/edge           { label, from, to, properties? } → add edge
 *   GET  /api/graph/query?label=X  nodes carrying a label
 *   GET  /api/graph/subgraph?label=X  induced subgraph (nodes + internal edges) for an explorer
 *   GET  /api/graph/resource?uri=X    dereferenceable resource CBD, content-negotiated (Turtle/JSON-LD/HTML/JSON)
 *   GET  /api/graph/ground?q=X&hops=N  GraphRAG retrieval: semantic (embedding) or lexical seeds + N-hop facts as citations
 *   POST /api/graph/ask            { question } → GraphRAG cited answer grounded in the graph (sovereign LLM, opt-in)
 *   POST /api/graph/reason         run PLN forward-chaining → counts
 *   POST /api/graph/sparql         { query }  → SPARQL 1.1 SELECT/CONSTRUCT subset (BGP, FILTER, OPTIONAL,
 *                                    UNION, MINUS, BIND, VALUES, aggregation+GROUP BY). Unsupported forms
 *                                    (UPDATE, SERVICE, GRAPH, paths, ASK/DESCRIBE) throw — never silently-wrong.
 *   POST /api/graph/gremlin        { query }  → Gremlin read-traversal subset (~14 read steps; no mutations)
 *   POST /api/graph/cypher         { query, params? } → Cypher read subset + queryHash (MATCH/RETURN/paths; no writes)
 *   POST /api/graph/shacl          { shapes } → SHACL validation (core constraints; complex shapes via pyshacl sidecar)
 */
import * as http from 'node:http'
import * as os from 'node:os'
import * as path from 'node:path'
import * as fs from 'node:fs'
import * as zlib from 'node:zlib'
import { fileURLToPath } from 'node:url'

// Storage isolation: this service must NOT share Noetica's single-writer JSONL
// store. Set a service-local store dir BEFORE the engine's lazy getAtomSpace()
// runs. Override with HELLGRAPH_STORE_DIR (e.g. a mounted volume in prod).
process.env['HELLGRAPH_STORE_DIR'] ||= path.join(os.homedir(), '.hellgraph-service')

import * as engine from '@socioprophet/hellgraph'
import { startFederation, handleFederation, type Federation } from './federation.js'
import { getHellGraph, getAtomSpace, attachRocksDB, forwardChain, runSparql, runGremlin, runCypher, shaclValidate } from '@socioprophet/hellgraph'
import { describeResource, toTurtle, toJsonLd, toHtml, negotiate } from './resource.js'
import { askGraph, retrieveGrounding, retrieveGroundingAuto, synthesisEnabled, semanticEnabled } from './graphrag.js'
import { pagerank, connectedComponents, bfs, sssp, cdlp, lcc, analyticsBackend, dataScope } from './analytics.js'

const PORT = Number(process.env.PORT ?? 8090)

function json(res: http.ServerResponse, code: number, body: unknown): void {
  const s = JSON.stringify(body)
  res.writeHead(code, { 'content-type': 'application/json' })
  res.end(s)
}

function readBody(req: http.IncomingMessage): Promise<string> {
  return new Promise((resolve, reject) => {
    let d = ''
    req.on('data', (c: Buffer) => { d += c.toString(); if (d.length > 5_000_000) req.destroy() })
    req.on('end', () => resolve(d))
    req.on('error', reject)
  })
}

// The org super-peer (opt-in; see federation.ts). Initialized before listen() below.
let federation: Federation | null = null

const server = http.createServer((req, res) => {
  const url = new URL(req.url ?? '/', `http://localhost:${PORT}`)
  const g = getHellGraph()

  // Federation governance surface (status open; admit scope-gated). Same port, nothing new exposed.
  if (url.pathname.startsWith('/api/federation/')) {
    if (req.method === 'POST') {
      return void readBody(req).then((b) => { handleFederation(federation, req, res, url, b) })
    }
    if (handleFederation(federation, req, res, url, '')) return
  }

  // KKO ontology surface — proves the KBpedia Knowledge Ontology (kko:) is live in this graph.
  //   GET /api/graph/kko                     → census: version, class count, in-graph count, roots
  //   GET /api/graph/kko?class=kko:Suchness  → { label, subClassOf, ancestors } via the type lattice
  //   GET /api/graph/kko?isa=Suchness,Monads → { isA } subsumption check via the type lattice
  if (req.method === 'GET' && url.pathname === '/api/graph/kko') {
    const as = getAtomSpace()
    const onto = engine.kkoOntology()
    const toIri = (x: string): string => (x.startsWith('http') ? x : engine.KKO_NS + x.replace(/^kko:/, ''))
    const cls = url.searchParams.get('class')
    if (cls) {
      const iri = toIri(cls)
      const node = onto.byIri.get(iri)
      if (!node) return void json(res, 404, { ok: false, error: `unknown KKO class: ${cls}` })
      const ancestors = [...as.types.ancestors(iri)].filter((a) => a.startsWith(engine.KKO_NS)).map(engine.kkoShort)
      return void json(res, 200, {
        ok: true, iri, short: engine.kkoShort(iri), label: node.label ?? null,
        subClassOf: node.subClassOf.map(engine.kkoShort), ancestors,
      })
    }
    const isa = url.searchParams.get('isa')
    if (isa) {
      const [c, p] = isa.split(',').map((s) => s.trim())
      if (!c || !p) return void json(res, 400, { ok: false, error: 'isa expects "child,parent"' })
      return void json(res, 200, { ok: true, child: c, parent: p, isA: as.types.isA(toIri(c), toIri(p)) })
    }
    const inGraph = g.nodesByLabel('KkoClass').length
    const childIris = new Set(onto.classes.filter((c) => c.subClassOf.some((p) => onto.byIri.has(p))).map((c) => c.iri))
    const roots = onto.classes.filter((c) => !childIris.has(c.iri)).map((c) => engine.kkoShort(c.iri))
    return void json(res, 200, { ok: true, version: onto.version, classes: onto.classes.length, inGraph, roots })
  }

  // Enrichment surface — profile a class's schema-in-use + rank useful new attributes (proof-carrying).
  //   GET /api/graph/enrich?label=X[&topK=N]  → { profile, recommendation, kkoCoherence }
  // Runs the enrichClass orchestrator: profile (coverage+cardinality) + the RRF-fused recommender
  // (consistency, PageRank-trust, PLN-probabilistic — and the KKO coherence ranker AUTO-ACTIVATES when
  // KBpedia reference concepts are loaded in this graph). Each result is sealed over the graph snapshot.
  if (req.method === 'GET' && url.pathname === '/api/graph/enrich') {
    const label = url.searchParams.get('label')
    if (!label) return void json(res, 400, { ok: false, error: 'enrich requires ?label=' })
    const topK = Math.max(1, Math.min(100, Number(url.searchParams.get('topK') ?? 10) || 10))
    return void json(res, 200, { ok: true, ...engine.enrichClass(g, label, { topK }) })
  }

  // Guided exploration — from seed node id(s), rank what to explore next (proof-carrying).
  //   GET /api/graph/explore?seeds=id1,id2[&topK=N]  → { exploration }
  // fuses personalized-PageRank (multi-hop relevance from the seeds) with seed-adjacency, RRF-fused,
  // seeds excluded, sealed with a hash over the ranked suggestions + graph snapshot.
  if (req.method === 'GET' && url.pathname === '/api/graph/explore') {
    const seedsParam = url.searchParams.get('seeds')
    if (!seedsParam) return void json(res, 400, { ok: false, error: 'explore requires ?seeds=id1,id2' })
    const seeds = seedsParam.split(',').map((s) => s.trim()).filter(Boolean)
    if (seeds.length === 0) return void json(res, 400, { ok: false, error: 'explore requires at least one seed id' })
    const topK = Math.max(1, Math.min(100, Number(url.searchParams.get('topK') ?? 10) || 10))
    return void json(res, 200, { ok: true, exploration: engine.exploreFrom(g, seeds, { topK }) })
  }

  if (req.method === 'GET' && url.pathname === '/healthz') {
    return json(res, 200, { ok: true, service: 'hellgraph-service', engine_exports: Object.keys(engine).length })
  }

  if (req.method === 'GET' && url.pathname === '/api/graph/stats') {
    return json(res, 200, { nodes: g.allNodes().length, edges: g.allEdges().length })
  }

  // Graph analytics over the BENCHMARKED Rust CSR kernel (hg_analytics via N-API) — the same code
  // hellgraph-bench measured, now actually running in the shipping service. `backend` reports whether the
  // native kernel or the TS fallback served it (no silent swap). The full LDBC-style suite:
  //   pagerank | components (WCC) | bfs&source= | sssp&source= | cdlp[&iters=].
  // bfs/sssp/cdlp are native-only (the fast Rust kernel is THE path — no slow TS re-implementation).
  if (req.method === 'GET' && url.pathname === '/api/graph/analytics') {
    const metric = url.searchParams.get('metric') ?? 'pagerank'
    const limit = Math.min(Number(url.searchParams.get('limit') ?? 20), 500)
    // scope=data (default) filters ontology nodes (KkoClass / KkoReferenceConcept) out of the analytics
    // projection so metrics rank DOMAIN data, not the type system. scope=all analyzes everything.
    const scope = url.searchParams.get('scope') ?? 'data'
    const ga = scope === 'all' ? g : dataScope(g)
    if (metric === 'components') return json(res, 200, { scope, ...connectedComponents(ga) })
    if (metric === 'pagerank') return json(res, 200, { metric, scope, ...pagerank(ga, limit) })
    try {
      if (metric === 'cdlp') return json(res, 200, { metric, scope, ...cdlp(ga, Math.min(Number(url.searchParams.get('iters') ?? 10), 100)) })
      if (metric === 'lcc') return json(res, 200, { metric, scope, ...lcc(ga) })
      if (metric === 'bfs' || metric === 'sssp') {
        const source = url.searchParams.get('source')
        if (!source) return json(res, 400, { error: `metric '${metric}' needs ?source=<nodeId>` })
        return json(res, 200, { metric, scope, ...(metric === 'bfs' ? bfs(ga, source) : sssp(ga, source)) })
      }
    } catch (e) { return json(res, 500, { error: String(e) }) }
    return json(res, 400, { error: `unknown metric '${metric}' (use pagerank | components | bfs | sssp | cdlp | lcc)` })
  }

  if (req.method === 'POST' && url.pathname === '/api/graph/node') {
    return void readBody(req).then((b) => {
      try {
        const { id, labels, properties } = JSON.parse(b) as { id: string; labels: string[]; properties?: Record<string, unknown> }
        if (!id || !Array.isArray(labels)) throw new Error('id and labels[] required')
        const node = g.addNode(id, labels, (properties ?? {}) as Record<string, never>)
        json(res, 200, { ok: true, node })
      } catch (e) { json(res, 400, { error: String(e) }) }
    })
  }

  if (req.method === 'POST' && url.pathname === '/api/graph/edge') {
    return void readBody(req).then((b) => {
      try {
        const { label, from, to, properties } = JSON.parse(b) as { label: string; from: string; to: string; properties?: Record<string, unknown> }
        if (!label || !from || !to) throw new Error('label, from, to required')
        g.addEdge(label, from, to, (properties ?? {}) as Record<string, never>)
        json(res, 200, { ok: true })
      } catch (e) { json(res, 400, { error: String(e) }) }
    })
  }

  if (req.method === 'GET' && url.pathname === '/api/graph/query') {
    const label = url.searchParams.get('label') ?? ''
    const nodes = g.allNodes().filter((n) => !label || n.labels.includes(label))
    return json(res, 200, { count: nodes.length, nodes: nodes.slice(0, 200) })
  }

  // Subgraph read: the topology a real graph explorer draws (nodes + the edges internal to them).
  // Node facade exposes reads but not a label-scoped induced subgraph — this composes nodesByLabel
  // with an endpoint-membership filter so an explorer gets exactly one project's proof-carrying graph.
  if (req.method === 'GET' && url.pathname === '/api/graph/subgraph') {
    const label = url.searchParams.get('label') ?? ''
    const limit = Math.min(Number(url.searchParams.get('limit') ?? 400), 2000)
    const nodes = (label ? g.allNodes().filter((n) => n.labels.includes(label)) : g.allNodes()).slice(0, limit)
    const ids = new Set(nodes.map((n) => n.id))
    // induced subgraph: keep an edge only when both endpoints are in the node set (no dangling)
    const edges = g.allEdges().filter((e) => ids.has(e.from) && ids.has(e.to))
    return json(res, 200, { count: nodes.length, edges: edges.length, nodes, edgeList: edges })
  }

  // Explorer "surface": the highest-degree induced neighbourhood shaped for a force/radial graph UI.
  // Mirrors the agent-machine /api/graph/surface contract (view + root + degree + featured) so the
  // cockpit KnowledgeGraph and the Studio GraphExplorer read ONE canonical backend with identical UX.
  if (req.method === 'GET' && url.pathname === '/api/graph/surface') {
    const view = url.searchParams.get('view') ?? 'all'
    const root = url.searchParams.get('root') ?? ''
    const limit = Math.min(Number(url.searchParams.get('limit') ?? 34), 500)
    const allEdges = g.allEdges()
    const deg = new Map<string, number>()
    for (const e of allEdges) { deg.set(e.from, (deg.get(e.from) ?? 0) + 1); deg.set(e.to, (deg.get(e.to) ?? 0) + 1) }
    const categorize = (labels: string[]): string => {
      const l = (labels ?? []).map((x) => x.toLowerCase())
      const has = (s: string) => l.some((x) => x.includes(s))
      if (has('code') || has('module') || has('service') || has('repo') || has('feature-atom')) return 'code'
      if (has('doc') || has('interaction') || has('note') || has('episode')) return 'docs'
      if (has('person') || has('people') || has('agent') || has('org') || has('company')) return 'people'
      if (has('course') || has('concept') || has('learn') || has('skill') || has('topic') || has('ontolog') || has('class') || has('kpi') || has('driver')) return 'learning'
      return labels && labels[0] ? labels[0].toLowerCase() : 'default'
    }
    const VIEW: Record<string, string[]> = {
      knowledge: ['learning', 'knowledge', 'concept', 'topic'],
      tech: ['code', 'tech'],
      people: ['people', 'person'],
    }
    let pool = g.allNodes().map((n) => ({
      id: n.id,
      label: (n.properties?.['name'] as string) ?? (n.properties?.['label'] as string) ?? n.id,
      category: categorize(n.labels),
      degree: deg.get(n.id) ?? 0,
    }))
    if (VIEW[view]) pool = pool.filter((n) => VIEW[view]!.includes(n.category))
    if (root) {
      const nbr = new Set<string>([root])
      for (const e of allEdges) { if (e.from === root) nbr.add(e.to); if (e.to === root) nbr.add(e.from) }
      pool = pool.filter((n) => nbr.has(n.id))
    }
    pool.sort((a, b) => b.degree - a.degree)
    const picked = pool.slice(0, limit)
    const featuredId = root || (picked[0]?.id ?? '')
    const nodes = picked.map((n) => ({ ...n, kind: n.category, kvClass: n.category, featured: n.id === featuredId }))
    const pids = new Set(nodes.map((n) => n.id))
    const links = allEdges
      .filter((e) => pids.has(e.from) && pids.has(e.to))
      .map((e) => ({ source: e.from, target: e.to, primary: !!root && (e.from === root || e.to === root), epistemic: 'derived', dimension: e.label }))
    return json(res, 200, { nodes, links, total: { nodes: pool.length, edges: links.length } })
  }

  // Dereferenceable resource description (Linked-Data publishing): GET the URI, get its Concise Bounded
  // Description content-negotiated on Accept — Turtle / JSON-LD / browsable HTML / JSON. This is the
  // gist/Prez/Pubby affordance the whole semantic-web field expects and we lacked. Read-only.
  if (req.method === 'GET' && url.pathname === '/api/graph/resource') {
    const uri = url.searchParams.get('uri') ?? url.searchParams.get('iri') ?? ''
    if (!uri) return json(res, 400, { error: 'uri (or iri) query param required' })
    const d = describeResource(g, uri)
    const fmt = negotiate(req.headers['accept'])
    const code = d.found ? 200 : 404
    if (fmt === 'turtle') { res.writeHead(code, { 'content-type': 'text/turtle; charset=utf-8' }); return void res.end(toTurtle(d)) }
    if (fmt === 'jsonld') { res.writeHead(code, { 'content-type': 'application/ld+json; charset=utf-8' }); return void res.end(JSON.stringify(toJsonLd(d))) }
    if (fmt === 'html')   { res.writeHead(code, { 'content-type': 'text/html; charset=utf-8' }); return void res.end(toHtml(d)) }
    return json(res, code, d)
  }

  // GraphRAG-for-LLMs, provenance-cited: ask a question, get an answer grounded in the graph with every
  // claim traceable to a node/edge + its assertion time. GET returns the grounding (retrieval only);
  // POST /ask synthesizes a cited answer via the sovereign LLM (opt-in, fail-open → facts-only otherwise).
  if (req.method === 'GET' && url.pathname === '/api/graph/ground') {
    const q = url.searchParams.get('q') ?? ''
    if (!q) return json(res, 400, { error: 'q (question) required' })
    const hops = Math.min(Math.max(Number(url.searchParams.get('hops') ?? 1), 1), 4)
    return void retrieveGroundingAuto(g, q, hops).then((grounding) =>
      json(res, 200, { question: q, semanticEnabled: semanticEnabled(), ...grounding }))
  }
  if (req.method === 'POST' && url.pathname === '/api/graph/ask') {
    return void readBody(req).then(async (b) => {
      try {
        const { question } = JSON.parse(b || '{}') as { question?: string }
        if (!question) throw new Error('question required')
        json(res, 200, { synthesisEnabled: synthesisEnabled(), ...(await askGraph(g, question)) })
      } catch (e) { json(res, 400, { error: String(e) }) }
    })
  }

  if (req.method === 'POST' && url.pathname === '/api/graph/reason') {
    const result = forwardChain({ maxIters: 3 })
    return json(res, 200, { ok: true, result })
  }

  // ── Standards query surfaces over a proof-carrying, replayable kernel. These are honest SUBSETS of
  // SPARQL 1.1 / Gremlin / Cypher / SHACL (not full parity with Stardog/Neptune/Neo4j/TopBraid) — the
  // languages interop so tools connect, and the store underneath (append-only, queryHash per result) is
  // the moat. Unsupported syntax throws rather than returning a silently-wrong empty result.
  if (req.method === 'POST' && url.pathname === '/api/graph/sparql') {
    return void readBody(req).then((b) => {
      try {
        const { query } = JSON.parse(b || '{}') as { query?: string }
        if (!query) throw new Error('query required')
        json(res, 200, { ok: true, ...runSparql(g, query) })
      } catch (e) { json(res, 400, { error: String(e) }) }
    })
  }

  if (req.method === 'POST' && url.pathname === '/api/graph/gremlin') {
    return void readBody(req).then((b) => {
      try {
        const { query } = JSON.parse(b || '{}') as { query?: string }
        if (!query) throw new Error('query required')
        json(res, 200, { ok: true, ...runGremlin(g, query) })
      } catch (e) { json(res, 400, { error: String(e) }) }
    })
  }

  // Cypher parity (Neo4j) — the engine ships runCypher; the result carries a queryHash + evaluatedAtSeq
  // so a Cypher read is a replayable, proof-carrying result like every other query surface here.
  if (req.method === 'POST' && url.pathname === '/api/graph/cypher') {
    return void readBody(req).then((b) => {
      try {
        const { query, params } = JSON.parse(b || '{}') as { query?: string; params?: Record<string, string> }
        if (!query) throw new Error('query required')
        json(res, 200, { ok: true, ...runCypher(getAtomSpace(), query, params ?? {}) })
      } catch (e) { json(res, 400, { error: String(e) }) }
    })
  }

  if (req.method === 'POST' && url.pathname === '/api/graph/shacl') {
    return void readBody(req).then(async (b) => {
      try {
        const { shapes } = JSON.parse(b || '{}') as { shapes?: string }
        if (!shapes) throw new Error('shapes (Turtle SHACL) required')
        const report = await shaclValidate(shapes)
        json(res, 200, { ok: true, report })
      } catch (e) { json(res, 400, { error: String(e) }) }
    })
  }

  json(res, 404, { error: 'not_found' })
})

// Auto-seed on boot (idempotent): a fresh pod starts with an empty store (the /data VOLUME is
// ephemeral — no PVC is mounted — so nothing persists across restarts), which leaves every knowledge
// surface blank: Graph Explorer, Query Console, Analytics, GraphRAG all render nothing. When the graph
// has zero nodes, ingest the bundled seed corpus (apps/hellgraph-service/seeds/*.json, schema matches
// POST /api/graph/node|edge) so the cockpit shows a coherent graph. Skipped when the store is already
// populated (idempotent — safe once a volume is mounted) or when HELLGRAPH_SEED=off (tests / clean box).
function seedIfEmpty(): void {
  if (process.env['HELLGRAPH_SEED'] === 'off') return
  try {
    const g = getHellGraph()
    if (g.allNodes().length > 0) return
    const seedDir = process.env['HELLGRAPH_SEED_DIR'] ||
      path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'seeds')
    if (!fs.existsSync(seedDir)) return
    const files = fs.readdirSync(seedDir).filter((f) => f.endsWith('.json')).sort()
    let nodes = 0, edges = 0
    for (const f of files) {
      const seed = JSON.parse(fs.readFileSync(path.join(seedDir, f), 'utf8')) as {
        nodes?: Array<{ id: string; labels: string[]; properties?: Record<string, unknown> }>
        edges?: Array<{ label: string; from: string; to: string; properties?: Record<string, unknown> }>
      }
      for (const n of seed.nodes ?? []) {
        if (!n?.id || !Array.isArray(n.labels)) continue
        g.addNode(n.id, n.labels, (n.properties ?? {}) as Record<string, never>); nodes++
      }
      for (const e of seed.edges ?? []) {
        if (!e?.label || !e.from || !e.to) continue
        g.addEdge(e.label, e.from, e.to, (e.properties ?? {}) as Record<string, never>); edges++
      }
    }
    if (nodes || edges) console.log(`[hellgraph-service] auto-seeded ${nodes} nodes / ${edges} edges from ${files.length} seed file(s)`)
  } catch (e) {
    // Never let a seed error take the service down — log and serve whatever is there.
    console.error('[hellgraph-service] auto-seed skipped (error):', e instanceof Error ? e.message : String(e))
  }
}

// Load the KKO ontology backbone (KBpedia Knowledge Ontology) into the live AtomSpace + type
// lattice at startup. Idempotent (content-addressed atoms), fast (168 classes), fail-safe.
// Disable with HELLGRAPH_LOAD_KKO=off.
function loadKkoIfEnabled(): void {
  if (process.env['HELLGRAPH_LOAD_KKO'] === 'off') return
  try {
    const stats = engine.loadKkoIntoAtomSpace(getAtomSpace())
    console.log(`[hellgraph-service] KKO ${stats.version} loaded — ${stats.classes} classes / ${stats.subClassOfEdges} subClassOf edges (label 'KkoClass'; query via SPARQL/Cypher or GET /api/graph/kko)`)
  } catch (e) {
    console.error('[hellgraph-service] KKO load skipped (error):', e instanceof Error ? e.message : String(e))
  }
}

// Load the ~55k KBpedia reference concepts (the RC ABox under KKO) from the vendored gzipped N3.
// Opt-in via HELLGRAPH_LOAD_RC=on: it adds ~55k nodes / ~75k edges to the persisted store (a real data
// load, idempotent via content-addressed atoms). With RCs present, /api/graph/enrich auto-activates the
// KKO coherence ranker and semantic entity typing has a target vocabulary.
function loadRcIfEnabled(): void {
  if (process.env['HELLGRAPH_LOAD_RC'] !== 'on') return
  try {
    const gzPath = process.env['HELLGRAPH_RC_PATH'] ||
      path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'ontology', 'kbpedia-rc-2.10.n3.gz')
    if (!fs.existsSync(gzPath)) { console.error(`[hellgraph-service] RC load skipped: ${gzPath} not found`); return }
    const t0 = Date.now()
    const text = zlib.gunzipSync(fs.readFileSync(gzPath)).toString('utf8')
    const stats = engine.loadReferenceConcepts(getHellGraph(), text)
    console.log(`[hellgraph-service] KBpedia RCs loaded — ${stats.concepts} concepts / ${stats.subClassOfEdges} subClassOf edges in ${((Date.now() - t0) / 1000).toFixed(1)}s (label 'KkoReferenceConcept')`)
  } catch (e) {
    console.error('[hellgraph-service] RC load skipped (error):', e instanceof Error ? e.message : String(e))
  }
}

// Bring the graph up to a coherent baseline: seed the demo corpus (if empty) + load the KKO backbone
// (+ the RC ABox when enabled).
function bootstrap(): void {
  seedIfEmpty()
  loadKkoIfEnabled()
  loadRcIfEnabled()
}

function startLocalService(): void {
  // Org super-peer first (opt-in, fail-closed, never fatal) — so /api/federation/status is
  // truthful from the first request the service answers.
  void startFederation().then((fed) => { federation = fed }).catch((e) => {
    console.error('[federation] init failed (service continues without it):', e instanceof Error ? e.message : String(e))
  })
  server.listen(PORT, () => {
    console.log(`[hellgraph-service] listening on :${PORT} (engine exports: ${Object.keys(engine).length})`)
    // Convergence backend: opt into RocksDB (same store model as Noetica, aligned to
    // OpenCog atomspace-rocks) with HELLGRAPH_BACKEND=rocksdb. Falls back to the JSONL
    // default if the binding is unavailable.
    if (process.env['HELLGRAPH_BACKEND'] === 'rocksdb') {
      const baseDir = process.env['HELLGRAPH_STORE_DIR'] as string
      void attachRocksDB(getAtomSpace(), baseDir).then((rocks) => {
        console.log(rocks
          ? `[hellgraph-service] RocksDB backend active — ${rocks.storagePath()}`
          : '[hellgraph-service] RocksDB requested but binding unavailable — using JSONL')
        // Seed AFTER the persisted store is attached, so the emptiness check sees existing data.
        bootstrap()
      })
    } else {
      bootstrap()
    }
  })
}

// Mode selection. The engine DOES export the super-peer entrypoint (startSuperPeerFromEnv/SuperPeer), but
// this image intentionally does NOT run it: federation needs the Hyperswarm networking + signed-replication
// deps and a governance/admit config this single-tenant HTTP service isn't provisioned for. Fail fast and
// loud rather than silently degrading to local. Anything else runs the local AtomSpace HTTP service (default).
if (process.env['HELLGRAPH_MODE'] === 'superpeer') {
  console.error('[hellgraph-service] HELLGRAPH_MODE=superpeer is not served by this image ' +
    '(federation networking/governance is not provisioned here). Run the dedicated federation image instead.')
  process.exit(1)
} else {
  startLocalService()
}

export { server }
