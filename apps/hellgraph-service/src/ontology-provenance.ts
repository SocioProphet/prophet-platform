/**
 * Vendored-ontology integrity — the KBpedia reference-concept ABox.
 *
 * ── Why this is fail-CLOSED, unlike the seeds ────────────────────────────────────────
 * The ~55k KBpedia reference concepts are not decoration and not a demo corpus: they are the
 * TARGET VOCABULARY that `/api/graph/enrich` ranks coherence against and that the engine's
 * semantic entity typing (`mapEntityToKkoSemantic`) resolves entities into. A drifted RC file
 * therefore does not fail — it RESOLVES DIFFERENTLY. Every enrichment, every typing decision,
 * every downstream receipt sealed over those answers inherits the drift, silently and durably,
 * because the atoms are content-addressed and persist.
 *
 * That asymmetry is the whole design here. Elsewhere in this file's neighbourhood the rule is
 * "never let a load error take the service down" (seedIfEmpty, loadKkoIfEnabled) and that is
 * right: a missing seed corpus means an empty graph, which is visibly wrong. But "wrong
 * vocabulary" is invisibly wrong, so the only honest options are LOAD THE DECLARED BYTES or
 * LOAD NOTHING. Refusing keeps the service up with an empty RC set — a state
 * `/healthz` and the enrich path already handle — instead of quietly poisoning answers.
 *
 * ── The chain this asserts (see ontology/PROVENANCE.md) ──────────────────────────────
 *   SocioProphet/kbpedia @ 3f888b39  versions/2.10/kbpedia_reference_concepts.zip
 *     -> kbpedia_reference_concepts.n3   sha256 0c23ca83…  (37,618,857 bytes)  CC-BY-4.0
 *     -> re-gzipped into this image as   kbpedia-rc-2.10.n3.gz  sha256 e48d0ff7…
 *
 * BOTH digests are asserted, and they answer different questions. The gz digest proves the file
 * shipped in the image is the vendored artifact (fast, catches a swapped file). The INFLATED
 * digest proves those bytes are upstream's bytes — gzip is not reproducible across zlib
 * versions and compression levels, so the gz digest alone can never demonstrate equivalence to
 * anything published upstream. Only the inflated digest is portable provenance.
 */
import { createHash } from 'node:crypto'

/** sha256 of the vendored `kbpedia-rc-2.10.n3.gz` as it ships in this repo/image. */
export const RC_GZ_SHA256 = 'e48d0ff7708d647cb35b1bcbcca05a041c731e5a1bfcea296209a086b72da06a'

/**
 * sha256 of the INFLATED N3 — byte-identical to `kbpedia_reference_concepts.n3` inside
 * `versions/2.10/kbpedia_reference_concepts.zip` in SocioProphet/kbpedia@3f888b39.
 * Verified against upstream on 2026-07-29.
 */
export const RC_N3_SHA256 = '0c23ca83ac0e1270c4ea5335268b54a32577ba5d8cec0e33345f48e2ac60e95f'

/** Inflated size in bytes — matches the zip's stated entry size exactly. */
export const RC_N3_BYTES = 37_618_857

export const RC_SOURCE =
  'SocioProphet/kbpedia@3f888b397255b69d1439fd95823e97011ed9440b ' +
  'versions/2.10/kbpedia_reference_concepts.zip -> kbpedia_reference_concepts.n3 (CC-BY-4.0)'

export const RC_LICENSE = 'CC-BY-4.0 (c) Michael K. Bergman & Fred Giasson — KBpedia/Cognonto'

export const sha256 = (b: Buffer | string): string => createHash('sha256').update(b).digest('hex')

export interface RcVerification {
  /** Did the artifact match everything it is required to match, and is it loadable? */
  ok: boolean
  /** Human-readable refusal, present only when `ok` is false. */
  reason?: string
  /** The digest of the compressed artifact actually on disk. */
  gzSha256: string
  /** The digest of the inflated N3, when inflation succeeded. */
  n3Sha256?: string
  /**
   * The inflated payload, when verification passed. Returned so the caller loads THE BYTES THAT
   * WERE VERIFIED rather than re-reading and re-inflating — a re-read is a second artifact, and
   * a check that does not cover the bytes actually used is not a check.
   */
  n3?: Buffer
  /** Which digest the gz was held to — the vendored pin, or an operator-supplied override. */
  expectedGzSha256: string
  /** True when the operator pointed the service at a non-vendored artifact. */
  overridden: boolean
  /**
   * True only when the inflated bytes were matched against the pinned UPSTREAM digest. False for
   * an operator corpus: we can confirm it is the file they named, but we make no claim that it
   * is anything published by KBpedia, and a claim we cannot support must not be implied.
   */
  upstreamVerified: boolean
}

/**
 * Verify a compressed RC artifact against its pinned digests, and return the verified payload.
 *
 * `expectedGzSha256` lets an operator run a DIFFERENT corpus (HELLGRAPH_RC_PATH) — but only by
 * stating its digest up front (HELLGRAPH_RC_SHA256). There is deliberately no unverified path:
 * a path override with no digest is the hole this closes, not a convenience to preserve.
 *
 * Three checks, and which of them apply depends on whether we vendored the bytes:
 *   1. gz digest        — ALWAYS. Is this the file you named?
 *   2. decompressable   — ALWAYS. An artifact that cannot be inflated is not loadable, whoever
 *                         supplied it; reporting `ok` for it would push the failure into the
 *                         caller's generic catch and reappear as a vague "skipped (error)".
 *   3. inflated digest + byte count — VENDORED ONLY. This is the upstream-equivalence claim, and
 *                         it is the only one that reaches SocioProphet/kbpedia.
 */
export function verifyRcArtifact(gz: Buffer, inflate: (b: Buffer) => Buffer,
                                 expectedGzSha256: string = RC_GZ_SHA256): RcVerification {
  const overridden = expectedGzSha256 !== RC_GZ_SHA256
  const gzSha256 = sha256(gz)
  const base = { gzSha256, expectedGzSha256, overridden, upstreamVerified: false }

  if (gzSha256 !== expectedGzSha256) {
    return {
      ...base,
      ok: false,
      reason: `RC artifact digest mismatch: sha256 ${gzSha256} != expected ${expectedGzSha256}. ` +
        (overridden
          ? 'HELLGRAPH_RC_SHA256 does not describe the file at HELLGRAPH_RC_PATH.'
          : `Re-vendor from ${RC_SOURCE} and update ontology/PROVENANCE.md.`),
    }
  }

  let n3: Buffer
  try {
    n3 = inflate(gz)
  } catch (e) {
    return { ...base, ok: false, reason: `RC artifact failed to decompress: ${msg(e)}` }
  }
  const n3Sha256 = sha256(n3)

  // An overridden corpus is held to the operator's digest only — we have no upstream claim to
  // make about bytes we did not vendor, and inventing one would be worse than silence.
  if (overridden) return { ...base, n3Sha256, n3, ok: true }

  if (n3Sha256 !== RC_N3_SHA256) {
    return {
      ...base,
      n3Sha256,
      ok: false,
      // Reaching here means the gz matched but its CONTENT did not — a re-gzip of altered
      // source, or a digest table updated without re-verifying upstream.
      reason: `RC inflated content mismatch: sha256 ${n3Sha256} != pinned ${RC_N3_SHA256} ` +
        `(the compressed artifact matched, so the pinned digests disagree with each other — ` +
        `re-verify against ${RC_SOURCE}).`,
    }
  }
  if (n3.length !== RC_N3_BYTES) {
    return { ...base, n3Sha256, ok: false, reason: `RC inflated size ${n3.length} != pinned ${RC_N3_BYTES}` }
  }
  return { ...base, n3Sha256, n3, ok: true, upstreamVerified: true }
}

/** Resolve the digest the artifact at `path` must match, given the env. */
export function expectedDigestFor(pathOverridden: boolean,
                                  envSha: string | undefined): { sha?: string; error?: string } {
  if (!pathOverridden) return { sha: RC_GZ_SHA256 }
  const sha = (envSha ?? '').trim().toLowerCase()
  if (!/^[0-9a-f]{64}$/.test(sha)) {
    return {
      error: 'HELLGRAPH_RC_PATH is set but HELLGRAPH_RC_SHA256 is missing or not a 64-hex sha256. ' +
        'A reference vocabulary loaded from an unverified path changes ANSWERS rather than failing, ' +
        'so there is no unverified load path: state the digest of the corpus you are pointing at.',
    }
  }
  return { sha }
}

const msg = (e: unknown): string => (e instanceof Error ? e.message : String(e))
