# SourceOS M2 lifecycle proof v0

This document defines the local deterministic proof path for the SourceOS M2 demo after the v0 contract surface lands.

The proof path is deliberately repo-local and deterministic. It does not perform live boot, disk writes, GitHub token use, or nlboot execution. It proves that the control-plane object loop can be generated, validated, indexed, compliance-evaluated, and surfaced through a Truth Plane current manifest without hidden state.

## Generated artifacts

`tools/build_sourceos_m2_lifecycle_proof.py` writes:

- `config-source.json`
- `release-set.json`
- `boot-release-set.json`
- `fingerprint.json`
- `compliance-result.json`
- `proof-index.json`

`tools/build_sourceos_truth_current_manifest.py` adds:

- `truth-current-manifest.json`

By default the bundle is written under:

```bash
artifacts/sourceos/m2-lifecycle-proof
```

## Command

Generate the lifecycle proof bundle:

```bash
python tools/build_sourceos_m2_lifecycle_proof.py
```

Generate the Truth Plane current manifest from that bundle:

```bash
python tools/build_sourceos_truth_current_manifest.py
```

Smoke test the full local spine:

```bash
python tools/smoke_sourceos_m2_lifecycle_proof.py
```

## What this proves

The v0 proof demonstrates the SourceOS control-plane lifecycle spine:

1. ConfigSource is declared as a Git/Nix lifecycle input.
2. ReleaseSet is assigned to the M2 demo device.
3. BootReleaseSet is available for recovery/install/live behavior.
4. Fingerprint reports observed state.
5. ComplianceResult compares observed state to assigned state.
6. ProofIndex ties the generated objects together with digests.
7. TruthCurrentManifest exposes the current trusted state and intended `/truth/*` service surface.

## Truth Plane surface

The generated Truth Plane current manifest declares these intended endpoint contracts:

- `GET /truth/current-manifest`
- `GET /truth/boot-release-set/current`
- `GET /truth/fingerprint/current`
- `GET /truth/compliance/current`

The v0 smoke path asserts that the TruthCurrentManifest references the generated ReleaseSet, BootReleaseSet, Fingerprint, ComplianceResult, and required endpoint paths. It also asserts that compliant state makes the fixture eligible for Agentplane, GAIA ingest, and Sherlock evidence paths.

## What this does not prove yet

- It does not prove an Apple Silicon boot-picker entry.
- It does not execute nlboot.
- It does not write disk partitions.
- It does not use live GitHub tokens.
- It does not provide the website UI.
- It does not run a local `/truth/*` service.
- It does not claim hardware-root attestation.

Those remain separate implementation tranches.

## Sociosphere integration

Sociosphere issue `SocioProphet/sociosphere#190` tracks workspace-governance awareness for SourceOS contract and lifecycle artifacts.
