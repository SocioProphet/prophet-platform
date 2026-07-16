import { test, beforeEach, afterEach } from 'node:test'
import assert from 'node:assert/strict'
import { blendedSearch } from './gateway.ts'

const origFetch = globalThis.fetch
let webResp: () => Promise<Response>
let commonsResp: () => Promise<Response>

beforeEach(() => {
  webResp = async () => new Response(JSON.stringify({ results: [
    { title: 'Web A', url: 'https://a.example', content: 'web a', engine: 'duckduckgo' },
    { title: 'Shared', url: 'https://shared.example', content: 'web shared', engine: 'brave' },
  ] }), { status: 200 })
  commonsResp = async () => new Response(JSON.stringify({ results: [
    { title: 'Commons X', url: 'noetica://open-chat/u/1', content: 'commons x [EMAIL_1]', publishedDate: 'now' },
    { title: 'Shared', url: 'https://shared.example', content: 'commons shared', publishedDate: 'now' },
  ] }), { status: 200 })
  globalThis.fetch = (async (input: string | URL | Request) => {
    const u = String(input)
    if (u.includes('/api/open-chats/search')) return commonsResp()
    if (u.includes('/search?q=')) return webResp()
    return new Response('{}', { status: 404 })
  }) as typeof fetch
})
afterEach(() => { globalThis.fetch = origFetch })

test('blends commons + web, commons leads, deduped by url', async () => {
  const r = await blendedSearch('anything')
  assert.equal(r.counts.commons, 2)
  assert.equal(r.counts.web, 2)
  // commons leads
  assert.equal(r.results[0]!.source, 'commons')
  // "Shared" url appears once (commons wins the dedupe since it's first)
  const shared = r.results.filter((x) => x.url === 'https://shared.example')
  assert.equal(shared.length, 1)
  assert.equal(shared[0]!.source, 'commons')
  // 3 unique urls total (Commons X, Shared, Web A)
  assert.equal(r.results.length, 3)
})

test('commons results carry the redacted snippet (source tagging + safety)', async () => {
  const r = await blendedSearch('x')
  const c = r.results.find((x) => x.source === 'commons' && x.title === 'Commons X')!
  assert.ok(c.snippet.includes('[EMAIL_1]'))
  assert.equal(c.engine, 'noetica-commons')
})

test('graceful degradation: web down still returns commons + degraded note', async () => {
  webResp = async () => { throw new Error('searxng unreachable') }
  const r = await blendedSearch('x')
  assert.equal(r.counts.web, 0)
  assert.ok(r.counts.commons >= 1)
  assert.ok(r.degraded?.web)
  assert.equal(r.degraded?.commons, undefined)
})

test('graceful degradation: commons down still returns web', async () => {
  commonsResp = async () => new Response('boom', { status: 500 })
  const r = await blendedSearch('x')
  assert.ok(r.counts.web >= 1)
  assert.equal(r.counts.commons, 0)
  assert.ok(r.degraded?.commons)
})

test('empty query short-circuits', async () => {
  const r = await blendedSearch('   ')
  assert.equal(r.results.length, 0)
})
