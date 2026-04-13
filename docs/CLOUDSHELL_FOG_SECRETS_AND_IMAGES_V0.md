# cloudshell-fog Secrets and Image Inventory v0

This document states the minimum platform-side secret and image inventory required to deploy `cloudshell-fog` through `prophet-platform`.

## 0. Purpose

The runtime overlays and Argo applications are not sufficient on their own. Operators also need a clear statement of:

- which secret objects must exist
- which keys those secrets must contain
- which images must be pinned by digest
- how the standard and federal lanes differ

## 1. Required Kubernetes secret

### `cloudshell-fog-secrets`

Minimum required key:

- `session-token-signing-key`

Purpose:

- used by the gateway to mint and verify short-lived session-scoped attach tokens

This secret should be sourced from a secret manager or an ExternalSecret-style mechanism in production rather than hand-managed in plain manifests.

## 2. Required image inventory

At minimum, the deployment must select a pinned digest for:

- `ghcr.io/socioprophet/cloudshell-fog`

Rules:

- mutable tags are not acceptable in production
- the selected digest should correspond to the desired standard or federal build lane
- federal lanes should document the crypto-module/FIPS posture of the selected image line

## 3. Policy bundle reference

The current platform-side policy bundle is vendored at:

- `infra/policy/cloudshell-fog/kyverno`

This path must remain aligned with the selected runtime lane.

## 4. Standard lane

Representative posture:

- profile: `standard`
- minimum trust tier: `managed_cloud`
- strict egress: `false`
- require FIPS validated crypto: `false`

## 5. Federal lane

Representative posture:

- profile: `federal`
- minimum trust tier: `attested_fog`
- strict egress: `true`
- require FIPS validated crypto: `true`

The federal lane does not, by itself, create a FedRAMP authorization. It only encodes stricter deployment assumptions compatible with a federal profile.

## 6. Inventory contract

Machine-readable deployment inventory contract:

- `contracts/cloudshell-fog/deployment-inventory-v0.json`

Example inventory document:

- `apps/cloudshell-fog/deployment-inventory.example.yaml`
