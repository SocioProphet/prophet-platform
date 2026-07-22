/**
 * The org super-peer membership loop (opt-in-once → percolate-forever), through the
 * SERVICE surface: fail-closed governance, scoped admission, and a real participant
 * whose local write replicates into the org index. Skips when autobase/corestore
 * (engine optional deps) are absent — same convention as the engine's own tests.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import * as fs from 'node:fs'
import * as os from 'node:os'
import * as path from 'node:path'
import type * as http from 'node:http'
import { FederatedAtomSpace, HmacTokenVerifier, nodeHandle, type AtomLogEntry } from '@socioprophet/hellgraph'
import { startFederation, handleFederation, type Federation } from './federation.js'

process.env['FEDERATION_SWARM'] = '0'   // no DHT in tests — direct replication streams only

const tmp = (): string => fs.mkdtempSync(path.join(os.tmpdir(), 'hgs-fed-'))
const wait = (ms: number): Promise<void> => new Promise((r) => setTimeout(r, ms))

async function federationAvailable(): Promise<boolean> {
  // non-literal specifiers: these are the engine's OPTIONAL deps — no type declarations exist
  try { await import('autobase' as string); await import('corestore' as string); return true } catch { return false }
}

/** Drive handleFederation with plain objects — the routes never touch the socket beyond
 *  headers/writeHead/end, so a stub keeps the test at the unit seam the server uses. */
function call(fed: Federation | null, method: string, pathName: string, body = '', authorization = ''):
  Promise<{ code: number; body: Record<string, unknown> }> {
  return new Promise((resolve) => {
    const req = { method, headers: { authorization } } as unknown as http.IncomingMessage
    let code = 0
    const res = {
      writeHead: (c: number) => { code = c },
      end: (payload: string) => resolve({ code, body: JSON.parse(payload) as Record<string, unknown> }),
    } as unknown as http.ServerResponse
    const handled = handleFederation(fed, req, res, new URL(`http://x${pathName}`), body)
    if (!handled) resolve({ code: -1, body: {} })
  })
}

test('federation is fail-closed: no secret → stays off; disabled → honest status', async () => {
  delete process.env['FEDERATION_ENABLED']
  assert.equal(await startFederation(), null)

  process.env['FEDERATION_ENABLED'] = '1'
  delete process.env['FEDERATION_HMAC_SECRET']
  assert.equal(await startFederation(), null)          // enabled but ungoverned → refuses

  const status = await call(null, 'GET', '/api/federation/status')
  assert.deepEqual(status.body, { enabled: false })
  const admit = await call(null, 'POST', '/api/federation/admit', '{}')
  assert.equal(admit.code, 503)
})

test('opt-in once: scoped admit → participant becomes writable → local write percolates to the org index', async (t) => {
  if (!(await federationAvailable())) return t.skip('autobase/corestore not installed')

  process.env['FEDERATION_ENABLED'] = '1'
  process.env['FEDERATION_HMAC_SECRET'] = 'org-secret'
  process.env['FEDERATION_DIR'] = tmp()
  const fed = await startFederation()
  assert.ok(fed, 'super-peer starts when governed')
  assert.equal(fed.sp.authEnforced, true)

  // status is open and carries what a cockpit needs
  const status = await call(fed, 'GET', '/api/federation/status')
  assert.equal(status.body['enabled'], true)
  assert.match(String(status.body['baseKey']), /^[0-9a-f]{64}$/i)

  // a sovereign participant joins from the base key — NOT writable until admitted
  const participant = await FederatedAtomSpace.create(tmp(), { bootstrap: fed.sp.baseKey() })
  const s1 = fed.sp.replicate(true) as { pipe: (x: unknown) => { pipe: (y: unknown) => void }; destroy?: () => void }
  const s2 = participant.replicate(false) as { pipe: (x: unknown) => void }
  ;(s1.pipe(s2) as { pipe: (y: unknown) => void }).pipe(s1)
  await wait(200)

  // governance: no token → 401; wrong scope → 401; bad key shape → 400
  assert.equal((await call(fed, 'POST', '/api/federation/admit', '{"writerKey":"ab"}')).code, 401)
  const readOnly = fed.verifier.mint({ id: 'reader', scopes: ['read'] })
  assert.equal((await call(fed, 'POST', '/api/federation/admit', '{}', `Bearer ${readOnly}`)).code, 401)
  const admin = fed.verifier.mint({ id: 'michael', scopes: ['admit'] })
  assert.equal((await call(fed, 'POST', '/api/federation/admit', '{"writerKey":"zz"}', `Bearer ${admin}`)).code, 400)

  // THE opt-in: admit the participant's writer key
  const admitted = await call(fed, 'POST', '/api/federation/admit',
    JSON.stringify({ writerKey: participant.localWriterKey() }), `Bearer ${admin}`)
  assert.equal(admitted.code, 200)
  assert.equal(admitted.body['by'], 'michael')

  await wait(300)
  await participant.update()
  assert.equal(participant.isWritable(), true, 'participant becomes writable after admission syncs')

  // seamless from here: a LOCAL write percolates into the ORG materialized view
  const entry: AtomLogEntry = { seq: 1, ts: new Date().toISOString(), op: 'add_atom',
    payload: { handle: nodeHandle('ConceptNode', 'YaYingLocalFact'), type: 'ConceptNode', name: 'YaYingLocalFact' } }
  await participant.appendEntry(entry)

  // replication + linearization are eventually-consistent — poll health (the engine's own
  // truth signal: indexed node count + the causal cut over the participant's writer key)
  let health = await fed.sp.health()
  for (let i = 0; i < 30 && health.nodes < 1; i++) {
    await wait(200)
    health = await fed.sp.health()
  }
  assert.ok(health.nodes >= 1, 'the local fact percolates into the org index')
  assert.equal((health.cut as Record<string, number>)[participant.localWriterKey()], 1,
    'causal cut records the participant op — provenance of WHO contributed WHAT')

  await fed.sp.close()
})
