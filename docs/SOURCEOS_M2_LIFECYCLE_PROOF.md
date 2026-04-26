# SourceOS M2 lifecycle proof v0

This document defines the local deterministic proof path for the SourceOS M2 demo after the v0 contract surface lands.

The proof path is deliberately repo-local and deterministic. It does not perform live boot, disk writes, GitHub token use, or nlboot execution. It proves that the control-plane object loop can be generated, validated, indexed, and compliance-evaluated without hidden state.

## Generated artifacts

`tools/build_sourceos_m2_lifecycle_proof.py` writes:

- `config-source.json`
- `release-set.json`
- `boot-release-set.json`
- `fingerprint.json`
- `compliance-result.json`
- `proof-index.json`

By default the bundle is written under:

```bash
artifacts/sourceos/m2-lifecycle-proof
```

## Command

```bash
python tools/build_sourceos_m2_lifecycle_proof.py
```

Smoke test:

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

## What this does not prove yet

- It does not prove an Apple Silicon boot-picker entry.
- It does not execute nlboot.
- It does not write disk partitions.
- It does not use live GitHub tokens.
- It does not provide the website UI.

Those remain separate implementation tranches.

## Sociosphere integration

Sociosphere issue `SocioProphet/sociosphere#190` tracks workspace-governance awareness for SourceOS contract and lifecycle artifacts.
