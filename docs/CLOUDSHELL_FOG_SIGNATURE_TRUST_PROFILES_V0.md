# cloudshell-fog Signature Trust Profiles v0

This document defines the current signature-verification choices for `cloudshell-fog` in `prophet-platform`.

## 0. Why this exists

The vendored Kyverno policy currently carries a placeholder public key block. That is useful for structure, but production deployment requires an explicit trust choice.

## 1. Profile A — key-backed verification

Use when:

- you manage a stable signing keypair
- you want explicit public-key material in policy or referenced trust configuration

Implications:

- replace the placeholder public key block in the vendored Kyverno policy
- document key ownership and rotation
- ensure the selected image digest has been signed with the expected key

## 2. Profile B — keyless verification

Use when:

- you prefer identity-based signing and verification
- your CI/CD and policy stack are set up to support keyless trust

Implications:

- adapt the vendored policy away from the placeholder public key profile
- document the expected signing identity / workflow identity
- ensure the selected digest is verifiable under the chosen keyless trust model

## 3. Current repo posture

Current repo posture is **structural, not final**:

- the vendored policy proves where signature verification lives
- production operators must still choose and encode the actual trust model

## 4. Operator rule

A deployment is not production-ready until:

- the trust profile is chosen
- the vendored verification policy is updated accordingly
- the readiness validator no longer reports unresolved signature placeholders
