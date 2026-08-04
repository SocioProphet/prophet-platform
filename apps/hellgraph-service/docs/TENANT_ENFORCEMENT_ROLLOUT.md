# Tenant / op_set enforcement rollout (hellgraph-service)

The **enforcement half** of "operational sets by default" (#1423) ships **flagged off**. Turning it on
partitions the graph by `tenant_id` (+ `op_set`) — but it also requires every graph-API caller to present
a token, so a blind flip would `401` the whole estate. This runbook rolls it out **without an outage**,
using the `TENANT_ENFORCE=audit` dry run to de-risk each step. **Nothing here is auto-executed — it is the
deliberate operator/CI sequence.**

## Blast radius — who reads/writes the graph API today
`grep -rl hellgraph-service deploy/values` + the apps with a graph client. Each needs a `graph:read`
(and, if it writes, `graph:write`) token once `AUTH_ENFORCE=on`:

- `nugget-extractor`, `prophet-materializer-clickhouse`, `hellgraph-percolator`, `market-replay`,
  `device-service` (writers/readers on the loop)
- `agora`, `grlplus-service`, `ie-engine`, `entity-resolution`, `holmes`, `lattice-studio`,
  `health-twin` (readers)
- `socioprophet-web` reaches it **same-origin** through the nginx `/svc/*` proxy — confirm it forwards a token.

## The three modes (`TENANT_ENFORCE`)
| value | reads | writes | unscopable endpoints | breaks anyone? |
|-------|-------|--------|----------------------|----------------|
| `off` (default) | unscoped | unguarded | served | no |
| `audit` | unscoped, **logged** | unguarded, **logged** | served, **logged** | **no** — dry run |
| `on` | scoped to caller tenant/op_set | cross-tenant → `403` | `403` (sparql/gremlin/cypher/reason/shacl/enrich/explore) | yes, without tokens |

`on` **requires** `AUTH_ENFORCE=on` or the service refuses to start (fail-closed).

## Sequence

### A. Observe (safe — enable anytime)
1. Set `TENANT_ENFORCE: "audit"` in `deploy/values/hellgraph-service.yaml`, commit, let ArgoCD sync.
2. Watch the log plane for `[tenant-audit]` lines:
   ```
   kubectl -n socioprophet logs deploy/hellgraph-service | grep tenant-audit | jq .
   ```
   Each line names the `path`, the caller's `principal_tenant` (null = no token yet), and what would be
   denied (`tenant_required` / `cross_tenant_write` / `op_set_forbidden` / `tenant_isolation_unavailable`).
   This is the empirical blast radius. **Nothing is blocked.**

### B. Provision identity (still non-breaking)
3. Mint the HMAC secret once (random, ≥32 bytes), if not already present:
   ```
   kubectl -n socioprophet create secret generic hellgraph-auth-hmac --from-literal=secret="$(openssl rand -hex 32)"
   ```
4. Mint one token per consumer (offline, from the secret — never a committed PAT; mint in CI):
   ```
   AUTH_HMAC_SECRET="$(kubectl -n socioprophet get secret hellgraph-auth-hmac -o jsonpath='{.data.secret}' | base64 -d)" \
     node --import tsx apps/hellgraph-service/scripts/mint-graph-token.ts \
       --id nugget-extractor --tenant <tenant> --op-sets <ingest,...> --scopes graph:read,graph:write
   ```
   Store each as a Secret (`hellgraph-graph-token-<consumer>`), and wire it into that consumer's
   `deploy/values/<consumer>.yaml` as `secretEnv.GRAPH_TOKEN`. Each consumer must send
   `Authorization: Bearer $GRAPH_TOKEN` on its graph calls (the percolator + materializer already read a
   token env; readers with a graph client need the header added).

### C. Authenticate
5. Once **every** consumer in the blast radius carries a token (audit logs show `principal_tenant`
   populated, no more `null` from real callers), flip `AUTH_ENFORCE: "on"` + uncomment the
   `AUTH_HMAC_SECRET` secretEnv in `hellgraph-service.yaml`. Tokenless callers now `401` — the audit logs
   from step 2 are your checklist that there are none left. Keep `TENANT_ENFORCE: "audit"`.

### D. Enforce
6. Flip `TENANT_ENFORCE: "on"`. Isolation is live: cross-tenant reads return nothing, cross-tenant writes
   `403`, unscopable endpoints `403`. Verify:
   ```
   # a token for tenant A cannot see tenant B's nodes, and cannot write into B
   curl -s -H "authorization: Bearer $TOKEN_A" '.../api/graph/query?label=X' | jq '.nodes | length'
   curl -s -o /dev/null -w '%{http_code}' -H "authorization: Bearer $TOKEN_A" -X POST '.../api/graph/node' \
     -d '{"id":"x","labels":["clause"],"properties":{"tenant_id":"B"}}'   # expect 403
   ```

## Rollback
Any step: set `TENANT_ENFORCE` back to `audit` (or `off`) — reverts to non-blocking immediately. `on → audit`
keeps observability without enforcement; `→ off` silences it. `AUTH_ENFORCE` back to `off` restores tokenless
access. All flag flips, no data migration.

## Known follow-ons
- The **unscopable** endpoints (raw query languages + engine recommenders) are `403` under `on`, not scoped
  — engine-side scoping inside the fenced engine is a separate change. Callers that need them under
  enforcement must move to the scoped read surfaces (`query`/`subgraph`/`surface`/`resource`/`ground`/`ask`/`analytics`).
- Durable per-consumer token rotation (re-mint + roll the Secret) is a standard secret-rotation task.
