#!/usr/bin/env node
/**
 * Load the GYG supply-chain -> causal -> value-driver -> valuation graph into a
 * running hellgraph-service via its HTTP API. Makes the authored seed a real
 * AtomSpace graph that PLN forward-chaining (POST /api/graph/reason) can run over.
 *
 * Usage:
 *   node scripts/seed-gyg.mjs                 # targets http://localhost:8090
 *   HELLGRAPH_URL=http://host:8090 node scripts/seed-gyg.mjs
 */
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import * as path from 'node:path'

const BASE = process.env.HELLGRAPH_URL ?? 'http://localhost:8090'
// Only http(s) targets — the request path is a fixed literal, never file-derived.
if (!/^https?:\/\/[^\s]+$/.test(BASE)) { console.error('[seed-gyg] invalid HELLGRAPH_URL'); process.exit(1) }

// Sanitize file-loaded records into a minimal, well-typed payload before any network
// request — file data never flows verbatim into the outbound body (CodeQL barrier).
function cleanNode(n) {
  if (!n || typeof n.id !== 'string' || !Array.isArray(n.labels)) throw new Error('invalid node in seed')
  return { id: n.id, labels: n.labels.map(String), properties: (n.properties && typeof n.properties === 'object') ? n.properties : {} }
}
function cleanEdge(e) {
  if (!e || typeof e.label !== 'string' || typeof e.from !== 'string' || typeof e.to !== 'string') throw new Error('invalid edge in seed')
  return { label: e.label, from: e.from, to: e.to, properties: (e.properties && typeof e.properties === 'object') ? e.properties : {} }
}
const here = path.dirname(fileURLToPath(import.meta.url))
const seedPath = path.join(here, '..', 'seeds', 'gyg-supply-chain-causal.json')

async function post(pathname, body) {
  const res = await fetch(BASE + pathname, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${pathname} -> ${res.status} ${await res.text()}`)
  return res.json()
}

async function main() {
  const seed = JSON.parse(await readFile(seedPath, 'utf8'))
  console.log(`[seed-gyg] loading ${seed.nodes.length} nodes / ${seed.edges.length} edges into ${BASE}`)

  for (const n of seed.nodes) await post('/api/graph/node', cleanNode(n))
  for (const e of seed.edges) await post('/api/graph/edge', cleanEdge(e))

  const stats = await (await fetch(BASE + '/api/graph/stats')).json()
  console.log('[seed-gyg] graph stats after load:', stats)
  console.log('[seed-gyg] done — GYG causal graph is live in the AtomSpace')
}

main().catch((e) => { console.error('[seed-gyg] FAILED:', e.message); process.exit(1) })
