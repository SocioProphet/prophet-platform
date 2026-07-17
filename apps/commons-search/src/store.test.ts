import { test } from 'node:test'
import assert from 'node:assert/strict'
import { InMemoryStore, lexicalSearch, type RedactedOpenChat } from './store.ts'

const entry = (author: string, sessionId: string, title: string, redacted: string): RedactedOpenChat =>
  ({ author, sessionId, title, redacted, publishedAt: new Date().toISOString() })

test('memory store: put → search finds the redacted entry', async () => {
  const s = new InMemoryStore()
  await s.put(entry('alice', 's1', 'Paris trip', 'planning a trip to paris in spring'))
  const hits = await s.search('paris trip', 5)
  assert.equal(hits.length, 1)
  assert.equal(hits[0]!.author, 'alice')
  assert.ok(hits[0]!.snippet.includes('paris'))
})

test('revoke is author-scoped and immediate — the entry leaves search at once', async () => {
  const s = new InMemoryStore()
  await s.put(entry('alice', 's1', 'Secret plan', 'foobar widget launch'))
  assert.equal((await s.search('foobar', 5)).length, 1)
  const r = await s.revoke('alice', 's1')
  assert.equal(r.removed, true)
  assert.equal((await s.search('foobar', 5)).length, 0, 'revoked entry still searchable')
})

test('a different author CANNOT revoke another author\'s chat', async () => {
  const s = new InMemoryStore()
  await s.put(entry('alice', 's1', 'Alice chat', 'unique-token-xyz here'))
  const r = await s.revoke('mallory', 's1')     // same sessionId, different author
  assert.equal(r.removed, false, 'cross-author revoke succeeded')
  assert.equal((await s.search('unique-token-xyz', 5)).length, 1, 'alice\'s chat was wrongly removed')
})

test('re-publishing un-revokes (latest-wins)', async () => {
  const s = new InMemoryStore()
  await s.put(entry('alice', 's1', 'T', 'zebra content'))
  await s.revoke('alice', 's1')
  assert.equal((await s.search('zebra', 5)).length, 0)
  await s.put(entry('alice', 's1', 'T', 'zebra content again'))
  assert.equal((await s.search('zebra', 5)).length, 1, 're-publish did not restore searchability')
})

test('lexicalSearch ranks by term overlap and returns redacted snippets only', () => {
  const entries = [
    entry('a', '1', 'apples', 'apples apples oranges'),
    entry('a', '2', 'oranges', 'oranges only'),
  ]
  const hits = lexicalSearch(entries, 'apples', 5)
  assert.equal(hits[0]!.title, 'apples')
  assert.ok(hits[0]!.score >= 2)
})

test('proto-pollution author/sessionId cannot reach Object.prototype', async () => {
  const s = new InMemoryStore()
  await s.put(entry('__proto__', 'constructor', 'x', 'y'))
  assert.equal(({} as Record<string, unknown>)['polluted'], undefined)
  assert.equal((Object.prototype as Record<string, unknown>)['constructor'] === Object, true)
})

// ── semantic ranking (sovereign embeddings) ────────────────────────────────────
test('rankSearch: semantic ranking picks the nearest entry even with no shared words (fake endpoint)', async () => {
  const { rankSearch } = await import('./store.js')
  const entries = [
    { sessionId: 'a', author: 'x', title: 'feline pets', redacted: 'cats and kittens', publishedAt: 't' },
    { sessionId: 'b', author: 'x', title: 'stock market', redacted: 'equities and bonds', publishedAt: 't' },
  ]
  // fake embeddings: cat-ish text → [1,0]; finance → [0,1]. Query "automobile"? no — query "kitten" (semantic to cats)
  const fakeFetch = (async (_u: any, opts: any) => {
    const text = JSON.parse(opts.body).input as string
    const vec = /kitten|feline|cat|pet/i.test(text) ? [1, 0] : [0, 1]
    return { ok: true, json: async () => ({ data: [{ embedding: vec }] }) } as any
  }) as any
  process.env.EMBEDDINGS_URL = 'http://fake/embed'
  try {
    const hits = await rankSearch(entries, 'a small kitten', 5, fakeFetch)
    assert.equal(hits[0].sessionId, 'a', 'semantic match = the feline entry, not finance')
  } finally { delete process.env.EMBEDDINGS_URL }
})

test('rankSearch: falls back to lexical when no embeddings endpoint configured', async () => {
  const { rankSearch } = await import('./store.js')
  delete process.env.EMBEDDINGS_URL
  const entries = [
    { sessionId: 'a', author: 'x', title: 'quantum widgets', redacted: 'about quantum things', publishedAt: 't' },
    { sessionId: 'b', author: 'x', title: 'gardening', redacted: 'about plants', publishedAt: 't' },
  ]
  const hits = await rankSearch(entries, 'quantum', 5)
  assert.equal(hits.length, 1)
  assert.equal(hits[0].sessionId, 'a')
})
