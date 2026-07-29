/**
 * auth — HMAC bearer-token scopes for the graph API (Wave 2 "doors": governance on the
 * graph surface).
 *
 * Reuses the vendored engine's federation-admit token machinery (HmacTokenVerifier —
 * stateless `<base64url(principal-json)>.<base64url(hmac)>` tokens, constant-time verify,
 * optional exp) so the estate has ONE token format, not two. Scopes here are graph-API
 * scopes, distinct from the engine's super-peer scopes ('read'/'query'/'admit'):
 *
 *   graph:read    every read surface (stats/log/analytics/kko/explore/query/subgraph/
 *                 surface/resource/ground + the read-only query languages ask/sparql/
 *                 gremlin/cypher/shacl)
 *   graph:write   graph mutations (node/edge upserts, reason — PLN forward-chaining
 *                 materializes inferred atoms, so it is a write) + POST /api/membrane/decide
 *                 (minting an EffectDecision is a governance write into the graph)
 *   graph:enrich  the enrichment recommender (GET /api/graph/enrich)
 *
 * Flagged rollout (AUTH_ENFORCE, default "off"):
 *   off  → passthrough with ONE startup WARN — behavior identical to today.
 *   on   → every /api/graph/* and /api/membrane/* route requires a Bearer token minted
 *          from AUTH_HMAC_SECRET carrying the route's scope. Enforce-on with a missing
 *          secret REFUSES STARTUP (fail-closed) — an "enforced" door with no lock is the
 *          declared-unenforced failure mode this estate refuses to ship again.
 *
 * Unmapped paths under the gated prefixes fail closed by verb: GET/HEAD need graph:read,
 * anything else needs graph:write — a future route added without updating the table gets
 * the strictest sane default instead of an open door.
 *
 * /healthz and /api/federation/* are NOT gated here: probes must stay tokenless, and
 * federation admit already carries its own fail-closed HMAC governance (federation.ts).
 *
 * Mint operator tokens with mintGraphToken() from this module (same secret), e.g.:
 *   node --import tsx -e "import('./src/auth.ts').then(m=>console.log(m.mintGraphToken(process.env.AUTH_HMAC_SECRET!,{id:'ops',scopes:['graph:read']})))"
 */
import type * as http from 'node:http'
import { HmacTokenVerifier, bearer } from '@socioprophet/hellgraph'

export type GraphScope = 'graph:read' | 'graph:write' | 'graph:enrich'

/** Engine Principal.scopes is typed to the super-peer scope union; on the wire it is a
 *  JSON string array, so graph scopes ride the same tokens. This is the honest runtime type. */
interface TokenPrincipal {
  id: string
  tenant?: string
  scopes: string[]
  exp?: number
}

export interface AuthState {
  enforce: boolean
  verifier: HmacTokenVerifier | null
}

export interface AuthDenial {
  code: 401 | 403
  body: {
    ok: false
    error: 'unauthorized' | 'forbidden'
    reason: 'missing_token' | 'invalid_token' | 'missing_scope'
    requiredScope: GraphScope
  }
}

/** Read AUTH_ENFORCE / AUTH_HMAC_SECRET. Fail-closed: enforce-on without a secret throws
 *  (callers refuse startup). Off = passthrough, announced by exactly one WARN. */
export function initAuth(env: NodeJS.ProcessEnv = process.env, warn: (msg: string) => void = console.warn): AuthState {
  const enforce = (env['AUTH_ENFORCE'] ?? 'off').trim().toLowerCase() === 'on'
  if (!enforce) {
    warn('[auth] WARN AUTH_ENFORCE=off — /api/graph/* and /api/membrane/* run UNAUTHENTICATED ' +
      '(flagged rollout; set AUTH_ENFORCE=on + AUTH_HMAC_SECRET to require scoped bearer tokens)')
    return { enforce: false, verifier: null }
  }
  const secret = env['AUTH_HMAC_SECRET'] ?? ''
  if (!secret) {
    throw new Error('AUTH_ENFORCE=on but AUTH_HMAC_SECRET is unset — refusing to start an ' +
      'ungoverned graph API (fail-closed). Provision the secret (deploy/values secretEnv) or set AUTH_ENFORCE=off.')
  }
  return { enforce: true, verifier: HmacTokenVerifier.fromSecret(secret) }
}

// Explicit route→scope table for every current route under the gated prefixes.
// Key: `${METHOD} ${pathname}`. Deny-by-default backstop below covers anything unmapped.
const ROUTE_SCOPES: Record<string, GraphScope> = {
  // reads
  'GET /api/graph/stats': 'graph:read',
  'GET /api/graph/log': 'graph:read',
  'GET /api/graph/analytics': 'graph:read',
  'GET /api/graph/kko': 'graph:read',
  'GET /api/graph/explore': 'graph:read',
  'GET /api/graph/query': 'graph:read',
  'GET /api/graph/subgraph': 'graph:read',
  'GET /api/graph/surface': 'graph:read',
  'GET /api/graph/resource': 'graph:read',
  'GET /api/graph/ground': 'graph:read',
  // read-only query/validation surfaces (POST carries the query text, not a mutation)
  'POST /api/graph/ask': 'graph:read',
  'POST /api/graph/sparql': 'graph:read',
  'POST /api/graph/gremlin': 'graph:read',
  'POST /api/graph/cypher': 'graph:read',
  'POST /api/graph/shacl': 'graph:read',
  // writes
  'POST /api/graph/node': 'graph:write',
  'POST /api/graph/edge': 'graph:write',
  'POST /api/graph/reason': 'graph:write', // forward-chaining materializes inferred atoms
  // membrane governance (minting an EffectDecision writes the graph)
  'POST /api/membrane/decide': 'graph:write',
  // enrichment recommender
  'GET /api/graph/enrich': 'graph:enrich',
}

/** The scope a request needs, or null when the path is not gated by this module. */
export function requiredScope(method: string, pathname: string): GraphScope | null {
  if (!pathname.startsWith('/api/graph/') && !pathname.startsWith('/api/membrane/')) return null
  const mapped = ROUTE_SCOPES[`${method} ${pathname}`]
  if (mapped) return mapped
  // Fail-closed default for unmapped paths under the gated prefixes.
  return method === 'GET' || method === 'HEAD' ? 'graph:read' : 'graph:write'
}

/** Gate one request. null = proceed (not enforcing, path not gated, or scope satisfied). */
export function authorize(state: AuthState, req: http.IncomingMessage, url: URL): AuthDenial | null {
  if (!state.enforce || !state.verifier) return null
  const scope = requiredScope(req.method ?? 'GET', url.pathname)
  if (!scope) return null
  const token = bearer(req.headers['authorization'])
  if (!token) {
    return { code: 401, body: { ok: false, error: 'unauthorized', reason: 'missing_token', requiredScope: scope } }
  }
  const principal = state.verifier.verify(token) as TokenPrincipal | null
  if (!principal) {
    return { code: 401, body: { ok: false, error: 'unauthorized', reason: 'invalid_token', requiredScope: scope } }
  }
  if (!Array.isArray(principal.scopes) || !principal.scopes.includes(scope)) {
    return { code: 403, body: { ok: false, error: 'forbidden', reason: 'missing_scope', requiredScope: scope } }
  }
  return null
}

/** Mint a graph-API token (tests + operator CLI). Same HMAC format as federation admit tokens. */
export function mintGraphToken(
  secret: string,
  principal: { id: string; scopes: GraphScope[]; tenant?: string; exp?: number },
): string {
  const verifier = HmacTokenVerifier.fromSecret(secret)
  return verifier.mint(principal as unknown as Parameters<HmacTokenVerifier['mint']>[0])
}
