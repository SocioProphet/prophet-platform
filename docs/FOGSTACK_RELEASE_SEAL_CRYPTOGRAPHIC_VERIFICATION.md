# Fog Stack release seal cryptographic verification

This document defines the first repo-native shape for **cryptographic verification of a release seal signature**.

## Goal

Move from:
- a release seal that can carry signature metadata
- helpers that attach and verify signed-seal shape

to:
- a separate `FogStackReleaseSealCryptographicVerificationRecord` that captures the result of an actual verification step over the seal signature.

## Minimal flow

1. produce or obtain external verification evidence for the seal signature
2. run `tools/emit_fogstack_release_seal_cryptographic_verification_record.py`
3. persist the resulting record into the release evidence set

## Example

```bash
python3 tools/emit_fogstack_release_seal_cryptographic_verification_record.py \
  --verification-evidence /tmp/fogstack.access.seal.verify.json \
  --bundle-id fogstack.access \
  --version 0.1.0 \
  --seal-ref releases/seals/fogstack.access-v0.1.seal.json \
  --signature-ref artifact://release/fogstack.access-v0.1.seal.sig \
  --verification-tool cosign \
  --seal-root-hash sha256:deadbeef \
  --output /tmp/fogstack.access-v0.1.seal.crypto-verification.record.json
```

## Digest consistency rule

If both of the following are present:
- `seal_root_hash`
- external `verified_root_hash`

then the emitter computes `seal_root_hash_matches`.

A mismatch should be treated as a failed cryptographic verification result even if the external tool reported pass.

## What this phase does not yet provide

This phase still does not provide:
- direct invocation of external verification tools
- CI-enforced execution
- automatic linkage of the seal verification record into the broader trust graph

Those remain later steps.
