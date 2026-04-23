# Fog Stack signature verification pipeline

This document defines the first repo-native pipeline from external verification output to a cryptographic verification record.

## Goal

Move from:
- external tool output
- normalized verification evidence
- a cryptographic verification record shape

to:
- one repo-native helper that normalizes the external evidence, checks digest consistency, and emits the cryptographic verification record.

## Minimal flow

1. prepare the release manifest
2. capture external verification output in JSON form
3. run `tools/run_fogstack_signature_verification_pipeline.py`
4. persist the normalized evidence and cryptographic verification record into deterministic release-evidence paths

## Example

```bash
python3 tools/run_fogstack_signature_verification_pipeline.py \
  --manifest releases/manifests/fogstack.access-v0.1.manifest.json \
  --raw-evidence /tmp/fogstack.access.cosign.verify.json \
  --tool cosign \
  --bundle-id fogstack.access \
  --version 0.1.0 \
  --normalized-output /tmp/fogstack.access.normalized.verify.json \
  --record-output /tmp/fogstack.access.crypto-verification.record.json
```

## Digest consistency rule

If both of the following are present:
- `manifest.bundle_digest`
- normalized `verified_digest`

then the pipeline computes `manifest_digest_matches` and includes it in the record summary.

A digest mismatch should be treated as a failed cryptographic verification result even if the external tool reported pass.

## Out of scope in this phase

This helper still does not:
- invoke `cosign verify` or equivalent itself
- enforce CI execution
- mutate manifests or trust records automatically

Those remain later steps.
