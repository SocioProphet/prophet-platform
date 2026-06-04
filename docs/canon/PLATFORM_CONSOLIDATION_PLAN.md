# Canon Platform Consolidation Plan v0.1

## Decision frame

The `prophet-core-*` repositories should not be treated as independent products by default. Several are deployable capabilities of Prophet Platform and should be collapsed into the platform when their lifecycle is not meaningfully independent.

The consolidation target is not immediate deletion. The target is controlled migration with compatibility checks, downstream consumer review, and service-register propagation.

## Recommended disposition

| Repository | Recommended disposition | Rationale |
|---|---|---|
| `SocioProphet/prophet-core-catalog` | Collapse into `prophet-platform/services/canon` | Catalog is a platform subsystem, now named Canon. |
| `SocioProphet/prophet-core-ingest` | Collapse into `prophet-platform/services/ingest` or `services/canon/ingest-adapters` | Ingest is deployed and operated with the platform. |
| `SocioProphet/prophet-core-infra` | Collapse into `prophet-platform/infra` | Infrastructure belongs with the deployable platform topology. |
| `SocioProphet/prophet-core-query` | Collapse into `prophet-platform/services/query` unless query release cadence diverges | Query is platform runtime capability and should integrate with Sherlock/Holmes/SynapseIQ. |
| `SocioProphet/prophet-core-ops-brief` | Collapse into `prophet-platform/ops/briefs` | Ops brief artifacts are platform operations collateral. |
| `SocioProphet/prophet-core-scaffolder` | Collapse into `prophet-platform/tools/scaffolder` | Scaffolding is a platform developer tool. |
| `SocioProphet/prophet-core-contracts` | Hold as boundary repo until consumers are mapped | Shared contracts may need independent package/version lifecycle. |
| `SocioProphet/prophet-core-ledger` | Hold as boundary repo until audit lifecycle is decided | Receipts and evidence durability may justify separate controls. |
| `SocioProphet/prophet-core-policy` | Review against Policy Fabric and Guardrail Fabric | Could collapse, become compatibility layer, or be absorbed into policy repos. |
| `SocioProphet/prophet-core-libs` | Review as package boundary | Either publish as libs or collapse into platform internals. |

## Target platform layout

```text
prophet-platform/
  services/
    canon/
      registry/
      sources/
      datasets/
      tasks/
      apps/
      receipts/
      product-packs/
    ingest/
    query/
  infra/
  ops/
    briefs/
  tools/
    scaffolder/
  docs/
    canon/
```

## Migration gates

1. Inventory current files, contracts, workflows, issues, and consumers in each candidate repo.
2. Decide whether each repo contains runtime code, schemas, docs, fixtures, CI, or release artifacts.
3. Move only after import paths and downstream references are mapped.
4. Add compatibility stubs or archive notices in retired repos.
5. Update workspace-inventory canonical estate and SocioSphere service-register mirror after the migration branch is validated.
6. Do not archive ledger/contracts/policy/libs until lifecycle independence is resolved.

## Immediate next steps

1. Add Canon architecture and consolidation plan to Prophet Platform.
2. Open consolidation issues in `workspace-inventory` and `sociosphere`.
3. Mark candidate repos as `collapse-candidate`, not removed.
4. Create migration inventory reports for catalog, ingest, infra, query, ops-brief, and scaffolder.
5. Only then mutate canonical repo counts.
