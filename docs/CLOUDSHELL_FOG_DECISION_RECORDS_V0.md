# cloudshell-fog Production Decision Records

This document defines how to use the production decision record artifacts for `cloudshell-fog`.

## Purpose

The platform now contains examples and a machine-readable contract for the unresolved production decisions that cannot be guessed safely.

These records are intended to capture, review, and approve:

- the exact gateway image digest
- the chosen secret-source profile
- the chosen signature trust profile
- the policy bundle path in use
- the federal fallback region when applicable
- the evidence references that justify promotion

## Files

- `contracts/cloudshell-fog/production-decision-record-v0.json`
- `apps/cloudshell-fog/production-decision-record.standard.example.yaml`
- `apps/cloudshell-fog/production-decision-record.federal.example.yaml`
- `tools/validate-cloudshell-fog-decision-records.sh`

## Rule

No production promotion should occur until:

1. the relevant decision record is copied from the example and completed with real values
2. placeholders are removed
3. the readiness validator passes
4. the named approvers have actually reviewed the deployment inputs

## Relationship to other artifacts

These decision records complement, but do not replace:

- deployment inventory examples
- secret-source profiles
- signature trust profiles
- runtime-v2 guide
- production-inputs checklist

Together, they turn the remaining operator choices into explicit, reviewable state.
