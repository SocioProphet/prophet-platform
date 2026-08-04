/**
 * tenant.ts — operational-set / tenant ISOLATION at the graph surface (Wave 2 "doors": the ENFORCEMENT
 * half of "operational sets by default"; the labeling half ships in the percolation writer, #1400).
 *
 * auth.ts proves WHO is calling (a scoped bearer token). This proves WHAT they may see. The graph store
 * is the fenced engine (getHellGraph) — historically single-tenant with label-only reads — so isolation
 * is enforced HERE, in the service layer: with TENANT_ENFORCE=on every read is scoped to the caller's
 * tenant_id (and, when requested, ONE op_set the caller is entitled to) by filtering the nodes/edges the
 * read sees on properties.tenant_id (+ op_set), and a write whose body targets another tenant is refused.
 * Because the percolation writer stamps tenant_id + op_set on every object, the label to enforce ON is
 * always present.
 *
 * The raw query LANGUAGES (sparql/gremlin/cypher/reason/shacl) run INSIDE the fenced engine over the whole
 * atomspace; they cannot be tenant-scoped from this TS layer without reaching into the engine. Rather than
 * serve possibly-cross-tenant results, they are REFUSED under enforcement (fail-closed) — the scoped read
 * surfaces (query/subgraph/surface/resource/ground/ask/analytics) stay available. Engine-side scoping of
 * the query languages is a follow-on inside the (fenced) engine, not a silent leak here.
 *
 * Flagged rollout (TENANT_ENFORCE, default "off"), mirroring AUTH_ENFORCE:
 *   off → passthrough, one startup WARN — reads/writes are NOT tenant-partitioned (today's behavior).
 *   on  → requires AUTH_ENFORCE=on (isolation needs authenticated principals to scope by); a token that
 *         carries no tenant is denied. TENANT_ENFORCE=on without AUTH_ENFORCE=on REFUSES STARTUP — an
 *         isolation door with no identity behind it is the declared-unenforced failure mode, again.
 */
import type * as http from 'node:http'
import { bearer } from '@socioprophet/hellgraph'
import type { AuthState } from './auth.js'

export interface TenantState {
  enforce: boolean
}

/** The identity a graph token carries for isolation: a tenant and the op_sets it is entitled to read. */
export interface TenantPrincipal {
  id?: string
  tenant?: string
  op_sets?: string[]
}

export interface TenantDenial {
  code: 403
  body: {
    ok: false
    error: 'forbidden'
    reason: 'tenant_required' | 'cross_tenant_write' | 'op_set_forbidden' | 'tenant_isolation_unavailable'
    detail: string
  }
}

/** Endpoints whose result-shaping happens INSIDE the fenced engine (a raw query language, or an
 *  `engine.*` call), so this TS layer cannot verify the result is tenant-scoped. Refused under
 *  enforcement rather than risk a cross-tenant leak — the doctrine is "verify or fail-closed", not
 *  "assume the engine scopes". Engine-side scoping of these is a follow-on inside the fenced engine.
 *  The scoped read surfaces (query/subgraph/surface/resource/ground/ask/analytics/stats) stay live. */
export const UNSCOPABLE_UNDER_ENFORCE: ReadonlySet<string> = new Set([
  '/api/graph/sparql',
  '/api/graph/gremlin',
  '/api/graph/cypher',
  '/api/graph/reason',
  '/api/graph/shacl',
  '/api/graph/enrich',   // engine.enrichClass — recommender over engine internals
  '/api/graph/explore',  // engine.exploreFrom — traversal over engine internals
])

/** Read TENANT_ENFORCE. Fail-closed: enforce-on without AUTH_ENFORCE=on throws (callers refuse startup).
 *  Off = passthrough, announced by exactly one WARN (mirrors initAuth). */
export function initTenant(
  env: NodeJS.ProcessEnv = process.env,
  warn: (msg: string) => void = console.warn,
): TenantState {
  const enforce = (env['TENANT_ENFORCE'] ?? 'off').trim().toLowerCase() === 'on'
  if (!enforce) {
    warn('[tenant] WARN TENANT_ENFORCE=off — graph reads/writes are NOT partitioned by tenant/op_set ' +
      '(flagged rollout; set TENANT_ENFORCE=on WITH AUTH_ENFORCE=on to isolate per tenant/op_set).')
    return { enforce: false }
  }
  const authOn = (env['AUTH_ENFORCE'] ?? 'off').trim().toLowerCase() === 'on'
  if (!authOn) {
    throw new Error('TENANT_ENFORCE=on requires AUTH_ENFORCE=on — tenant isolation needs authenticated ' +
      'principals to scope by (fail-closed). Set AUTH_ENFORCE=on + AUTH_HMAC_SECRET, or TENANT_ENFORCE=off.')
  }
  return { enforce: true }
}

/** The verified principal (tenant + entitled op_sets) behind a request, or null when the token is absent
 *  or invalid. Verifies via the same HMAC verifier auth.ts already gated the request with. */
export function tenantPrincipal(auth: AuthState, req: http.IncomingMessage): TenantPrincipal | null {
  if (!auth.verifier) return null
  const token = bearer(req.headers['authorization'])
  if (!token) return null
  return auth.verifier.verify(token) as TenantPrincipal | null
}

interface PropsNode { id: string; properties?: Record<string, unknown> | null }
interface EndpointEdge { from: string; to: string }
interface TripleLite { subject: string; object: unknown; isIri?: boolean }

/** A read-only view of the graph scoped to ONE tenant (and, if given, one op_set). allNodes()/allEdges()/
 *  triples() return only in-scope objects. Edges AND triples are INDUCED — kept only when both endpoints
 *  (an edge's from/to; a triple's subject and, when it is an IRI, its object) are in-scope nodes — so a
 *  cross-tenant edge or fact can never surface even if its own label were mislabeled. A triple whose
 *  subject is not an in-scope node (e.g. a shared-ontology fact) is conservatively excluded: over-filter
 *  before leak. Generic over the concrete shapes so labels + properties pass through untouched. */
export function tenantScope<N extends PropsNode, E extends EndpointEdge, T extends TripleLite>(
  g: { allNodes(): N[]; allEdges(): E[]; triples(): T[] },
  tenant: string,
  opSet?: string,
): { allNodes(): N[]; allEdges(): E[]; triples(): T[] } {
  const inScope = (n: N): boolean => {
    const p = n.properties ?? {}
    if (p['tenant_id'] !== tenant) return false
    if (opSet !== undefined && p['op_set'] !== opSet) return false
    return true
  }
  const scopedIds = (): Set<string> => new Set(g.allNodes().filter(inScope).map((n) => n.id))
  return {
    allNodes(): N[] {
      return g.allNodes().filter(inScope)
    },
    allEdges(): E[] {
      const keep = scopedIds()
      return g.allEdges().filter((e) => keep.has(e.from) && keep.has(e.to))
    },
    triples(): T[] {
      const keep = scopedIds()
      return g.triples().filter((t) => keep.has(t.subject) && (t.isIri ? keep.has(String(t.object)) : true))
    },
  }
}

/** Resolve the scope of a READ: passthrough (null) when not enforcing; a denial when the token carries no
 *  tenant or requests an op_set it is not entitled to; else the { tenant, opSet } to scope by. */
export function scopeForRead(
  state: TenantState,
  principal: TenantPrincipal | null,
  url: URL,
): { tenant: string; opSet?: string } | TenantDenial | null {
  if (!state.enforce) return null
  if (!principal?.tenant) {
    return {
      code: 403,
      body: { ok: false, error: 'forbidden', reason: 'tenant_required',
        detail: 'TENANT_ENFORCE=on but the bearer token carries no tenant — cannot scope this read' },
    }
  }
  const requested = url.searchParams.get('op_set') ?? undefined
  if (requested !== undefined && Array.isArray(principal.op_sets) && !principal.op_sets.includes(requested)) {
    return {
      code: 403,
      body: { ok: false, error: 'forbidden', reason: 'op_set_forbidden',
        detail: `token for tenant '${principal.tenant}' is not entitled to op_set '${requested}'` },
    }
  }
  return { tenant: principal.tenant, opSet: requested }
}

/** Guard a WRITE: a node/edge may be written only into the caller's OWN tenant. A body whose tenant_id is
 *  absent or differs from the principal's tenant is refused (no cross-tenant overwrite, no unlabeled write). */
export function assertWriteTenant(
  state: TenantState,
  principal: TenantPrincipal | null,
  properties: Record<string, unknown> | undefined | null,
): TenantDenial | null {
  if (!state.enforce) return null
  if (!principal?.tenant) {
    return {
      code: 403,
      body: { ok: false, error: 'forbidden', reason: 'tenant_required',
        detail: 'TENANT_ENFORCE=on but the bearer token carries no tenant — cannot attribute this write' },
    }
  }
  const bodyTenant = (properties ?? {})['tenant_id']
  if (bodyTenant !== principal.tenant) {
    return {
      code: 403,
      body: { ok: false, error: 'forbidden', reason: 'cross_tenant_write',
        detail: `write targets tenant ${JSON.stringify(bodyTenant)} but the token is scoped to '${principal.tenant}'` },
    }
  }
  return null
}

/** Refuse an endpoint that cannot be tenant-scoped in this layer (fail-closed under enforcement). */
export function refuseUnscopable(state: TenantState, pathname: string): TenantDenial | null {
  if (!state.enforce || !UNSCOPABLE_UNDER_ENFORCE.has(pathname)) return null
  return {
    code: 403,
    body: { ok: false, error: 'forbidden', reason: 'tenant_isolation_unavailable',
      detail: `${pathname} runs in the graph engine over all tenants and cannot be tenant-scoped in the ` +
        'service layer; it is refused under TENANT_ENFORCE=on. Use the scoped read surfaces ' +
        '(query/subgraph/surface/resource/ground/ask/analytics).' },
  }
}
