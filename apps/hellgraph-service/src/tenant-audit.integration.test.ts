/**
 * tenant AUDIT integration — TENANT_ENFORCE=audit over real HTTP: the dry run BLOCKS NOTHING. A
 * cross-tenant write succeeds and a read returns every tenant's nodes (unscoped) — audit only LOGS the
 * would-be denials ("[tenant-audit] ..."). This is the safety property the rollout depends on: enabling
 * audit can never break a caller. (Enforcement itself is proven in tenant.integration.test.ts.)
 */
import { test, before, after } from 'node:test'
import assert from 'node:assert/strict'

// PORT ALLOCATION (see spine.test.ts): 19105 free for this suite.
process.env.PORT = String(19105)
process.env.HELLGRAPH_STORE_DIR = `${process.env.TMPDIR ?? '/tmp'}/hgsvc-tenant-audit-${process.pid}`
process.env.HELLGRAPH_SEED = 'off'
process.env.HELLGRAPH_LOAD_KKO = 'off'
process.env.TENANT_ENFORCE = 'audit'   // dry run — no AUTH required, nothing enforced
delete process.env.AUTH_ENFORCE
delete process.env.MEMBRANE_ENFORCE

const BASE = `http://127.0.0.1:${process.env.PORT}`
let srv: { close: (cb?: () => void) => void }
let audits = 0
const realWarn = console.warn.bind(console)

before(async () => {
  // capture [tenant-audit] lines so we can prove the dry run is actually observing, not silent
  console.warn = (...a: unknown[]) => { if (String(a[0] ?? '').includes('[tenant-audit]')) audits++; realWarn(...a) }
  const mod = await import('./server')
  srv = mod.server as unknown as typeof srv
  await new Promise((r) => setTimeout(r, 150))
})
after(() => { srv?.close(); console.warn = realWarn })

async function req(method: string, p: string, body?: unknown) {
  const r = await fetch(BASE + p, {
    method,
    headers: body !== undefined ? { 'content-type': 'application/json' } : {},
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  return { status: r.status, json: (await r.json()) as any }
}
const node = (id: string, tenant: string) =>
  ({ id, labels: ['clause'], properties: { tenant_id: tenant, op_set: 'discourse' } })

test('audit blocks NOTHING: cross-tenant writes succeed and reads are unscoped', async () => {
  assert.equal((await req('POST', '/api/graph/node', node('acme:a1', 'acme'))).status, 200)
  assert.equal((await req('POST', '/api/graph/node', node('gx:b1', 'globex'))).status, 200)

  // a plain read returns BOTH tenants (audit did not scope) — nothing broke
  const ids = ((await req('GET', '/api/graph/query')).json.nodes as { id: string }[]).map((n) => n.id)
  assert.ok(ids.includes('acme:a1') && ids.includes('gx:b1'), 'audit read is unscoped (allowed)')

  // an "unscopable" endpoint is NOT refused under audit (it would be under enforce)
  assert.notEqual((await req('POST', '/api/graph/sparql', { query: 'SELECT ?s WHERE { ?s ?p ?o } LIMIT 1' })).status, 403)
})

test('audit is actually OBSERVING — [tenant-audit] lines were emitted', () => {
  // the tokenless reads/writes above each had a would-be denial (tenant_required) that audit logged
  assert.ok(audits > 0, 'expected [tenant-audit] dry-run lines to be emitted')
})
