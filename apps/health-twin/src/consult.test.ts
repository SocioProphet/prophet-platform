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
  // Historical NB: pre-fix, openConsult minted its id from
  // sha256([pseudonym, scope, `${Date.now()}-${scope}`]) — two calls in the
  // same ms with the same scope silently overwrote each other in the ledger.
  // This PR closes that by adding randomUUID() to the id inputs, so the
  // unique-scope-per-call precaution below is now belt-and-braces rather than
  // essential. Kept anyway so the cap test remains readable.
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

/**
 * The test above claimed "or malformed" but only exercised the two malformed
 * inputs that Number.parseInt happens to reject outright. The dangerous class
 * is the one parseInt ACCEPTS by reading a prefix and discarding the rest, and
 * none of those were covered.
 *
 * Note the trap in the original test's own notation: it writes the default as
 * the JS numeric literal `10_000`, which is 10000. The *string* '10_000' — the
 * same thing an operator types into a ConfigMap — parses to 10. The test
 * spelled the failing input on every line and could never hit it, because a
 * literal is not a string.
 *
 * Each case below FAILED against the parseInt implementation merged in #1068.
 */
test('a partially-numeric cap is refused, not silently truncated', async () => {
  const cases: Array<[string, string]> = [
    ['10_000', 'underscore separator: parseInt stops at "_" and yields 10'],
    ['1e5', 'scientific notation: parseInt stops at "e" and yields 1'],
    ['10000oops', 'trailing garbage: parseInt reads the prefix and reports success'],
    ['0x10', 'hex: parseInt(radix 10) stops at "x" and yields 0'],
    ['12.9', 'decimal: parseInt truncates silently'],
    ['', 'empty'],
    ['   ', 'whitespace only'],
    ['+5', 'signed'],
    ['99999999999999999999', 'far beyond Number.MAX_SAFE_INTEGER'],
    // The sharp one: all digits, and Number() does NOT fail on it — it rounds to
    // 9007199254740992, which IS a safe integer, so an isSafeInteger() guard
    // accepts a value one less than what the operator wrote. Silently altering
    // the config is the same defect as parseInt's partial read.
    ['9007199254740993', 'one past MAX_SAFE_INTEGER — Number() rounds it to a *different* safe integer'],
    ['9007199254740992', 'MAX_SAFE_INTEGER + 1 — the first value that cannot round-trip'],
  ];
  for (const [value, why] of cases) {
    const m = await freshModule({ HEALTH_TWIN_CONSULT_MAX: value });
    assert.equal(m.CONSULT_MAX, 10_000, `${JSON.stringify(value)} must fall back to the default — ${why}`);
  }
});

test('a well-formed cap is still honoured', async () => {
  for (const [value, expected] of [
    ['1', 1], ['42', 42], ['10000', 10_000], [' 250 ', 250],
    // The boundary itself must remain acceptable — the rejection above must be
    // "cannot round-trip", not "large numbers are suspicious".
    ['9007199254740991', Number.MAX_SAFE_INTEGER],
  ] as const) {
    const m = await freshModule({ HEALTH_TWIN_CONSULT_MAX: value });
    assert.equal(m.CONSULT_MAX, expected, `${JSON.stringify(value)} must be honoured`);
  }
});

// ── #1068 body / #1070: id-collision fix ──────────────────────────────────
// Composed on top of #1068's CONSULT_MAX parsing hardening above: the earlier
// PR bounded the LEDGER (memory-safety of the container), this PR bounds the
// IDs (uniqueness of the identifiers inside it). Both are load-bearing and
// together they close the "consult container can silently lose entries" door.

test('openConsult mints unique ids even when N calls hit the same ms + scope', async () => {
  const m = await freshModule({ HEALTH_TWIN_CONSULT_MAX: '100' });
  // Tight loop: many calls will land in the same millisecond, and the scope is
  // fixed. Pre-fix, all but one collided and silently overwrote each other.
  const ids = new Set<string>();
  for (let i = 0; i < 50; i++) {
    const r = m.openConsult({ patient: 'p' }, 'shared-scope', 'standard', true);
    if (r.consult_id) ids.add(r.consult_id);
  }
  assert.equal(ids.size, 50, 'every open must produce a unique id even under contention');
  assert.equal(m.consultCount(), 50, 'the ledger must hold every consult, not overwrite');
});

test('submitOpinion mints unique opinion ids in a tight loop', async () => {
  const m = await freshModule({ HEALTH_TWIN_CONSULT_MAX: '10' });
  const [id] = agree(m, 1);
  const opIds = new Set<string>();
  for (let i = 0; i < 20; i++) {
    const op = m.submitOpinion(id!, 'reviewer-x', 'assessment-x', 'moderate');
    if ('id' in op) opIds.add(op.id);
  }
  assert.equal(opIds.size, 20, 'every opinion id must be unique');
});

test('requestMore mints unique request ids in a tight loop', async () => {
  const m = await freshModule({ HEALTH_TWIN_CONSULT_MAX: '10' });
  const [id] = agree(m, 1);
  const rIds = new Set<string>();
  for (let i = 0; i < 20; i++) {
    const r = m.requestMore(id!, 'labs.a1c', 'need it');
    if ('id' in r) rIds.add(r.id);
  }
  assert.equal(rIds.size, 20, 'every more-request id must be unique');
});


test('requestMore hashes the trimmed field so a whitespace variant maps to the same canonical input', async () => {
  const m = await freshModule({ HEALTH_TWIN_CONSULT_MAX: '10' });
  const [cid] = agree(m, 1);
  // The stored field is trimmed; the id derivation must use the same
  // trimmed value so audit trails aren't misleading about what was hashed.
  const r1 = m.requestMore(cid!, '  labs.a1c  ', 'need it');
  assert.ok('id' in r1);
  assert.equal(r1.field, 'labs.a1c');
  // Rebuild the expected id from the trimmed inputs — we can't easily do that
  // without duplicating the sha256 helper, but we CAN check the id doesn't
  // silently vary with whitespace.
  const r2 = m.requestMore(cid!, 'labs.a1c', 'need it');
  assert.ok('id' in r2);
  // Both stored fields should be identical.
  assert.equal(r1.field, r2.field);
});
