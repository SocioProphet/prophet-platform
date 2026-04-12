# Zone Model

This document introduces the initial zone model for `prophet-platform` runtime work.

## Initial zones

- **edge**: workstation-local daemons and local receipt/catalog emission
- **workspace**: promoted shared artifacts, approvals, and governed knowledge surfaces
- **platform**: hosted runtime services and deployment-managed APIs
- **memory**: memory runtime and writeback/search integrations
- **ops**: observability, evaluation, and operations-intelligence projections
- **export**: explicit outbound delivery and external handoff lane

## Key rule

Zone crossing is policy-bound. Raw local events do not automatically become shared or exported artifacts.

## Immediate runtime consequence

The first runtime slice should extend the existing Lampstand local-daemon lane with zone-aware publication, then route admitted events through a dedicated zone router.
