/**
 * Mint a graph-API bearer token for the tenant-enforcement rollout. Operator / CI tool — graph tokens
 * are HMAC and minted OFFLINE from AUTH_HMAC_SECRET (there is NO runtime mint endpoint), then provisioned
 * as a k8s Secret and injected (secretEnv GRAPH_TOKEN) into each graph-API consumer. Carries the tenant
 * and the op_sets the caller is entitled to read, plus its scopes. See docs/TENANT_ENFORCEMENT_ROLLOUT.md.
 *
 * Usage (never echo the secret into shell history — read it from the k8s Secret or a file):
 *   AUTH_HMAC_SECRET="$(kubectl -n socioprophet get secret hellgraph-auth-hmac -o jsonpath='{.data.secret}' | base64 -d)" \
 *     node --import tsx scripts/mint-graph-token.ts \
 *       --id nugget-extractor --tenant acme --op-sets ingest,discourse --scopes graph:read,graph:write
 *
 * In CI, mint into a Secret (secrets minted in CI, never a committed PAT):
 *   kubectl create secret generic hellgraph-graph-token-<consumer> --from-literal=token="$(...mint...)"
 */
import { mintGraphToken, type GraphScope } from '../src/auth.js'

function arg(name: string, def = ''): string {
  const i = process.argv.indexOf(`--${name}`)
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1]! : def
}

function main(): void {
  const secret = process.env['AUTH_HMAC_SECRET'] ?? ''
  if (!secret) {
    console.error('AUTH_HMAC_SECRET is required — the value of the hellgraph-auth-hmac Secret.')
    process.exit(1)
  }
  const id = arg('id')
  const tenant = arg('tenant')
  if (!id || !tenant) {
    console.error('--id <principal-id> and --tenant <tenant-id> are required.')
    process.exit(1)
  }
  const opSets = arg('op-sets').split(',').map((s) => s.trim()).filter(Boolean)
  const scopes = arg('scopes', 'graph:read').split(',').map((s) => s.trim()).filter(Boolean) as GraphScope[]
  // op_sets omitted ⇒ no op_set entitlement restriction (tenant-only scoping); pass --op-sets to restrict.
  const token = mintGraphToken(secret, {
    id, tenant, scopes, ...(opSets.length ? { op_sets: opSets } : {}),
  })
  process.stdout.write(token + '\n')
}

main()
