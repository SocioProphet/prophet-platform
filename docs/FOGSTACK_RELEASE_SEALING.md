# Fog Stack release sealing

This document defines the first repo-native **release sealing** step for Fog Stack.

## Goal

Move from linked release/trust artifacts to a deterministic, tamper-evident summary hash for a bundle version.

## Minimal flow

1. choose the artifact files that define the release/trust state for a bundle version
2. run `tools/emit_fogstack_release_seal.py`
3. persist the resulting `FogStackReleaseSeal` as part of the release evidence set

## Example

```bash
python3 tools/emit_fogstack_release_seal.py \
  --bundle-id fogstack.access \
  --version 0.1.0 \
  --artifact manifest releases/manifests/fogstack.access-v0.1.manifest.json \
  --artifact validation releases/evidence/fogstack.access-v0.1.validation.record.json \
  --artifact sigverify releases/evidence/fogstack.access-v0.1.signature-verification.record.json \
  --artifact sigtrust releases/evidence/fogstack.access-v0.1.signature-trust.record.json \
  --artifact evidenceindex releases/evidence/fogstack.access-v0.1.evidence.index.json \
  --output /tmp/fogstack.access-v0.1.seal.json
```

## What this phase provides

- deterministic SHA-256 hashes for each referenced artifact
- a deterministic `release_root_hash` computed from the sorted artifact-hash set
- a single machine-readable seal object for a bundle version

## What this phase does not yet provide

- Merkle proofs
- signature over the seal itself
- CI enforcement of the seal
- automatic rebuild of the seal when any artifact changes

Those remain the next release-engineering tranche.
