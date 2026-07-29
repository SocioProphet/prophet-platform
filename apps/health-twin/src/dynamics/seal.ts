// Sealing discipline for twin predictions — the SAME discipline the rest of this engine already uses
// (server.ts receipts, enclave.ts attestation): REAL sha256 from node:crypto, a `sha256-<64 hex>` label
// that matches the math, and a receipt id of the shape `ht-<kind>-<64 hex>`. Nothing new is invented here.
//
// Why this file exists at all: a prediction that reaches a patient-facing surface has to be PROVABLE
// after the fact — which mechanistic model produced the base, which surrogate version proposed the
// correction, and what the reconciliation gate decided and why. That means the seal must bind a
// SNAPSHOT of all three, not just the output number. `snapshotDigest` is that binding.
//
// 🔴 The djb2-labelled-as-"sha-" regression (fixed 2026-07-29) is why this is a shared helper: a
// governance surface whose hash is a 32-bit non-cryptographic mixer makes "tamper-evident" a false
// claim. Everything below goes through node:crypto's SHA-256 and nothing else.
import { createHash } from 'node:crypto';

/** Real SHA-256, node:crypto, no deps. */
export function sha256(s: string): string {
  return createHash('sha256').update(s).digest('hex');
}

/** `sha256-<64 hex>` — the label and the math agree. */
export const digest = (s: string): string => `sha256-${sha256(s)}`;

/**
 * Deterministic JSON: object keys sorted at every depth, numbers normalised, so the same content always
 * produces the same bytes and therefore the same seal regardless of construction order. A seal computed
 * over JSON.stringify's insertion order would silently differ between two runs that mean the same thing.
 */
export function canonical(v: unknown): string {
  if (v === null || typeof v !== 'object') {
    if (typeof v === 'number') {
      if (!Number.isFinite(v)) throw new Error(`cannot seal a non-finite number: ${v}`);
      // -0 and 0 must serialise identically, and 1 and 1.0 must too
      return JSON.stringify(v === 0 ? 0 : v);
    }
    return JSON.stringify(v ?? null);
  }
  if (Array.isArray(v)) return `[${v.map(canonical).join(',')}]`;
  const keys = Object.keys(v as Record<string, unknown>).filter((k) => (v as any)[k] !== undefined).sort();
  return `{${keys.map((k) => `${JSON.stringify(k)}:${canonical((v as any)[k])}`).join(',')}}`;
}

/** Round to a fixed number of decimals before sealing so float noise cannot break determinism. */
export const q = (x: number, dp = 6): number => Math.round(x * 10 ** dp) / 10 ** dp;

export interface Seal {
  /** `ht-<kind>-<64 hex>` — the estate's receipt id shape. */
  id: string;
  verifier: 'health-twin-dynamics';
  /** Digest of the sealed content: what was computed and under which model/surrogate/gate versions. */
  snapshotDigest: string;
  /** Digest of the inputs alone (state + horizon) — proves what it was computed ON. */
  inputsDigest: string;
  /** Digest of the output alone — proves what was emitted. */
  outputDigest: string;
  /** ISO time. Deliberately OUTSIDE the sealed content: the seal binds content, not the clock. */
  at: string;
}

/**
 * Seal a prediction. `inputs` and `output` are digested separately (so either can be re-derived and
 * checked independently) and the whole snapshot — inputs, output, and the provenance block naming the
 * mechanistic model, the surrogate version and the gate policy — is bound into one digest.
 */
export function seal(kind: string, inputs: unknown, output: unknown, provenance: unknown): Seal {
  const inputsDigest = digest(canonical(inputs));
  const outputDigest = digest(canonical(output));
  const snapshotDigest = digest(canonical({ inputsDigest, outputDigest, provenance }));
  return {
    id: `ht-${kind}-${snapshotDigest.slice('sha256-'.length)}`,
    verifier: 'health-twin-dynamics',
    snapshotDigest, inputsDigest, outputDigest,
    at: new Date().toISOString(),
  };
}

/** Re-derive a seal from the same three parts and check it matches — the verification side of the seal. */
export function verifySeal(s: Seal, kind: string, inputs: unknown, output: unknown, provenance: unknown): boolean {
  const again = seal(kind, inputs, output, provenance);
  return again.id === s.id && again.snapshotDigest === s.snapshotDigest
    && again.inputsDigest === s.inputsDigest && again.outputDigest === s.outputDigest;
}
