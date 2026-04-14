# Fog Stack CI validation artifacts

This document defines the first CI-oriented path for Fog Stack validation records.

## Goal

Turn verifier output into a schema-conforming `FogStackValidationRecord` that can later be referenced by release manifests and release evidence packages.

## Minimal flow

1. run `python3 tools/validate_fogstack.py` or `python3 tools/fogstack_verify.py ... --json`
2. capture the verifier JSON output
3. run `python3 tools/emit_fogstack_validation_record.py` to convert that JSON into a `FogStackValidationRecord`
4. write the record into a deterministic artifact location under CI workspace or release packaging output

## Example

```bash
python3 tools/fogstack_verify.py bundles/fogstack.access-v0.1.yaml --json > /tmp/fogstack.verify.json
python3 tools/emit_fogstack_validation_record.py \
  --verifier-json /tmp/fogstack.verify.json \
  --bundle-id fogstack.access \
  --version 0.1.0 \
  --source ci \
  --evidence-ref artifact://ci/fogstack.access.verify.json \
  --output /tmp/fogstack.access.validation.record.json
```

## What counts as executed evidence

A record should only be treated as release evidence when:
- `source` is `ci`
- the underlying verifier JSON came from the native validation path
- the bundle/rulepack on disk match the release candidate being published

## Out of scope in this phase

- automatic CI wiring
- artifact upload/storage backend
- cryptographic signing of validation records
- release-manifest back-linking automation
