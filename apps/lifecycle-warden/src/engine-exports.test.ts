/**
 * Vendored-engine contract: the exact machinery this service exists to run —
 * lifecycle.ts, policy.ts, object-store.ts, vendor-cache.ts — must be exported by
 * the vendored @socioprophet/hellgraph tarball. If a future re-vendor drops or
 * renames any of it, this fails before anything ships.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import * as engine from '@socioprophet/hellgraph'

test('lifecycle.ts surface: 10-state FSM + TRANSITIONS + guards', () => {
  assert.equal(typeof engine.TRANSITIONS, 'object')
  const states = Object.keys(engine.TRANSITIONS)
  for (const s of ['IngestedRaw', 'Normalized', 'Extracted', 'Indexed', 'Served',
    'VendorMaterialized', 'ExpiredVendorCache', 'FlaggedRetention', 'LegalHold', 'Deleted']) {
    assert.ok(states.includes(s), `FSM state missing: ${s}`)
  }
  assert.equal(states.length, 10)
  assert.equal(typeof engine.edgeFor, 'function')
  assert.equal(typeof engine.canTransition, 'function')
  assert.equal(typeof engine.applyTransition, 'function')
  assert.deepEqual(engine.validateModel(), { ok: true })
  assert.deepEqual([...engine.DELETE_TRIGGERS].sort(), ['delete_after_release', 'retention_delete', 'window_ends'])
})

test('policy.ts surface: decide + dueTransitions + Governor', () => {
  assert.equal(typeof engine.decide, 'function')
  assert.equal(typeof engine.dueTransitions, 'function')
  assert.equal(typeof engine.Governor, 'function')
  const g = new engine.Governor()
  assert.equal(typeof g.decide, 'function')
  assert.equal(typeof g.transition, 'function')
  assert.equal(typeof g.runRetention, 'function')
})

test('object-store.ts surface: CanonicalObjectStore + the BYOS S3 seam', () => {
  assert.equal(typeof engine.CanonicalObjectStore, 'function')
  assert.equal(typeof engine.InMemoryObjectBackend, 'function')
  assert.equal(typeof engine.S3ObjectBackend, 'function')
  const store = new engine.CanonicalObjectStore()
  for (const m of ['ingest', 'entry', 'get', 'verify', 'newVersion', 'setState', 'provenanceOf', 'toPolicyObject']) {
    assert.equal(typeof (store as unknown as Record<string, unknown>)[m], 'function', `CanonicalObjectStore.${m}`)
  }
})

test('vendor-cache.ts surface: VendorCacheManager materialize/gc', () => {
  assert.equal(typeof engine.VendorCacheManager, 'function')
  const store = new engine.CanonicalObjectStore()
  const mgr = new engine.VendorCacheManager(store, new engine.Governor(), engine.StaticKeyProvider.fromPassphrase('t'), {})
  assert.equal(typeof mgr.materialize, 'function')
  assert.equal(typeof mgr.rematerialize, 'function')
  assert.equal(typeof mgr.gc, 'function')
  assert.equal(typeof mgr.handle, 'function')
})
