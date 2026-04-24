# Fog Stack release seal signatures

This document defines the first repo-native meaning of a **signed release seal**.

## Goal

Move from:
- an unsigned `FogStackReleaseSeal`
- a helper that computes `release_root_hash`

to:
- a seal that can explicitly carry signature metadata
- a helper that can verify the signed-seal shape before later cryptographic verification layers exist.

## Minimal flow

1. emit the release seal with `tools/emit_fogstack_release_seal.py`
2. attach signature metadata with `tools/attach_fogstack_release_seal_signature.py`
3. verify the signed-seal shape with `tools/verify_fogstack_release_seal_signature.py`

## Example

```bash
python3 tools/attach_fogstack_release_seal_signature.py \
  --seal releases/seals/fogstack.access-v0.1.seal.json \
  --signature-type cosign \
  --signature-ref artifact://release/fogstack.access-v0.1.seal.sig \
  --output /tmp/fogstack.access-v0.1.signed.seal.json

python3 tools/verify_fogstack_release_seal_signature.py \
  --seal /tmp/fogstack.access-v0.1.signed.seal.json \
  --require-signed \
  --json
```

## What this phase provides

- seal schema can carry `signed` + `signature`
- helper to attach signature metadata to a seal
- helper to verify signed-seal metadata shape

## What this phase does not yet provide

- cryptographic verification of the seal signature payload
- automatic CI verification of the seal signature
- publication of signed seals
- linking the seal signature into the broader trust graph

Those remain later steps.
