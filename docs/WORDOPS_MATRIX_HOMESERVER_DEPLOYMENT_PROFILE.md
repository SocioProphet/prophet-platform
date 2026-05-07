# WordOps Matrix Homeserver Deployment Profile v0.1

## Purpose

This profile defines the first deployable Matrix homeserver shape for WordOps.

WordOps needs a controlled Matrix homeserver estate because client-facing self-service support, private escalation rooms, Matrix-native agent rendezvous, and regulated public-to-private case pivots cannot rely on arbitrary public homeservers.

## Deployment principle

Start with our own Matrix homeserver containers, not public-server dependency.

Public federation compatibility is required, but public-server dependency is not.

## Estate split

### Public edge estate

Purpose:
- public intake
- support entry
- community rooms
- low-sensitivity self-service

Default posture:
- federated where appropriate
- public directory publication disabled until moderation is live
- no regulated case content
- no high-risk agent capability exposure

### Private core estate

Purpose:
- case rooms
- escalation rooms
- incident rooms
- internal operator rooms
- private agent workspaces

Default posture:
- private visibility
- no third-party identity server by default
- no public room directory publication
- federation disabled for sensitive rooms unless policy allows it
- E2EE posture checks before sensitive agent context is released

## Container approach

Phase 0 should use containerized Synapse estates with explicit image pinning.

Required container responsibilities:
- homeserver process
- Postgres database
- reverse proxy / TLS termination
- worker separation when scaling requires it
- media store volume
- config volume
- signing key persistence
- backup path

## Pull/build logic

The deployment tooling should support two paths:

### Pull path

Use a pinned upstream Synapse image for initial deployment.

Required controls:
- image tag pinned
- digest recorded when promoted
- config generated into versioned deployment directory
- signing key generated once and persisted outside disposable containers
- Postgres volume explicitly named and backed up

### Build path

Build a local image only when we need a patched homeserver, custom hardening, or reproducible internal base images.

Required controls:
- Dockerfile or Containerfile checked into the repo before use
- SBOM generated during build
- image digest recorded
- provenance emitted into the platform evidence lane
- no mutable `latest` image in deployment profiles

## Minimal local stack

The first local stack should include:
- `synapse-public`
- `postgres-public`
- `synapse-private`
- `postgres-private`
- `reverse-proxy`

Optional later:
- Element Web
- Hookshot
- maubot
- Mjolnir
- Matrix RTC stack
- media repository split
- workers and Redis

## Config artifacts to produce next

The next implementation slice should add:

```text
infra/wordops/matrix/local/docker-compose.yml
infra/wordops/matrix/public/homeserver.yaml.template
infra/wordops/matrix/private/homeserver.yaml.template
infra/wordops/matrix/nginx/matrix.conf
infra/wordops/matrix/scripts/render-config.sh
infra/wordops/matrix/scripts/generate-signing-key.sh
infra/wordops/matrix/scripts/smoke-check.sh
```

## Smoke checks

Minimum checks:
- public homeserver `/_matrix/client/versions` responds
- private homeserver `/_matrix/client/versions` responds
- public discovery JSON is served
- private discovery JSON is served
- registration disabled by default
- room creation through service account works
- public room publication is blocked until moderation baseline is enabled

## Security gates

Before public exposure:
- TLS configured
- registration policy explicit
- admin account creation procedure documented
- moderation bot configured
- backup/restore path tested
- homeserver signing key backed up
- media retention policy documented
- E2EE posture check documented for private rooms

## Relationship to AgentTerm

AgentTerm may connect to this Matrix estate as a terminal-native adapter.
WordOps owns the Matrix-native client-facing self-service surface.
Both consume the same homeserver substrate and shared platform authorities.
