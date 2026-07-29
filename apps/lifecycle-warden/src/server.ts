/**
 * lifecycle-warden — the L5 governance EXECUTOR (blueprint-audit remediation).
 *
 * The engine shipped a complete lifecycle state machine (lifecycle.ts, 10 states
 * IngestedRaw…Deleted + TRANSITIONS + guards), a policy engine + retention scheduler
 * (policy.ts decide/dueTransitions/Governor), a canonical object store with a BYOS S3
 * seam (object-store.ts), and vendor-cache materialize/gc (vendor-cache.ts) — with
 * ZERO production callers: governance as a library nobody ran. This service runs it.
 *
 * Routes:
 *   GET  /healthz                    the truth: lastRun, dueCounts, auditHead, dryRun/enforce,
 *                                    unsealedRuns, storage + object counts
 *   POST /v1/run                     run one governance pass now (also on WARDEN_INTERVAL_SECONDS)
 *   POST /v1/objects                 { id, content, mime, residency, sensitiveFields?, ttlAt?,
 *                                      retentionDeleteAt?, vendorOptIn? } → ingest + govern
 *   GET  /v1/objects                 governed registry (id, state, schedule fields)
 *   GET  /v1/objects/:id             registry object + catalog entry (if ingested this boot)
 *   POST /v1/objects/:id/transition  { trigger } → gated, audited FSM transition
 *   POST /v1/objects/:id/hold        legal hold (policy flag + LegalHold state)
 *   POST /v1/objects/:id/release     release hold (→ Served)
 *   POST /v1/objects/:id/materialize { vendor, optIn, ttlMs } → L3 vendor egress (default-deny)
 *   GET  /v1/audit/head              chain head { seq, hash }
 *   GET  /v1/audit/verify            walk + re-hash every persisted chunk; reports tamper seq
 *
 * Mode: DRY-RUN by default. Enforcement requires BOTH levers — WARDEN_ENFORCE=on AND
 * WARDEN_DRY_RUN=off — and refuses to boot without MinIO credentials (fail-closed:
 * an enforcing warden with amnesia would re-plan deletes it can't account for).
 */
import * as http from 'node:http'
import { Warden } from './warden.js'
import { GatewaySealer, NoopSealer, type Sealer } from './seal.js'
import { MemoryBlobStore, type BlobStore } from './audit.js'
import { MinioBlobStore, MinioS3Client, connect, ensureBucket, parseEndpoint, type MinioConfig } from './minio-store.js'
import { S3ObjectBackend, type ObjectBackend, type Trigger } from '@socioprophet/hellgraph'

const PORT = Number(process.env.PORT ?? 8095)
const INTERVAL_S = Number(process.env.WARDEN_INTERVAL_SECONDS ?? 300)

export interface BootConfig {
  dryRun: boolean
  enforce: boolean
  minio: MinioConfig | null
  gatewayUrl: string
  gatewayToken: string
}

/**
 * Resolve + validate boot config. Throws on the fail-closed cases so both the process
 * (exit 1) and the tests can assert refusal without spawning.
 */
export function resolveBootConfig(env: NodeJS.ProcessEnv): BootConfig {
  const enforceFlag = (env.WARDEN_ENFORCE ?? 'off').toLowerCase() === 'on'
  const dryRunFlag = (env.WARDEN_DRY_RUN ?? 'on').toLowerCase() !== 'off'
  const enforce = enforceFlag && !dryRunFlag
  const endpoint = (env.MINIO_ENDPOINT ?? '').trim()
  const accessKey = (env.MINIO_ACCESS_KEY ?? '').trim()
  const secretKey = (env.MINIO_SECRET_KEY ?? '').trim()
  let minio: MinioConfig | null = null
  if (endpoint || accessKey || secretKey) {
    if (!endpoint || !accessKey || !secretKey) {
      throw new Error('partial MinIO config: MINIO_ENDPOINT, MINIO_ACCESS_KEY and MINIO_SECRET_KEY must all be set (or none, for dry-run memory mode)')
    }
    minio = { ...parseEndpoint(endpoint), accessKey, secretKey, bucket: (env.MINIO_BUCKET ?? 'lifecycle-warden').trim() }
  }
  if (enforceFlag && !minio) {
    // FAIL-CLOSED: enforcement without durable storage/credentials is refused outright.
    throw new Error('WARDEN_ENFORCE=on but MinIO credentials are missing — refusing to start (fail-closed). Provide MINIO_ENDPOINT + MINIO_ACCESS_KEY/MINIO_SECRET_KEY via secretEnv.')
  }
  return {
    dryRun: !enforce,
    enforce,
    minio,
    gatewayUrl: env.COMPUTE_GATEWAY_URL ?? 'http://compute-gateway:8080',
    gatewayToken: (env.GATEWAY_TOKEN ?? '').trim(),
  }
}

interface RunStatus {
  at: number
  runId: string
  dryRun: boolean
  objectsScanned: number
  dueCount: number
  appliedCount: number
  plannedCount: number
  gcCount: number
  sealed: boolean
  receiptId?: string
  sealError?: string
  error?: string
}

export interface WardenService {
  warden: Warden
  server: http.Server
  stop(): Promise<void>
  runNow(): Promise<RunStatus>
}

export async function start(cfg: BootConfig, port = PORT, intervalSeconds = INTERVAL_S): Promise<WardenService> {
  let blobs: BlobStore
  let backend: ObjectBackend | undefined
  let storage: 'minio' | 'memory'
  if (cfg.minio) {
    const client = connect(cfg.minio)
    await ensureBucket(client, cfg.minio.bucket) // fail-closed: unreachable MinIO refuses boot
    blobs = new MinioBlobStore(client, cfg.minio.bucket)
    backend = new S3ObjectBackend(new MinioS3Client(client), cfg.minio.bucket, 'objects/')
    storage = 'minio'
  } else {
    blobs = new MemoryBlobStore()
    backend = undefined // engine InMemoryObjectBackend
    storage = 'memory'
  }

  const warden = new Warden({
    dryRun: cfg.dryRun,
    blobs,
    ...(backend ? { backend } : {}),
    ...(process.env.WARDEN_MASK_PASSPHRASE ? { maskPassphrase: process.env.WARDEN_MASK_PASSPHRASE } : {}),
  })
  await warden.load()

  const sealer: Sealer = cfg.gatewayToken ? new GatewaySealer(cfg.gatewayUrl, cfg.gatewayToken) : new NoopSealer()
  const sealingEnabled = Boolean(cfg.gatewayToken)

  let lastRun: RunStatus | null = null
  let unsealedRuns = 0
  let sealedRuns = 0
  let inflight: Promise<RunStatus> | null = null

  function runNow(): Promise<RunStatus> {
    if (inflight) return inflight // interval + manual /v1/run coalesce onto one pass
    inflight = doRun().finally(() => { inflight = null })
    return inflight
  }

  async function doRun(): Promise<RunStatus> {
    try {
      const report = await warden.runOnce()
      let status: RunStatus = {
        at: report.at, runId: report.runId, dryRun: report.dryRun,
        objectsScanned: report.objectsScanned, dueCount: report.dueCount,
        appliedCount: report.applied.length, plannedCount: report.planned.length,
        gcCount: report.gcCount, sealed: false,
      }
      const seal = await sealer.seal(report)
      if (seal.ok) {
        sealedRuns += 1
        status = { ...status, sealed: true, ...(seal.receiptId ? { receiptId: seal.receiptId } : {}) }
      } else {
        // Honest degradation: the audit chain above already committed locally; only the
        // spine attestation is missing, and healthz says exactly how many runs lack it.
        unsealedRuns += 1
        status = { ...status, sealed: false, ...(seal.error ? { sealError: seal.error } : {}) }
      }
      lastRun = status
      return status
    } catch (err) {
      const status: RunStatus = {
        at: Date.now(), runId: 'failed', dryRun: cfg.dryRun, objectsScanned: 0, dueCount: 0,
        appliedCount: 0, plannedCount: 0, gcCount: 0, sealed: false, error: (err as Error).message,
      }
      lastRun = status
      return status
    }
  }

  const timer = intervalSeconds > 0 ? setInterval(() => { void runNow() }, intervalSeconds * 1000) : null
  if (timer) timer.unref()

  function json(res: http.ServerResponse, code: number, body: unknown): void {
    const s = JSON.stringify(body)
    res.writeHead(code, { 'content-type': 'application/json' })
    res.end(s)
  }

  function readBody(req: http.IncomingMessage): Promise<string> {
    return new Promise((resolve, reject) => {
      let d = ''
      req.on('data', (c: Buffer) => { d += c.toString(); if (d.length > 5_000_000) req.destroy() })
      req.on('end', () => resolve(d))
      req.on('error', reject)
    })
  }

  const server = http.createServer((req, res) => {
    void (async () => {
      const url = new URL(req.url ?? '/', `http://localhost:${port}`)
      const p = url.pathname

      if (req.method === 'GET' && p === '/healthz') {
        return json(res, 200, {
          ok: true,
          service: 'lifecycle-warden',
          dryRun: cfg.dryRun,
          enforce: cfg.enforce,
          intervalSeconds,
          storage,
          objects: warden.objects().length,
          lastRun,
          dueCounts: lastRun && !lastRun.error ? (await peekDueCounts()) : {},
          auditHead: warden.audit.head(),
          sealing: sealingEnabled,
          sealedRuns,
          unsealedRuns,
        })
      }

      if (req.method === 'POST' && p === '/v1/run') {
        return json(res, 200, await runNow())
      }

      if (req.method === 'POST' && p === '/v1/objects') {
        const b = JSON.parse((await readBody(req)) || '{}') as {
          id?: string, content?: string, mime?: string, residency?: string,
          sensitiveFields?: string[], ttlAt?: number, retentionDeleteAt?: number, vendorOptIn?: boolean,
        }
        if (!b.id || typeof b.content !== 'string') return json(res, 400, { ok: false, error: 'id and content required' })
        try {
          const { entry, object } = await warden.ingest(b.id, b.content, {
            mime: b.mime ?? 'text/plain',
            residency: b.residency ?? 'sovereign',
            ...(b.sensitiveFields ? { sensitiveFields: b.sensitiveFields } : {}),
            ...(b.ttlAt !== undefined ? { ttlAt: b.ttlAt } : {}),
            ...(b.retentionDeleteAt !== undefined ? { retentionDeleteAt: b.retentionDeleteAt } : {}),
            ...(b.vendorOptIn !== undefined ? { vendorOptIn: b.vendorOptIn } : {}),
          })
          return json(res, 201, { ok: true, object, contentHash: entry.contentHash, codexSha: entry.codex._sha256 })
        } catch (err) {
          return json(res, 409, { ok: false, error: (err as Error).message })
        }
      }

      if (req.method === 'GET' && p === '/v1/objects') {
        return json(res, 200, { ok: true, objects: warden.objects() })
      }

      const obj = p.match(/^\/v1\/objects\/([^/]+)(?:\/([a-z]+))?$/)
      if (obj) {
        const [, id, action] = obj
        if (req.method === 'GET' && !action) {
          const object = warden.object(id!)
          if (!object) return json(res, 404, { ok: false, error: `unknown object: ${id}` })
          return json(res, 200, { ok: true, object, catalog: warden.catalogEntry(id!) ?? null })
        }
        if (req.method === 'POST' && action) {
          if (!warden.object(id!)) return json(res, 404, { ok: false, error: `unknown object: ${id}` })
          try {
            if (action === 'transition') {
              const b = JSON.parse((await readBody(req)) || '{}') as { trigger?: string }
              if (!b.trigger) return json(res, 400, { ok: false, error: 'trigger required' })
              return json(res, 200, { ok: true, object: await warden.advance(id!, b.trigger as Trigger) })
            }
            if (action === 'hold') return json(res, 200, { ok: true, object: await warden.hold(id!) })
            if (action === 'release') return json(res, 200, { ok: true, object: await warden.releaseHold(id!) })
            if (action === 'materialize') {
              const b = JSON.parse((await readBody(req)) || '{}') as { vendor?: string, optIn?: boolean, ttlMs?: number }
              if (!b.vendor) return json(res, 400, { ok: false, error: 'vendor required' })
              const r = await warden.materialize(id!, b.vendor, { optIn: b.optIn === true, ttlMs: b.ttlMs ?? 3_600_000 })
              return json(res, r.ok ? 200 : 403, { ok: r.ok, ...(r.reason ? { reason: r.reason } : {}), object: warden.object(id!) })
            }
          } catch (err) {
            return json(res, 500, { ok: false, error: (err as Error).message })
          }
        }
      }

      if (req.method === 'GET' && p === '/v1/audit/head') {
        return json(res, 200, { ok: true, head: warden.audit.head(), pending: warden.audit.pendingCount() })
      }
      if (req.method === 'GET' && p === '/v1/audit/verify') {
        const v = await warden.audit.verify()
        return json(res, v.ok ? 200 : 409, v)
      }

      return json(res, 404, { ok: false, error: `no route: ${req.method} ${p}` })
    })().catch((err: Error) => {
      res.writeHead(500, { 'content-type': 'application/json' })
      res.end(JSON.stringify({ ok: false, error: err.message }))
    })
  })

  // dueCounts for healthz without mutating anything: a pure dueTransitions sweep.
  async function peekDueCounts(): Promise<Record<string, number>> {
    const { dueTransitions } = await import('@socioprophet/hellgraph')
    const counts: Record<string, number> = {}
    const now = Date.now()
    for (const o of warden.objects()) {
      for (const d of dueTransitions(o, now)) counts[d.trigger] = (counts[d.trigger] ?? 0) + 1
    }
    return counts
  }

  await new Promise<void>((resolve) => server.listen(port, resolve))
  return {
    warden,
    server,
    runNow,
    stop: async () => {
      if (timer) clearInterval(timer)
      await new Promise<void>((resolve) => server.close(() => resolve()))
    },
  }
}

/* c8 ignore start — process entrypoint */
if (require.main === module) {
  let cfg: BootConfig
  try {
    cfg = resolveBootConfig(process.env)
  } catch (err) {
    console.error(`[lifecycle-warden] REFUSING TO START: ${(err as Error).message}`)
    process.exit(1)
  }
  start(cfg)
    .then((svc) => {
      console.log(`[lifecycle-warden] listening on :${PORT} — mode=${cfg.enforce ? 'ENFORCE' : 'dry-run'} storage=${cfg.minio ? 'minio' : 'memory'} interval=${INTERVAL_S}s`)
      if ((process.env.WARDEN_ENFORCE ?? 'off').toLowerCase() === 'on' && !cfg.enforce) {
        console.warn('[lifecycle-warden] WARDEN_ENFORCE=on but WARDEN_DRY_RUN is not "off" — dry-run wins; throw BOTH levers to enforce')
      }
      // First pass shortly after boot, so healthz shows real lastRun/dueCounts quickly.
      setTimeout(() => { void svc.runNow() }, 3_000).unref()
    })
    .catch((err: Error) => {
      console.error(`[lifecycle-warden] boot failed (fail-closed): ${err.message}`)
      process.exit(1)
    })
}
/* c8 ignore stop */
