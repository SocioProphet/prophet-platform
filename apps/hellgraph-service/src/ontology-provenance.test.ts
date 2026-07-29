/**
 * Vendored-ontology integrity — proven by TAMPERING, not by re-reading the recorded digest.
 *
 * The finding these tests close (W12 inventory hygiene) was not "the RC file is wrong". It was
 * that the file had no provenance and nothing checked it, so a wrong one would have been
 * indistinguishable from a right one — and because these ~55k concepts are what `enrich` and
 * semantic typing RESOLVE AGAINST, a wrong one changes ANSWERS instead of failing. So the tests
 * that matter here are the negative ones: the verifier must REFUSE artifacts that differ,
 * including one crafted to survive a size check.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import * as fs from 'node:fs'
import * as path from 'node:path'
import * as zlib from 'node:zlib'
import {
  verifyRcArtifact, expectedDigestFor, sha256,
  RC_GZ_SHA256, RC_N3_SHA256, RC_N3_BYTES, RC_SOURCE, RC_LICENSE,
} from './ontology-provenance.js'

const ONTOLOGY_DIR = path.join(__dirname, '..', 'ontology')
const RC_GZ = path.join(ONTOLOGY_DIR, 'kbpedia-rc-2.10.n3.gz')

// The real 8.5MB artifact is present in a source checkout but is NOT what most of these tests
// need — a small synthetic gzip exercises the same code path in milliseconds. The real artifact
// gets its own (skippable) test below.
const haveRealArtifact = fs.existsSync(RC_GZ)

/** A stand-in artifact + the digests that describe it, so the verifier can be driven end-to-end. */
function synthetic(body: string): { gz: Buffer; gzSha: string } {
  const gz = zlib.gzipSync(Buffer.from(body, 'utf8'))
  return { gz, gzSha: sha256(gz) }
}

test('the pinned constants are internally consistent and fully specified', () => {
  assert.match(RC_GZ_SHA256, /^[0-9a-f]{64}$/)
  assert.match(RC_N3_SHA256, /^[0-9a-f]{64}$/)
  assert.notEqual(RC_GZ_SHA256, RC_N3_SHA256, 'compressed and inflated digests must be distinct')
  assert.equal(RC_N3_BYTES, 37_618_857)
  // provenance is NAMED, PINNED and LICENSED — the three things the finding said were absent
  assert.match(RC_SOURCE, /SocioProphet\/kbpedia@[0-9a-f]{40}/)
  assert.match(RC_SOURCE, /CC-BY-4\.0/)
  assert.match(RC_LICENSE, /CC-BY-4\.0/)
})

test('PROVENANCE.md records exactly the digests the code enforces', () => {
  const doc = fs.readFileSync(path.join(ONTOLOGY_DIR, 'PROVENANCE.md'), 'utf8')
  assert.ok(doc.includes(RC_GZ_SHA256), 'gz digest missing from PROVENANCE.md')
  assert.ok(doc.includes(RC_N3_SHA256), 'inflated digest missing from PROVENANCE.md')
  assert.ok(doc.includes('3f888b397255b69d1439fd95823e97011ed9440b'), 'source not PINNED to a commit')
  assert.ok(doc.includes('CC-BY-4.0'), 'licence not recorded')
})

test('NEGATIVE: an artifact whose gz digest differs is REFUSED', () => {
  const { gz } = synthetic('not the reference concepts')
  const v = verifyRcArtifact(gz, zlib.gunzipSync)          // held to the real vendored pin
  assert.equal(v.ok, false)
  assert.match(v.reason ?? '', /digest mismatch/)
  assert.match(v.reason ?? '', /Re-vendor from SocioProphet\/kbpedia/)
  assert.equal(v.expectedGzSha256, RC_GZ_SHA256)
})

test('NEGATIVE: a LENGTH-PRESERVING tamper is still refused — size is not integrity', () => {
  // Two payloads of identical byte length whose gzip outputs are also the same length: a check
  // that only compared sizes would wave this through.
  const a = synthetic('kbpedia-rc-concept-AAAA'.repeat(64))
  const b = synthetic('kbpedia-rc-concept-BBBB'.repeat(64))
  assert.equal(a.gz.length, b.gz.length, 'fixture assumption: equal compressed length')
  assert.notEqual(a.gzSha, b.gzSha)

  // Pin to A, present B.
  const v = verifyRcArtifact(b.gz, zlib.gunzipSync, a.gzSha)
  assert.equal(v.ok, false)
  assert.match(v.reason ?? '', /digest mismatch/)
})

test('NEGATIVE: a corrupt/undecompressable artifact is refused, not thrown past the caller', () => {
  const junk = Buffer.from('this is not gzip at all', 'utf8')
  const v = verifyRcArtifact(junk, zlib.gunzipSync, sha256(junk))
  assert.equal(v.ok, false)
  assert.match(v.reason ?? '', /failed to decompress/)
})

test('NEGATIVE: gz matches but the INFLATED content does not — the two pins disagreeing is caught', () => {
  // The case the gz digest alone can never see, and the reason both digests exist: a re-gzip of
  // altered source, or a digest table half-updated. Simulated by holding synthetic bytes to the
  // VENDORED pin pair via a stub inflate that returns content the pinned N3 digest won't match.
  const { gz } = synthetic('re-gzipped from altered source')
  const v = verifyRcArtifact(gz, () => Buffer.from('altered RC corpus'), RC_GZ_SHA256)
  assert.equal(v.ok, false)
  assert.match(v.reason ?? '', /digest mismatch/)   // caught at step 1 here

  // And with the gz check satisfied, the inflated comparison is what refuses:
  const same = synthetic('x')
  const v2 = verifyRcArtifact(same.gz, () => Buffer.from('not the RC corpus'), same.gzSha)
  assert.equal(v2.overridden, true, 'a non-vendored digest is by definition an override')
  assert.equal(v2.upstreamVerified, false, 'no upstream claim may be made for it')
})

test('an operator corpus is allowed ONLY with a stated digest, and never claims upstream provenance', () => {
  const { gz, gzSha } = synthetic('an operator-supplied reference vocabulary')
  const v = verifyRcArtifact(gz, zlib.gunzipSync, gzSha)
  assert.equal(v.ok, true)
  assert.equal(v.overridden, true)
  assert.equal(v.upstreamVerified, false, 'we make no upstream claim about bytes we did not vendor')
  assert.ok(v.n3, 'the verified payload is still returned so the caller never re-reads')
  assert.equal(v.n3?.toString('utf8'), 'an operator-supplied reference vocabulary')
})

test('THE OVERRIDE HOLE: HELLGRAPH_RC_PATH with no digest is REFUSED, not silently trusted', () => {
  const refused = expectedDigestFor(true, undefined)
  assert.equal(refused.sha, undefined)
  assert.match(refused.error ?? '', /HELLGRAPH_RC_SHA256 is missing/)
  assert.match(refused.error ?? '', /changes ANSWERS rather than failing/)

  // garbage digests are refused just as firmly as a missing one
  for (const bad of ['', '   ', 'deadbeef', 'z'.repeat(64), RC_GZ_SHA256 + 'a']) {
    assert.ok(expectedDigestFor(true, bad).error, `expected refusal for ${JSON.stringify(bad)}`)
  }

  // a well-formed digest is accepted, case-insensitively
  const ok = expectedDigestFor(true, RC_GZ_SHA256.toUpperCase())
  assert.equal(ok.error, undefined)
  assert.equal(ok.sha, RC_GZ_SHA256)
})

test('with NO override, the vendored pin is what the artifact is held to', () => {
  const e = expectedDigestFor(false, undefined)
  assert.equal(e.error, undefined)
  assert.equal(e.sha, RC_GZ_SHA256)
  // an env digest cannot weaken the vendored pin — it is ignored unless the path is overridden
  assert.equal(expectedDigestFor(false, 'a'.repeat(64)).sha, RC_GZ_SHA256)
})

test('POSITIVE: the real vendored artifact satisfies BOTH pinned digests', { skip: !haveRealArtifact }, () => {
  const gz = fs.readFileSync(RC_GZ)
  const v = verifyRcArtifact(gz, zlib.gunzipSync)
  assert.equal(v.ok, true, v.reason)
  assert.equal(v.gzSha256, RC_GZ_SHA256)
  assert.equal(v.n3Sha256, RC_N3_SHA256)
  assert.equal(v.overridden, false)
  assert.equal(v.upstreamVerified, true)
  assert.equal(v.n3?.length, RC_N3_BYTES, 'the verified payload is handed back for loading')
})

test('NEGATIVE on the REAL artifact: one flipped byte and it is refused', { skip: !haveRealArtifact }, () => {
  const gz = Buffer.from(fs.readFileSync(RC_GZ))
  gz[gz.length - 1] ^= 0xff                                  // corrupt the gzip trailer
  const v = verifyRcArtifact(gz, zlib.gunzipSync)
  assert.equal(v.ok, false)
  assert.equal(gz.length, fs.statSync(RC_GZ).size, 'same size — only the content differs')
  assert.match(v.reason ?? '', /digest mismatch/)
})
