# SourceOS Truth Plane M2 spine v0

This document defines the first concrete Boot & Trust vertical slice for the SourceOS M2 lifecycle proof.

The slice connects the existing local lifecycle proof objects to a queryable Truth Plane surface. It remains deterministic and side-effect-free: it does not create an Apple Silicon boot-picker entry, run `nlboot`, fetch artifacts, mutate disks, invoke `kexec`, or claim hardware-root attestation.

## Purpose

The current demo spine is:

```text
ConfigSource
-> ReleaseSet
-> BootReleaseSet
-> Fingerprint
-> ComplianceResult
-> ProofIndex
-> TruthCurrentManifest
```

`TruthCurrentManifest` is the web/API-facing trust summary that downstream surfaces can consume before accepting work or rendering node trust status.

## Contract

The contract lives at:

- `contracts/sourceos/truth-current-manifest.v0.schema.json`

A canonical M2 example lives at:

- `contracts/sourceos/examples/truth-current-manifest.m2-demo.v0.json`

The generated deterministic fixture is emitted as:

- `artifacts/sourceos/m2-lifecycle-proof/truth-current-manifest.json`

## Fixture builder

Run the local proof generator:

```bash
python tools/build_sourceos_m2_lifecycle_proof.py
```

Then emit the Truth Plane current manifest:

```bash
python tools/build_sourceos_truth_current_manifest.py
```

The smoke harness performs both operations:

```bash
python tools/smoke_sourceos_m2_lifecycle_proof.py
```

## Local endpoint shape

`TruthCurrentManifest.truth_plane.endpoints` defines the intended service surface for the next implementation tranche:

| Endpoint | Returns | Purpose |
|---|---|---|
| `GET /truth/current-manifest` | `SourceOSTruthCurrentManifest` | Primary node trust summary |
| `GET /truth/boot-release-set/current` | `SourceOSBootReleaseSet` | Current boot/recovery assignment |
| `GET /truth/fingerprint/current` | `SourceOSFingerprint` | Observed runtime state |
| `GET /truth/compliance/current` | `SourceOSComplianceResult` | Drift/compliance result |

The v0 artifact is marked `service_shape: fixture`. A later service implementation can expose the same objects over HTTP, gRPC, or TriTRPC without changing the contract family.

## Eligibility rule

For this tranche, downstream eligibility is deliberately simple:

```text
agentplane_eligible = gaia_ingest_eligible = sherlock_evidence_eligible = (ComplianceResult.status == compliant)
```

That gives the demo a concrete, visible gate:

- Agentplane should not accept local-first apply/work eligibility if the node state is unknown or drifted.
- GAIA ingest should not mint strong runtime proofs from a node whose assigned release is non-compliant.
- Sherlock evidence records should not claim full provenance when the producing node lacks a compliant current manifest.

## Integrity model

The v0 Truth Plane fixture records SHA-256 digests for the generated local proof objects. It is intentionally marked:

```json
"signature_state": "unsigned_fixture"
```

This is honest for the current repo-local deterministic proof. Later tranches should advance this to signed manifests backed by release keys and, for Apple Silicon, hardware-root-adjacent observations that are represented explicitly rather than mislabeled as TPM PCR sealing.

## Non-goals in this tranche

This slice does not implement:

- Apple Silicon boot-picker installation.
- Apple Secure Enclave / LocalPolicy binding.
- TPM 2.0 PCR sealing.
- live `nlboot` execution.
- artifact fetching.
- disk writes.
- `kexec` execution.
- website UI.
- GAIA live ingest gating.
- Agentplane runtime enforcement.

Those remain implementation tranches, but now they have a single current-manifest object to consume.

## Next implementation tranche

The next useful tranche is a tiny local service adapter:

```text
artifacts/sourceos/m2-lifecycle-proof/*.json
-> read-only local Truth Plane service
-> /truth/* endpoints
-> Agentplane preflight check
```

After that, wire the web trust panel to `/truth/current-manifest` and make GAIA/Sherlock proof minting depend on the same eligibility state.
