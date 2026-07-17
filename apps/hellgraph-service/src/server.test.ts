/**
 * hellgraph-service HTTP smoke — focuses the new induced-subgraph endpoint that
 * feeds the Studio graph explorer: nodes for a label + only the edges internal to
 * them (no dangling), which is the topology a real graph explorer draws.
 */
import { test, before, after } from 'node:test'
import assert from 'node:assert/strict'

process.env.PORT = String(19091) // free test port, read at module import
process.env.HELLGRAPH_STORE_DIR = `${process.env.TMPDIR ?? '/tmp'}/hgsvc-test-${process.pid}`

const BASE = `http://127.0.0.1:${process.env.PORT}`
let srv: { close: (cb?: () => void) => void }

before(async () => {
  const mod = await import('./server')
  srv = mod.server as unknown as typeof srv
  // give the listener a tick
  await new Promise((r) => setTimeout(r, 150))
})
after(() => srv?.close())

async function req(method: string, path: string, body?: unknown) {
  const r = await fetch(BASE + path, {
    method,
    headers: body ? { 'content-type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  return { status: r.status, json: (await r.json()) as any }
}

test('healthz is live', async () => {
  const r = await req('GET', '/healthz')
  assert.equal(r.status, 200)
  assert.equal(r.json.ok, true)
})

test('subgraph returns nodes + only internal edges (induced, no dangling)', async () => {
  const L = `proj-test${process.pid}`
  await req('POST', '/api/graph/node', { id: `${L}:a`, labels: [L, 'Entity'], properties: { name: 'A' } })
  await req('POST', '/api/graph/node', { id: `${L}:b`, labels: [L, 'Entity'], properties: { name: 'B' } })
  await req('POST', '/api/graph/node', { id: `other:z`, labels: ['other'], properties: { name: 'Z' } })
  // internal edge (both endpoints in the label set)
  await req('POST', '/api/graph/edge', { label: 'CO_OCCURS', from: `${L}:a`, to: `${L}:b`, properties: { n: 2 } })
  // dangling edge (b is in the set, z is not) — must be excluded from the induced subgraph
  await req('POST', '/api/graph/edge', { label: 'CO_OCCURS', from: `${L}:b`, to: `other:z` })

  const r = await req('GET', `/api/graph/subgraph?label=${L}`)
  assert.equal(r.status, 200)
  assert.equal(r.json.count, 2)
  const ids = new Set(r.json.nodes.map((n: any) => n.id))
  assert.ok(ids.has(`${L}:a`) && ids.has(`${L}:b`) && !ids.has('other:z'))
  // exactly the one internal edge; the dangling one is dropped
  assert.equal(r.json.edges, 1)
  assert.equal(r.json.edgeList.length, 1)
  assert.equal(r.json.edgeList[0].from, `${L}:a`)
  assert.equal(r.json.edgeList[0].to, `${L}:b`)
})

test('subgraph respects limit', async () => {
  const r = await req('GET', '/api/graph/subgraph?limit=1')
  assert.equal(r.status, 200)
  assert.ok(r.json.nodes.length <= 1)
})

test('SPARQL parity: query returns bindings over the proof-carrying kernel', async () => {
  const L = `sparql-${process.pid}`
  await req('POST', '/api/graph/node', { id: `${L}:hg`, labels: [L], properties: { name: 'HellGraph' } })
  const r = await req('POST', '/api/graph/sparql', { query: 'SELECT ?s ?o WHERE { ?s ?p ?o } LIMIT 5' })
  assert.equal(r.status, 200)
  assert.ok(Array.isArray(r.json.variables) && Array.isArray(r.json.bindings))
  assert.ok(r.json.bindings.length >= 1)
})

test('Gremlin parity: g.V() returns vertices', async () => {
  const r = await req('POST', '/api/graph/gremlin', { query: 'g.V().limit(2)' })
  assert.equal(r.status, 200)
  assert.ok(Array.isArray(r.json.values) && typeof r.json.count === 'number')
})

test('Cypher parity: MATCH returns columns/rows + a proof-carrying queryHash', async () => {
  const L = `cy-${process.pid}`
  await req('POST', '/api/graph/node', { id: `${L}:1`, labels: ['Person', L], properties: { name: 'Ada' } })
  const r = await req('POST', '/api/graph/cypher', { query: 'MATCH (n:Person) RETURN n LIMIT 5' })
  assert.equal(r.status, 200)
  assert.ok(Array.isArray(r.json.columns) && Array.isArray(r.json.rows))
  assert.match(r.json.queryHash, /^sha256:/)              // replayable, proof-carrying result
  assert.equal((await req('POST', '/api/graph/cypher', {})).status, 400)   // query required
})

test('Cypher: unsupported node-property WHERE 400 loudly (was silently-wrong, engine 0.4.6)', async () => {
  const L = `cyw-${process.pid}`
  await req('POST', '/api/graph/node', { id: `${L}:1`, labels: ['Person', L], properties: { name: 'Ada', age: '30' } })
  await req('POST', '/api/graph/node', { id: `${L}:2`, labels: ['Person', L], properties: { name: 'Al' } })
  await req('POST', '/api/graph/edge', { label: 'KNOWS', from: `${L}:1`, to: `${L}:2` })
  const r = await req('POST', '/api/graph/cypher', { query: 'MATCH (a)-[:KNOWS]->(b) WHERE a.age > 10 RETURN b LIMIT 5' })
  assert.equal(r.status, 400)                             // was a silently-wrong empty 200
  assert.match(r.json.error, /unsupported/i)
})

test('query endpoints 400 on missing query', async () => {
  const r = await req('POST', '/api/graph/sparql', {})
  assert.equal(r.status, 400)
})

test('analytics: PageRank ranks a hub highest + reports the backend (Rust kernel or TS fallback)', async () => {
  const L = `an-${process.pid}`
  // star: a,b,c all point at hub h → h has the highest PageRank
  for (const x of ['a', 'b', 'c', 'h']) await req('POST', '/api/graph/node', { id: `${L}:${x}`, labels: [L] })
  for (const x of ['a', 'b', 'c']) await req('POST', '/api/graph/edge', { label: 'to', from: `${L}:${x}`, to: `${L}:h` })
  const r = await req('GET', `/api/graph/analytics?metric=pagerank&limit=10`)
  assert.equal(r.status, 200)
  assert.ok(typeof r.json.backend === 'string' && r.json.backend.length > 0)   // honest backend report
  assert.ok(r.json.nodes >= 4 && r.json.edges >= 3)
  const hub = r.json.top.find((t: any) => t.id === `${L}:h`)
  const leaf = r.json.top.find((t: any) => t.id === `${L}:a`)
  assert.ok(hub && leaf && hub.score > leaf.score, 'the hub must outrank a leaf')
})

test('analytics: connected components counts + unknown metric 400', async () => {
  const c = await req('GET', '/api/graph/analytics?metric=components')
  assert.equal(c.status, 200)
  assert.ok(typeof c.json.components === 'number' && typeof c.json.largest === 'number')
  assert.equal((await req('GET', '/api/graph/analytics?metric=bogus')).status, 400)
})

test('SPARQL 1.1: UNION + aggregation over the endpoint (vendored engine 0.4.5)', async () => {
  const L = `s11-${process.pid}`
  await req('POST', '/api/graph/node', { id: `${L}:1`, labels: ['Person', L], properties: { name: 'Ada' } })
  await req('POST', '/api/graph/node', { id: `${L}:2`, labels: ['Person', L], properties: { name: 'Alan' } })
  // UNION
  const u = await req('POST', '/api/graph/sparql', { query: `SELECT ?s WHERE { { ?s ?p "Ada" } UNION { ?s ?p "Alan" } }` })
  assert.equal(u.status, 200)
  assert.ok(u.json.bindings.length >= 2)
  // aggregation + GROUP BY
  const c = await req('POST', '/api/graph/sparql', { query: `SELECT ?t (COUNT(?s) AS ?c) WHERE { ?s a ?t } GROUP BY ?t` })
  assert.equal(c.status, 200)
  assert.ok(c.json.bindings.some((b: any) => Number(b.c) >= 2))
})

test('SPARQL: unsupported forms 400 (loud, not silently-wrong)', async () => {
  const r = await req('POST', '/api/graph/sparql', { query: 'ASK { ?s ?p ?o }' })
  assert.equal(r.status, 400)                       // throws → 400, never an empty 200
  assert.match(r.json.error, /unsupported/i)
})

test('resource: dereferenceable CBD content-negotiates turtle / json-ld / html / json', async () => {
  const S = `res-${process.pid}`
  const subj = `${S}:acme`, obj = `${S}:nyc`
  await req('POST', '/api/graph/node', { id: subj, labels: ['Org'], properties: { name: 'Acme' } })
  await req('POST', '/api/graph/node', { id: obj, labels: ['City'], properties: { name: 'NYC' } })
  await req('POST', '/api/graph/edge', { label: 'basedIn', from: subj, to: obj })
  const u = `/api/graph/resource?uri=${encodeURIComponent(subj)}`

  // JSON default — CBD carries the resource's own facts (rdf:type, name, basedIn edge)
  const j = await fetch(BASE + u).then((r) => r.json()) as any
  assert.equal(j.uri, subj)
  assert.ok(j.outgoing.some((t: any) => t.predicate === 'rdf:type' && t.object === 'Org'))
  assert.ok(j.outgoing.some((t: any) => t.predicate === 'basedIn' && t.isIri && t.object === obj))

  // Turtle via Accept
  const ttl = await fetch(BASE + u, { headers: { accept: 'text/turtle' } })
  assert.equal(ttl.headers.get('content-type'), 'text/turtle; charset=utf-8')
  const ttlBody = await ttl.text()
  assert.match(ttlBody, /@prefix ph:/)
  assert.match(ttlBody, /basedIn/)

  // JSON-LD via Accept — @id + @type present
  const ld = await fetch(BASE + u, { headers: { accept: 'application/ld+json' } }).then((r) => r.json()) as any
  assert.equal(ld['@id'], subj)
  assert.equal(ld['@type'], 'Org')

  // HTML via Accept — browsable page
  const html = await fetch(BASE + u, { headers: { accept: 'text/html' } })
  assert.match(html.headers.get('content-type') ?? '', /text\/html/)
  assert.match(await html.text(), /<h1>/)

  // back-links: the object resource is "referenced by" the subject
  const back = await fetch(BASE + `/api/graph/resource?uri=${encodeURIComponent(obj)}`).then((r) => r.json()) as any
  assert.ok(back.incoming.some((t: any) => t.subject === subj && t.predicate === 'basedIn'))
})

test('resource: 400 without uri, 404 for unknown uri', async () => {
  assert.equal((await req('GET', '/api/graph/resource')).status, 400)
  assert.equal((await req('GET', '/api/graph/resource?uri=urn:nope:missing')).status, 404)
})

test('graphrag: /ground retrieves seeds + 1-hop facts as provenance-carrying citations', async () => {
  const S = `rag-${process.pid}`
  const acme = `${S}:acme`, nyc = `${S}:nyc`, jane = `${S}:jane`
  await req('POST', '/api/graph/node', { id: acme, labels: ['Org'], properties: { name: 'Acme Aerospace' } })
  await req('POST', '/api/graph/node', { id: nyc, labels: ['City'], properties: { name: 'New York' } })
  await req('POST', '/api/graph/node', { id: jane, labels: ['Person'], properties: { name: 'Jane' } })
  await req('POST', '/api/graph/edge', { label: 'basedIn', from: acme, to: nyc })
  await req('POST', '/api/graph/edge', { label: 'worksAt', from: jane, to: acme })

  const r = await req('GET', `/api/graph/ground?q=${encodeURIComponent('what is Acme Aerospace')}`)
  assert.equal(r.status, 200)
  assert.ok(r.json.seeds.includes(acme))                                   // seeded by the query term
  assert.ok(r.json.groundedNodes.includes(nyc))                           // 1-hop neighbour pulled in
  assert.ok(r.json.citations.length >= 1)
  const c = r.json.citations[0]
  assert.ok('assertedAt' in c && 'fact' in c && 'n' in c)                 // provenance-carrying, numbered
  assert.ok(r.json.citations.some((x: any) => x.predicate === 'basedIn' && x.object === nyc))
})

test('graphrag: /ask degrades to facts-only when no sovereign LLM is configured (fail-open, grounded)', async () => {
  const S = `ask-${process.pid}`
  await req('POST', '/api/graph/node', { id: `${S}:widget`, labels: ['Product'], properties: { name: 'Widget9000' } })
  const r = await req('POST', '/api/graph/ask', { question: 'tell me about Widget9000' })
  assert.equal(r.status, 200)
  assert.equal(r.json.synthesized, false)      // no GRAPHRAG_LLM_URL in CI → extractive
  assert.equal(r.json.grounded, true)          // but it DID ground in the graph
  assert.ok(r.json.citations.length >= 1)
  assert.equal((await req('POST', '/api/graph/ask', {})).status, 400)     // question required
})
