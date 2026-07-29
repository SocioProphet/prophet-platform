/**
 * Seal-the-Walls W1.3 — receipt unification: chain the engine's sealed() receipts
 * into the compute-gateway receipt spine (THE estate's one hash-chained,
 * Ed25519/in-toto-attested evidence line — never a parallel receipt lineage).
 *
 * After /api/graph/enrich | /api/graph/explore computes its proof-carrying result
 * (sealed sha256 over the ranked output + snapshot {seq,nodes,edges}), the engine
 * receipt is POSTed to compute-gateway POST /v1/engine-receipts (kind=engine-seal),
 * which RECOMPUTES the seal byte-exactly, wraps it in the signed envelope, and
 * chains it — so ONE gateway verify() walks signature → engine hash → snapshot.seq
 * binding end-to-end. The HTTP response then carries spine:{ok:true, receiptId}.
 *
 * HONEST DEGRADATION (availability over ceremony, but never a false claim): a
 * sealing failure NEVER fails the graph read. The result still serves, with
 * spine:{ok:false, reason}, the /healthz `unsealedReceipts` counter incremented,
 * and a warn log — sealed is a verifiable statement here, not a vibe.
 *
 * Env (deploy/values/hellgraph-service.yaml): GATEWAY_RECEIPTS=on enables the
 * attach; GATEWAY_URL (in-cluster: http://compute-gateway:8080); GATEWAY_TOKEN
 * (same compute-gateway-token Secret the materializer uses; optional — absent
 * just degrades honestly); GATEWAY_TIMEOUT_MS (default 3000 — a slow spine must
 * not stall a graph read); GATEWAY_PROJECT (chain namespace, default 'default').
 * All read per call, so ops/tests can flip them without a restart.
 */

export type SpineResult = { ok: true; receiptId: string } | { ok: false; reason: string }

let unsealed = 0

/** How many enrich/explore results served WITHOUT a spine receipt (reported in /healthz). */
export const unsealedReceipts = (): number => unsealed

/** The values default is "on"; anything else disables the attach entirely (no spine field). */
export const spineEnabled = (): boolean => (process.env['GATEWAY_RECEIPTS'] ?? '').toLowerCase() === 'on'

function degrade(kind: string, reason: string): SpineResult {
  unsealed++
  console.warn(`[hellgraph-service] engine ${kind} receipt NOT sealed to spine (unsealed total ${unsealed}): ${reason}`)
  return { ok: false, reason }
}

/** POST one engine sealed() receipt to the gateway spine. Resolves, never rejects. */
export async function sealToSpine(
  kind: 'enrich' | 'explore',
  engineReceipt: unknown,
  subject: Record<string, unknown>,
): Promise<SpineResult> {
  const base = (process.env['GATEWAY_URL'] ?? 'http://compute-gateway:8080').replace(/\/+$/, '')
  const token = process.env['GATEWAY_TOKEN'] ?? ''
  const timeoutMs = Number(process.env['GATEWAY_TIMEOUT_MS'] ?? 3000) || 3000
  const project = process.env['GATEWAY_PROJECT'] ?? 'default'
  try {
    const r = await fetch(`${base}/v1/engine-receipts`, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        ...(token ? { authorization: `Bearer ${token}` } : {}),
      },
      // the receipt object serializes here with the SAME V8 JSON.stringify that
      // minted its hash — the gateway recomputes over exactly these semantics.
      body: JSON.stringify({ kind, engineReceipt, subject, project, actor: 'hellgraph-service' }),
      signal: AbortSignal.timeout(timeoutMs),
    })
    if (!r.ok) {
      const text = await r.text().catch(() => '')
      return degrade(kind, `gateway HTTP ${r.status}: ${text.slice(0, 300)}`)
    }
    const body = (await r.json()) as { receiptId?: unknown }
    if (typeof body.receiptId !== 'string' || body.receiptId.length === 0) {
      return degrade(kind, 'gateway response missing receiptId')
    }
    return { ok: true, receiptId: body.receiptId }
  } catch (e) {
    return degrade(kind, `gateway unreachable: ${e instanceof Error ? e.message : String(e)}`)
  }
}
