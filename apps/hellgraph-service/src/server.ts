/**
 * HellGraph service — exposes the shared @socioprophet/hellgraph AtomSpace engine
 * over HTTP so other prophet-platform services (Go, Python, the browser app) can
 * use the metagraph without embedding a TS engine. Zero web-framework deps:
 * Node's built-in http server is enough.
 *
 * Routes:
 *   GET  /healthz                  liveness + engine export count
 *   GET  /api/graph/stats          node / edge counts
 *   POST /api/graph/node           { id, labels[], properties? } → upsert node
 *   POST /api/graph/edge           { label, from, to, properties? } → add edge
 *   GET  /api/graph/query?label=X  nodes carrying a label
 *   POST /api/graph/reason         run PLN forward-chaining → counts
 */
import * as http from 'node:http'
import * as engine from '@socioprophet/hellgraph'
import { getHellGraph, forwardChain } from '@socioprophet/hellgraph'

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

  if (req.method === 'POST' && url.pathname === '/api/graph/reason') {
    const result = forwardChain({ maxIters: 3 })
    return json(res, 200, { ok: true, result })
  }

  json(res, 404, { error: 'not_found' })
})

server.listen(PORT, () => {
  console.log(`[hellgraph-service] listening on :${PORT} (engine exports: ${Object.keys(engine).length})`)
})

export { server }
