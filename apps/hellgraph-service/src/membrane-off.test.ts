/**
 * membrane flags-off — the default posture: passthrough with a single startup WARN,
 * decisions still mintable (so an estate can stage approvals BEFORE flipping
 * MEMBRANE_ENFORCE on), and no gating of ExecutionReport / EffectDecision writes.
 */
import { test, before, after } from 'node:test'
import assert from 'node:assert/strict'
import { initMembrane } from './membrane.js'

process.env.PORT = String(19094)
process.env.HELLGRAPH_STORE_DIR = `${process.env.TMPDIR ?? '/tmp'}/hgsvc-membrane-off-test-${process.pid}`
process.env.HELLGRAPH_SEED = 'off'
process.env.HELLGRAPH_LOAD_KKO = 'off'
delete process.env.MEMBRANE_ENFORCE // default = off
delete process.env.AUTH_ENFORCE     // default = off
delete process.env.COMPUTE_GATEWAY_URL
delete process.env.GATEWAY_TOKEN

const BASE = `http://127.0.0.1:${process.env.PORT}`
let srv: { close: (cb?: () => void) => void }

before(async () => {
  const mod = await import('./server')
  srv = mod.server as unknown as typeof srv
  await new Promise((r) => setTimeout(r, 150))
})
after(() => srv?.close())

async function post(path: string, body: unknown) {
  const r = await fetch(BASE + path, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) })
  return { status: r.status, json: (await r.json()) as any }
}

test('initMembrane off = exactly one passthrough WARN; on = no off-WARN', () => {
  const offWarns: string[] = []
  const s = initMembrane({ COMPUTE_GATEWAY_URL: 'http://x', GATEWAY_TOKEN: 't' } as NodeJS.ProcessEnv, (m) => offWarns.push(m))
  assert.equal(s.enforce, false)
  assert.equal(offWarns.length, 1)
  assert.match(offWarns[0]!, /MEMBRANE_ENFORCE=off/)

  const onWarns: string[] = []
  const on = initMembrane({ MEMBRANE_ENFORCE: 'on', COMPUTE_GATEWAY_URL: 'http://x', GATEWAY_TOKEN: 't' } as NodeJS.ProcessEnv, (m) => onWarns.push(m))
  assert.equal(on.enforce, true)
  assert.deepEqual(onWarns, [])

  // unconfigured gateway wiring is announced too (its own WARN, not silence)
  const noGw: string[] = []
  initMembrane({ MEMBRANE_ENFORCE: 'on' } as NodeJS.ProcessEnv, (m) => noGw.push(m))
  assert.equal(noGw.length, 1)
  assert.match(noGw[0]!, /COMPUTE_GATEWAY_URL/)
})

test('flags off: ExecutionReport writes pass through ungated', async () => {
  const b = await post('/api/graph/node', {
    id: 'urn:srcos:execution-report:off-1', labels: ['ExecutionReport'],
    properties: { reportKind: 'fill' }, // no decisionRef, no intentRef — still lands
  })
  assert.equal(b.status, 200)
  assert.equal(b.json.ok, true)
})

test('flags off: no forge guard on EffectDecision-labeled writes', async () => {
  const n = await post('/api/graph/node', { id: 'off:decision-like', labels: ['EffectDecision'], properties: {} })
  assert.equal(n.status, 200)
})

test('flags off: /api/membrane/decide still mints (staging decisions before the flip); unsealed without gateway wiring', async () => {
  const it = {
    id: 'urn:srcos:order-intent:off-a', type: 'OrderIntent', specVersion: '0.1.0',
    actorRef: 'urn:srcos:agent:off-test', wallTime: '2026-07-29T12:00:00Z',
    strategyRef: 's', instrumentRef: 'SP:AAA', intentKind: 'new', side: 'buy',
    orderType: 'market', quantity: 5, timeInForce: 'day',
  }
  const d = await post('/api/membrane/decide', {
    id: 'urn:srcos:effect:off-a', type: 'EffectRequest', specVersion: '0.1.0',
    requestedByEventRef: it.id, effectKind: 'execute', capability: 'trading.order.place',
    target: { kind: 'venue_order_gateway', identifier: 'SYNTH' },
    parameters: { orderIntent: it }, idempotencyKey: 'off-key-a',
    requiresHumanApproval: false, policyLabels: [], riskLabels: [],
    requestedAt: '2026-07-29T12:00:00Z',
  })
  assert.equal(d.status, 200)
  assert.equal(d.json.decision, 'approved')
  assert.equal(d.json.sealed, false)
  assert.equal(d.json.sealError, 'gateway_unconfigured')
})
