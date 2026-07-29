/**
 * contract — the vendored-schema validator's own gates.
 *
 * The membrane's whole claim is "what enters the graph conforms to the estate
 * contract", so the validator is load-bearing: a keyword it implements loosely is
 * a hole in every downstream guarantee. These tests pin the sharp edges.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { validateAgainst, canonicalJson, SPEC_VERSION, SCHEMAS } from './contract.js'

function report(over: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: 'urn:srcos:execution-report:contract-test-1',
    type: 'ExecutionReport',
    specVersion: SPEC_VERSION,
    wallTime: '2026-07-29T12:00:00Z',
    orderIntentRef: 'urn:srcos:order-intent:contract-test-1',
    reportKind: 'fill',
    ...over,
  }
}

test('the baseline fixture is valid — so a failure below means the KEYWORD fired', () => {
  assert.deepEqual(validateAgainst('ExecutionReport', report()), [])
})

test('uniqueItems is order-INSENSITIVE for objects: {rel,ref} and {ref,rel} are ONE item', () => {
  // These two schemas really do apply uniqueItems to arrays of objects, which is
  // what makes this more than theory.
  for (const name of ['ExecutionReport', 'OrderIntent'] as const) {
    const links = (SCHEMAS[name]['properties'] as Record<string, Record<string, unknown>>)['provenanceLinks']!
    assert.equal(links['uniqueItems'], true, `${name}.provenanceLinks must still be uniqueItems`)
    assert.equal((links['items'] as Record<string, unknown>)['type'], 'object',
      `${name}.provenanceLinks must still be an array OF OBJECTS (else this test is moot)`)
  }

  // Same content, keys typed in the other order. JSON.stringify called these two
  // different values, so the duplicate slipped through.
  const reordered = validateAgainst('ExecutionReport', report({
    provenanceLinks: [
      { rel: 'derived_from', ref: 'urn:srcos:order-intent:x' },
      { ref: 'urn:srcos:order-intent:x', rel: 'derived_from' },
    ],
  }))
  assert.ok(reordered.some((e) => e.includes('items must be unique')),
    `reordered-key duplicate must be rejected, got: ${JSON.stringify(reordered)}`)

  // literal duplicates still rejected (the case that always worked)
  const literal = validateAgainst('ExecutionReport', report({
    provenanceLinks: [
      { rel: 'derived_from', ref: 'urn:srcos:order-intent:x' },
      { rel: 'derived_from', ref: 'urn:srcos:order-intent:x' },
    ],
  }))
  assert.ok(literal.some((e) => e.includes('items must be unique')))

  // genuinely DIFFERENT links still pass — the fix must not over-reject
  assert.deepEqual(validateAgainst('ExecutionReport', report({
    provenanceLinks: [
      { rel: 'derived_from', ref: 'urn:srcos:order-intent:x' },
      { rel: 'quotes', ref: 'urn:srcos:order-intent:x' },
      { rel: 'derived_from', ref: 'urn:srcos:order-intent:y' },
    ],
  })), [])

  // and string arrays (the common case) are unaffected
  assert.ok(validateAgainst('ExecutionReport', report({ policyLabels: ['a', 'a'] }))
    .some((e) => e.includes('items must be unique')))
  assert.deepEqual(validateAgainst('ExecutionReport', report({ policyLabels: ['a', 'b'] })), [])
})

test('canonicalJson is key-order independent at every depth (the identity uniqueness uses)', () => {
  assert.equal(
    canonicalJson({ b: 1, a: { d: [{ z: 1, y: 2 }], c: 3 } }),
    canonicalJson({ a: { c: 3, d: [{ y: 2, z: 1 }] }, b: 1 }),
  )
  // …but NOT array-order independent: [1,2] and [2,1] are different values
  assert.notEqual(canonicalJson([1, 2]), canonicalJson([2, 1]))
})
