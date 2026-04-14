# Fog Stack signature verification evidence

This document defines the first repo-native shape for **signature verification evidence**.

## Goal

Move from:
- manifests that can carry signature metadata
- a helper that can attach signature metadata
- a helper that can check signed-manifest shape

to:
- a separate `FogStackSignatureVerificationRecord` that can link:
  - back to the manifest being verified
  - sideways to the validation record for the same bundle version

## Minimal flow

1. verify the signed-manifest shape with `tools/verify_fogstack_manifest_signature.py`
2. capture the verification JSON output
3. run `tools/emit_fogstack_signature_verification_record.py`
4. write the resulting record into a deterministic release-evidence location

## Example

```bash
python3 tools/verify_fogstack_manifest_signature.py \
  --manifest releases/manifests/fogstack.access-v0.1.manifest.json \
  --require-signed \
  --json > /tmp/fogstack.access.signature.verify.json

python3 tools/emit_fogstack_signature_verification_record.py \
  --verification-json /tmp/fogstack.access.signature.verify.json \
  --bundle-id fogstack.access \
  --version 0.1.0 \
  --manifest-ref releases/manifests/fogstack.access-v0.1.manifest.json \
  --signature-ref artifact://release/fogstack.access-v0.1.sig \
  --validation-record-ref releases/evidence/fogstack.access-v0.1.validation.record.json \
  --output /tmp/fogstack.access.signature-verification.record.json
```

## What this phase does not yet provide

This phase still does not provide:
- cryptographic verification of the signature payload itself
- registry resolution of signature refs
- automatic back-linking into the manifest or validation record
- CI-emitted verified truth records

Those remain the next tranche after this helper + record shape land.
