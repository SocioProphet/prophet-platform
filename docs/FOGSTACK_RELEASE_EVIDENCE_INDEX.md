# Fog Stack release evidence index

This document defines the first repo-native **release evidence index** for Fog Stack.

## Goal

The release-engineering surfaces now produce separate machine-readable artifacts for one bundle version:
- a release manifest
- a validation record
- a signature verification record
- a signature trust record

The purpose of the release evidence index is to provide one stable object that links those artifact refs together for a single bundle release.

## Minimal flow

1. prepare or update the release manifest
2. emit the validation record
3. emit the signature verification record
4. emit the signature trust record
5. run `tools/emit_fogstack_release_evidence_index.py` to produce the linking object

## Example

```bash
python3 tools/emit_fogstack_release_evidence_index.py \
  --bundle-id fogstack.access \
  --version 0.1.0 \
  --manifest-ref releases/manifests/fogstack.access-v0.1.manifest.json \
  --validation-record-ref releases/evidence/fogstack.access-v0.1.validation.record.json \
  --signature-verification-record-ref releases/evidence/fogstack.access-v0.1.signature-verification.record.json \
  --signature-trust-record-ref releases/evidence/fogstack.access-v0.1.signature-trust.record.json \
  --output /tmp/fogstack.access-v0.1.evidence.index.json
```

## What this phase does not yet provide

This phase does not yet provide:
- automatic generation of the index in CI
- back-link insertion into the manifest or evidence records
- publication or registry integration for the index itself

Those remain for the next release-engineering tranche.
