# cloudshell-fog Release Evidence v0

This document defines the release-evidence lane for `cloudshell-fog` inside `prophet-platform`.

## 0. Why this exists

The platform already carries runtime deployment, policy, inventory, and go-live controls for `cloudshell-fog`. What was still missing was a clear link from those deployment assets to the existing Fog Stack signed-manifest model and the accepted Tekton + Argo GitOps strategy.

This document provides that link.

## 1. Existing platform conventions reused here

### Fog Stack signed manifests

`prophet-platform` already defines a repo-native meaning for signed Fog Stack bundle manifests and includes a helper at:

- `tools/attach_fogstack_manifest_signature.py`

That helper adds:

- `signed: true`
- `signature.type`
- `signature.ref`

to a manifest JSON object.

### Tekton + Argo GitOps

The current platform standard accepts:

- Tekton for build/test/provenance/signing
- Argo CD for GitOps deployment and promotion

So the release-evidence lane for `cloudshell-fog` should assume that model rather than inventing a second one.

## 2. Required evidence classes for a release candidate

A `cloudshell-fog` release candidate should have, at minimum:

- pinned gateway image digest
- SBOM reference
- provenance reference
- signature verification reference
- component-version manifest
- compatibility statement
- production decision record for the chosen profile
- signed Fog Stack bundle manifest

## 3. Repo landing points

Representative assets:

- `apps/cloudshell-fog/component-version-manifest.example.yaml`
- `contracts/cloudshell-fog/compatibility-statement-v0.json`
- `contracts/cloudshell-fog/deployment-inventory-v0.json`
- `contracts/cloudshell-fog/production-decision-record-v0.json`
- `releases/manifests/fogstack.access-cloudshell-fog.example.manifest.json`

## 4. Promotion model

Recommended operator sequence:

1. resolve production decision record
2. resolve deployment inventory and pinned digest
3. generate component-version manifest
4. attach or reference SBOM, provenance, and signature evidence
5. prepare unsigned Fog Stack bundle manifest
6. attach signature metadata using the existing helper
7. only then treat the bundle as a release candidate for promotion

## 5. Non-goal

This document does not claim that CI already automates all of this. It defines the expected release-evidence shape so the repo is ready for that automation.
