import { test, before, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import { SocbaseStore } from './socbase.ts'

// A tiny in-memory PostgREST stand-in over fetch: records requests + serves a rows table.
interface Req { method: string; url: string; headers: Record<string, string>; body?: unknown }
let requests: Req[] = []
let rows: Array<Record<string, unknown>> = []
const origFetch = globalThis.fetch

before(() => {
  process.env['COMMONS_SOCBASE_URL'] = 'http://socbase.test/rest/v1'
  process.env['COMMONS_SOCBASE_TOKEN'] = 'test-token'
  globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
    const url = String(input)
    const method = init?.method ?? 'GET'
    const headers = (init?.headers ?? {}) as Record<string, string>
    const body = init?.body ? JSON.parse(String(init.body)) : undefined
    requests.push({ method, url, headers, body })
    // GET open_chats?revoked=eq.false → live rows
    if (method === 'GET' && url.includes('/open_chats') && url.includes('revoked=eq.false')) {
      return new Response(JSON.stringify(rows.filter((r) => r['revoked'] === false)), { status: 200, headers: { 'content-type': 'application/json' } })
    }
    if (method === 'GET' && url.includes('/open_chats')) return new Response('[]', { status: 200 })
    if (method === 'POST' && url.includes('/open_chats')) {
      const r = body as Record<string, unknown>
      rows = rows.filter((x) => !(x['author'] === r['author'] && x['session_id'] === r['session_id']))
      rows.push({ ...r })
      return new Response('', { status: 201 })
    }
    if (method === 'PATCH' && url.includes('/open_chats')) {
      const m = url.match(/author=eq\.([^&]+)&session_id=eq\.([^&]+)/)!
      const author = decodeURIComponent(m[1]!); const sid = decodeURIComponent(m[2]!)
      const hit = rows.filter((x) => x['author'] === author && x['session_id'] === sid)
      hit.forEach((x) => { x['revoked'] = true })
      return new Response(JSON.stringify(hit), { status: 200, headers: { 'content-type': 'application/json' } })
    }
    return new Response('', { status: 404 })
  }) as typeof fetch
})
beforeEach(() => { requests = []; rows = [] })

test('put issues an upsert (merge-duplicates) with revoked=false', async () => {
  const s = await SocbaseStore.create()
  await s.put({ author: 'alice', sessionId: 's1', title: 'T', redacted: 'hello world', publishedAt: 'now' })
  const post = requests.find((r) => r.method === 'POST')!
  assert.ok(post, 'no POST issued')
  assert.match(post.headers['Prefer'] ?? '', /merge-duplicates/)
  assert.equal((post.body as Record<string, unknown>)['revoked'], false)
})

test('search only sees revoked=false rows; a revoked chat disappears', async () => {
  const s = await SocbaseStore.create()
  await s.put({ author: 'alice', sessionId: 's1', title: 'Paris', redacted: 'paris trip notes', publishedAt: 'now' })
  assert.equal((await s.search('paris', 5)).length, 1)
  const r = await s.revoke('alice', 's1')
  assert.equal(r.removed, true)
  assert.equal((await s.search('paris', 5)).length, 0, 'revoked row still searchable')
})

test('revoke is author-scoped in the query (author=eq + session_id=eq)', async () => {
  const s = await SocbaseStore.create()
  await s.revoke('alice', 's1')
  const patch = requests.find((r) => r.method === 'PATCH')!
  assert.match(patch.url, /author=eq\.alice/)
  assert.match(patch.url, /session_id=eq\.s1/)
})

// restore
test('teardown', () => { globalThis.fetch = origFetch })
