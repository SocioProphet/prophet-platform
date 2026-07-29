import { test } from 'node:test'
import assert from 'node:assert/strict'

import {
  declaredOrgans, foldHealth, assembleOrgan, assembleOrgans, httpProber,
  type Health, type OrganMember, type Prober, type OrganSpec,
} from './organs.js'

const member = (health: Health): OrganMember => ({ service: 's', health })

const SPEC: OrganSpec = {
  kind: 'memory', name: 'Memory organ',
  members: [
    { service: 'a', endpoint: 'http://a', capabilities: ['recall', 'ground'] },
    { service: 'b', endpoint: 'http://b', capabilities: ['recall'] },
  ],
}

const proberFor = (byUrl: Record<string, Health>): Prober =>
  async (endpoint) => ({ health: byUrl[endpoint] ?? 'unknown' })

// ── OR-I2: health is DERIVED, never asserted ────────────────────────────────────
test('all healthy members ⇒ healthy organ', () => {
  assert.equal(foldHealth([member('healthy'), member('healthy')]), 'healthy')
})

test('all down ⇒ down', () => {
  assert.equal(foldHealth([member('down'), member('down')]), 'down')
})

test('an UNKNOWN member blocks a healthy verdict — an organ we cannot see is not one we can call well', () => {
  assert.equal(foldHealth([member('healthy'), member('unknown')]), 'degraded')
})

test('nothing knowable ⇒ unknown, never a guess', () => {
  assert.equal(foldHealth([member('unknown'), member('unknown')]), 'unknown')
  assert.equal(foldHealth([]), 'unknown')
})

test('a mix of healthy and down is degraded', () => {
  assert.equal(foldHealth([member('healthy'), member('down')]), 'degraded')
})

// ── OR-I1: never invent a member, never assume health ───────────────────────────
test('assembled members correspond exactly to the declared services', async () => {
  const organ = await assembleOrgan(SPEC, proberFor({ 'http://a': 'healthy', 'http://b': 'healthy' }))
  assert.deepEqual(organ.members.map((m) => m.service), ['a', 'b'])
  assert.equal(organ.members.length, SPEC.members.length, 'no phantom members')
})

test('a failed probe yields unknown, NOT healthy', async () => {
  const organ = await assembleOrgan(SPEC, async () => { throw new Error('boom') })
  assert.ok(organ.members.every((m) => m.health === 'unknown'))
  assert.equal(organ.health, 'unknown')
  assert.ok(organ.members[0]!.detail, 'and the reason is recorded')
})

test('assembleOrgan never throws — a probe failure is data, not an outage', async () => {
  const organ = await assembleOrgan(SPEC, async () => { throw new Error('nope') })
  assert.equal(organ.type, 'Organ')
})

// ── shape conforms to the spec ──────────────────────────────────────────────────
test('organ carries a urn id, capability union, and observation time', async () => {
  const organ = await assembleOrgan(SPEC, proberFor({ 'http://a': 'healthy', 'http://b': 'down' }))
  assert.equal(organ.id, 'urn:srcos:organ:memory')
  assert.deepEqual(organ.capabilities, ['ground', 'recall'], 'deduped + sorted union of member capabilities')
  assert.equal(organ.health, 'degraded')
  assert.ok(Date.parse(organ.observedAt) > 0)
  assert.equal(organ.specVersion, '2.0')
})

// ── the declared anatomy ────────────────────────────────────────────────────────
test('four organs are declared over real estate services', () => {
  const specs = declaredOrgans({})
  assert.deepEqual(specs.map((s) => s.kind).sort(), ['memory', 'perception', 'policy', 'routing'])
  const services = specs.flatMap((s) => s.members.map((m) => m.service))
  for (const expected of ['memory-mesh', 'zone-router', 'compute-gateway', 'ie-engine', 'identity-policy']) {
    assert.ok(services.includes(expected), `${expected} should be a declared member`)
  }
  assert.ok(specs.every((s) => s.members.length > 0), 'no empty organs')
})

test('endpoints are env-overridable so another topology declares the same organs over its own addresses', () => {
  const specs = declaredOrgans({ MEMORY_MESH_URL: 'http://edge-mesh:9999' })
  const mesh = specs.find((s) => s.kind === 'memory')!.members.find((m) => m.service === 'memory-mesh')!
  assert.equal(mesh.endpoint, 'http://edge-mesh:9999')
})

test('assembleOrgans probes the whole anatomy in one pass', async () => {
  const organs = await assembleOrgans(declaredOrgans({}), async () => ({ health: 'healthy' }))
  assert.equal(organs.length, 4)
  assert.ok(organs.every((o) => o.health === 'healthy'))
})

// ── the prober distinguishes "answered badly" from "did not answer" ─────────────
test('httpProber: non-2xx is down, unreachable is unknown', async () => {
  const originalFetch = globalThis.fetch
  try {
    globalThis.fetch = (async () => ({ ok: false, status: 503 })) as unknown as typeof fetch
    assert.deepEqual(await httpProber(50)('http://x'), { health: 'down', detail: 'HTTP 503' })

    globalThis.fetch = (async () => { throw new Error('ECONNREFUSED') }) as unknown as typeof fetch
    const unreachable = await httpProber(50)('http://x')
    assert.equal(unreachable.health, 'unknown', 'no answer is NOT evidence of death — it is absence of evidence')
  } finally {
    globalThis.fetch = originalFetch
  }
})
