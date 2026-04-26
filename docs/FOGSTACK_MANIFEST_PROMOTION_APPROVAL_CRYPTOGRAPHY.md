# Fog Stack manifest promotion approval cryptography

This document defines the repo-native cryptographic verification layer for Fog Stack manifest promotion approval.

## Goal

Move from approval records that carry signature metadata to approval records whose signature payload is verified in CI, with approver role policy checked independently.

## Approval signature verification

The OpenSSL-backed verifier lives at:
- `tools/run_openssl_fogstack_manifest_promotion_approval_verifier.py`

It verifies an approval-record signature with a public key and emits JSON verification output with:
- approval record reference
- approval record digest
- signature reference
- verifier
- key reference
- pass/fail status

## Approver policy

The approver policy catalog lives at:
- `catalog/fogstack-manifest-promotion-approver-policy-v0.1.yaml`

It defines:
- required approval roles
- allowed approver identities
- roles allowed for each approver

## CI enforcement

The manifest-promotion workflow now enforces:
1. publication-set promotion policy
2. approval metadata
3. approver role policy
4. cryptographic verification of the approval-record signature

## What this phase does not yet provide

- external identity-provider backed approver resolution
- long-lived release signing keys
- registry publication gates

Those remain later steps.
