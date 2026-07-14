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

  for (const n of seed.nodes) await post('/api/graph/node', n)
  for (const e of seed.edges) await post('/api/graph/edge', e)

  const stats = await (await fetch(BASE + '/api/graph/stats')).json()
  console.log('[seed-gyg] graph stats after load:', stats)
  console.log('[seed-gyg] done — GYG causal graph is live in the AtomSpace')
}

main().catch((e) => { console.error('[seed-gyg] FAILED:', e.message); process.exit(1) })
