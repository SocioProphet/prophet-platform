/**
 * Seal-the-Walls W1.3 — receipt unification: chain the engine's sealed() receipts
 * into the compute-gateway receipt spine (THE estate's one hash-chained,
 * Ed25519/in-toto-attested evidence line — never a parallel receipt lineage).
 *
 * After /api/graph/enrich | /api/graph/explore computes its proof-carrying result
 * (sealed sha256 over the ranked output + snapshot {seq,nodes,edges}), the engine
 * receipt is POSTed to compute-gateway POST /v1/engine-receipts with body
 * kind=enrich|explore (WHICH engine receipt this is — engine-seal is the gateway's
 * own COMPUTE kind, minted on its side, never sent by us). The gateway then
 * RECOMPUTES the seal byte-exactly, wraps it in the signed envelope, and
 * chains it — so ONE gateway verify() walks signature → engine hash → snapshot.seq
 * binding end-to-end. The HTTP response then carries spine:{ok:true, receiptId}.
 *
 * HONEST DEGRADATION (availability over ceremony, but never a false claim): a
 * sealing failure NEVER fails the graph read. The result still serves, with
 * spine:{ok:false, reason}, the /healthz `unsealedReceipts` counter incremented,
 * and a warn log — sealed is a verifiable statement here, not a vibe. The COUNTER
 * is exact and unsampled; only the log line is rate-limited (an outage under load
 * warned once per request and buried its own incident), and each emitted line
 * reports how many it suppressed.
 *
 * Env (deploy/values/hellgraph-service.yaml): GATEWAY_RECEIPTS=on enables the
 * attach; GATEWAY_URL (in-cluster: http://compute-gateway:8080); GATEWAY_TOKEN
 * (same compute-gateway-token Secret the materializer uses; optional — absent
 * just degrades honestly); GATEWAY_TIMEOUT_MS (default 3000 — a slow spine must
 * not stall a graph read); GATEWAY_PROJECT (chain namespace, default 'default');
 * SPINE_WARN_INTERVAL_MS (minimum gap between degrade warnings, default 60000;
 * 0 = never throttle). All read per call, so ops/tests can flip them without a
 * restart.
 */

export type SpineResult = { ok: true; receiptId: string } | { ok: false; reason: string }

let unsealed = 0
let lastWarnAt = 0
let suppressedWarns = 0

/** How many enrich/explore results served WITHOUT a spine receipt (reported in /healthz). */
export const unsealedReceipts = (): number => unsealed

/** How many degrade warnings the throttle swallowed since the last emitted line. */
export const suppressedSpineWarns = (): number => suppressedWarns

/** The values default is "on"; anything else disables the attach entirely (no spine field). */
export const spineEnabled = (): boolean => (process.env['GATEWAY_RECEIPTS'] ?? '').toLowerCase() === 'on'

/** Minimum gap between degrade warnings. 0 disables throttling (tests). */
const warnIntervalMs = (): number => {
  const raw = process.env['SPINE_WARN_INTERVAL_MS']
  if (raw === undefined || raw.trim() === '') return 60_000
  const n = Number(raw)
  return Number.isFinite(n) && n >= 0 ? n : 60_000
}

/**
 * Degrade honestly, but do not SHOUT once per request: a gateway outage under load
 * emitted one warn line per enrich/explore, which buries the incident it is meant to
 * report (and, on a busy node, everything else in the log with it).
 *
 * The counter is NOT sampled — `unsealed` moves on every single degradation, so
 * /healthz `unsealedReceipts` remains the exact, unthrottled truth an outage is
 * detected by. Only the LOG LINE is rate-limited, and each emitted line carries the
 * number of lines suppressed since the last one, so the log never implies the
 * problem happened fewer times than it did.
 */
function degrade(kind: string, reason: string): SpineResult {
  unsealed++ // always: the metric is the alarm, and an alarm may not be sampled
  const interval = warnIntervalMs()
  const now = Date.now()
  if (lastWarnAt === 0 || interval === 0 || now - lastWarnAt >= interval) {
    const alsoSuppressed = suppressedWarns > 0
      ? ` [+${suppressedWarns} similar warning(s) suppressed in the last ${Math.round(interval / 1000)}s]`
      : ''
    console.warn(`[hellgraph-service] engine ${kind} receipt NOT sealed to spine (unsealed total ${unsealed})${alsoSuppressed}: ${reason}`)
    lastWarnAt = now
    suppressedWarns = 0
  } else {
    suppressedWarns++
  }
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
