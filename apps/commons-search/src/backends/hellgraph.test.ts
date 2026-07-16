import { test, before } from 'node:test'
import assert from 'node:assert/strict'
import * as fs from 'node:fs'
import * as os from 'node:os'
import * as path from 'node:path'
import { HellgraphStore } from './hellgraph.ts'
import type { RedactedOpenChat } from '../store.ts'

let dir: string
before(() => {
  dir = fs.mkdtempSync(path.join(os.tmpdir(), 'commons-hg-'))
  process.env['COMMONS_HELLGRAPH_OUTBOX'] = path.join(dir, 'delta.jsonl')
  process.env['COMMONS_HELLGRAPH_VIEW'] = path.join(dir, 'view.jsonl')
})

const entry = (author: string, sessionId: string, redacted: string): RedactedOpenChat =>
  ({ author, sessionId, title: 't', redacted, publishedAt: new Date().toISOString() })

test('put emits the sovereign UPSERT delta to the outbox AND serves read-after-write search', async () => {
  const s = await HellgraphStore.create()
  await s.put(entry('alice', 's1', 'quantum widgets are neat'))
  const outbox = fs.readFileSync(process.env['COMMONS_HELLGRAPH_OUTBOX']!, 'utf8')
  assert.match(outbox, /"op":"UPSERT_OPEN_CHAT"/)
  assert.match(outbox, /"author":"alice"/)
  const hits = await s.search('quantum widgets', 5)
  assert.equal(hits.length, 1)
})

test('revoke emits a tombstone delta and drops the entry from search immediately', async () => {
  const s = await HellgraphStore.create()
  await s.put(entry('bob', 's2', 'gamma ray burst notes'))
  assert.equal((await s.search('gamma', 5)).length, 1)
  await s.revoke('bob', 's2')
  const outbox = fs.readFileSync(process.env['COMMONS_HELLGRAPH_OUTBOX']!, 'utf8')
  assert.match(outbox, /"op":"REVOKE_OPEN_CHAT"/)
  assert.equal((await s.search('gamma', 5)).length, 0)
})

test('a fresh store hydrates the materialized view from the log (survives restart)', async () => {
  const s1 = await HellgraphStore.create()
  await s1.put(entry('carol', 's3', 'persisted delta content'))
  // new instance reading the same view file
  const s2 = await HellgraphStore.create()
  assert.equal((await s2.search('persisted', 5)).length, 1, 'view did not rebuild from the log')
})
