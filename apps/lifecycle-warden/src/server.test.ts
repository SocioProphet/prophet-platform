/**
 * HTTP surface + boot semantics: /healthz tells the truth (mode, lastRun, dueCounts,
 * auditHead, unsealedRuns), sealing degrades honestly when the gateway is down, and
 * boot is fail-closed for enforce-without-credentials.
 */
import { test, before, after } from 'node:test'
import assert from 'node:assert/strict'
import { resolveBootConfig, start, MAX_BODY_BYTES, type WardenService } from './server.js'

const PORT = 19095
const BASE = `http://127.0.0.1:${PORT}`
let svc: WardenService

before(async () => {
  svc = await start({
    dryRun: true,
    enforce: false,
    minio: null, // memory mode — a dry-run warden may run credential-less; enforce may NOT
    gatewayUrl: `http://127.0.0.1:1`, // nothing listens: sealing must degrade, not crash
    gatewayToken: 'test-token',
  }, PORT, 0) // no interval — tests drive runs
})
after(async () => { await svc.stop() })

async function req(method: string, path: string, body?: unknown) {
  const r = await fetch(BASE + path, {
    method,
    headers: body ? { 'content-type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  return { status: r.status, json: (await r.json()) as any }
}

test('fail-closed: ENFORCING with missing MinIO creds refuses to boot', () => {
  assert.throws(
    () => resolveBootConfig({ WARDEN_ENFORCE: 'on', WARDEN_DRY_RUN: 'off' } as NodeJS.ProcessEnv),
    /fail-closed/,
  )
  // partial credentials are also refused — half a config is a misconfiguration, not a mode
  assert.throws(
    () => resolveBootConfig({ MINIO_ENDPOINT: 'minio:9000' } as NodeJS.ProcessEnv),
    /partial MinIO config/,
  )
})

test('ENFORCE=on while dry-run wins BOOTS and warns loudly — the refusal tracks real enforcement', () => {
  // The two-lever contract, honoured: nothing is applied in dry-run, so there is no
  // delete to be amnesiac about and no reason to refuse. What there IS reason for is
  // saying out loud that the operator asked to enforce and is not getting it.
  const warnings: string[] = []
  const cfg = resolveBootConfig(
    { WARDEN_ENFORCE: 'on' } as NodeJS.ProcessEnv, // DRY_RUN unset ⇒ defaults to on
    (m) => warnings.push(m),
  )
  assert.equal(cfg.enforce, false)
  assert.equal(cfg.dryRun, true)
  assert.equal(cfg.minio, null)
  assert.equal(warnings.length, 1, `expected exactly one warning, got ${JSON.stringify(warnings)}`)
  assert.match(warnings[0]!, /DRY-RUN WINS/)
  assert.match(warnings[0]!, /MinIO credentials/) // credential-less is named too

  // same lever combination WITH creds: still boots, still warns (it always could —
  // this is the case the old code handled, kept here so the two stay consistent)
  const warned2: string[] = []
  const withCreds = resolveBootConfig(
    { WARDEN_ENFORCE: 'on', MINIO_ENDPOINT: 'm:9000', MINIO_ACCESS_KEY: 'a', MINIO_SECRET_KEY: 's' } as NodeJS.ProcessEnv,
    (m) => warned2.push(m),
  )
  assert.equal(withCreds.enforce, false)
  assert.equal(warned2.length, 1)
  assert.match(warned2[0]!, /DRY-RUN WINS/)

  // and the quiet, correct default says nothing at all
  const silent: string[] = []
  resolveBootConfig({} as NodeJS.ProcessEnv, (m) => silent.push(m))
  assert.deepEqual(silent, [])
})

test('both levers required: ENFORCE=on alone stays dry-run; +DRY_RUN=off enforces', () => {
  const dflt = resolveBootConfig({} as NodeJS.ProcessEnv)
  assert.equal(dflt.dryRun, true)
  assert.equal(dflt.enforce, false)
  const half = resolveBootConfig({ WARDEN_ENFORCE: 'on', MINIO_ENDPOINT: 'm:9000', MINIO_ACCESS_KEY: 'a', MINIO_SECRET_KEY: 's' } as NodeJS.ProcessEnv)
  assert.equal(half.enforce, false) // dry-run wins until explicitly turned off
  const full = resolveBootConfig({ WARDEN_ENFORCE: 'on', WARDEN_DRY_RUN: 'off', MINIO_ENDPOINT: 'm:9000', MINIO_ACCESS_KEY: 'a', MINIO_SECRET_KEY: 's' } as NodeJS.ProcessEnv)
  assert.equal(full.enforce, true)
  assert.equal(full.minio!.endPoint, 'm')
})

test('healthz tells the truth: flags, lastRun, dueCounts, auditHead, unsealedRuns', async () => {
  const h0 = await req('GET', '/healthz')
  assert.equal(h0.status, 200)
  assert.equal(h0.json.service, 'lifecycle-warden')
  assert.equal(h0.json.dryRun, true)
  assert.equal(h0.json.enforce, false)
  assert.equal(h0.json.storage, 'memory')
  assert.equal(h0.json.lastRun, null)

  // govern one overdue object, then run — over a DEAD gateway
  const c = await req('POST', '/v1/objects', {
    id: 'h-1', content: 'x', retentionDeleteAt: Date.now() - 1000,
  })
  assert.equal(c.status, 201)
  assert.equal(c.json.object.state, 'Normalized')
  assert.ok(c.json.contentHash)

  const run = await req('POST', '/v1/run')
  assert.equal(run.status, 200)
  assert.equal(run.json.dryRun, true)
  assert.equal(run.json.plannedCount, 1)
  assert.equal(run.json.appliedCount, 0)
  assert.equal(run.json.sealed, false) // gateway is down — degradation, not pretense
  assert.match(run.json.sealError, /unreachable/)

  const h1 = await req('GET', '/healthz')
  assert.equal(h1.json.lastRun.runId, run.json.runId)
  assert.equal(h1.json.unsealedRuns, 1)
  assert.equal(h1.json.sealedRuns, 0)
  assert.deepEqual(h1.json.dueCounts, { retention_delete: 1 }) // dry-run left it due
  assert.ok(h1.json.auditHead && typeof h1.json.auditHead.hash === 'string')
})

test('lifecycle over HTTP: transition/hold/release are gated + audited; chain verifies', async () => {
  await req('POST', '/v1/objects', { id: 'h-2', content: 'y' })
  for (const t of ['extract', 'index', 'serve']) {
    const r = await req('POST', '/v1/objects/h-2/transition', { trigger: t })
    assert.equal(r.status, 200)
  }
  assert.equal((await req('POST', '/v1/objects/h-2/hold')).json.object.state, 'LegalHold')
  // blocked delete: object unchanged (the Governor audits `blocked`)
  const blocked = await req('POST', '/v1/objects/h-2/transition', { trigger: 'delete_after_release' })
  assert.equal(blocked.json.object.state, 'LegalHold')
  assert.equal((await req('POST', '/v1/objects/h-2/release')).json.object.state, 'Served')

  const head = await req('GET', '/v1/audit/head')
  assert.equal(head.status, 200)
  assert.ok(head.json.head.seq > 0)
  const verify = await req('GET', '/v1/audit/verify')
  assert.equal(verify.status, 200)
  assert.equal(verify.json.ok, true)
})

test('vendor materialize without a configured client is refused (egress default-deny)', async () => {
  await req('POST', '/v1/objects', { id: 'h-3', content: 'z', vendorOptIn: true })
  for (const t of ['extract', 'index', 'serve']) await req('POST', '/v1/objects/h-3/transition', { trigger: t })
  const r = await req('POST', '/v1/objects/h-3/materialize', { vendor: 'gemini', optIn: true, ttlMs: 1000 })
  assert.equal(r.status, 403) // no vendor client configured → structurally impossible
  assert.equal(r.json.ok, false)
})

test('an oversized body is ANSWERED (413), never left hanging', async () => {
  // The bug: over the cap the read called req.destroy(), which emits neither 'end'
  // nor necessarily 'error', so the promise never settled and the handler awaited a
  // body that would never arrive — the client hung until its own timeout, forever on
  // a keep-alive connection. The guarantee under test is simply: it SETTLES, fast.
  const oversized = 'x'.repeat(MAX_BODY_BYTES + 1024)
  const answered = fetch(`${BASE}/v1/objects`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ id: 'too-big', content: oversized }),
  }).then(async (r) => ({ hung: false as const, status: r.status, body: await r.text() }))
  const verdict = await Promise.race([
    answered,
    new Promise<{ hung: true }>((r) => setTimeout(() => r({ hung: true }), 5_000).unref()),
  ])
  assert.equal(verdict.hung, false, 'readBody HUNG: no response within 5s for an oversized body')
  assert.equal((verdict as { status: number }).status, 413)
  assert.match((verdict as { body: string }).body, /exceeds 5000000 bytes/)

  // and the server is still healthy afterwards — refusing one body did not wound it
  const h = await req('GET', '/healthz')
  assert.equal(h.status, 200)
  assert.equal(h.json.ok, true)

  // a normal body on the same route still works
  const ok = await req('POST', '/v1/objects', { id: 'not-too-big', content: 'small' })
  assert.equal(ok.status, 201)
})

test('unknown object and bad routes answer honestly', async () => {
  assert.equal((await req('GET', '/v1/objects/nope')).status, 404)
  assert.equal((await req('POST', '/v1/objects/nope/hold')).status, 404)
  assert.equal((await req('GET', '/nope')).status, 404)
})
