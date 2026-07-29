/**
 * membrane — the B-after-A gate: no ExecutionReport without an approved intent.
 *
 * This is the estate's typed-precondition enforcer made STRUCTURAL on the graph surface —
 * the same gate for a trade and for a door-unlock. The lifecycle is the sourceos-spec
 * effect contract (vendored + sha-asserted in contract.ts):
 *
 *   A  OrderIntent, wrapped in an EffectRequest  →  POST /api/membrane/decide
 *      policy kernel v0 (explicit allow-list, deny-by-default) → EffectDecision node
 *      (labels [EffectDecision], idempotent by idempotencyKey), sealed on the estate
 *      receipt spine via the deployed compute-gateway (kind=materialize — reusing the
 *      Seal-the-Walls W1.1 attestation shape; never a parallel receipt lineage).
 *   B  a node write labeled ExecutionReport REQUIRES properties.decisionRef resolving to
 *      an existing APPROVED EffectDecision whose intentRef matches the report's — else
 *      403 with a typed reason. Structural, not advisory: with MEMBRANE_ENFORCE=on the
 *      public write path also refuses to mint/overwrite EffectDecision nodes directly
 *      (decision_mint_via_membrane_only) — a gate you can forge in one call is advisory.
 *
 * Flag: MEMBRANE_ENFORCE (default "off" = passthrough with ONE startup WARN; deploy
 * values set "on"). /api/membrane/decide works in BOTH modes, so decisions can be minted
 * before enforcement flips.
 *
 * Sealing env (same wiring as prophet-materializer-clickhouse):
 *   COMPUTE_GATEWAY_URL   e.g. http://compute-gateway:8080
 *   GATEWAY_TOKEN         secretEnv, secret compute-gateway-token (already provisioned)
 * Seal outcome is recorded honestly on the decision node (sealed / receiptRef /
 * sealError) — an unreachable gateway degrades the ATTESTATION, never the decision's
 * structural existence, and never silently.
 */
import type * as http from 'node:http'
import { canonicalJson, sha256Hex, urnLocalId, validateAgainst, type Json, SPEC_VERSION } from './contract.js'

// ── graph facade (the subset membrane uses; matches @socioprophet/hellgraph HellGraphStore) ──
type PropertyValue = string | number | boolean | null
interface GraphNode { id: string; labels: string[]; properties: Record<string, PropertyValue> }
export interface MembraneGraph {
  addNode(id: string, labels: string[], properties?: Record<string, PropertyValue>): GraphNode
  getNode(id: string): GraphNode | undefined
  version(): number
}

export const DECISION_URN_PREFIX = 'urn:srcos:effect-decision:'
const MEMBRANE_ACTOR = 'urn:srcos:agent:hellgraph-membrane'
const POLICY_REF = 'hellgraph-membrane/policy-kernel@v0'

export interface MembraneState { enforce: boolean }

export function initMembrane(env: NodeJS.ProcessEnv = process.env, warn: (msg: string) => void = console.warn): MembraneState {
  // Contract self-check runs UNCONDITIONALLY (market-replay startup_check discipline):
  // a membrane whose own emissions no longer conform must die at boot, flag or no flag.
  probeContract()
  const enforce = (env['MEMBRANE_ENFORCE'] ?? 'off').trim().toLowerCase() === 'on'
  if (!enforce) {
    warn('[membrane] WARN MEMBRANE_ENFORCE=off — ExecutionReport writes are NOT gated on approved ' +
      'EffectDecisions (passthrough; /api/membrane/decide still mints decisions for the flip)')
  }
  if (!env['COMPUTE_GATEWAY_URL'] || !env['GATEWAY_TOKEN']) {
    warn('[membrane] WARN COMPUTE_GATEWAY_URL/GATEWAY_TOKEN unset — decisions will record sealed:false ' +
      '(no receipt on the estate spine) until the gateway wiring is configured')
  }
  return { enforce }
}

// ── policy kernel v0: explicit allow-list, deny-by-default ──────────────────────────────
export interface PolicyKernelV0 {
  allowedEffectKinds: ReadonlySet<string>
  allowedCapabilities: ReadonlySet<string>
  allowedTargetKinds: ReadonlySet<string>
  allowedIntentKinds: ReadonlySet<string>
  maxQuantity: number
  maxNotional: number
}

export function policyKernelV0(env: NodeJS.ProcessEnv = process.env): PolicyKernelV0 {
  return {
    allowedEffectKinds: new Set(['execute']),
    allowedCapabilities: new Set(['trading.order.place', 'trading.order.amend', 'trading.order.cancel']),
    allowedTargetKinds: new Set(['venue_order_gateway']),
    allowedIntentKinds: new Set(['new', 'amend', 'cancel']),
    maxQuantity: Number(env['MEMBRANE_MAX_QUANTITY'] ?? 10_000) || 10_000,
    maxNotional: Number(env['MEMBRANE_MAX_NOTIONAL'] ?? 1_000_000) || 1_000_000,
  }
}

type Dict = Record<string, unknown>

function asNumber(v: unknown): number | null {
  if (typeof v === 'number') return Number.isFinite(v) ? v : null
  if (typeof v === 'string' && /^-?[0-9]+(\.[0-9]+)?$/.test(v)) return Number(v)
  return null
}

/** Evaluate one spec-valid (EffectRequest, OrderIntent) pair. Deny-by-default: every
 *  check must pass; reasons list every failure (typed strings, not prose). */
export function evaluatePolicy(kernel: PolicyKernelV0, request: Dict, intent: Dict): { decision: 'approved' | 'denied'; reasons: string[] } {
  const reasons: string[] = []
  const effectKind = String(request['effectKind'])
  const capability = String(request['capability'])
  const targetKind = String((request['target'] as Dict | undefined)?.['kind'])
  if (!kernel.allowedEffectKinds.has(effectKind)) reasons.push(`effect_kind_not_allowed:${effectKind}`)
  if (!kernel.allowedCapabilities.has(capability)) reasons.push(`capability_not_allowed:${capability}`)
  if (!kernel.allowedTargetKinds.has(targetKind)) reasons.push(`target_kind_not_allowed:${targetKind}`)
  // v0 is a machine kernel with no human-approval channel: a request that DECLARES it
  // needs a human cannot be approved here — deny, never silently downgrade the requirement.
  if (request['requiresHumanApproval'] === true) reasons.push('human_approval_required_no_human_channel')

  const intentKind = String(intent['intentKind'])
  if (!kernel.allowedIntentKinds.has(intentKind)) reasons.push(`intent_kind_not_allowed:${intentKind}`)
  if (intentKind === 'new') {
    if (intent['side'] !== 'buy' && intent['side'] !== 'sell') reasons.push('side_required_for_new')
    if (intent['orderType'] === undefined) reasons.push('order_type_required_for_new')
    if (intent['orderType'] === 'limit' && (intent['price'] === undefined || intent['price'] === null)) {
      reasons.push('limit_price_required')
    }
  }
  const qty = asNumber(intent['quantity'])
  if (qty === null || qty <= 0) reasons.push('quantity_not_positive')
  else if (qty > kernel.maxQuantity) reasons.push(`quantity_exceeds_limit:${kernel.maxQuantity}`)
  const price = asNumber(intent['price'])
  if (qty !== null && price !== null && qty * price > kernel.maxNotional) {
    reasons.push(`notional_exceeds_limit:${kernel.maxNotional}`)
  }
  return reasons.length === 0 ? { decision: 'approved', reasons: [] } : { decision: 'denied', reasons }
}

// ── decision identity: deterministic by idempotencyKey ─────────────────────────────────
export function decisionIdFor(idempotencyKey: string): string {
  // readable prefix + content hash: URN-safe, collision-proof, deterministic per key.
  return `${DECISION_URN_PREFIX}${urnLocalId(idempotencyKey).slice(0, 40)}-${sha256Hex(idempotencyKey).slice(0, 16)}`
}

/** Build the spec-valid EffectDecision object. decisionHash seals the canonical decision
 *  payload WITHOUT the hash field itself (the PolicyDecision/ExecutionDecision convention). */
export function buildDecision(request: Dict, intent: Dict, verdict: { decision: 'approved' | 'denied'; reasons: string[] }, decidedAt: string): Dict {
  const base: Dict = {
    id: decisionIdFor(String(request['idempotencyKey'])),
    type: 'EffectDecision',
    specVersion: SPEC_VERSION,
    effectRequestRef: request['id'],
    subjectEventRef: intent['id'],
    decision: verdict.decision,
    decidedByActorRef: MEMBRANE_ACTOR,
    authorityContext: {
      principal: 'system',
      delegationChain: [],
      capabilities: [request['capability']],
      approvalState: verdict.decision === 'approved' ? 'approved' : 'denied',
      policyContext: [POLICY_REF],
    },
    rationale: verdict.decision === 'approved'
      ? 'policy kernel v0: explicit allow-list satisfied (effectKind, capability, target, intentKind, size limits)'
      : `policy kernel v0 denied: ${verdict.reasons.join('; ')}`,
    ruleRefs: [POLICY_REF],
    evidenceRefs: [],
    policyLabels: ['membrane-policy-kernel-v0'],
    riskLabels: verdict.decision === 'denied' ? ['denied-effect'] : [],
    decidedAt,
  }
  return { ...base, decisionHash: `sha256:${sha256Hex(canonicalJson(base as Json))}` }
}

// Boot-time probe: OUR builder must emit schema-conformant objects. Any drift dies here.
function probeContract(): void {
  const intent: Dict = {
    id: 'urn:srcos:order-intent:probe-0', type: 'OrderIntent', specVersion: SPEC_VERSION,
    actorRef: MEMBRANE_ACTOR, wallTime: '2026-07-29T00:00:00Z', strategyRef: 'probe',
    instrumentRef: 'SP:PROBE', intentKind: 'new', side: 'buy', orderType: 'limit',
    quantity: 1, price: 1, timeInForce: 'day',
  }
  const request: Dict = {
    id: 'urn:srcos:effect:probe-0', type: 'EffectRequest', specVersion: SPEC_VERSION,
    requestedByEventRef: 'urn:srcos:order-intent:probe-0', effectKind: 'execute',
    capability: 'trading.order.place', target: { kind: 'venue_order_gateway', identifier: 'probe' },
    parameters: { orderIntent: intent }, idempotencyKey: 'probe-0',
    requiresHumanApproval: false, policyLabels: [], riskLabels: [],
    requestedAt: '2026-07-29T00:00:00Z',
  }
  for (const [name, value] of [['OrderIntent', intent], ['EffectRequest', request]] as const) {
    const errs = validateAgainst(name as 'OrderIntent' | 'EffectRequest', value)
    if (errs.length > 0) throw new Error(`membrane probe: ${name} builder drifted from vendored schema: ${errs.join('; ')}`)
  }
  const decision = buildDecision(request, intent, { decision: 'approved', reasons: [] }, '2026-07-29T00:00:00Z')
  const errs = validateAgainst('EffectDecision', decision)
  if (errs.length > 0) throw new Error(`membrane probe: EffectDecision builder drifted from vendored schema: ${errs.join('; ')}`)
}

// ── sealing on the estate receipt spine (compute-gateway, kind=materialize) ────────────
interface SealOutcome { sealed: boolean; receiptRef: string | null; sealError: string | null }

async function sealDecision(decisionHash: string, fromCursor: number, toCursor: number, env: NodeJS.ProcessEnv): Promise<SealOutcome> {
  const base = (env['COMPUTE_GATEWAY_URL'] ?? '').replace(/\/$/, '')
  const token = env['GATEWAY_TOKEN'] ?? ''
  if (!base || !token) return { sealed: false, receiptRef: null, sealError: 'gateway_unconfigured' }
  const ctl = new AbortController()
  const timer = setTimeout(() => ctl.abort(), Number(env['MEMBRANE_SEAL_TIMEOUT_MS'] ?? 3000) || 3000)
  try {
    // The deployed gateway's EXISTING receipt door (W1.1 materialize attestation — reuse
    // its shape, no new kind): one decision "row" materialized through the graph's
    // logical-clock cut, batch-bound by the decision's own tamper-evident hash.
    const r = await fetch(`${base}/v1/compute`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', authorization: `Bearer ${token}` },
      body: JSON.stringify({
        kind: 'materialize',
        spec: { source: 'membrane', sink: 'hellgraph', table: 'EffectDecision',
                from_cursor: fromCursor, to_cursor: toCursor, row_count: 1, batch_hash: decisionHash },
        project: env['MEMBRANE_PROJECT'] ?? 'default',
        actor: 'hellgraph-membrane',
      }),
      signal: ctl.signal,
    })
    const body = await r.json() as { status?: string; receipt?: { id?: string }; error?: string }
    if (!r.ok || body.status !== 'ok' || !body.receipt?.id) {
      return { sealed: false, receiptRef: null, sealError: `gateway_${r.status}:${body.error ?? body.status ?? 'no_receipt'}` }
    }
    return { sealed: true, receiptRef: body.receipt.id, sealError: null }
  } catch (e) {
    return { sealed: false, receiptRef: null, sealError: `gateway_unreachable:${e instanceof Error ? e.message : String(e)}` }
  } finally {
    clearTimeout(timer)
  }
}

// ── POST /api/membrane/decide ──────────────────────────────────────────────────────────
function respond(res: http.ServerResponse, code: number, obj: unknown): void {
  res.writeHead(code, { 'content-type': 'application/json' })
  res.end(JSON.stringify(obj))
}

function decisionResponse(node: GraphNode, idempotent: boolean): Dict {
  const p = node.properties
  return {
    ok: true, decision: p['decision'], decisionRef: node.id,
    effectRequestRef: p['effectRequestRef'], intentRef: p['intentRef'],
    idempotencyKey: p['idempotencyKey'], idempotent,
    reasons: JSON.parse(String(p['reasons'] ?? '[]')) as string[],
    sealed: p['sealed'] === true, receiptRef: p['receiptRef'] ?? null, sealError: p['sealError'] ?? null,
    decisionHash: p['decisionHash'],
  }
}

/** Handle /api/membrane/* on the main port. Returns true when the request was handled. */
export function handleMembrane(g: MembraneGraph, req: http.IncomingMessage, res: http.ServerResponse, url: URL, body: string): boolean {
  if (!(req.method === 'POST' && url.pathname === '/api/membrane/decide')) return false
  void (async () => {
    let payload: unknown
    try { payload = JSON.parse(body || '{}') } catch {
      return respond(res, 400, { ok: false, error: 'invalid_json' })
    }
    // 1) The envelope must be a spec-valid EffectRequest (vendored schema, sha-asserted).
    const reqErrors = validateAgainst('EffectRequest', payload)
    if (reqErrors.length > 0) return respond(res, 400, { ok: false, error: 'invalid_effect_request', errors: reqErrors })
    const request = payload as Dict
    // 2) It must WRAP a spec-valid OrderIntent in parameters.orderIntent.
    const intent = (request['parameters'] as Dict)['orderIntent'] as Dict | undefined
    if (!intent || typeof intent !== 'object' || Array.isArray(intent)) {
      return respond(res, 400, { ok: false, error: 'invalid_effect_request', errors: ['EffectRequest.parameters.orderIntent: a spec-valid OrderIntent is required'] })
    }
    const intentErrors = validateAgainst('OrderIntent', intent)
    if (intentErrors.length > 0) return respond(res, 400, { ok: false, error: 'invalid_order_intent', errors: intentErrors })
    // 3) Binding: the effect must be requested BY the intent it wraps — one identity, no smuggling.
    if (request['requestedByEventRef'] !== intent['id']) {
      return respond(res, 400, {
        ok: false, error: 'intent_binding_mismatch',
        errors: [`requestedByEventRef ${String(request['requestedByEventRef'])} != parameters.orderIntent.id ${String(intent['id'])}`],
      })
    }
    // 4) Idempotency by key: same key twice = the SAME decision, never re-evaluated.
    const idempotencyKey = String(request['idempotencyKey'])
    const decisionId = decisionIdFor(idempotencyKey)
    const existing = g.getNode(decisionId)
    if (existing) {
      if (existing.properties['idempotencyKey'] !== idempotencyKey) {
        return respond(res, 409, { ok: false, error: 'idempotency_collision', decisionRef: decisionId })
      }
      return respond(res, 200, decisionResponse(existing, true))
    }
    // 5) Policy kernel v0 (deny-by-default). A deny IS a decision: recorded + sealed like an approve.
    const verdict = evaluatePolicy(policyKernelV0(), request, intent)
    const decidedAt = new Date().toISOString()
    const decision = buildDecision(request, intent, verdict, decidedAt)
    const selfCheck = validateAgainst('EffectDecision', decision)
    if (selfCheck.length > 0) { // unreachable if the boot probe passed; belt-and-suspenders
      return respond(res, 500, { ok: false, error: 'decision_nonconformant', errors: selfCheck })
    }
    // 6) Structural write: the EffectDecision node (scalar projection + the full
    //    spec-conformant object as canonical JSON — the log carries the OBJECT, not
    //    just a lossy projection; market-replay flatten() discipline).
    const props: Record<string, PropertyValue> = {
      decision: verdict.decision,
      effectRequestRef: String(request['id']),
      intentRef: String(intent['id']),
      idempotencyKey,
      decidedAt,
      decidedByActorRef: MEMBRANE_ACTOR,
      capability: String(request['capability']),
      effectKind: String(request['effectKind']),
      specVersion: SPEC_VERSION,
      decisionHash: String(decision['decisionHash']),
      rationale: String(decision['rationale']),
      reasons: JSON.stringify(verdict.reasons),
      decisionEvent: canonicalJson(decision as Json),
      sealed: false,
      receiptRef: null,
      sealError: null,
    }
    const vBefore = g.version()
    g.addNode(decisionId, ['EffectDecision'], props)
    const vAfter = g.version()
    // 7) Seal on the estate receipt spine; record the outcome HONESTLY either way.
    const seal = await sealDecision(String(decision['decisionHash']), vBefore, vAfter, process.env)
    const sealedProps: Record<string, PropertyValue> = {
      ...props, sealed: seal.sealed, receiptRef: seal.receiptRef, sealError: seal.sealError,
    }
    const node = g.addNode(decisionId, ['EffectDecision'], sealedProps)
    return respond(res, 200, decisionResponse(node, false))
  })()
  return true
}

// ── the write-path enforcer: B refuses to land without an approved A ───────────────────
export interface MembraneDenial {
  ok: false
  error: 'membrane_denied'
  reason: 'decision_mint_via_membrane_only' | 'missing_decisionRef' | 'missing_intentRef'
        | 'decision_not_found' | 'not_a_decision' | 'decision_not_approved' | 'intent_mismatch'
  decisionRef?: string
  intentRef?: string
  decision?: string
}

/** Gate one node write. {ok:true} = proceed. Structural, not advisory: called by the
 *  write route BEFORE the store mutates. */
export function membraneCheckNodeWrite(
  state: MembraneState,
  g: MembraneGraph,
  node: { id: string; labels: string[]; properties?: Record<string, unknown> },
): { ok: true } | { ok: false; body: MembraneDenial } {
  if (!state.enforce) return { ok: true }
  // Forge guard: EffectDecision nodes are minted ONLY through /api/membrane/decide —
  // by label AND by URN prefix, so neither a labeled forgery nor a label-stripped
  // overwrite of an existing decision can pass through the public write path.
  if (node.labels.includes('EffectDecision') || node.id.startsWith(DECISION_URN_PREFIX)) {
    return { ok: false, body: { ok: false, error: 'membrane_denied', reason: 'decision_mint_via_membrane_only' } }
  }
  if (!node.labels.includes('ExecutionReport')) return { ok: true }

  const p = node.properties ?? {}
  const declared = [p['intentRef'], p['orderIntentRef']].filter((x) => typeof x === 'string' && x.length > 0) as string[]
  if (declared.length === 0) {
    return { ok: false, body: { ok: false, error: 'membrane_denied', reason: 'missing_intentRef' } }
  }
  if (declared.length === 2 && declared[0] !== declared[1]) {
    return { ok: false, body: { ok: false, error: 'membrane_denied', reason: 'intent_mismatch', intentRef: declared.join(' != ') } }
  }
  const intentRef = declared[0]!
  const decisionRef = typeof p['decisionRef'] === 'string' ? (p['decisionRef'] as string) : ''
  if (!decisionRef) {
    return { ok: false, body: { ok: false, error: 'membrane_denied', reason: 'missing_decisionRef', intentRef } }
  }
  const decision = g.getNode(decisionRef)
  if (!decision) {
    return { ok: false, body: { ok: false, error: 'membrane_denied', reason: 'decision_not_found', decisionRef, intentRef } }
  }
  if (!decision.labels.includes('EffectDecision')) {
    return { ok: false, body: { ok: false, error: 'membrane_denied', reason: 'not_a_decision', decisionRef, intentRef } }
  }
  if (decision.properties['decision'] !== 'approved') {
    return { ok: false, body: { ok: false, error: 'membrane_denied', reason: 'decision_not_approved', decisionRef, intentRef, decision: String(decision.properties['decision']) } }
  }
  if (decision.properties['intentRef'] !== intentRef) {
    return { ok: false, body: { ok: false, error: 'membrane_denied', reason: 'intent_mismatch', decisionRef, intentRef } }
  }
  return { ok: true }
}
