# catalog-gateway

The unified read / resolve / lineage + external-interop seam over the Crystal Atlas
catalog families — the "GMS-equivalent" the data-catalog design brief
(`docs/strategy/PROPHET_DATA_CATALOG_DESIGN.md`) calls for. It **composes** the pieces
that already exist rather than reinventing them: the Crystal Atlas contract families
(`contracts/crystal-atlas/schemas/*-catalog-entry.v0`), the shared platform file-state
layout (as used by `crystal-atlas-contract-intel` / `evidence-receipts`), and — in later
increments — lattice-studio's DataCite/PROV-O/lineage logic, compute-gateway receipts,
and the masking PDP.

## First increment (read-only)

| Endpoint | Purpose |
|---|---|
| `GET /healthz` | liveness + supported kinds |
| `GET /v1/catalog/{kind}/{id}` | resolve a `source`\|`asset`\|`model`\|`workflow` entry from file-state |
| `GET /v1/catalog/{kind}/{id}/lineage` | upstream `source_refs`, best-effort resolved |
| `GET /v1/catalog/asset/{id}.dcat.json` | **the first real DCAT / schema.org emitter** (`application/ld+json`) |

The DCAT emitter is the strategic unlock: it is the standards seam CKAN (`ckanext-dcat`),
the DataHub Project, and CK.org harvest from. It also carries the Prophet extension
(`prophet:distributionClass`, and later `prophet:verifiedComputeRef`) — the governance a
plain catalog cannot represent.

## Storage layout
```
$SOCIOPROFIT_STATE_HOME/prophet-platform/catalog/<kind>/<id>.json
```
Ids are constrained to `[A-Za-z0-9._:-]` and resolved under the catalog root only
(path-traversal fails closed).

## Test
```
cd apps/catalog-gateway && python3 -m pytest tests -q
```

## Next increments
Registration (write path) · search/faceting (via sherlock) · mount the masking PDP as a
read-path filter (compute-gateway pattern) · real CKAN / DataHub-MCP / CK.org emitters
off the DCAT bridge.
