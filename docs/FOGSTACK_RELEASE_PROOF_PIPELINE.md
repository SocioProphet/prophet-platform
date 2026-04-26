# Fog Stack release proof pipeline

This document defines the first repo-native **release proof pipeline** for the seal side of Fog Stack.

## Goal

Move from separate helpers for:
- external release seal verification execution
- release seal cryptographic verification record emission
- release seal artifact backlinking

to:
- one wrapper that runs the external seal verifier, emits the seal cryptographic verification record, and then links the resulting artifacts into the seal-side trust graph.

## Minimal flow

1. provide the release seal, bundle identity/version, signature reference, and evidence index
2. optionally provide canonical contract/deployment/runtime/policy surface refs
3. invoke `tools/run_fogstack_release_proof_pipeline.py`
4. pass the external verifier command after `--`
5. the wrapper emits the seal cryptographic verification record and updates the seal-side backlinks

## Example

Use the wrapper with a seal file, a signature reference, output paths for evidence and the cryptographic verification record, an evidence index path, optional canonical surface refs, and the external verifier command after `--`.

```bash
python tools/run_fogstack_release_proof_pipeline.py \
  --tool cosign \
  --seal releases/seals/fogstack.access-v0.1.seal.json \
  --bundle-id fogstack.access \
  --version 0.1.0 \
  --signature-ref artifact://release/fogstack.access-v0.1.seal.sig \
  --evidence-output releases/evidence/fogstack.access-v0.1.seal.verify.json \
  --seal-crypto-record releases/evidence/fogstack.access-v0.1.seal.crypto-verification.record.json \
  --evidence-index releases/evidence/fogstack.access-v0.1.evidence.index.json \
  --canonical-contract-surface-ref schema://fogstack/access/contracts/v0.1 \
  --canonical-deployment-surface-ref k8s://fogstack/access/deployment/v0.1 \
  --canonical-runtime-surface-ref runtime://fogstack/access/runtime/v0.1 \
  --canonical-policy-surface-ref policy://fogstack/access/policy/v0.1 \
  -- cosign verify ...
```

## Canonical surface refs

The release evidence index can carry canonical refs for the surfaces that define the release boundary:

- `canonical_contract_surface_ref`
- `canonical_deployment_surface_ref`
- `canonical_runtime_surface_ref`
- `canonical_policy_surface_ref`

These refs are optional. When provided to the release proof pipeline, they are passed to `tools/link_fogstack_release_seal_artifacts.py` and persisted into the `FogStackReleaseEvidenceIndex` alongside the release seal and cryptographic verification record refs.

## What this phase provides

- one orchestrated proof step for the seal side of the trust graph
- automatic invocation of the seal verification wrapper
- automatic backlink insertion after the cryptographic record is produced
- optional canonical surface refs in the release evidence index

## What this phase does not yet provide

- CI enforcement of the proof pipeline
- mutation of the non-seal side of the wider trust graph
- registry publication of the resulting proof set
- validation that canonical surface refs resolve to live external systems

Those remain later steps.
