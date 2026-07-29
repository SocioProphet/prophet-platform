/**
 * auth unit tests — the scope table, the allow/deny matrix, and the fail-closed init.
 * Pure module tests (no HTTP server); the wired end-to-end behavior is covered by
 * auth.integration.test.ts.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import type * as http from 'node:http'
import { initAuth, authorize, requiredScope, mintGraphToken, type AuthState, type GraphScope } from './auth.js'

const SECRET = 'unit-test-secret'

function req(method: string, token?: string): http.IncomingMessage {
  return { method, headers: token ? { authorization: `Bearer ${token}` } : {} } as unknown as http.IncomingMessage
}
const at = (p: string): URL => new URL(`http://localhost${p}`)
const tok = (scopes: GraphScope[], extra?: { exp?: number }): string =>
  mintGraphToken(SECRET, { id: 'unit', scopes, ...extra })

function enforcing(): AuthState {
  return initAuth({ AUTH_ENFORCE: 'on', AUTH_HMAC_SECRET: SECRET } as NodeJS.ProcessEnv, () => {})
}

test('initAuth: off (default) = passthrough with exactly one WARN', () => {
  const warns: string[] = []
  const s = initAuth({} as NodeJS.ProcessEnv, (m) => warns.push(m))
  assert.equal(s.enforce, false)
  assert.equal(warns.length, 1)
  assert.match(warns[0]!, /AUTH_ENFORCE=off/)
  // passthrough: even a write route with no token proceeds
  assert.equal(authorize(s, req('POST'), at('/api/graph/node')), null)
})

test('initAuth: enforce-on without AUTH_HMAC_SECRET throws (fail-closed)', () => {
  assert.throws(() => initAuth({ AUTH_ENFORCE: 'on' } as NodeJS.ProcessEnv, () => {}), /AUTH_HMAC_SECRET.*fail-closed/s)
})

test('initAuth: enforce-on with secret enforces and does NOT emit the off-WARN', () => {
  const warns: string[] = []
  const s = initAuth({ AUTH_ENFORCE: 'on', AUTH_HMAC_SECRET: SECRET } as NodeJS.ProcessEnv, (m) => warns.push(m))
  assert.equal(s.enforce, true)
  assert.deepEqual(warns, [])
})

test('requiredScope: the route table maps every surface to its scope', () => {
  // reads (the task-named four + the rest of the read surface)
  for (const p of ['explore', 'kko', 'log', 'analytics', 'stats', 'query', 'subgraph', 'surface', 'resource', 'ground']) {
    assert.equal(requiredScope('GET', `/api/graph/${p}`), 'graph:read', `GET ${p}`)
  }
  for (const p of ['ask', 'sparql', 'gremlin', 'cypher', 'shacl']) {
    assert.equal(requiredScope('POST', `/api/graph/${p}`), 'graph:read', `POST ${p}`)
  }
  // writes
  assert.equal(requiredScope('POST', '/api/graph/node'), 'graph:write')
  assert.equal(requiredScope('POST', '/api/graph/edge'), 'graph:write')
  assert.equal(requiredScope('POST', '/api/graph/reason'), 'graph:write')
  assert.equal(requiredScope('POST', '/api/membrane/decide'), 'graph:write')
  // enrichment
  assert.equal(requiredScope('GET', '/api/graph/enrich'), 'graph:enrich')
  // unmapped under the gated prefixes: fail-closed by verb
  assert.equal(requiredScope('GET', '/api/graph/future-route'), 'graph:read')
  assert.equal(requiredScope('POST', '/api/graph/future-route'), 'graph:write')
  assert.equal(requiredScope('DELETE', '/api/membrane/future'), 'graph:write')
  // not gated by this module
  assert.equal(requiredScope('GET', '/healthz'), null)
  assert.equal(requiredScope('GET', '/api/federation/status'), null)
  assert.equal(requiredScope('POST', '/api/federation/admit'), null)
})

test('authorize: each scope allows its routes and denies the others', () => {
  const s = enforcing()
  const matrix: Array<[string, string, GraphScope]> = [
    ['GET', '/api/graph/explore', 'graph:read'],
    ['GET', '/api/graph/kko', 'graph:read'],
    ['GET', '/api/graph/log', 'graph:read'],
    ['GET', '/api/graph/analytics', 'graph:read'],
    ['POST', '/api/graph/node', 'graph:write'],
    ['POST', '/api/graph/edge', 'graph:write'],
    ['POST', '/api/membrane/decide', 'graph:write'],
    ['GET', '/api/graph/enrich', 'graph:enrich'],
  ]
  const all: GraphScope[] = ['graph:read', 'graph:write', 'graph:enrich']
  for (const [method, path, needed] of matrix) {
    // the right scope passes
    assert.equal(authorize(s, req(method, tok([needed])), at(path)), null, `${method} ${path} with ${needed}`)
    // every other scope is denied with a typed 403
    for (const wrong of all.filter((x) => x !== needed)) {
      const d = authorize(s, req(method, tok([wrong])), at(path))
      assert.ok(d, `${method} ${path} with ${wrong} must deny`)
      assert.equal(d.code, 403)
      assert.equal(d.body.reason, 'missing_scope')
      assert.equal(d.body.requiredScope, needed)
    }
  }
})

test('authorize: missing / invalid / wrong-secret / expired tokens are 401', () => {
  const s = enforcing()
  const missing = authorize(s, req('GET'), at('/api/graph/stats'))
  assert.equal(missing?.code, 401)
  assert.equal(missing?.body.reason, 'missing_token')

  const garbage = authorize(s, req('GET', 'not-a-token'), at('/api/graph/stats'))
  assert.equal(garbage?.code, 401)
  assert.equal(garbage?.body.reason, 'invalid_token')

  const wrongSecret = mintGraphToken('some-other-secret', { id: 'x', scopes: ['graph:read'] })
  assert.equal(authorize(s, req('GET', wrongSecret), at('/api/graph/stats'))?.body.reason, 'invalid_token')

  const expired = tok(['graph:read'], { exp: Date.now() - 60_000 })
  assert.equal(authorize(s, req('GET', expired), at('/api/graph/stats'))?.body.reason, 'invalid_token')
})

test('authorize: multi-scope tokens work; ungated paths never challenge', () => {
  const s = enforcing()
  const t = tok(['graph:read', 'graph:write', 'graph:enrich'])
  assert.equal(authorize(s, req('GET', t), at('/api/graph/stats')), null)
  assert.equal(authorize(s, req('POST', t), at('/api/graph/node')), null)
  assert.equal(authorize(s, req('GET', t), at('/api/graph/enrich')), null)
  // ungated: healthz + federation pass with no token even under enforcement
  assert.equal(authorize(s, req('GET'), at('/healthz')), null)
  assert.equal(authorize(s, req('GET'), at('/api/federation/status')), null)
})

test('requiredScope: /api/organs is gated — it discloses topology and triggers probing', () => {
  // It sat outside /api/graph/ and /api/membrane/, so it answered unauthenticated even
  // with AUTH_ENFORCE=on. The endpoint returns internal service endpoints with live
  // health AND makes the server probe those members, so an anonymous caller both reads
  // the mesh's shape and gets the service to emit outbound requests for them.
  assert.equal(requiredScope('GET', '/api/organs'), 'graph:read')
  assert.equal(requiredScope('HEAD', '/api/organs'), 'graph:read')
  assert.equal(requiredScope('POST', '/api/organs'), 'graph:write')
  // a genuine subpath is gated too
  assert.equal(requiredScope('GET', '/api/organs/memory'), 'graph:read')
  // ...but a sibling that merely shares the prefix string is NOT silently captured
  assert.equal(requiredScope('GET', '/api/organs-public'), null)
  assert.equal(requiredScope('GET', '/api/organsomething'), null)
})

test('authorize: /api/organs refuses without a token under enforcement', () => {
  const s = enforcing()
  const denied = authorize(s, req('GET'), at('/api/organs'))
  assert.ok(denied, 'unauthenticated /api/organs must be refused when enforcing')
  assert.equal(denied!.code, 401)
  assert.equal((denied!.body as any).requiredScope, 'graph:read')
  // and proceeds with a scoped token
  assert.equal(authorize(s, req('GET', tok(['graph:read'])), at('/api/organs')), null)
  // a token without the scope is forbidden, not merely unauthorized
  const wrong = authorize(s, req('GET', tok(['graph:enrich'])), at('/api/organs'))
  assert.equal(wrong!.code, 403)
})
