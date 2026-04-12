# Fog Stack offerings (initial status)

This document records the **current upstream status** of Fog Stack offerings relative to `prophet-platform`.

## Offerings

### Fog Stack Access
**Status:** initial upstream slice landed in this branch

Source/runtime anchors:
- `SocioProphet/cloudshell-fog`
- `apps/gateway`
- `apps/api`

Current upstream artifacts:
- `bundles/fogstack.access-v0.1.yaml`
- `conformance/rulepacks/fogstack.access-v0.1.yaml`
- `tools/fogstack_verify.py`
- `tools/validate_fogstack.py`

### Fog Stack Knowledge
**Status:** substrate-grounded in sandbox, not yet upstreamed

Source/runtime anchors:
- `apps/knowledge-reason`
- `apps/lampstand`

Why not yet upstream:
- needs the first verifier path to be accepted
- needs a clean local-daemon + cluster-service offering shape reviewed against current runtime classes

### Fog Stack Evaluation
**Status:** substrate-grounded in sandbox, not yet upstreamed

Source/runtime anchors:
- `apps/eval-fabric-api`
- `infra/local/docker-compose.eval-fabric.unified.yml`
- `infra/datastores/postgres/`
- `infra/datastores/clickhouse/`

Why not yet upstream:
- needs the first verifier path and bundle layout accepted
- needs a release/compatibility story that matches current platform eval-fabric responsibility boundaries

## Interpretation

At the moment, `prophet-platform` should be read as:
- runtime/deployment substrate for platform services
- home for a minimal first Fog Stack validation slice
- **not yet** the complete home for the full Fog Stack product catalog

That broader catalog still belongs in staged incubation until the first upstream integration path is accepted.
