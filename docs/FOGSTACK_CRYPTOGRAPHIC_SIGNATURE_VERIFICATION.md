# Fog Stack cryptographic signature verification

This document defines the first repo-native shape for **cryptographic signature verification results**.

## Goal

Move from:
- manifests that can carry signature metadata
- helpers that attach signature metadata
- helpers that verify signed-manifest shape
- trust records that reference signature evidence

to:
- a separate `FogStackCryptographicSignatureVerificationRecord` that captures the result of an actual external verification step.

## Minimal flow

1. run an external cryptographic verification step for the signature artifact
2. capture its JSON or normalized evidence output
3. run `tools/emit_fogstack_cryptographic_signature_verification_record.py`
4. write the resulting record into a deterministic release-evidence location

## Example

```bash
python3 tools/emit_fogstack_cryptographic_signature_verification_record.py \
  --verification-evidence /tmp/fogstack.access.cosign.verify.json \
  --bundle-id fogstack.access \
  --version 0.1.0 \
  --manifest-ref releases/manifests/fogstack.access-v0.1.manifest.json \
  --signature-ref artifact://release/fogstack.access-v0.1.sig \
  --verification-tool cosign \
  --manifest-digest sha256:deadbeef \
  --key-ref key://release/cosign.pub \
  --validation-record-ref releases/evidence/fogstack.access-v0.1.validation.record.json \
  --signature-verification-record-ref releases/evidence/fogstack.access-v0.1.signature-verification.record.json \
  --signature-trust-record-ref releases/evidence/fogstack.access-v0.1.signature-trust.record.json \
  --release-evidence-index-ref releases/evidence/fogstack.access-v0.1.evidence.index.json \
  --output /tmp/fogstack.access-v0.1.crypto-verification.record.json
```

## What this phase does not yet provide

This phase still does not provide:
- integrated execution of `cosign verify` or equivalent inside this helper
- registry resolution of signature refs
- CI-enforced verified truth records
- automatic mutation/back-linking of existing artifacts

Those remain for the next release-engineering tranche.
