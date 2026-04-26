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

## Canonical CLI

```bash
python3 tools/run_fogstack_signature_verification_pipeline.py \
  --manifest releases/manifests/fogstack.access-v0.1.manifest.json \
  --external-evidence /tmp/fogstack.access.cosign.verify.json \
  --out /tmp/fogstack.access.crypto-verification.record.json
```

The helper also preserves the older aliases:
- `--raw-evidence` for `--external-evidence`
- `--record-output` for `--out`

Use `--normalized-output` when the normalized external evidence object should be persisted separately.

## Digest consistency rule

The pipeline requires:
- `manifest.bundle_digest`
- normalized `verified_digest`

The cryptographic verification record is `verified` only when the external evidence status is `pass` and the verified digest exactly matches the manifest bundle digest.

A digest mismatch is a hard failed verification result. The helper still emits the failed record when an output path is provided so reviewers can inspect the evidence, but the process exits nonzero.

## Exit codes

- `0`: pass / verified
- `1`: warning / non-fatal shape-only record
- `2`: failure, including digest mismatch or external verification failure
- `3`: invalid input or tool usage error, including malformed JSON, missing inputs, missing manifest digest, or missing verified digest

## Out of scope in this phase

This helper still does not:
- invoke `cosign verify` or equivalent itself
- enforce CI execution
- mutate manifests or trust records automatically

Those remain later steps.
