# Fog Stack signed manifest verification

This document defines the smallest repo-native meaning of **signed-manifest verification** for Fog Stack.

## Goal

Move from:
- unsigned manifest stubs
- a helper that can attach signature metadata

to:
- a helper that can check whether a manifest claiming to be signed actually carries the required signature metadata shape.

## Minimal verification scope in this phase

The verification helper in this phase checks only manifest-local conditions:
- `signed` is present and boolean
- if `signed: true`, a `signature` object exists
- `signature.type` is one of the supported enum values
- `signature.ref` is present and non-empty

This phase does **not** verify the cryptographic validity of the signature reference.

## Example

```bash
python3 tools/verify_fogstack_manifest_signature.py \
  --manifest releases/manifests/fogstack.access-v0.1.manifest.json \
  --require-signed \
  --json
```

## Future evolution

The next tranche after this helper should define:
- how CI resolves and verifies the signature reference
- how signature verification results are emitted as release evidence
- how release manifests and validation records link to the same evidence package
