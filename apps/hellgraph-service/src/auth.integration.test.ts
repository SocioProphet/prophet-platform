/**
 * auth integration — AUTH_ENFORCE=on over real HTTP: the scope gate is WIRED, not a
 * library nobody calls. Includes the fail-closed startup contract (enforce-on with a
 * missing secret refuses to boot) as a real child-process spawn.
 */
import { test, before, after } from 'node:test'
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import * as path from 'node:path'
import { mintGraphToken, type GraphScope } from './auth.js'

const SECRET = 'integration-secret'
process.env.PORT = String(19095)
process.env.HELLGRAPH_STORE_DIR = `${process.env.TMPDIR ?? '/tmp'}/hgsvc-auth-test-${process.pid}`
process.env.HELLGRAPH_SEED = 'off'
process.env.HELLGRAPH_LOAD_KKO = 'off'
process.env.AUTH_ENFORCE = 'on'
process.env.AUTH_HMAC_SECRET = SECRET
delete process.env.MEMBRANE_ENFORCE

const BASE = `http://127.0.0.1:${process.env.PORT}`
let srv: { close: (cb?: () => void) => void }

before(async () => {
  const mod = await import('./server')
  srv = mod.server as unknown as typeof srv
  await new Promise((r) => setTimeout(r, 150))
})
after(() => srv?.close())

const tok = (...scopes: GraphScope[]): string => mintGraphToken(SECRET, { id: 'itest', scopes })

async function req(method: string, path: string, opts: { token?: string; body?: unknown } = {}) {
  const r = await fetch(BASE + path, {
    method,
    headers: {
      ...(opts.body !== undefined ? { 'content-type': 'application/json' } : {}),
      ...(opts.token ? { authorization: `Bearer ${opts.token}` } : {}),
    },
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  })
  return { status: r.status, json: (await r.json()) as any }
}

test('healthz and federation status stay tokenless under enforcement', async () => {
  assert.equal((await req('GET', '/healthz')).status, 200)
  assert.equal((await req('GET', '/api/federation/status')).status, 200)
})

test('reads: 401 without token, 401 on garbage, 403 on wrong scope, 200 with graph:read', async () => {
  const none = await req('GET', '/api/graph/stats')
  assert.equal(none.status, 401)
  assert.equal(none.json.reason, 'missing_token')

  const garbage = await req('GET', '/api/graph/stats', { token: 'garbage' })
  assert.equal(garbage.status, 401)
  assert.equal(garbage.json.reason, 'invalid_token')

  const wrong = await req('GET', '/api/graph/stats', { token: tok('graph:write') })
  assert.equal(wrong.status, 403)
  assert.equal(wrong.json.reason, 'missing_scope')
  assert.equal(wrong.json.requiredScope, 'graph:read')

  const ok = await req('GET', '/api/graph/stats', { token: tok('graph:read') })
  assert.equal(ok.status, 200)
  assert.ok(typeof ok.json.nodes === 'number')

  // a POSTed read surface (sparql) needs graph:read, not graph:write
  const sparql = await req('POST', '/api/graph/sparql', { token: tok('graph:read'), body: { query: 'SELECT ?s WHERE { ?s ?p ?o } LIMIT 1' } })
  assert.equal(sparql.status, 200)
})

test('writes: node/edge need graph:write; graph:read is denied', async () => {
  const denied = await req('POST', '/api/graph/node', { token: tok('graph:read'), body: { id: 'auth:n1', labels: ['T'] } })
  assert.equal(denied.status, 403)
  assert.equal(denied.json.requiredScope, 'graph:write')

  const ok = await req('POST', '/api/graph/node', { token: tok('graph:write'), body: { id: 'auth:n1', labels: ['T'], properties: { name: 'n1' } } })
  assert.equal(ok.status, 200)
  const edge = await req('POST', '/api/graph/edge', { token: tok('graph:write'), body: { label: 'rel', from: 'auth:n1', to: 'auth:n1' } })
  assert.equal(edge.status, 200)
})

test('enrich needs graph:enrich specifically (read/write do not suffice)', async () => {
  await req('POST', '/api/graph/node', { token: tok('graph:write'), body: { id: 'auth:e1', labels: ['AuthEnrich'], properties: { k: 'v' } } })
  for (const t of [tok('graph:read'), tok('graph:write')]) {
    const d = await req('GET', '/api/graph/enrich?label=AuthEnrich', { token: t })
    assert.equal(d.status, 403)
    assert.equal(d.json.requiredScope, 'graph:enrich')
  }
  const ok = await req('GET', '/api/graph/enrich?label=AuthEnrich', { token: tok('graph:enrich') })
  assert.equal(ok.status, 200)
})

test('membrane decide is gated as a governance write', async () => {
  const none = await req('POST', '/api/membrane/decide', { body: {} })
  assert.equal(none.status, 401)
  const wrong = await req('POST', '/api/membrane/decide', { token: tok('graph:read'), body: {} })
  assert.equal(wrong.status, 403)
  // with graph:write the gate opens and the SPEC gate answers (400 invalid_effect_request)
  const past = await req('POST', '/api/membrane/decide', { token: tok('graph:write'), body: {} })
  assert.equal(past.status, 400)
  assert.equal(past.json.error, 'invalid_effect_request')
})

test('unmapped paths under the gated prefixes fail closed by verb', async () => {
  // GET falls back to graph:read: token passes auth, router then 404s (auth ran first)
  const g = await req('GET', '/api/graph/route-that-does-not-exist', { token: tok('graph:read') })
  assert.equal(g.status, 404)
  // without read scope it never reaches the router
  const gDenied = await req('GET', '/api/graph/route-that-does-not-exist', { token: tok('graph:enrich') })
  assert.equal(gDenied.status, 403)
  // non-GET defaults to graph:write — a read token is refused
  const p = await req('POST', '/api/graph/route-that-does-not-exist', { token: tok('graph:read'), body: {} })
  assert.equal(p.status, 403)
  assert.equal(p.json.requiredScope, 'graph:write')
})

test('fail-closed startup: AUTH_ENFORCE=on without AUTH_HMAC_SECRET refuses to boot', () => {
  const appRoot = path.join(__dirname, '..')
  const r = spawnSync(process.execPath, ['--import', 'tsx', 'src/server.ts'], {
    cwd: appRoot,
    env: {
      ...process.env,
      AUTH_ENFORCE: 'on',
      AUTH_HMAC_SECRET: '',
      PORT: '19099',
      HELLGRAPH_SEED: 'off',
      HELLGRAPH_LOAD_KKO: 'off',
      HELLGRAPH_STORE_DIR: `${process.env.TMPDIR ?? '/tmp'}/hgsvc-failclosed-${process.pid}`,
    },
    encoding: 'utf8',
    timeout: 30_000,
  })
  assert.equal(r.status, 1, `expected exit 1, got ${r.status}; stderr: ${r.stderr}`)
  assert.match(r.stderr, /AUTH_HMAC_SECRET/)
  assert.match(r.stderr, /fail-closed/)
})
