# Fog Stack signature verification execution

This document defines the first repo-native execution wrapper for external signature verification.

## Goal

Move from:
- a normalization contract for external signature verification output
- a repo-native pipeline runner that transforms normalized evidence into a cryptographic verification record

to:
- one wrapper that runs an external verifier command, captures its output, normalizes it, and feeds the Fog Stack verification pipeline.

## Minimal flow

1. provide a release manifest and bundle identity/version
2. invoke `tools/run_external_fogstack_signature_verifier.py`
3. pass the external verifier command after `--`
4. the wrapper captures stdout JSON, normalizes it, and emits the cryptographic verification record

## Example

```bash
python3 tools/run_external_fogstack_signature_verifier.py \
  --tool cosign \
  --manifest releases/manifests/fogstack.access-v0.1.manifest.json \
  --bundle-id fogstack.access \
  --version 0.1.0 \
  --raw-output /tmp/fogstack.access.raw.verify.json \
  --normalized-output /tmp/fogstack.access.normalized.verify.json \
  --record-output /tmp/fogstack.access.crypto-verification.record.json \
  -- cosign verify-blob --signature artifact://release/fogstack.access-v0.1.sig bundle.tar.gz
```

## What this phase does not yet provide

This wrapper still does not:
- interpret every verifier's output format automatically beyond the normalized contract
- enforce CI execution
- mutate manifest/trust artifacts after verification
- guarantee registry resolution of signature references

Those remain later steps.
