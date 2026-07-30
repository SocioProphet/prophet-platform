/**
 * Tests for the bounded consult ledger (#942).
 *
 * The failure this pins: openConsult() had no size cap. An attacker (or a
 * benign integration that spins up consults in a loop) grew the in-memory
 * Map without ceiling — a slow-burn DoS that a running twin cannot recover
 * from without a restart. Fix caps the store and fails-closed on overflow
 * so the failure mode is a visible refusal rather than an OOM crash.
 *
 * We reload the module per test so CONSULT_MAX can be overridden via env
 * without racing other tests; the ledger is module-scoped state.
 */
import test from 'node:test';
import assert from 'node:assert/strict';

async function freshModule(env: Record<string, string> = {}) {
  for (const [k, v] of Object.entries(env)) process.env[k] = v;
  // Bust the ESM cache by appending a unique query to the specifier.
  const suffix = Math.random().toString(36).slice(2);
  return await import(`./consult.js?fresh=${suffix}`);
}

function agree(m: typeof import('./consult.js'), n: number) {
  // NB: openConsult mints id from sha256([pseudonym, scope, `${Date.now()}-${scope}`]).
  // Two calls in the same millisecond with the same scope collide on id and one
  // silently overwrites the other in the Map. That is a preexisting bug in the
  // codebase (see PR body — separate follow-up). We pass a unique scope per call
  // here so the cap test measures the cap and not the collision.
  const opened: string[] = [];
  for (let i = 0; i < n; i++) {
    const r = m.openConsult({ patient: `p${i}` }, `scope-${i}`, 'standard', true);
    if (r.consult_id) opened.push(r.consult_id);
  }
  return opened;
}

test('openConsult opens up to the cap then fails-closed with an explicit reason', async () => {
  const m = await freshModule({ HEALTH_TWIN_CONSULT_MAX: '3' });
  assert.equal(m.CONSULT_MAX, 3);

  const ok = agree(m, 3);
  assert.equal(ok.length, 3);
  assert.equal(m.consultCount(), 3);

  const overflow = m.openConsult({ patient: 'p3' }, 'cardiometabolic', 'standard', true);
  assert.ok(!overflow.consult_id, 'must not admit a 4th consult');
  assert.match(overflow.error!, /consult ledger full/);
  assert.match(overflow.error!, /HEALTH_TWIN_CONSULT_MAX/);
});

test('closeConsult frees a slot so a new consult can open', async () => {
  const m = await freshModule({ HEALTH_TWIN_CONSULT_MAX: '2' });
  const ids = agree(m, 2);
  assert.equal(m.consultCount(), 2);
  assert.equal(m.openConsult({}, 'x', 'standard', true).error?.includes('full'), true);

  assert.equal(m.closeConsult(ids[0]!), true);
  assert.equal(m.consultCount(), 1);

  const r = m.openConsult({ patient: 'new' }, 'x', 'standard', true);
  assert.ok(r.consult_id, 'must accept after slot freed');
});

test('closeConsult on an unknown id returns false without touching the ledger', async () => {
  const m = await freshModule({ HEALTH_TWIN_CONSULT_MAX: '10' });
  const [id] = agree(m, 1);
  assert.equal(m.consultCount(), 1);
  assert.equal(m.closeConsult('nope'), false);
  assert.equal(m.consultCount(), 1, 'ledger untouched');
  assert.equal(m.closeConsult(id!), true);
});

test('a non-consenting request never counts against the cap', async () => {
  const m = await freshModule({ HEALTH_TWIN_CONSULT_MAX: '2' });
  // 3 non-consenting opens must not fill the ledger.
  for (let i = 0; i < 3; i++) {
    const r = m.openConsult({}, 'x', 'standard' /* agreed defaults false */);
    assert.match(r.error!, /must agree/);
  }
  assert.equal(m.consultCount(), 0);
  // Room for two legitimate consults still available.
  assert.equal(agree(m, 2).length, 2);
});

test('default cap is 10_000 when env is unset or malformed', async () => {
  delete process.env.HEALTH_TWIN_CONSULT_MAX;
  const m1 = await freshModule();
  assert.equal(m1.CONSULT_MAX, 10_000);

  const m2 = await freshModule({ HEALTH_TWIN_CONSULT_MAX: 'not a number' });
  assert.equal(m2.CONSULT_MAX, 10_000);

  const m3 = await freshModule({ HEALTH_TWIN_CONSULT_MAX: '-5' });
  assert.equal(m3.CONSULT_MAX, 10_000, 'negatives fall back to default');
});
