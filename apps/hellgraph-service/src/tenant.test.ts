/**
 * Theorems of tenant/op_set ISOLATION (tenant.ts) — the enforcement half of "operational sets by
 * default". Cross-tenant reads return nothing, cross-tenant writes are refused, an op_set-scoped read
 * excludes other op_sets (and INCLUDES a relation's reified role-edges, which carry the same op_set),
 * and the flag is fail-closed. Pure functions, injectable fake graph — no engine, no server boot.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  initTenant, tenantActive, tenantScope, scopeForRead, assertWriteTenant, refuseUnscopable,
  type TenantState,
} from './tenant.js'

const ENFORCING: TenantState = { enforce: true, audit: false }
const OFF: TenantState = { enforce: false, audit: false }
const AUDIT: TenantState = { enforce: false, audit: true }

// A fake graph: two tenants (acme/globex), two op_sets in acme (ingest/discourse), and a reified
// hyperedge (an "argument" node + its role-edges) in acme/discourse — exactly what the writer lands.
function fakeGraph() {
  const N = (id: string, tenant: string, op_set: string, labels: string[] = ['clause']) =>
    ({ id, labels, properties: { tenant_id: tenant, op_set } })
  const E = (from: string, to: string, tenant: string, op_set: string, label = 'support',
    extra: Record<string, unknown> = {}) =>
    ({ id: `${from}->${to}`, label, from, to,
       properties: { tenant_id: tenant, op_set, ...extra } as Record<string, unknown> })
  const T = (subject: string, object: string, isIri = true) =>
    ({ subject, predicate: 'p', object, isIri })
  const nodes = [
    N('acme:c0', 'acme', 'discourse'), N('acme:p0', 'acme', 'discourse'),
    N('arg:acme:c0', 'acme', 'discourse', ['argument', 'hyperedge']),  // reified hyperedge node
    N('acme:ing0', 'acme', 'ingest', ['dataset']),                     // a different op_set in acme
    N('globex:x0', 'globex', 'discourse'),                             // ANOTHER tenant
  ]
  const edges = [
    E('acme:p0', 'acme:c0', 'acme', 'discourse'),                      // premise -> claim
    E('arg:acme:c0', 'acme:c0', 'acme', 'discourse', 'claim', { reified_from: 'arg:acme:c0', member_role: 'claim' }),
    E('arg:acme:c0', 'acme:p0', 'acme', 'discourse', 'premise', { reified_from: 'arg:acme:c0', member_role: 'premise' }),
    E('globex:x0', 'globex:x0', 'globex', 'discourse'),                // globex-only edge
  ]
  const triples = [
    T('acme:c0', 'acme:p0'), T('globex:x0', 'globex:x0'),
    T('acme:c0', 'a literal', false),                                  // literal object (not a node)
  ]
  return { allNodes: () => nodes, allEdges: () => edges, triples: () => triples }
}

test('initTenant: off is passthrough with one WARN', () => {
  let warned = 0
  const s = initTenant({ TENANT_ENFORCE: 'off' }, () => { warned++ })
  assert.equal(s.enforce, false)
  assert.equal(warned, 1)
})

test('initTenant: on REQUIRES AUTH_ENFORCE=on (fail-closed startup)', () => {
  assert.throws(() => initTenant({ TENANT_ENFORCE: 'on', AUTH_ENFORCE: 'off' }, () => {}),
    /requires AUTH_ENFORCE=on/)
  assert.deepEqual(initTenant({ TENANT_ENFORCE: 'on', AUTH_ENFORCE: 'on' }, () => {}), { enforce: true, audit: false })
})

test('initTenant: audit is a safe dry-run — no AUTH requirement, enforces nothing', () => {
  let warned = 0
  // audit does NOT require AUTH_ENFORCE=on (it blocks nothing) — safe to enable anytime.
  const s = initTenant({ TENANT_ENFORCE: 'audit', AUTH_ENFORCE: 'off' }, () => { warned++ })
  assert.deepEqual(s, { enforce: false, audit: true })
  assert.equal(warned, 1)
})

test('audit mode COMPUTES would-be decisions (so the server can log them) but is not enforcing', () => {
  // THEOREM: under audit the gate functions still compute the denial/scope (tenantActive true), so a
  // dry run surfaces would-be breaks; the SERVER decides to log-not-block (tested in the integration).
  assert.equal(tenantActive(AUDIT), true)
  const noTenant = scopeForRead(AUDIT, { id: 'ops' }, new URL('http://x/api/graph/query'))
  assert.ok(noTenant && 'code' in noTenant && noTenant.body.reason === 'tenant_required')
  const cross = assertWriteTenant(AUDIT, { tenant: 'acme' }, { tenant_id: 'globex' })
  assert.ok(cross && cross.body.reason === 'cross_tenant_write')
  assert.ok(refuseUnscopable(AUDIT, '/api/graph/sparql'))  // would-refuse computed
})

test('tenantScope: a read sees ONLY its own tenant — cross-tenant is invisible', () => {
  const acme = tenantScope(fakeGraph(), 'acme')
  const ids = acme.allNodes().map((n) => n.id)
  assert.ok(ids.includes('acme:c0'))
  assert.ok(!ids.includes('globex:x0'), 'globex node must not surface for acme')
  // an induced edge/triple can never cross the boundary
  assert.ok(acme.allEdges().every((e) => !e.from.startsWith('globex') && !e.to.startsWith('globex')))
  assert.ok(acme.triples().every((t) => t.subject.startsWith('acme')))
  // and globex sees only globex
  const gl = tenantScope(fakeGraph(), 'globex')
  assert.deepEqual(gl.allNodes().map((n) => n.id), ['globex:x0'])
})

test('tenantScope: op_set scopes WITHIN a tenant, and a relation keeps its reified role-edges', () => {
  const disc = tenantScope(fakeGraph(), 'acme', 'discourse')
  const ids = disc.allNodes().map((n) => n.id)
  assert.ok(ids.includes('acme:c0') && ids.includes('arg:acme:c0'), 'discourse nodes present')
  assert.ok(!ids.includes('acme:ing0'), 'the ingest-op_set node is excluded from a discourse read')
  // THEOREM: the reified hyperedge role-edges carry op_set discourse, so an op_set-scoped edge read
  // still sees them (a role-edge that dropped op_set would vanish here — the exact #1400 regression).
  const roleEdges = disc.allEdges().filter((e) => e.properties['reified_from'] === 'arg:acme:c0')
  assert.equal(roleEdges.length, 2, 'both role-edges of the argument are visible in its op_set')
  // the other op_set is invisible
  assert.deepEqual(tenantScope(fakeGraph(), 'acme', 'ingest').allNodes().map((n) => n.id), ['acme:ing0'])
})

test('scopeForRead: passthrough off; deny no-tenant; deny unentitled op_set; else scope', () => {
  assert.equal(scopeForRead(OFF, { tenant: 'acme' }, new URL('http://x/api/graph/query')), null)
  const noTenant = scopeForRead(ENFORCING, { id: 'ops' }, new URL('http://x/api/graph/query'))
  assert.ok(noTenant && 'code' in noTenant && noTenant.body.reason === 'tenant_required')
  const forbidden = scopeForRead(ENFORCING, { tenant: 'acme', op_sets: ['discourse'] },
    new URL('http://x/api/graph/query?op_set=finance'))
  assert.ok(forbidden && 'code' in forbidden && forbidden.body.reason === 'op_set_forbidden')
  const ok = scopeForRead(ENFORCING, { tenant: 'acme', op_sets: ['discourse'] },
    new URL('http://x/api/graph/query?op_set=discourse'))
  assert.deepEqual(ok, { tenant: 'acme', opSet: 'discourse' })
})

test('assertWriteTenant: a write into another tenant (or unlabeled) is refused 403', () => {
  assert.equal(assertWriteTenant(OFF, { tenant: 'acme' }, { tenant_id: 'globex' }), null)  // off = passthrough
  const cross = assertWriteTenant(ENFORCING, { tenant: 'acme' }, { tenant_id: 'globex' })
  assert.ok(cross && cross.code === 403 && cross.body.reason === 'cross_tenant_write')
  const unlabeled = assertWriteTenant(ENFORCING, { tenant: 'acme' }, {})  // no tenant_id
  assert.ok(unlabeled && unlabeled.body.reason === 'cross_tenant_write')
  assert.equal(assertWriteTenant(ENFORCING, { tenant: 'acme' }, { tenant_id: 'acme' }), null)  // own tenant OK
})

test('refuseUnscopable: engine-internal endpoints are refused under enforcement, scopable ones pass', () => {
  for (const p of ['/api/graph/sparql', '/api/graph/cypher', '/api/graph/reason', '/api/graph/enrich']) {
    const d = refuseUnscopable(ENFORCING, p)
    assert.ok(d && d.code === 403 && d.body.reason === 'tenant_isolation_unavailable', `${p} must be refused`)
  }
  for (const p of ['/api/graph/query', '/api/graph/subgraph', '/api/graph/surface']) {
    assert.equal(refuseUnscopable(ENFORCING, p), null, `${p} is scopable, must not be refused`)
  }
  assert.equal(refuseUnscopable(OFF, '/api/graph/sparql'), null)  // off = nothing refused
})
