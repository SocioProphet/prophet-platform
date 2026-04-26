# Fog Stack release publication gate

This document defines the repo-native publication gate for Fog Stack promoted manifest sets.

## Goal

Move from approved and signature-verified promotion to a final publication gate that verifies the promotion can be published by a permitted release identity.

## Gate policy

The gate policy lives at:
- `catalog/fogstack-release-publication-gate-policy-v0.1.yaml`

It currently requires:
- approved promotion approval status
- passing approval-signature verification
- an allowed release identity

## Gate record

The gate record schema lives at:
- `schemas/release/fogstack-release-publication-gate-record-v0.1.schema.json`

The gate record captures:
- publication set reference
- approval record reference
- approval-signature verification reference
- release identity reference
- pass/fail checks

## Minimal flow

1. build and promote the manifest publication set
2. enforce promotion policy
3. emit and verify the signed promotion approval record
4. emit a release identity record
5. evaluate the release publication gate with `tools/emit_fogstack_release_publication_gate_record.py`
6. only publish the promoted manifest set if the gate passes

## What this phase provides

- explicit publication gate policy
- release identity binding
- gate record emission
- CI enforcement in the manifest-promotion workflow

## What this phase does not yet provide

- registry publication of the gated artifact set
- external identity-provider backed release identity
- long-lived KMS/HSM-backed signing keys

Those remain later steps.
