/**
 * The audit chain: append-only, hash-chained, chunk-persisted, tamper-evident —
 * the properties the engine's InMemoryAuditLog (a shift()ing ring buffer) cannot give.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { GENESIS_PREV, HashChainedAudit, MemoryBlobStore, canonicalJson, entryHash, verifyEntries, type AuditEntry } from './audit.js'

test('canonicalJson is key-order independent at every depth', () => {
  const a = canonicalJson({ b: 1, a: { d: [1, { z: 0, y: 1 }], c: 2 } })
  const b = canonicalJson({ a: { c: 2, d: [1, { y: 1, z: 0 }] }, b: 1 })
  assert.equal(a, b)
})

test('chain appends link by prev-hash and verify passes end-to-end', async () => {
  const store = new MemoryBlobStore()
  const audit = new HashChainedAudit(store)
  audit.append({ kind: 'decision', objectId: 'a', effect: 'deny' })
  audit.append({ kind: 'transition', objectId: 'a', from: 'Served', to: 'Deleted' })
  const head1 = await audit.flush()
  audit.append({ kind: 'run', runId: 'r1' })
  const head2 = await audit.flush()
  assert.ok(head1 && head2)
  assert.equal(head2.seq, 2)
  const v = await audit.verify()
  assert.equal(v.ok, true)
  if (v.ok) { assert.equal(v.entries, 3); assert.equal(v.chunks, 2) } // chunks self-link across flushes
})

test('a restarted audit resumes the SAME chain (no fork, no reset)', async () => {
  const store = new MemoryBlobStore()
  const first = new HashChainedAudit(store)
  first.append({ kind: 'run', runId: 'r1' })
  const h1 = await first.flush()

  const second = new HashChainedAudit(store) // "restart"
  const resumed = await second.load()
  assert.deepEqual(resumed, h1)
  second.append({ kind: 'run', runId: 'r2' })
  const h2 = await second.flush()
  assert.equal(h2!.seq, h1!.seq + 1)
  const v = await second.verify()
  assert.equal(v.ok, true)
  if (v.ok) assert.equal(v.entries, 2)
})

test('tampering with a persisted entry is DETECTED with the seq where the chain broke', async () => {
  const store = new MemoryBlobStore()
  const audit = new HashChainedAudit(store)
  audit.append({ kind: 'transition', objectId: 'x', from: 'Served', to: 'Deleted' })
  audit.append({ kind: 'run', runId: 'r1' })
  await audit.flush()
  assert.equal((await audit.verify()).ok, true)

  // The attack the chain exists to catch: rewrite history — make the delete look like a hold.
  const chunkKey = store.keys().find((k) => k.startsWith('audit/chunk-'))!
  const chunk = JSON.parse((await store.get(chunkKey))!.toString('utf8'))
  chunk.entries[0].event = { kind: 'transition', objectId: 'x', from: 'Served', to: 'LegalHold' }
  await store.put(chunkKey, Buffer.from(JSON.stringify(chunk)))

  const v = await audit.verify()
  assert.equal(v.ok, false)
  if (!v.ok) assert.equal(v.atSeq, 1) // entry 1's prev no longer matches the doctored entry 0
})

test('truncating the head is detected (head must match the final entry)', () => {
  const e0: AuditEntry = { seq: 0, ts: 1, prev: GENESIS_PREV, event: { kind: 'a' } }
  const e1: AuditEntry = { seq: 1, ts: 2, prev: entryHash(e0), event: { kind: 'b' } }
  assert.equal(verifyEntries([e0, e1], { seq: 1, hash: entryHash(e1) }).ok, true)
  assert.equal(verifyEntries([e0], { seq: 1, hash: entryHash(e1) }).ok, false)
  assert.equal(verifyEntries([e0, e1], { seq: 1, hash: 'not-the-hash' }).ok, false)
})

test('flush failure keeps the tail pending — nothing is dropped', async () => {
  let fail = true
  const inner = new MemoryBlobStore()
  const flaky = {
    put: (k: string, b: Buffer) => fail ? Promise.reject(new Error('minio down')) : inner.put(k, b),
    get: (k: string) => inner.get(k),
  }
  const audit = new HashChainedAudit(flaky)
  audit.append({ kind: 'run', runId: 'r1' })
  await assert.rejects(audit.flush())
  assert.equal(audit.pendingCount(), 1) // still pending, not lost
  fail = false
  const head = await audit.flush()
  assert.equal(head!.seq, 0)
  assert.equal((await audit.verify()).ok, true)
})
