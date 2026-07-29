#!/usr/bin/env node
/**
 * Vendored-ontology digest guard for hellgraph-service.
 *
 * ── Why this exists (W12 inventory hygiene, 2026-07) ─────────────────────────────────
 * The 8.5MB KBpedia reference-concept ABox shipped into the image with NO provenance of any
 * kind: no source URL, no licence note, no digest, no retrieval date. It is the vocabulary
 * `/api/graph/enrich` coherence-ranks against and that semantic entity typing resolves into, so
 * a drifted copy does not fail — it returns DIFFERENT ANSWERS, and those answers persist as
 * content-addressed atoms. Nothing would have noticed.
 *
 * `src/ontology-provenance.ts` now asserts the digests at LOAD time. That closes the runtime
 * hole but not the supply hole: a bad artifact committed to the repo would still build, publish,
 * and only refuse once a pod started. This guard is the CI half — it fails the BUILD, so a
 * mismatched artifact never reaches an image. Same constants, two enforcement points:
 *
 *     CI (this file)          the committed artifact is the declared one   -> build red
 *     runtime (server.ts)     the artifact in THIS image is the declared one -> refuse to load
 *
 * Wired into `make engine-guards`, alongside the engine-version guards, because it answers the
 * same question about a different vendored input: IS THE THING WE SHIP THE THING WE INTEND?
 *
 * Deliberately dependency-free and TypeScript-free (plain .mjs reading the .ts as text) so it
 * runs in a bare CI container with no npm install and no build step.
 */
import { readFileSync, existsSync, createReadStream } from 'node:fs'
import { createHash } from 'node:crypto'
import { createGunzip } from 'node:zlib'
import { pipeline } from 'node:stream/promises'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const die = (m) => { console.error(`✗ ${m}`); process.exit(1) }

const here = dirname(fileURLToPath(import.meta.url))
const svcRoot = join(here, '..')
const provTs = join(svcRoot, 'src', 'ontology-provenance.ts')
const provMd = join(svcRoot, 'ontology', 'PROVENANCE.md')
const artifact = join(svcRoot, 'ontology', 'kbpedia-rc-2.10.n3.gz')

// ── 1) read the pins out of the module the RUNTIME uses, so CI and runtime can never disagree ──
if (!existsSync(provTs)) die(`missing ${provTs} — the provenance module is the source of the pins`)
const src = readFileSync(provTs, 'utf8')
const pin = (name) => {
  const m = src.match(new RegExp(`export const ${name} =\\s*'([0-9a-f]{64})'`))
  return m ? m[1] : die(`cannot read ${name} from src/ontology-provenance.ts`)
}
const RC_GZ_SHA256 = pin('RC_GZ_SHA256')
const RC_N3_SHA256 = pin('RC_N3_SHA256')
const bytesMatch = src.match(/export const RC_N3_BYTES = ([\d_]+)/)
const RC_N3_BYTES = bytesMatch ? Number(bytesMatch[1].replace(/_/g, '')) : die('cannot read RC_N3_BYTES')

// ── 2) the PROVENANCE.md must record what the code enforces (a doc nobody verifies is decoration) ──
if (!existsSync(provMd)) die('ontology/PROVENANCE.md is missing — a vendored artifact must state its origin')
const doc = readFileSync(provMd, 'utf8')
for (const [what, needle] of [
  ['the gz digest', RC_GZ_SHA256],
  ['the inflated digest', RC_N3_SHA256],
  ['a pinned source commit', '3f888b397255b69d1439fd95823e97011ed9440b'],
  ['the licence', 'CC-BY-4.0'],
  ['the source repo', 'SocioProphet/kbpedia'],
]) if (!doc.includes(needle)) die(`ontology/PROVENANCE.md does not record ${what} (${needle})`)

// ── 3) the artifact itself ──
if (!existsSync(artifact)) die(`vendored RC artifact missing: ${artifact}`)

const gzSha = createHash('sha256').update(readFileSync(artifact)).digest('hex')
if (gzSha !== RC_GZ_SHA256)
  die(`RC artifact DRIFTED: sha256 ${gzSha} != pinned ${RC_GZ_SHA256}. This artifact is the target ` +
      `vocabulary enrich + semantic typing resolve against — a drifted copy changes ANSWERS rather ` +
      `than failing. Re-vendor from SocioProphet/kbpedia and update src/ontology-provenance.ts + ` +
      `ontology/PROVENANCE.md together.`)

// Inflate as a STREAM: the payload is 37MB and a CI container should not need it resident.
const h = createHash('sha256')
let n3Bytes = 0
await pipeline(
  createReadStream(artifact),
  createGunzip(),
  async function* (chunks) { for await (const c of chunks) { h.update(c); n3Bytes += c.length } },
)
const n3Sha = h.digest('hex')
if (n3Sha !== RC_N3_SHA256)
  die(`RC inflated content DRIFTED: sha256 ${n3Sha} != pinned ${RC_N3_SHA256}. The compressed file ` +
      `matched, so the two pinned digests disagree with each other — re-verify against upstream.`)
if (n3Bytes !== RC_N3_BYTES)
  die(`RC inflated size ${n3Bytes} != pinned ${RC_N3_BYTES}`)

console.log(`✓ hellgraph-service RC ABox verified — gz ${gzSha.slice(0, 16)}… / inflated ${n3Sha.slice(0, 16)}… ` +
            `(${n3Bytes.toLocaleString()} bytes, CC-BY-4.0, SocioProphet/kbpedia@3f888b39)`)
