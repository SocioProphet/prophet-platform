# identity-twin

The prophet-platform surface for the **Multiverseal Twin** — a federation-facing
identity/reputation projection of a sovereign core. This app *consumes* the twin library
(VSA medium + VRF references + interferometric read) rather than reimplementing it.

## Status
**Service.** The twin library is vendored and the HTTP surface (`app/`) now consumes it —
`attest / verify / recall / medium / diff / interfere` + `health` — proof-gated by
`tests/test_http_main.py`. Durable persistence of the attested medium (in-memory today) and
cluster deploy are the next slice.

## HTTP surface (`app.main:app`, uvicorn on :8080)
- `POST /attest {context, value}` — mints a VRF context reference and binds the value against it
  (**reference-at-ingest**, never bare); returns the `VerifiableReference` + the new medium digest.
- `POST /verify {context, proof, verify_key}` — is the reference genuine? **Fail-closed**: a forged
  or malformed reference is unverifiable, not a 500.
- `POST /recall {context, value}` — fidelity of the recalled value against a claimed value (1.0 = exact).
- `GET /medium` — the tamper-evident fingerprint (digest + record count) of the federation-facing
  medium; never the raw hypervector.
- `POST /diff {from_digest}` — the interferometric **fringe** between a prior medium snapshot and
  the current one (phase energy + where state moved), not a scalar score.
- `POST /interfere {value, context_a, context_b}` — the thesis read: the same value under two
  provenances is magnitude-identical (**score-blind**) yet has a nonzero phase fringe (**fringe-visible**).
- `GET /health` — liveness.

The sovereign core's master key is sealed from `$IDENTITY_TWIN_SEED` (64 hex chars); absent → an
ephemeral dev key. No raw hypervector ever crosses the HTTP boundary.

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
`pytest -q apps/identity-twin/tests` (needs `numpy` + `cryptography` + `fastapi` + `httpx`) — the
smoke test proves the vendored twin attests/recalls/verifies/tamper-detects and that the vendor
pins are honest; the HTTP test proves every endpoint wires it correctly and fails closed.
