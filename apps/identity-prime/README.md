# identity-prime

`identity-prime` is the intended platform runtime lane for identity normalization and first-party session shaping inside `prophet-platform`.

This directory is currently a **placeholder runtime landing zone**.

It exists so future implementation work has a clear, bounded home and does not drift into unrelated gateway or service surfaces.

## Why this lane exists

The upstream SocioProphet agent standards define the platform posture for:

- authentication, session, and recovery
- credential enrollment and authenticator lifecycle
- enterprise federation and claim mapping
- workload and service identity

`prophet-platform` is the runtime and deployment hub where those upstream standards become platform behavior.

`identity-prime` is the intended runtime seam for that work.

## Intended responsibilities

This lane is expected to cover:

- first-party session orchestration
- normalization of external identity proof into internal subject / tenant / assurance context
- platform-facing identity contracts
- identity/session lifecycle evidence emission

## Current status

This subtree is a designated runtime landing zone and boundary marker, plus a
first promoted kernel.

### Promoted: prime kernel (`src/identity_prime/prime_kernel.py`)

The proven "identity is prime" kernel from the `identity_is_prime_reference`
toy impl has been promoted here as a clean, self-contained module:

- **prime-topic basis** — identity-as-prime encode/decode (`encode_topics` /
  `decode_topics`)
- **policy veto** — forbidden prime-pair / feature-key / sensitive-prime-in-ad-realm
  checks (`Policy`, `default_policy`)
- **entity resolution** — blocking + stable-exclusive conflict + policy veto on
  merges (`resolve_entities`)
- **bounded congruence** — modular nonce-stream leak detection (`NonceStream`)

Output is bound to the **canonical** platform schema
`schemas/proof-artifact.schema.json` (Trust-First Proof Artifact v0.1), not the
toy reference schema. See `emit_proof_artifact` for the toy→canonical mapping
(notably toy `status`→canonical `result`, free-text claim→`claim.kind="ifc_no_flow"`,
toy domains→the constrained `labels`/`capabilities`/`congruence` enum, and
`precision.mode="Exact"`).

Run the end-to-end Michael-trace conformance test:

```
cd apps/identity-prime
pip install -r requirements-test.txt
pytest
```

### Intentionally deferred (out of scope for this kernel promotion)

- `surface343` projection
- `naming_projection`
- the recommendation loop
- real proof-artifact signing (left as `TODO(cosign)`, consistent with how the
  repo defers artifact signing elsewhere — `policy_bundle.sig` is `UNSIGNED`)

## Review rule

Future PRs that touch this lane should state:

- which upstream auth standard(s) they implement
- which ingress or session seam they bind
- what they intentionally defer

## Related platform seams

- `standards.lock.yaml`
- `contracts/identity/`
- gateway/browser ingress
- enterprise identity ingress
- service-to-service identity handoff
