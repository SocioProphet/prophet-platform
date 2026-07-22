/**
 * federation — the ORG SUPER-PEER, hosted inside hellgraph-service (opt-in).
 *
 * The membership model Michael specified for the Noetica→platform loop: a user opts in
 * ONCE (their writer key is admitted via a signed addWriter control op) and from then on
 * their local graph changes percolate to the org graph automatically — no publish button,
 * no per-document upload. Participants replicate over Hyperswarm (P2P, discovery by the
 * federation base key — no ingress or cluster exposure needed); the super-peer is an
 * INDEX, never a data owner, so its storage is reconstructible from participants' logs.
 *
 * Governance is fail-closed: no FEDERATION_HMAC_SECRET → federation refuses to start.
 * /admit requires a bearer token minted from that secret carrying the 'admit' scope —
 * admission IS the identity primitive until the login work lands (P007/P019).
 *
 * Env:
 *   FEDERATION_ENABLED=1          opt in (default off — the graph service runs unchanged)
 *   FEDERATION_HMAC_SECRET        token-mint/verify secret (required when enabled)
 *   FEDERATION_DIR                corestore dir (default /data/federation; ephemeral OK —
 *                                 the index re-materializes from participant replication)
 */
import * as os from 'node:os'
import * as path from 'node:path'
import type * as http from 'node:http'
import { SuperPeer, HmacTokenVerifier, bearer, hasScope } from '@socioprophet/hellgraph'

export interface Federation {
  sp: SuperPeer
  verifier: HmacTokenVerifier
}

export async function startFederation(): Promise<Federation | null> {
  if (process.env['FEDERATION_ENABLED'] !== '1') return null
  const secret = process.env['FEDERATION_HMAC_SECRET'] ?? ''
  if (!secret) {
    // fail-closed, but never take the graph service down with it
    console.error('[federation] FEDERATION_ENABLED=1 but FEDERATION_HMAC_SECRET unset — refusing to start ungoverned; federation stays OFF')
    return null
  }
  const dir = process.env['FEDERATION_DIR'] || path.join(os.tmpdir(), 'hellgraph-federation')
  const verifier = HmacTokenVerifier.fromSecret(secret)
  let sp: SuperPeer
  try {
    sp = await SuperPeer.create(dir, { auth: verifier })
  } catch (e) {
    // autobase/corestore are optional deps — an image built without them degrades honestly
    console.error(`[federation] super-peer unavailable (autobase/corestore missing?): ${String((e as Error)?.message ?? e)}`)
    return null
  }
  if (process.env['FEDERATION_SWARM'] !== '0') {   // '0' = direct-replication only (tests; air-gapped tiers)
    try {
      await sp.joinSwarm()
      console.log('[federation] hyperswarm joined — participants can discover by base key')
    } catch (e) {
      console.error(`[federation] swarm unavailable (hyperswarm optional) — direct replication only: ${String((e as Error)?.message ?? e)}`)
    }
  }
  console.log(`[federation] org super-peer LIVE — baseKey=${sp.baseKey()}`)
  return { sp, verifier }
}

/** Routes on the MAIN service port (no second listener, nothing new exposed):
 *    GET  /api/federation/status  → open: what a cockpit needs to render federation state
 *    POST /api/federation/admit   → {writerKey}; bearer token with 'admit' scope (governance)
 *  Returns true when the request was handled. */
export function handleFederation(
  fed: Federation | null,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  url: URL,
  body: string,
): boolean {
  const json = (code: number, obj: unknown): void => {
    res.writeHead(code, { 'content-type': 'application/json' })
    res.end(JSON.stringify(obj))
  }

  if (req.method === 'GET' && url.pathname === '/api/federation/status') {
    if (!fed) { json(200, { enabled: false }); return true }
    void fed.sp.health()
      .then((h) => json(200, { enabled: true, authEnforced: fed.sp.authEnforced,
                               baseKey: fed.sp.baseKey(), writerKey: fed.sp.writerKey(), health: h }))
      .catch((e) => json(200, { enabled: true, baseKey: fed.sp.baseKey(),
                                degraded: String((e as Error)?.message ?? e) }))
    return true
  }

  if (req.method === 'POST' && url.pathname === '/api/federation/admit') {
    if (!fed) { json(503, { error: 'federation disabled' }); return true }
    const principal = fed.verifier.verify(bearer(req.headers['authorization']) ?? '')
    if (!principal || !hasScope(principal, 'admit')) {
      json(401, { error: 'admit requires a bearer token with the admit scope' })
      return true
    }
    let writerKey = ''
    try { writerKey = String((JSON.parse(body || '{}') as { writerKey?: string }).writerKey ?? '') } catch { /* fall through */ }
    if (!/^[0-9a-f]{64}$/i.test(writerKey)) {
      json(400, { error: 'writerKey must be a 64-hex-char participant key' })
      return true
    }
    void fed.sp.admit(writerKey)
      .then(() => json(200, { admitted: writerKey, by: principal.id }))
      .catch((e) => json(500, { error: String((e as Error)?.message ?? e) }))
    return true
  }

  return false
}
