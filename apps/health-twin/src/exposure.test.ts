/**
 * The Authorization header parse on the PHI read path.
 *
 * Raised by Copilot on #1038 (exposure.ts:60) and never answered: the gate
 * stripped a Bearer prefix *if it happened to be there* rather than requiring
 * the scheme, so `replace(/^Bearer\s+/i, '')` was a no-op on any other input and
 * the whole header value was then compared as though it were the credential.
 *
 * The consequence worth pinning is the bare one: `Authorization: <secret>`, with
 * no scheme at all, authenticated. That is not a bearer credential, and a gate
 * that accepts inputs it never meant to accept is one refactor away from
 * accepting the wrong one.
 *
 * These live in their own file rather than in invariants.ts because that module
 * is owned by another lane (#1081) while this landed.
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import { exposureDenial, type ExposureInputs } from './exposure.js';

const authed = (authorization: string): ExposureInputs => ({
  mode: 'authenticated',
  token: 's3cret',
  authorization,
  ingestedRecords: 0,
});

test('a well-formed Bearer credential is accepted', () => {
  assert.equal(exposureDenial(authed('Bearer s3cret')), null);
});

test('the Bearer scheme is case-insensitive per RFC 7235', () => {
  assert.equal(exposureDenial(authed('bearer s3cret')), null);
  assert.equal(exposureDenial(authed('BEARER s3cret')), null);
});

test('surrounding whitespace does not change the credential', () => {
  assert.equal(exposureDenial(authed('  Bearer   s3cret  ')), null);
});

test('a schemeless credential is NOT a bearer credential', () => {
  // The defect: replace() left this untouched, so `presented === token` held.
  assert.equal(exposureDenial(authed('s3cret'))?.code, 401);
});

test('a non-Bearer scheme carrying the secret is refused', () => {
  assert.equal(exposureDenial(authed('Basic s3cret'))?.code, 401);
  assert.equal(exposureDenial(authed('Token s3cret'))?.code, 401);
});

test('a scheme with no credential is refused', () => {
  assert.equal(exposureDenial(authed('Bearer'))?.code, 401);
  assert.equal(exposureDenial(authed('Bearer   '))?.code, 401);
});

test('the wrong credential is still refused', () => {
  assert.equal(exposureDenial(authed('Bearer wrong'))?.code, 401);
  assert.equal(exposureDenial(authed(''))?.code, 401);
});

test('an unset token fails closed with 503, not open', () => {
  assert.equal(
    exposureDenial({ ...authed('Bearer anything'), token: '' })?.code,
    503,
  );
});
