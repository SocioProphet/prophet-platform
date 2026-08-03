# identity-twin

The prophet-platform surface for the **Multiverseal Twin** — a federation-facing
identity/reputation projection of a sovereign core. This app *consumes* the twin library
(VSA medium + VRF references + interferometric read) rather than reimplementing it.

## Status
**Foundation.** The twin library is vendored and proven usable here; the HTTP service surface
(attest / medium / diff / verify endpoints) + deploy are the next slice.

## What the library gives you
- `MultiversealTwin(seed?)` — a sovereign core (master Ed25519 key).
- `attest(context, value)` — mint a VRF context reference and bind the value against it
  (reference-at-ingest; never stored bare). Returns a `VerifiableReference` relying parties check.
- `recall(context)`, `medium()`, `diff(other)`, `is_tampered(snapshot)`, `verify(ref)`.
- FIPS-approvable crypto throughout: Ed25519 (FIPS 186-5) + SHA-256 (FIPS 180-4).

## Vendored dependency (not forked)
`third_party/procyber/semantic/` is a pinned copy of `SocioProphet/ProCybernetica:procyber/semantic`,
recorded in `third_party/procyber/VENDOR.json` (source commit + per-file sha256). The smoke test
asserts the vendored files match their pins — a drifted copy fails CI (vendor freshness, no rot).

### Refreshing the vendor
1. `git -C <ProCybernetica> archive origin/main procyber/semantic | tar -x` and copy the `.py` files
   into `third_party/procyber/semantic/`.
2. Regenerate `VENDOR.json` (source_commit + sha256 of each file).
3. `pytest -q apps/identity-twin/tests` — the pin check and twin smoke must pass.

## Tests
`pytest -q apps/identity-twin/tests` (needs `numpy` + `cryptography`) — proves the vendored twin
attests/recalls/verifies/tamper-detects and that the vendor pins are honest.
