# Fog Stack release seal verification execution

This document defines the first repo-native execution wrapper for external verification of a signed Fog Stack release seal.

## Goal

Move from:
- a release seal
- seal signature support
- a cryptographic verification record shape

to:
- one wrapper that runs an external verifier command, captures its output, normalizes it, compares the verified root hash to the seal's `release_root_hash`, and emits the seal cryptographic verification record.

## Minimal flow

1. provide the release seal and bundle identity/version
2. invoke `tools/run_external_fogstack_release_seal_verifier.py`
3. pass the external verifier command after `--`
4. the wrapper captures stdout JSON, normalizes it, and emits the seal cryptographic verification record

## Example

```bash
python3 tools/run_external_fogstack_release_seal_verifier.py \
  --tool cosign \
  --seal releases/seals/fogstack.access-v0.1.seal.json \
  --bundle-id fogstack.access \
  --version 0.1.0 \
  --signature-ref artifact://release/fogstack.access-v0.1.seal.sig \
  --evidence-output /tmp/fogstack.access.seal.verify.json \
  --record-output /tmp/fogstack.access.seal.crypto-verification.record.json \
  -- cosign verify-blob --signature artifact://release/fogstack.access-v0.1.seal.sig seal.json
```

## Root-hash consistency rule

If both of the following are present:
- `seal.release_root_hash`
- external `verified_root_hash`

then the runner passes both into the seal cryptographic verification record emitter, which computes `seal_root_hash_matches`.

A mismatch should be treated as a failed verification result even if the external tool reported pass.

## What this phase does not yet provide

This wrapper still does not:
- interpret every verifier's output format automatically beyond the minimal normalization logic
- enforce CI execution
- mutate the wider trust graph after verification
- guarantee registry resolution of signature references

Those remain later steps.
