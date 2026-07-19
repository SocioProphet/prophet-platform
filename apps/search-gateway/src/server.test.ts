import { test, before, after, beforeEach, afterEach } from 'node:test'
import assert from 'node:assert/strict'
import type { AddressInfo } from 'node:net'
import { makeServer } from './server.ts'

const origFetch = globalThis.fetch
let base: string
let server: ReturnType<typeof makeServer>

before(async () => {
  process.env['SEARCH_CORS_ORIGINS'] = 'https://socioprophet.ai'
  server = makeServer()
  await new Promise<void>((r) => server.listen(0, r))
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`
})
after(() => server.close())

beforeEach(() => {
  // Intercept ONLY the upstream engine calls (searxng / commons-search hosts). The test's own requests to `base`
  // (127.0.0.1) must fall through to the REAL fetch so they actually hit the gateway under test.
  globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
    const u = String(input)
    if (u.includes('commons-search')) return new Response(JSON.stringify({ results: [{ title: 'C', url: 'noetica://x', content: 'c' }] }), { status: 200 })
    if (u.includes('searxng')) return new Response(JSON.stringify({ results: [{ title: 'W', url: 'https://w.example', content: 'w', engine: 'ddg' }] }), { status: 200 })
    if (u.includes('sherlock-engine')) return new Response(JSON.stringify({ hits: [] }), { status: 200 })
    return origFetch(input as never, init)   // the test → gateway requests
  }) as typeof fetch
})
afterEach(() => { globalThis.fetch = origFetch })

test('healthz', async () => {
  const r = await fetch(`${base}/healthz`)
  assert.equal(r.status, 200)
  assert.equal((await r.json()).ok, true)
})

test('search blends web + commons', async () => {
  const r = await fetch(`${base}/search?q=hello`)
  const b = await r.json()
  assert.equal(r.status, 200)
  assert.equal(b.results.length, 2)
  assert.deepEqual(b.counts, { web: 1, commons: 1, corpus: 0 })
})

test('CORS: allowed origin is echoed', async () => {
  const r = await fetch(`${base}/search?q=x`, { headers: { origin: 'https://socioprophet.ai' } })
  assert.equal(r.headers.get('access-control-allow-origin'), 'https://socioprophet.ai')
})

test('CORS: disallowed origin gets no allow header', async () => {
  const r = await fetch(`${base}/search?q=x`, { headers: { origin: 'https://evil.example' } })
  assert.equal(r.headers.get('access-control-allow-origin'), null)
})

test('OPTIONS preflight returns 204 with CORS for allowed origin', async () => {
  const r = await fetch(`${base}/search`, { method: 'OPTIONS', headers: { origin: 'https://socioprophet.ai' } })
  assert.equal(r.status, 204)
  assert.equal(r.headers.get('access-control-allow-methods'), 'GET, OPTIONS')
})

test('no write routes — POST /search is 404', async () => {
  const r = await fetch(`${base}/search`, { method: 'POST' })
  assert.equal(r.status, 404)
})
