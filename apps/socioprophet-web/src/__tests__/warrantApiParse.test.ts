/**
 * W11 — `parseWalk()` strictness (the gateway door).
 *
 * The distinction under test is the whole reason <Warrant> exists:
 *
 *   "we could not understand the response"   ≠   "the proof is bad"
 *
 * A payload-SHAPE error is NOT a verification failure. Coercing an unrecognized step name
 * to `unknown-step` or an unrecognized status to `fail` turns the first fact into the
 * second, and the surface then renders UNSEALED — an accusation the gateway never made.
 * Malformed ⇒ `unavailable`, surfaced as such.
 *
 * The module also pins the walk's shape: `steps` is "always length 3", in the order
 * gateway-signature → engine-seal-hash → snapshot-seq-binding. That claim is enforced here
 * rather than merely asserted in a comment.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { RECEIPT_WALK_STEPS } from '../features/warrant/types';

const GW = 'http://gateway.test';

/**
 * `GATEWAY` is resolved once at module load, so each case re-imports the module with the
 * host runtime config already in place. Without a base the door short-circuits to
 * `unavailable` and never reaches the parser.
 */
async function loadApi(base: string | null = GW) {
  vi.resetModules();
  const w = window as unknown as { __COCKPIT_CONFIG__?: unknown };
  if (base) w.__COCKPIT_CONFIG__ = { bases: { gateway: base } };
  else delete w.__COCKPIT_CONFIG__;
  return import('../services/warrantApi');
}

function respondWith(body: unknown, ok = true, status = 200) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({ ok, status, json: async () => body })),
  );
}

/**
 * A well-formed walk, used as the base every malformed case mutates away from. Typed loosely
 * on purpose: these cases are about payloads the compiler would never let us construct, which
 * is exactly the class of input the parser has to survive at runtime.
 */
interface LooseStep {
  step: unknown;
  status: unknown;
  detail: unknown;
}
interface LooseWalk {
  valid: unknown;
  receipt_id: unknown;
  project: unknown;
  steps: LooseStep[];
}

function goodWalk(): LooseWalk {
  return {
    valid: true,
    receipt_id: 'rcpt-1',
    project: 'default',
    steps: RECEIPT_WALK_STEPS.map((step): LooseStep => ({ step, status: 'ok', detail: null })),
  };
}

beforeEach(() => {
  const w = window as unknown as { __COCKPIT_CONFIG__?: unknown };
  delete w.__COCKPIT_CONFIG__;
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe('parseWalk — a shape error is not a verification failure', () => {
  it('accepts the real gateway shape', async () => {
    const api = await loadApi();
    respondWith(goodWalk());
    const r = await api.verifyReceipt('rcpt-1');
    expect(r.mode).toBe('live');
    expect(r.data?.valid).toBe(true);
    expect(r.data?.steps.map((s) => s.step)).toEqual([...RECEIPT_WALK_STEPS]);
  });

  it('rejects an unrecognized STATUS instead of coercing it to "fail"', async () => {
    const api = await loadApi();
    const body = goodWalk();
    // A gateway that grows a fourth status must not be read as an accusation.
    body.steps[1] = { step: 'engine-seal-hash', status: 'indeterminate', detail: null };
    respondWith(body);

    const r = await api.verifyReceipt('rcpt-1');
    expect(r.mode).toBe('unavailable');
    expect(r.data).toBeNull();
    expect(r.error).toMatch(/unrecognized/i);
  });

  it('rejects a non-string STEP NAME instead of coercing it to "unknown-step"', async () => {
    const api = await loadApi();
    const body = goodWalk();
    body.steps[0] = { step: 42, status: 'ok', detail: null };
    respondWith(body);

    const r = await api.verifyReceipt('rcpt-1');
    expect(r.mode).toBe('unavailable');
    expect(r.data).toBeNull();
  });

  it('rejects a step whose `detail` is neither string nor null', async () => {
    const api = await loadApi();
    const body = goodWalk();
    body.steps[2] = { step: 'snapshot-seq-binding', status: 'ok', detail: { oops: true } };
    respondWith(body);

    const r = await api.verifyReceipt('rcpt-1');
    expect(r.mode).toBe('unavailable');
    expect(r.data).toBeNull();
  });

  it('rejects a null / non-object step entry', async () => {
    const api = await loadApi();
    const body = goodWalk();
    body.steps[1] = null as unknown as LooseStep;
    respondWith(body);

    const r = await api.verifyReceipt('rcpt-1');
    expect(r.mode).toBe('unavailable');
    expect(r.data).toBeNull();
  });
});

describe('parseWalk — the "always length 3, pinned order" claim is enforced, not just asserted', () => {
  it('rejects a walk with too few steps', async () => {
    const api = await loadApi();
    const body = goodWalk();
    body.steps = body.steps.slice(0, 2);
    respondWith(body);

    const r = await api.verifyReceipt('rcpt-1');
    expect(r.mode).toBe('unavailable');
    expect(r.data).toBeNull();
  });

  it('rejects a walk with an extra step', async () => {
    const api = await loadApi();
    const body = goodWalk();
    body.steps = [...body.steps, { step: 'bonus-step', status: 'ok', detail: null }];
    respondWith(body);

    const r = await api.verifyReceipt('rcpt-1');
    expect(r.mode).toBe('unavailable');
    expect(r.data).toBeNull();
  });

  it('rejects the three steps in the wrong ORDER', async () => {
    const api = await loadApi();
    const body = goodWalk();
    body.steps = [body.steps[1], body.steps[0], body.steps[2]];
    respondWith(body);

    const r = await api.verifyReceipt('rcpt-1');
    expect(r.mode).toBe('unavailable');
    expect(r.data).toBeNull();
  });

  it('rejects an unexpected step NAME', async () => {
    const api = await loadApi();
    const body = goodWalk();
    body.steps[2] = { step: 'snapshot-seq-bindings', status: 'ok', detail: null };
    respondWith(body);

    const r = await api.verifyReceipt('rcpt-1');
    expect(r.mode).toBe('unavailable');
    expect(r.data).toBeNull();
  });

  it('still keeps `skipped` — the status that must never read as passed', async () => {
    const api = await loadApi();
    const body = goodWalk();
    body.valid = false;
    body.steps[1] = { step: 'engine-seal-hash', status: 'fail', detail: 'hash mismatch' };
    body.steps[2] = { step: 'snapshot-seq-binding', status: 'skipped', detail: 'prior step failed' };
    respondWith(body);

    const r = await api.verifyReceipt('rcpt-1');
    expect(r.mode).toBe('live');
    expect(r.data?.steps[2].status).toBe('skipped');
  });
});

describe('parseWalk — the envelope', () => {
  it('rejects a payload that is not an object', async () => {
    const api = await loadApi();
    respondWith('nope');
    const r = await api.verifyReceipt('rcpt-1');
    expect(r.mode).toBe('unavailable');
  });

  it('reports an unconfigured gateway as unavailable, never as a pass', async () => {
    const api = await loadApi(null);
    const r = await api.verifyReceipt('rcpt-1');
    expect(r.mode).toBe('unavailable');
    expect(r.data).toBeNull();
    expect(r.error).toMatch(/no compute-gateway base configured/);
  });
});
