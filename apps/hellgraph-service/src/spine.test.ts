/**
 * W1.3 receipt unification — hellgraph-service side: the sealed engine receipt is
 * chained onto the compute-gateway spine and the enrich/explore response carries
 * spine:{ok, receiptId}; failure degrades HONESTLY (result still serves,
 * spine:{ok:false, reason}, /healthz unsealedReceipts counts it, warn log) —
 * never fail the read because sealing failed, never claim sealed when it isn't.
 *
 * The gateway here is a local mock: these tests pin OUR side of the contract
 * (what we POST, how we attach, how we degrade). The gateway's own recomputation
 * and verify walk are covered by apps/compute-gateway/tests/test_engine_seal.py
 * against REAL engine fixtures.
 */
import { test, before, after } from 'node:test'
import assert from 'node:assert/strict'
import * as http from 'node:http'

process.env.PORT = String(19093) // free test port, read at module import
process.env.HELLGRAPH_STORE_DIR = `${process.env.TMPDIR ?? '/tmp'}/hgsvc-spine-test-${process.pid}`
process.env.HELLGRAPH_SEED = 'off' // tests build their own graphs — don't auto-seed the boot corpus
process.env.GATEWAY_RECEIPTS = 'on'
process.env.GATEWAY_URL = 'http://127.0.0.1:19094'
process.env.GATEWAY_TOKEN = 'spine-test-token'
process.env.GATEWAY_TIMEOUT_MS = '900'

const BASE = `http://127.0.0.1:${process.env.PORT}`

// ── mock compute-gateway: records requests; behavior switched per test ──
type Seen = { path: string; auth: string | undefined; body: any }
const seen: Seen[] = []
let mode: 'ok' | 'http401' = 'ok'
const MOCK_RECEIPT_ID = 'sha256:' + 'ab'.repeat(32)

const mockGateway = http.createServer((req, res) => {
  let d = ''
  req.on('data', (c: Buffer) => { d += c.toString() })
  req.on('end', () => {
    seen.push({ path: req.url ?? '', auth: req.headers.authorization, body: d ? JSON.parse(d) : undefined })
    if (mode === 'http401') {
      res.writeHead(401, { 'content-type': 'application/json' })
      return void res.end(JSON.stringify({ detail: 'unauthorized' }))
    }
    res.writeHead(200, { 'content-type': 'application/json' })
    res.end(JSON.stringify({ receiptId: MOCK_RECEIPT_ID, envelope: { receipt: { id: MOCK_RECEIPT_ID } } }))
  })
})

let srv: { close: (cb?: () => void) => void }

before(async () => {
  await new Promise<void>((r) => mockGateway.listen(19094, r))
  const mod = await import('./server')
  srv = mod.server as unknown as typeof srv
  await new Promise((r) => setTimeout(r, 150)) // give the listener a tick
})
after(() => { srv?.close(); mockGateway.close() })

async function req(method: string, path: string, body?: unknown) {
  const r = await fetch(BASE + path, {
    method,
    headers: body ? { 'content-type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  return { status: r.status, json: (await r.json()) as any }
}

async function unsealedCount(): Promise<number> {
  return (await req('GET', '/healthz')).json.unsealedReceipts as number
}

test('enrich attaches spine:{ok,receiptId} and POSTs the sealed engine receipt to the gateway', async () => {
  const L = `sp-enr-${process.pid}`
  await req('POST', '/api/graph/node', { id: `${L}:c1`, labels: [L], properties: { spKey: 'a' } })
  await req('POST', '/api/graph/node', { id: `${L}:c2`, labels: [L], properties: { spKey: 'b' } })
  await req('POST', '/api/graph/node', { id: `${L}:p1`, labels: [`${L}-peer`], properties: { spKey: 'c', spExtra: 'x' } })

  seen.length = 0
  const r = await req('GET', `/api/graph/enrich?label=${encodeURIComponent(L)}&topK=5`)
  assert.equal(r.status, 200)
  assert.equal(r.json.ok, true)
  assert.match(r.json.recommendation.hash, /^sha256:/)              // result unchanged: still proof-carrying
  assert.deepEqual(r.json.spine, { ok: true, receiptId: MOCK_RECEIPT_ID })

  // what crossed the wire is the CONTRACT: kind + the sealed receipt + subject, bearer-authed
  assert.equal(seen.length, 1)
  assert.equal(seen[0].path, '/v1/engine-receipts')
  assert.equal(seen[0].auth, 'Bearer spine-test-token')
  assert.equal(seen[0].body.kind, 'enrich')
  assert.equal(seen[0].body.actor, 'hellgraph-service')
  assert.equal(seen[0].body.engineReceipt.hash, r.json.recommendation.hash)   // the EXACT sealed receipt
  assert.deepEqual(seen[0].body.engineReceipt.snapshot, r.json.recommendation.snapshot)
  assert.equal(seen[0].body.subject.endpoint, '/api/graph/enrich')
  assert.equal(seen[0].body.subject.label, L)
})

test('explore attaches spine too, POSTing the exploration receipt', async () => {
  const L = `sp-exp-${process.pid}`
  await req('POST', '/api/graph/node', { id: `${L}:s`, labels: [L] })
  await req('POST', '/api/graph/node', { id: `${L}:n1`, labels: [L] })
  await req('POST', '/api/graph/edge', { label: 'rel', from: `${L}:s`, to: `${L}:n1` })

  seen.length = 0
  const r = await req('GET', `/api/graph/explore?seeds=${encodeURIComponent(`${L}:s`)}&topK=5`)
  assert.equal(r.status, 200)
  assert.deepEqual(r.json.spine, { ok: true, receiptId: MOCK_RECEIPT_ID })
  assert.equal(seen[0].body.kind, 'explore')
  assert.equal(seen[0].body.engineReceipt.hash, r.json.exploration.hash)
  assert.deepEqual(seen[0].body.subject.seeds, [`${L}:s`])
})

test('gateway unreachable ⇒ honest degradation: result serves, spine:{ok:false}, counter + warn', async () => {
  const L = `sp-deg-${process.pid}`
  await req('POST', '/api/graph/node', { id: `${L}:s`, labels: [L] })
  const before = await unsealedCount()
  process.env.GATEWAY_URL = 'http://127.0.0.1:19099' // nothing listens here (read per call)
  try {
    const r = await req('GET', `/api/graph/explore?seeds=${encodeURIComponent(`${L}:s`)}`)
    assert.equal(r.status, 200)                                     // availability: the read never fails
    assert.ok(r.json.exploration && Array.isArray(r.json.exploration.suggestions))
    assert.equal(r.json.spine.ok, false)                            // …but we never claim sealed
    assert.match(r.json.spine.reason, /unreachable/)
    assert.equal(await unsealedCount(), before + 1)                  // /healthz counts every unsealed serve
  } finally {
    process.env.GATEWAY_URL = 'http://127.0.0.1:19094'
  }
})

test('gateway refusal (HTTP 401) degrades honestly with the status in the reason', async () => {
  const L = `sp-401-${process.pid}`
  await req('POST', '/api/graph/node', { id: `${L}:s`, labels: [L] })
  const before = await unsealedCount()
  mode = 'http401'
  try {
    const r = await req('GET', `/api/graph/explore?seeds=${encodeURIComponent(`${L}:s`)}`)
    assert.equal(r.status, 200)
    assert.equal(r.json.spine.ok, false)
    assert.match(r.json.spine.reason, /gateway HTTP 401/)
    assert.equal(await unsealedCount(), before + 1)
  } finally {
    mode = 'ok'
  }
})

test('GATEWAY_RECEIPTS off ⇒ no spine field at all (exact pre-W1.3 response shape)', async () => {
  const L = `sp-off-${process.pid}`
  await req('POST', '/api/graph/node', { id: `${L}:s`, labels: [L] })
  process.env.GATEWAY_RECEIPTS = 'off'
  try {
    seen.length = 0
    const r = await req('GET', `/api/graph/explore?seeds=${encodeURIComponent(`${L}:s`)}`)
    assert.equal(r.status, 200)
    assert.ok(!('spine' in r.json), 'no spine field when disabled')
    assert.equal(seen.length, 0, 'no gateway call when disabled')
  } finally {
    process.env.GATEWAY_RECEIPTS = 'on'
  }
})

test('healthz reports the unsealedReceipts counter', async () => {
  const h = await req('GET', '/healthz')
  assert.equal(h.status, 200)
  assert.equal(typeof h.json.unsealedReceipts, 'number')
  assert.ok(h.json.unsealedReceipts >= 2, 'the two degradation tests above were counted')
})
