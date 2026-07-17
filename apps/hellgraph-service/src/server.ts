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

// Storage isolation: this service must NOT share Noetica's single-writer JSONL
// store. Set a service-local store dir BEFORE the engine's lazy getAtomSpace()
// runs. Override with HELLGRAPH_STORE_DIR (e.g. a mounted volume in prod).
process.env['HELLGRAPH_STORE_DIR'] ||= path.join(os.homedir(), '.hellgraph-service')

import * as engine from '@socioprophet/hellgraph'
import { getHellGraph, getAtomSpace, attachRocksDB, forwardChain, runSparql, runGremlin, runCypher, shaclValidate } from '@socioprophet/hellgraph'
import { describeResource, toTurtle, toJsonLd, toHtml, negotiate } from './resource.js'
import { askGraph, retrieveGrounding, retrieveGroundingAuto, synthesisEnabled, semanticEnabled } from './graphrag.js'
import { pagerank, connectedComponents, analyticsBackend } from './analytics.js'

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

const server = http.createServer((req, res) => {
  const url = new URL(req.url ?? '/', `http://localhost:${PORT}`)
  const g = getHellGraph()

  if (req.method === 'GET' && url.pathname === '/healthz') {
    return json(res, 200, { ok: true, service: 'hellgraph-service', engine_exports: Object.keys(engine).length })
  }

  if (req.method === 'GET' && url.pathname === '/api/graph/stats') {
    return json(res, 200, { nodes: g.allNodes().length, edges: g.allEdges().length })
  }

  // Graph analytics over the BENCHMARKED Rust CSR kernel (hg_analytics via N-API) — the same code
  // hellgraph-bench measured, now actually running in the shipping service. `backend` reports whether the
  // native kernel or the TS fallback served the result (no silent swap). metric = pagerank | components.
  if (req.method === 'GET' && url.pathname === '/api/graph/analytics') {
    const metric = url.searchParams.get('metric') ?? 'pagerank'
    const limit = Math.min(Number(url.searchParams.get('limit') ?? 20), 500)
    if (metric === 'components') return json(res, 200, connectedComponents(g))
    if (metric === 'pagerank') return json(res, 200, { metric, ...pagerank(g, limit) })
    return json(res, 400, { error: `unknown metric '${metric}' (use pagerank | components)` })
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

function startLocalService(): void {
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
      })
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
