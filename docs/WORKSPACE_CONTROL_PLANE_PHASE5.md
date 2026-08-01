# Workspace Control Plane — Phase 5 (trust broker)

Implements **Phase 5** of the control spec: remote discovery must not precede
signed manifests and revocation semantics (D9), under a staged security stance
(D16). Verifies over the `capability-manifest` / `topic-manifest` / `catalog-entry`
schemas frozen in Phase 1.

## What it verifies (`tools/trust_broker.py`)

- **Signature** — the manifest/catalog signature verifies under the configured verifier.
- **Freshness** — not past `expiry`, and (optionally) signed within `max_age_seconds`.
- **Revocation** — `revocation.revoked` must be false.
- **Delegation threshold** (catalogs) — at least `delegation.threshold` signatures
  must verify (TUF-style).
- **Transparency** — every verification (trusted or not, with reasons) is appended
  to an in-memory transparency log.

## Pluggable, staged crypto (D16)

Signature verification is an interface. The **lab default** implements a real
keyed MAC — `hmac-blake2b`, stdlib only, no heavy dependency — so trust is
genuinely enforced in the trusted-lab stance. **Asymmetric** algorithms
(`ed25519`, `ecdsa-p256`, `sigstore-keyless`) require production keys/infra and
report `verifier_unavailable` rather than pretending to verify. Swap in a
production verifier behind the same interface for the hardened stance.

`hmac-blake2b` was added to the three manifest algorithm enums as a deliberate,
additive extension (existing values unchanged).

## Relationship to the capability broker (Phase 2)

The Phase-2 capability broker gates `trusted_catalog` resolution on structural
catalog validity; the trust broker is the deeper verifier a hardened deployment
routes those checks through.

## Validation

`tools/tests/test_trust_broker.py` — 7 tests: valid→trusted, tamper→bad_signature,
expired/revoked/unsigned, unknown-signer + asymmetric-unavailable, stale via
max_age, catalog delegation threshold, transparency log. Path-filtered CI:
`.github/workflows/control-plane-trust.yml`.

## Next (Phase 6)

Hypercore/Hyperswarm/Autobase overlay for approved private topics — needs the
Hyper stack deps; scaffold-first (topic-manifest transport already frozen).
