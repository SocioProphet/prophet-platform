/**
 * membrane integration — the B-after-A gate END TO END over real HTTP with
 * MEMBRANE_ENFORCE=on and a stub compute-gateway capturing the seal calls:
 * A (OrderIntent in an EffectRequest) → decide → EffectDecision node (idempotent,
 * sealed) → B (ExecutionReport write) lands ONLY with a matching approved decision.
 */
import { test, before, after } from 'node:test'
import assert from 'node:assert/strict'
import * as http from 'node:http'

process.env.PORT = String(19093)
process.env.HELLGRAPH_STORE_DIR = `${process.env.TMPDIR ?? '/tmp'}/hgsvc-membrane-test-${process.pid}`
process.env.HELLGRAPH_SEED = 'off'
process.env.HELLGRAPH_LOAD_KKO = 'off'
process.env.MEMBRANE_ENFORCE = 'on'
process.env.AUTH_ENFORCE = 'off'
process.env.COMPUTE_GATEWAY_URL = 'http://127.0.0.1:19097'
process.env.GATEWAY_TOKEN = 'stub-gateway-token'

const BASE = `http://127.0.0.1:${process.env.PORT}`
let srv: { close: (cb?: () => void) => void }

// ── stub compute-gateway: captures /v1/compute seal calls, answers a sealed receipt ──
interface SealCall { path: string; authorization: string; body: any }
const sealCalls: SealCall[] = []
let gatewayMode: 'ok' | 'error' = 'ok'
const stubGateway = http.createServer((req, res) => {
  let d = ''
  req.on('data', (c) => { d += c })
  req.on('end', () => {
    sealCalls.push({ path: req.url ?? '', authorization: String(req.headers['authorization'] ?? ''), body: JSON.parse(d || '{}') })
    res.writeHead(gatewayMode === 'ok' ? 200 : 500, { 'content-type': 'application/json' })
    res.end(JSON.stringify(gatewayMode === 'ok'
      ? { status: 'ok', kind: 'materialize', backend: 'gateway', receipt: { id: `sha256:stub-receipt-${sealCalls.length}` } }
      : { status: 'error', error: 'stub-induced failure' }))
  })
})

before(async () => {
  await new Promise<void>((r) => stubGateway.listen(19097, '127.0.0.1', () => r()))
  const mod = await import('./server')
  srv = mod.server as unknown as typeof srv
  await new Promise((r) => setTimeout(r, 150))
})
after(() => { srv?.close(); stubGateway.close() })

async function post(path: string, body: unknown) {
  const r = await fetch(BASE + path, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) })
  return { status: r.status, json: (await r.json()) as any }
}
async function get(path: string) {
  const r = await fetch(BASE + path)
  return { status: r.status, json: (await r.json()) as any }
}

// spec-valid builders (mirror the vendored sourceos-spec profiles)
function intent(n: string, over: Record<string, unknown> = {}) {
  return {
    id: `urn:srcos:order-intent:t-${n}`, type: 'OrderIntent', specVersion: '0.1.0',
    actorRef: 'urn:srcos:agent:membrane-test', wallTime: '2026-07-29T12:00:00Z',
    strategyRef: 'strat-test', instrumentRef: 'SP:AAA', intentKind: 'new', side: 'buy',
    orderType: 'limit', quantity: 100, price: 10, timeInForce: 'day', ...over,
  }
}
function effectRequest(n: string, intentOver: Record<string, unknown> = {}, reqOver: Record<string, unknown> = {}) {
  const it = intent(n, intentOver)
  return {
    id: `urn:srcos:effect:t-${n}`, type: 'EffectRequest', specVersion: '0.1.0',
    requestedByEventRef: it.id, effectKind: 'execute', capability: 'trading.order.place',
    target: { kind: 'venue_order_gateway', identifier: 'SYNTH' },
    parameters: { orderIntent: it }, idempotencyKey: `key-${n}`,
    requiresHumanApproval: false, policyLabels: [], riskLabels: [],
    requestedAt: '2026-07-29T12:00:00Z', ...reqOver,
  }
}

test('happy path: A → decide(approved, sealed on the spine) → B lands', async () => {
  const sealsBefore = sealCalls.length
  const d = await post('/api/membrane/decide', effectRequest('happy'))
  assert.equal(d.status, 200)
  assert.equal(d.json.ok, true)
  assert.equal(d.json.decision, 'approved')
  assert.equal(d.json.idempotent, false)
  assert.equal(d.json.intentRef, 'urn:srcos:order-intent:t-happy')
  assert.match(d.json.decisionRef, /^urn:srcos:effect-decision:key-happy-/)
  assert.match(d.json.decisionHash, /^sha256:[a-f0-9]{64}$/)
  // sealed via the deployed gateway's EXISTING receipt door (kind=materialize shape)
  assert.equal(d.json.sealed, true)
  assert.match(d.json.receiptRef, /^sha256:stub-receipt-/)
  assert.equal(sealCalls.length, sealsBefore + 1)
  const seal = sealCalls[sealCalls.length - 1]!
  assert.equal(seal.path, '/v1/compute')
  assert.equal(seal.authorization, 'Bearer stub-gateway-token')
  assert.equal(seal.body.kind, 'materialize')
  assert.equal(seal.body.spec.table, 'EffectDecision')
  assert.equal(seal.body.spec.source, 'membrane')
  assert.equal(seal.body.spec.row_count, 1)
  assert.equal(seal.body.spec.batch_hash, d.json.decisionHash)
  assert.ok(seal.body.spec.to_cursor > seal.body.spec.from_cursor, 'seal binds a real logical-clock cut')

  // B: the ExecutionReport write carries decisionRef + matching intentRef → lands
  const b = await post('/api/graph/node', {
    id: 'urn:srcos:execution-report:t-happy-1', labels: ['ExecutionReport'],
    properties: { decisionRef: d.json.decisionRef, intentRef: 'urn:srcos:order-intent:t-happy', reportKind: 'fill' },
  })
  assert.equal(b.status, 200)
  assert.equal(b.json.ok, true)
  // the spec field name orderIntentRef works too (same decision, second report)
  const b2 = await post('/api/graph/node', {
    id: 'urn:srcos:execution-report:t-happy-2', labels: ['ExecutionReport'],
    properties: { decisionRef: d.json.decisionRef, orderIntentRef: 'urn:srcos:order-intent:t-happy', reportKind: 'accepted' },
  })
  assert.equal(b2.status, 200)
})

test('B without any decision is a typed 403 (missing_decisionRef / decision_not_found)', async () => {
  const noRef = await post('/api/graph/node', {
    id: 'urn:srcos:execution-report:t-norefs', labels: ['ExecutionReport'],
    properties: { intentRef: 'urn:srcos:order-intent:t-none', reportKind: 'fill' },
  })
  assert.equal(noRef.status, 403)
  assert.equal(noRef.json.error, 'membrane_denied')
  assert.equal(noRef.json.reason, 'missing_decisionRef')

  const dangling = await post('/api/graph/node', {
    id: 'urn:srcos:execution-report:t-dangling', labels: ['ExecutionReport'],
    properties: { decisionRef: 'urn:srcos:effect-decision:does-not-exist-0000000000000000', intentRef: 'urn:srcos:order-intent:t-none', reportKind: 'fill' },
  })
  assert.equal(dangling.status, 403)
  assert.equal(dangling.json.reason, 'decision_not_found')

  const noIntent = await post('/api/graph/node', {
    id: 'urn:srcos:execution-report:t-nointent', labels: ['ExecutionReport'],
    properties: { decisionRef: 'urn:srcos:effect-decision:x-0', reportKind: 'fill' },
  })
  assert.equal(noIntent.status, 403)
  assert.equal(noIntent.json.reason, 'missing_intentRef')
})

test('policy kernel v0 denies over-limit + human-approval requests; B on a denied decision is 403', async () => {
  // size limit: quantity above MEMBRANE_MAX_QUANTITY default (10000)
  const d = await post('/api/membrane/decide', effectRequest('denied', { quantity: 999_999 }))
  assert.equal(d.status, 200)
  assert.equal(d.json.decision, 'denied')
  assert.ok(d.json.reasons.includes('quantity_exceeds_limit:10000'), `reasons: ${JSON.stringify(d.json.reasons)}`)
  // a deny IS a decision: recorded AND sealed on the spine
  assert.equal(d.json.sealed, true)

  const b = await post('/api/graph/node', {
    id: 'urn:srcos:execution-report:t-denied', labels: ['ExecutionReport'],
    properties: { decisionRef: d.json.decisionRef, intentRef: 'urn:srcos:order-intent:t-denied', reportKind: 'fill' },
  })
  assert.equal(b.status, 403)
  assert.equal(b.json.reason, 'decision_not_approved')
  assert.equal(b.json.decision, 'denied')

  // declared human-approval requirement cannot be machine-approved (deny, never downgrade)
  const h = await post('/api/membrane/decide', effectRequest('human', {}, { requiresHumanApproval: true }))
  assert.equal(h.json.decision, 'denied')
  assert.ok(h.json.reasons.includes('human_approval_required_no_human_channel'))

  // deny-by-default on kinds outside the allow-list
  const k = await post('/api/membrane/decide', effectRequest('badkinds', { intentKind: 'pause' }, { effectKind: 'notify', capability: 'doors.unlock' }))
  assert.equal(k.json.decision, 'denied')
  assert.ok(k.json.reasons.includes('effect_kind_not_allowed:notify'))
  assert.ok(k.json.reasons.includes('capability_not_allowed:doors.unlock'))
  assert.ok(k.json.reasons.includes('intent_kind_not_allowed:pause'))
})

test('intentRef mismatch is a typed 403 — the approval is FOR an intent, not a bearer chip', async () => {
  const d = await post('/api/membrane/decide', effectRequest('match-a'))
  assert.equal(d.json.decision, 'approved')
  const b = await post('/api/graph/node', {
    id: 'urn:srcos:execution-report:t-mismatch', labels: ['ExecutionReport'],
    properties: { decisionRef: d.json.decisionRef, intentRef: 'urn:srcos:order-intent:t-OTHER', reportKind: 'fill' },
  })
  assert.equal(b.status, 403)
  assert.equal(b.json.reason, 'intent_mismatch')
  // ambiguous double declaration (intentRef != orderIntentRef) also refuses
  const amb = await post('/api/graph/node', {
    id: 'urn:srcos:execution-report:t-ambiguous', labels: ['ExecutionReport'],
    properties: { decisionRef: d.json.decisionRef, intentRef: 'urn:srcos:order-intent:t-match-a', orderIntentRef: 'urn:srcos:order-intent:t-OTHER', reportKind: 'fill' },
  })
  assert.equal(amb.status, 403)
  assert.equal(amb.json.reason, 'intent_mismatch')
})

test('decide is idempotent by key: same key twice = the SAME decision, sealed once', async () => {
  const sealsBefore = sealCalls.length
  const first = await post('/api/membrane/decide', effectRequest('idem'))
  assert.equal(first.json.idempotent, false)
  // same idempotencyKey, even with a different (over-limit) payload → the stored decision, NOT re-evaluated
  const replay = await post('/api/membrane/decide', effectRequest('idem', { quantity: 999_999 }))
  assert.equal(replay.status, 200)
  assert.equal(replay.json.idempotent, true)
  assert.equal(replay.json.decision, 'approved')
  assert.equal(replay.json.decisionRef, first.json.decisionRef)
  assert.equal(replay.json.decisionHash, first.json.decisionHash)
  assert.equal(sealCalls.length, sealsBefore + 1, 'exactly one seal for one decision')
  // exactly one EffectDecision node exists for the key
  const q = await get('/api/graph/query?label=EffectDecision')
  assert.equal(q.json.nodes.filter((n: any) => n.id === first.json.decisionRef).length, 1)
})

test('spec-validation rejects malformed requests (vendored schemas, loud errors)', async () => {
  // not JSON
  const r0 = await fetch(BASE + '/api/membrane/decide', { method: 'POST', body: '{nope' })
  assert.equal(r0.status, 400)
  assert.equal(((await r0.json()) as any).error, 'invalid_json')
  // missing idempotencyKey (required by EffectRequest)
  const { idempotencyKey: _drop, ...noKey } = effectRequest('nokey') as any
  const r1 = await post('/api/membrane/decide', noKey)
  assert.equal(r1.status, 400)
  assert.equal(r1.json.error, 'invalid_effect_request')
  assert.ok(r1.json.errors.some((e: string) => e.includes("missing required 'idempotencyKey'")))
  // invented envelope property (additionalProperties: false)
  const r2 = await post('/api/membrane/decide', effectRequest('extra', {}, { smuggled: true }))
  assert.equal(r2.status, 400)
  assert.ok(r2.json.errors.some((e: string) => e.includes("unknown property 'smuggled'")))
  // no wrapped intent
  const r3 = await post('/api/membrane/decide', effectRequest('nointent', {}, { parameters: {} }))
  assert.equal(r3.status, 400)
  assert.ok(r3.json.errors[0].includes('parameters.orderIntent'))
  // malformed wrapped intent (enum violation)
  const r4 = await post('/api/membrane/decide', effectRequest('badside', { side: 'hold' }))
  assert.equal(r4.status, 400)
  assert.equal(r4.json.error, 'invalid_order_intent')
  assert.ok(r4.json.errors.some((e: string) => e.includes('OrderIntent.side')))
  // envelope↔intent identity binding
  const r5 = await post('/api/membrane/decide', effectRequest('bind', {}, { requestedByEventRef: 'urn:srcos:order-intent:t-SOMETHING-ELSE' }))
  assert.equal(r5.status, 400)
  assert.equal(r5.json.error, 'intent_binding_mismatch')
})

test('forge guard: EffectDecision nodes cannot be minted or overwritten via the public write path', async () => {
  const byLabel = await post('/api/graph/node', {
    id: 'urn:srcos:effect-decision:forged-0000000000000000', labels: ['EffectDecision'],
    properties: { decision: 'approved', intentRef: 'urn:srcos:order-intent:t-forged' },
  })
  assert.equal(byLabel.status, 403)
  assert.equal(byLabel.json.reason, 'decision_mint_via_membrane_only')
  // label-stripped overwrite of a decision URN is refused too
  const byPrefix = await post('/api/graph/node', {
    id: 'urn:srcos:effect-decision:forged-0000000000000000', labels: ['InnocentLabel'],
    properties: { decision: 'approved' },
  })
  assert.equal(byPrefix.status, 403)
  assert.equal(byPrefix.json.reason, 'decision_mint_via_membrane_only')
})

test('non-ExecutionReport writes pass untouched with enforcement on', async () => {
  const n = await post('/api/graph/node', { id: 'plain:node-1', labels: ['Org'], properties: { name: 'Acme' } })
  assert.equal(n.status, 200)
  const e = await post('/api/graph/edge', { label: 'rel', from: 'plain:node-1', to: 'plain:node-1' })
  assert.equal(e.status, 200)
})

test('seal degradation is honest: gateway down/erroring ⇒ decision lands with sealed:false + sealError', async () => {
  // gateway returns 500
  gatewayMode = 'error'
  try {
    const d = await post('/api/membrane/decide', effectRequest('seal-err'))
    assert.equal(d.status, 200)
    assert.equal(d.json.decision, 'approved')
    assert.equal(d.json.sealed, false)
    assert.match(String(d.json.sealError), /^gateway_500/)
  } finally { gatewayMode = 'ok' }
  // gateway unreachable
  const prev = process.env.COMPUTE_GATEWAY_URL
  process.env.COMPUTE_GATEWAY_URL = 'http://127.0.0.1:19099' // nothing listens here
  try {
    const d = await post('/api/membrane/decide', effectRequest('seal-down'))
    assert.equal(d.status, 200)
    assert.equal(d.json.sealed, false)
    assert.match(String(d.json.sealError), /^gateway_unreachable:/)
  } finally { process.env.COMPUTE_GATEWAY_URL = prev }
})
