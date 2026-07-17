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

test('query endpoints 400 on missing query', async () => {
  const r = await req('POST', '/api/graph/sparql', {})
  assert.equal(r.status, 400)
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
