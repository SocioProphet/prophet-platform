/**
 * organs — the mesh's functional groups, typed and observable.
 *
 * The organogenesis design's first mechanical form, and deliberately its least ambitious:
 * v1 organs are DECLARED over services that already exist, not grown. Four kinds —
 * memory retains, routing directs, perception ingests, policy governs — each a named group
 * of real services with live health. That turns "the mesh has capabilities" from an
 * implicit property of a deployment into something you can GET and audit.
 *
 * Two invariants (sourceos-spec Organ.json), and they are the whole point:
 *   OR-I1 — an organ never invents a member. Every member is a real addressable service, and
 *           a member whose health cannot be determined is `unknown`. Never optimistically
 *           "healthy": a probe that failed is not evidence of health.
 *   OR-I2 — organ health is DERIVED from members. An organ cannot claim to be healthier than
 *           what it is made of.
 *
 * Membership dynamics (v2, join/leave by capability + load over the admit/writer-key
 * machinery) and true differentiation (v3) stay out of scope until v1 proves useful — the
 * same membrane-before-organs ordering the twin program used.
 */

export type OrganKind = 'memory' | 'routing' | 'perception' | 'policy'
export type Health = 'healthy' | 'degraded' | 'down' | 'unknown'

export interface OrganMember {
  service: string
  endpoint?: string
  health: Health
  checkedAt?: string
  detail?: string
}

export interface Organ {
  type: 'Organ'
  specVersion: string
  id: string
  kind: OrganKind
  name: string
  members: OrganMember[]
  capabilities: string[]
  health: Health
  observedAt: string
}

export const SPEC_VERSION = '2.0'

/** A member declaration: which real service, where, and what it contributes. */
export interface MemberSpec { service: string; endpoint: string; capabilities: string[] }

export interface OrganSpec { kind: OrganKind; name: string; members: MemberSpec[] }

/**
 * The declared anatomy. Every entry names a service that actually exists in the estate;
 * endpoints are env-overridable so a different topology (edge, one-box, air-gapped) declares
 * the same organs over its own addresses rather than pretending the cluster's are present.
 */
export function declaredOrgans(env: Record<string, string | undefined> = process.env): OrganSpec[] {
  const url = (name: string, fallback: string): string => env[name] || fallback
  return [
    {
      kind: 'memory', name: 'Memory organ',
      members: [
        { service: 'memory-mesh', endpoint: url('MEMORY_MESH_URL', 'http://memory-mesh:8080'), capabilities: ['recall', 'append'] },
        { service: 'hellgraph-service', endpoint: url('HELLGRAPH_SELF_URL', 'http://hellgraph-service:8090'), capabilities: ['ground', 'graph-query'] },
      ],
    },
    {
      kind: 'routing', name: 'Routing organ',
      members: [
        { service: 'zone-router', endpoint: url('ZONE_ROUTER_URL', 'http://zone-router:8080'), capabilities: ['zone-route', 'retry', 'dead-letter'] },
        { service: 'compute-gateway', endpoint: url('COMPUTE_GATEWAY_URL', 'http://compute-gateway:8080'), capabilities: ['compute-route', 'entitlement-gate'] },
      ],
    },
    {
      kind: 'perception', name: 'Perception organ',
      members: [
        { service: 'ie-engine', endpoint: url('IE_ENGINE_URL', 'http://ie-engine:8080'), capabilities: ['extract'] },
        { service: 'entity-resolution', endpoint: url('ENTITY_RESOLUTION_URL', 'http://entity-resolution:8080'), capabilities: ['resolve'] },
        { service: 'embeddings', endpoint: url('EMBEDDINGS_URL', 'http://embeddings:8080'), capabilities: ['embed'] },
      ],
    },
    {
      kind: 'policy', name: 'Policy organ',
      members: [
        { service: 'identity-policy', endpoint: url('IDENTITY_POLICY_URL', 'http://identity-policy:8080'), capabilities: ['policy-decision'] },
        { service: 'evidence-receipts', endpoint: url('EVIDENCE_RECEIPTS_URL', 'http://evidence-receipts:8080'), capabilities: ['receipt', 'attest'] },
      ],
    },
  ]
}

/**
 * Fold member health into organ health (OR-I2).
 *   healthy   — every member whose health is KNOWN is healthy, and at least one is known
 *   down      — every known member is down
 *   unknown   — nothing is known (no member could be probed)
 *   degraded  — anything else, including a healthy member sitting beside an unknown one
 *
 * `unknown` members deliberately prevent a `healthy` verdict: an organ we cannot fully see
 * is not an organ we can call well.
 */
export function foldHealth(members: OrganMember[]): Health {
  if (!members.length) return 'unknown'
  const known = members.filter((m) => m.health !== 'unknown')
  if (!known.length) return 'unknown'
  const allHealthy = known.every((m) => m.health === 'healthy')
  const allDown = known.every((m) => m.health === 'down')
  if (allDown) return 'down'
  if (allHealthy && known.length === members.length) return 'healthy'
  return 'degraded'
}

export type Prober = (endpoint: string) => Promise<{ health: Health; detail?: string }>

/**
 * Default prober: GET {endpoint}/healthz with a hard timeout. Any non-2xx is `down`; a
 * network error or timeout is `unknown` — we distinguish "answered badly" from "did not
 * answer", because conflating them is how a dead service gets reported as merely degraded.
 */
export function httpProber(timeoutMs = 2000): Prober {
  return async (endpoint: string) => {
    const ctl = new AbortController()
    const timer = setTimeout(() => ctl.abort(), timeoutMs)
    try {
      const res = await fetch(`${endpoint}/healthz`, { signal: ctl.signal })
      return res.ok ? { health: 'healthy' } : { health: 'down', detail: `HTTP ${res.status}` }
    } catch (e) {
      return { health: 'unknown', detail: (e as Error).name === 'AbortError' ? 'probe timed out' : 'unreachable' }
    } finally {
      clearTimeout(timer)
    }
  }
}

/** Assemble one organ by probing its declared members. Never throws — a probe failure is data. */
export async function assembleOrgan(spec: OrganSpec, probe: Prober, now = new Date()): Promise<Organ> {
  const checkedAt = now.toISOString()
  const members: OrganMember[] = await Promise.all(spec.members.map(async (m) => {
    const r = await probe(m.endpoint).catch(() => ({ health: 'unknown' as Health, detail: 'prober threw' }))
    return { service: m.service, endpoint: m.endpoint, health: r.health, checkedAt, ...(r.detail ? { detail: r.detail } : {}) }
  }))
  return {
    type: 'Organ', specVersion: SPEC_VERSION,
    id: `urn:srcos:organ:${spec.kind}`,
    kind: spec.kind, name: spec.name, members,
    capabilities: [...new Set(spec.members.flatMap((m) => m.capabilities))].sort(),
    health: foldHealth(members),
    observedAt: checkedAt,
  }
}

/** The whole anatomy, probed in parallel. */
export async function assembleOrgans(
  specs: OrganSpec[] = declaredOrgans(), probe: Prober = httpProber(), now = new Date(),
): Promise<Organ[]> {
  return Promise.all(specs.map((s) => assembleOrgan(s, probe, now)))
}
