/**
 * tenant integration — TENANT_ENFORCE=on over real HTTP: isolation is WIRED into the request handler,
 * not just a library. A token scopes a caller to ONE tenant; a read sees only that tenant's nodes, a
 * write into another tenant is refused, an op_set-scoped read excludes other op_sets, endpoints that
 * can't be scoped here are refused, and TENANT_ENFORCE=on without AUTH_ENFORCE=on refuses to boot.
 */
import { test, before, after } from 'node:test'
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import * as path from 'node:path'
import { mintGraphToken } from './auth.js'

const SECRET = 'tenant-integration-secret'
// PORT ALLOCATION (see spine.test.ts): 19103 free for this suite, 19104 for its fail-closed spawn.
process.env.PORT = String(19103)
process.env.HELLGRAPH_STORE_DIR = `${process.env.TMPDIR ?? '/tmp'}/hgsvc-tenant-test-${process.pid}`
process.env.HELLGRAPH_SEED = 'off'
process.env.HELLGRAPH_LOAD_KKO = 'off'
process.env.AUTH_ENFORCE = 'on'
process.env.AUTH_HMAC_SECRET = SECRET
process.env.TENANT_ENFORCE = 'on'
delete process.env.MEMBRANE_ENFORCE

const BASE = `http://127.0.0.1:${process.env.PORT}`
let srv: { close: (cb?: () => void) => void }

before(async () => {
  const mod = await import('./server')
  srv = mod.server as unknown as typeof srv
  await new Promise((r) => setTimeout(r, 150))
})
after(() => srv?.close())

// Tokens: acme (may read/write, entitled to op_sets discourse+ingest), globex, and a tenantless token.
const acme = mintGraphToken(SECRET, { id: 'acme', scopes: ['graph:read', 'graph:write'], tenant: 'acme', op_sets: ['discourse', 'ingest'] })
const globex = mintGraphToken(SECRET, { id: 'globex', scopes: ['graph:read', 'graph:write'], tenant: 'globex', op_sets: ['discourse'] })
const tenantless = mintGraphToken(SECRET, { id: 'nobody', scopes: ['graph:read', 'graph:write'] })

async function req(method: string, p: string, token: string, body?: unknown) {
  const r = await fetch(BASE + p, {
    method,
    headers: { authorization: `Bearer ${token}`, ...(body !== undefined ? { 'content-type': 'application/json' } : {}) },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  return { status: r.status, json: (await r.json()) as any }
}
const node = (id: string, tenant: string, op_set: string) =>
  ({ id, labels: ['clause'], properties: { tenant_id: tenant, op_set } })
const queryIds = async (token: string, qs = '') =>
  ((await req('GET', `/api/graph/query${qs}`, token)).json.nodes as { id: string }[]).map((n) => n.id)

test('writes: own-tenant OK; cross-tenant and unlabeled writes are refused 403', async () => {
  assert.equal((await req('POST', '/api/graph/node', acme, node('acme:doc1', 'acme', 'discourse'))).status, 200)
  assert.equal((await req('POST', '/api/graph/node', acme, node('acme:ing1', 'acme', 'ingest'))).status, 200)
  assert.equal((await req('POST', '/api/graph/node', globex, node('gx:doc1', 'globex', 'discourse'))).status, 200)

  // acme's token cannot write into globex, nor write an unlabeled node
  const cross = await req('POST', '/api/graph/node', acme, node('acme:evil', 'globex', 'discourse'))
  assert.equal(cross.status, 403)
  assert.equal(cross.json.reason, 'cross_tenant_write')
  const unlabeled = await req('POST', '/api/graph/node', acme, { id: 'acme:bare', labels: ['clause'] })
  assert.equal(unlabeled.status, 403)
  assert.equal(unlabeled.json.reason, 'cross_tenant_write')
})

test('reads: a caller sees ONLY its own tenant — cross-tenant nodes are invisible', async () => {
  const acmeIds = await queryIds(acme)
  assert.ok(acmeIds.includes('acme:doc1') && acmeIds.includes('acme:ing1'), 'acme sees its own nodes')
  assert.ok(!acmeIds.includes('gx:doc1'), 'acme must NOT see globex nodes')

  const gxIds = await queryIds(globex)
  assert.ok(gxIds.includes('gx:doc1'))
  assert.ok(!gxIds.some((id) => id.startsWith('acme:')), 'globex must NOT see acme nodes')

  // stats are tenant-scoped too (counts are the caller's, not the whole graph's)
  const gxStats = (await req('GET', '/api/graph/stats', globex)).json
  assert.equal(gxStats.nodes, 1, 'globex sees exactly its 1 node')
})

test('op_set scopes within a tenant; an unentitled op_set is refused', async () => {
  const disc = await queryIds(acme, '?op_set=discourse')
  assert.ok(disc.includes('acme:doc1'), 'discourse read includes the discourse node')
  assert.ok(!disc.includes('acme:ing1'), 'discourse read excludes the ingest-op_set node')

  const forbidden = await req('GET', '/api/graph/query?op_set=secret', acme)
  assert.equal(forbidden.status, 403)
  assert.equal(forbidden.json.reason, 'op_set_forbidden')
})

test('a token carrying no tenant is denied every scoped read', async () => {
  const d = await req('GET', '/api/graph/query', tenantless)
  assert.equal(d.status, 403)
  assert.equal(d.json.reason, 'tenant_required')
})

test('endpoints that cannot be tenant-scoped here are refused (fail-closed)', async () => {
  for (const p of ['/api/graph/sparql', '/api/graph/cypher', '/api/graph/enrich?label=X']) {
    const method = p.startsWith('/api/graph/enrich') ? 'GET' : 'POST'
    const token = p.startsWith('/api/graph/enrich') ? mintGraphToken(SECRET, { id: 'e', scopes: ['graph:enrich'], tenant: 'acme' }) : acme
    const d = await req(method, p, token, method === 'POST' ? { query: 'x' } : undefined)
    assert.equal(d.status, 403, `${p} must be refused under TENANT_ENFORCE`)
    assert.equal(d.json.reason, 'tenant_isolation_unavailable')
  }
})

test('fail-closed startup: TENANT_ENFORCE=on without AUTH_ENFORCE=on refuses to boot', () => {
  const appRoot = path.join(__dirname, '..')
  const r = spawnSync(process.execPath, ['--import', 'tsx', 'src/server.ts'], {
    cwd: appRoot,
    env: {
      ...process.env, TENANT_ENFORCE: 'on', AUTH_ENFORCE: 'off', PORT: '19104',
      HELLGRAPH_SEED: 'off', HELLGRAPH_LOAD_KKO: 'off',
      HELLGRAPH_STORE_DIR: `${process.env.TMPDIR ?? '/tmp'}/hgsvc-tenant-failclosed-${process.pid}`,
    },
    encoding: 'utf8',
    timeout: 30_000,
  })
  assert.equal(r.status, 1, `expected exit 1, got ${r.status}; stderr: ${r.stderr}`)
  assert.match(r.stderr, /requires AUTH_ENFORCE=on/)
})
