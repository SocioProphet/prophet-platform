# WordOps Matrix Local Homeserver Profile

This directory seeds the first local, containerized Matrix homeserver profile for WordOps.

It is intentionally local-first and non-secret-bearing. The profile creates two Synapse estates:

- public edge homeserver for low-sensitivity intake and self-service flows
- private core homeserver for escalation, case, incident, and agent workspace flows

## Layout

```text
infra/wordops/matrix/
  .env.example
  local/docker-compose.yml
  nginx/matrix.conf
  scripts/render-config.sh
  scripts/generate-signing-keys.sh
  scripts/smoke-check.sh
  templates/public-homeserver.yaml.tpl
  templates/private-homeserver.yaml.tpl
  well-known/matrix/client
  well-known/matrix/support
```

Generated files are written under:

```text
infra/wordops/matrix/public/
infra/wordops/matrix/private/
```

Those generated directories contain rendered `homeserver.yaml` files, log configs, signing keys, and local media state.

## Local start

From the repository root:

```bash
cp infra/wordops/matrix/.env.example infra/wordops/matrix/.env && sh infra/wordops/matrix/scripts/render-config.sh && sh infra/wordops/matrix/scripts/generate-signing-keys.sh && docker compose --env-file infra/wordops/matrix/.env -f infra/wordops/matrix/local/docker-compose.yml up --build
```

In another shell, run:

```bash
sh infra/wordops/matrix/scripts/smoke-check.sh
```

## Host requirements

The local helper scripts expect:

- Docker with Compose v2
- `envsubst` for template rendering
- `curl` for smoke checks

## Ports

Defaults:

- public Synapse: `http://localhost:8008`
- private Synapse: `http://localhost:8018`
- Matrix edge proxy: `http://localhost:8088`

## Security notes

This is a local bootstrap profile, not production hardening.

Before public exposure, we still need:

- TLS termination
- real secrets
- admin account provisioning process
- backup and restore runbook
- moderation bot baseline
- registration policy hardening
- public directory publication gates
- private-room E2EE posture checks
- room factory and service-account controls

## Design relationship

This profile implements the deployment target described in `docs/WORDOPS_MATRIX_HOMESERVER_DEPLOYMENT_PROFILE.md`.

WordOps owns the Matrix-native client-facing self-service surface. AgentTerm may connect to these Matrix estates as a terminal-native adapter, but it does not replace the Matrix-native surface.
