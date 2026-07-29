/**
 * The executor over the engine's L5 machinery: FSM transitions actually executed via
 * Governor, dry-run vs enforce, structural legal-hold undeletability, vendor-cache
 * materialize + gc — the behaviors the blueprint audit found existed only as libraries.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { TRANSITIONS, canTransition, type VendorFilesClient } from '@socioprophet/hellgraph'
import { MemoryBlobStore } from './audit.js'
import { Warden } from './warden.js'

const META = { mime: 'text/plain', residency: 'sovereign' }

test('FSM executed via Governor: ingest → extract → index → serve, every step audited on the chain', async () => {
  const w = new Warden({ dryRun: true, blobs: new MemoryBlobStore() })
  await w.load()
  const { object } = await w.ingest('doc-1', 'hello estate', META)
  assert.equal(object.state, 'Normalized') // CanonicalObjectStore ingests at Normalized
  assert.equal((await w.advance('doc-1', 'extract')).state, 'Extracted')
  assert.equal((await w.advance('doc-1', 'index')).state, 'Indexed')
  assert.equal((await w.advance('doc-1', 'serve')).state, 'Served')
  // an illegal trigger is BLOCKED (audited), not applied and not an exception
  assert.equal((await w.advance('doc-1', 'normalize')).state, 'Served')
  const v = await w.audit.verify()
  assert.equal(v.ok, true)
  if (v.ok) assert.ok(v.entries >= 5, `expected ≥5 chained audit entries, got ${v.entries}`)
})

test('retention DRY-RUN plans + audits but mutates NOTHING; ENFORCE applies the same transitions', async () => {
  const past = Date.now() - 60_000

  const dry = new Warden({ dryRun: true, blobs: new MemoryBlobStore() })
  await dry.load()
  await dry.ingest('exp-1', 'expiring', { ...META, retentionDeleteAt: past })
  const dryReport = await dry.runOnce()
  assert.equal(dryReport.dryRun, true)
  assert.equal(dryReport.dueCount, 1)
  assert.deepEqual(dryReport.dueByTrigger, { retention_delete: 1 })
  assert.equal(dryReport.applied.length, 0)
  assert.equal(dryReport.planned.length, 1)
  assert.equal(dryReport.planned[0]!.wouldApply, true)
  assert.equal(dry.object('exp-1')!.state, 'Normalized') // untouched — that is the point of dry-run

  const enforce = new Warden({ dryRun: false, blobs: new MemoryBlobStore() })
  await enforce.load()
  await enforce.ingest('exp-1', 'expiring', { ...META, retentionDeleteAt: past })
  const report = await enforce.runOnce()
  assert.equal(report.dryRun, false)
  assert.equal(report.applied.length, 1)
  assert.deepEqual(report.applied[0], { objectId: 'exp-1', from: 'Normalized', to: 'Deleted', trigger: 'retention_delete' })
  assert.equal(enforce.object('exp-1')!.state, 'Deleted')
  // Deleted is terminal: a second pass finds nothing due
  const again = await enforce.runOnce()
  assert.equal(again.dueCount, 0)
})

test('LEGAL HOLD is structurally undeletable — model, guard, and Governor all refuse', async () => {
  // 1. Structural: the LegalHold state has NO retention_delete edge at all.
  const holdEdges = TRANSITIONS.LegalHold.map((e) => e.trigger)
  assert.ok(!holdEdges.includes('retention_delete'), 'LegalHold must have no retention-delete edge')
  assert.deepEqual(holdEdges.sort(), ['delete_after_release', 'hold_release'])
  // 2. Guard: even asking is a no.
  assert.equal(canTransition({ id: 'h', state: 'LegalHold', retentionDeleteAt: 1 }, 'retention_delete'), false)

  // 3. Executed: an ENFORCING warden cannot delete a held object.
  const w = new Warden({ dryRun: false, blobs: new MemoryBlobStore() })
  await w.load()
  await w.ingest('held-1', 'litigation evidence', { ...META, retentionDeleteAt: Date.now() - 1000 })
  await w.advance('held-1', 'extract')
  await w.advance('held-1', 'index')
  await w.advance('held-1', 'serve')
  await w.hold('held-1')
  assert.equal(w.object('held-1')!.state, 'LegalHold')

  const report = await w.runOnce()
  assert.equal(report.applied.length, 0) // retention ran, the hold held
  assert.equal(w.object('held-1')!.state, 'LegalHold')

  // even a direct delete trigger through the Governor is blocked by the delete-gate
  await w.advance('held-1', 'delete_after_release')
  assert.equal(w.object('held-1')!.state, 'LegalHold')

  // 4. The ONLY ways out are release → Served, or delete AFTER release (guarded on holdReleased).
  await w.releaseHold('held-1')
  assert.equal(w.object('held-1')!.state, 'Served')
  const v = await w.audit.verify()
  assert.equal(v.ok, true)
})

test('dry-run reports that a due delete WOULD BE BLOCKED by legal hold (honest plan)', async () => {
  const w = new Warden({ dryRun: true, blobs: new MemoryBlobStore() })
  await w.load()
  // A held object whose FSM state still has a retention edge exercises the policy gate:
  // dueTransitions sees retentionDeleteAt, but the delete decision denies while held.
  await w.ingest('held-2', 'x', { ...META, retentionDeleteAt: Date.now() - 1000 })
  w.object('held-2')!.legalHold = true
  const report = await w.runOnce()
  assert.equal(report.planned.length, 1)
  assert.equal(report.planned[0]!.wouldApply, false)
  assert.match(report.planned[0]!.reason ?? '', /hold/i)
  assert.equal(w.object('held-2')!.state, 'Normalized')
})

test('vendor cache: opt-in materialize egresses, gc reaps expired handles (enforce) / counts them (dry-run)', async () => {
  const uploads: string[] = []
  const deletes: string[] = []
  const fakeVendor: VendorFilesClient = {
    uploadFile: async (content: string) => { uploads.push(content); return `file-${uploads.length}` },
    deleteFile: async (fileId: string) => { deletes.push(fileId) },
  }

  const w = new Warden({ dryRun: false, blobs: new MemoryBlobStore(), vendorClients: { gemini: fakeVendor } })
  await w.load()
  await w.ingest('doc-v', 'sensitive payload', { ...META, vendorOptIn: true })
  await w.advance('doc-v', 'extract')
  await w.advance('doc-v', 'index')
  await w.advance('doc-v', 'serve')

  // egress WITHOUT opt-in is denied by the policy engine (default-deny non-negotiable)
  const denied = await w.materialize('doc-v', 'gemini', { optIn: false, ttlMs: 50 })
  assert.equal(denied.ok, false)
  assert.equal(uploads.length, 0)

  const okRes = await w.materialize('doc-v', 'gemini', { optIn: true, ttlMs: 50 })
  assert.equal(okRes.ok, true)
  assert.equal(uploads.length, 1)
  assert.equal(w.object('doc-v')!.state, 'VendorMaterialized')

  // expire the handle, then gc through runOnce (the scheduler path)
  await new Promise((r) => setTimeout(r, 60))
  const report = await w.runOnce()
  assert.equal(report.gcCount, 1)
  assert.equal(deletes.length, 1) // the vendor copy was actually deleted
  assert.equal(w.object('doc-v')!.state, 'ExpiredVendorCache') // re-materializable from canonical

  // dry-run variant: counts the expired candidate, deletes nothing
  const dry = new Warden({ dryRun: true, blobs: new MemoryBlobStore(), vendorClients: { gemini: fakeVendor } })
  await dry.load()
  await dry.ingest('doc-w', 'y', { ...META, vendorOptIn: true })
  await dry.advance('doc-w', 'extract'); await dry.advance('doc-w', 'index'); await dry.advance('doc-w', 'serve')
  await dry.materialize('doc-w', 'gemini', { optIn: true, ttlMs: 1 })
  await new Promise((r) => setTimeout(r, 10))
  const deletesBefore = deletes.length
  const dryReport = await dry.runOnce()
  assert.equal(dryReport.gcCount, 1)
  assert.equal(deletes.length, deletesBefore) // nothing reaped in dry-run
  assert.equal(dry.object('doc-w')!.state, 'VendorMaterialized')
})

test('governed registry survives restart (state persisted to the blob store)', async () => {
  const blobs = new MemoryBlobStore()
  const w1 = new Warden({ dryRun: true, blobs })
  await w1.load()
  await w1.ingest('p-1', 'persist me', { ...META, retentionDeleteAt: 123 })
  await w1.advance('p-1', 'extract')

  const w2 = new Warden({ dryRun: true, blobs }) // "restart"
  await w2.load()
  const restored = w2.object('p-1')
  assert.ok(restored)
  assert.equal(restored.state, 'Extracted')
  assert.equal(restored.retentionDeleteAt, 123)
  // and the audit chain continues rather than restarting
  w2.audit.append({ kind: 'run', runId: 'after-restart' })
  await w2.audit.flush()
  assert.equal((await w2.audit.verify()).ok, true)
})
