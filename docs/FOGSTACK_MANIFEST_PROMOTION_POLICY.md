# Fog Stack manifest promotion policy

This document defines the repo-native policy surface for Fog Stack manifest promotion.

## Goal

Move from unrestricted manifest promotion to governed promotion transitions that are checked against an explicit policy catalog.

## Policy model

The policy catalog lives at:
- `catalog/fogstack-manifest-promotion-policy-v0.1.yaml`

It currently defines:
- whether explicit target channel/support-state values are required
- which channel/support-state transitions are allowed

## Minimal flow

1. build the canonical publication set
2. promote the publication set with `tools/promote_fogstack_manifest_publication_set.py`
3. check the promoted output with `tools/check_fogstack_manifest_promotion_policy.py`
4. only treat the promoted set as valid if the checker passes

## Example

Run the checker against:
- the promoted `manifest-publication-set.json`
- `catalog/fogstack-manifest-promotion-policy-v0.1.yaml`

## What this phase provides

- explicit transition policy for channel/support-state movement
- CI enforcement of that policy in the manifest-promotion workflow
- prior-state carry-through in the promoted publication set so transitions are auditable

## What this phase does not yet provide

- approval workflows with human sign-off
- external signing as a requirement for promotion
- registry publication gates

Those remain later steps.
