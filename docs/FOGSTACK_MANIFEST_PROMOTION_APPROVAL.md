# Fog Stack manifest promotion approval

This document defines the repo-native approval surface for Fog Stack manifest promotion.

## Goal

Move from policy-valid promotion to promotion that is also approval-bound, signature-aware, and digest-bound to the promoted manifest publication set.

## Approval record

The approval record schema lives at:
- `schemas/release/fogstack-manifest-promotion-approval-record-v0.1.schema.json`

The approval record captures:
- promoted publication-set reference
- promoted publication-set digest
- target channel and support state
- required approval count
- approver identities and roles
- signature metadata

## Minimal flow

1. build the canonical publication set
2. promote it through the manifest promotion helper
3. check the promotion policy
4. emit a promotion approval record
5. check that the approval record is approved, sufficiently approved, signed, and digest-bound to the promoted set

## What this phase provides

- explicit approval record shape
- approval emitter
- approval checker
- CI enforcement that the promoted set has a signed approval record

## What this phase does not yet provide

- external identity-provider backed approver resolution
- cryptographic verification of the approval signature payload
- registry publication gates

Those remain later steps.
