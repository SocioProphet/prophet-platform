/**
 * Warden core — the L5 governance EXECUTOR over the engine's complete-but-never-called
 * lifecycle machinery (blueprint-audit finding: lifecycle.ts FSM + policy.ts
 * Governor/dueTransitions + object-store.ts CanonicalObjectStore + vendor-cache.ts
 * VendorCacheManager all had ZERO production callers).
 *
 * One Warden owns:
 *   - a governed-object REGISTRY (ContentObject + legalHold flag) — the durable
 *     governance state, persisted as JSON to the object store on every mutation;
 *   - the engine Governor, constructed over the warden's hash-chained audit, so every
 *     decision / transition / blocked event the engine emits lands on the chain;
 *   - a CanonicalObjectStore over the real MinIO S3ObjectBackend (bytes are
 *     content-addressed and codex-sealed; the in-memory catalog is per-boot
 *     enrichment — the engine exposes no catalog-rehydrate API — while bytes,
 *     registry, and audit chain are the durable truth);
 *   - a VendorCacheManager for L3 vendor materialization. Egress stays OPT-IN and
 *     default-deny: no vendor clients are configured unless injected, and every
 *     materialize is gated by the engine's policy engine anyway.
 *
 * runOnce() is the retention scheduler made real: policy.ts dueTransitions → (enforce)
 * Governor.runRetention → VendorCacheManager.gc, or (dry-run, the default) an audited
 * plan of exactly what WOULD happen — including whether the delete-gate would block it.
 */
import {
  CanonicalObjectStore,
  Governor,
  InMemoryObjectBackend,
  S3ObjectBackend,
  StaticKeyProvider,
  VendorCacheManager,
  canTransition,
  dueTransitions,
  validateModel,
  type CatalogEntry,
  type ContentObject,
  type IngestMeta,
  type ObjectBackend,
  type Trigger,
  type VendorFilesClient,
} from '@socioprophet/hellgraph'
import { randomBytes, randomUUID } from 'node:crypto'
import { HashChainedAudit, type BlobStore, type ChainHead } from './audit.js'

export type GovernedObject = ContentObject & { legalHold?: boolean }

const REGISTRY_KEY = 'state/objects.json'

export interface PlannedTransition {
  objectId: string
  trigger: Trigger
  to: string
  /** Would the gated transition actually apply? false = the delete/egress gate or a guard blocks it. */
  wouldApply: boolean
  reason?: string
}

export interface AppliedTransition { objectId: string, from: string, to: string, trigger: Trigger }

export interface RunReport {
  runId: string
  at: number
  dryRun: boolean
  objectsScanned: number
  dueCount: number
  /** due triggers by name — the healthz dueCounts surface. */
  dueByTrigger: Record<string, number>
  planned: PlannedTransition[]
  applied: AppliedTransition[]
  /** enforce: handles actually GC'd. dry-run: expired handles that WOULD be GC'd. */
  gcCount: number
  auditHead: ChainHead | null
}

export interface WardenOptions {
  dryRun: boolean
  blobs: BlobStore | null
  backend?: ObjectBackend
  /** Injected vendor Files clients (none by default — egress stays structurally impossible
   *  until a client is configured AND the per-object opt-in passes the policy gate). */
  vendorClients?: Record<string, VendorFilesClient>
  maskPassphrase?: string
}

export class Warden {
  readonly audit: HashChainedAudit
  readonly governor: Governor
  readonly store: CanonicalObjectStore
  readonly vendorCache: VendorCacheManager
  readonly dryRun: boolean
  private readonly blobs: BlobStore | null
  private readonly registry = new Map<string, GovernedObject>()
  private readonly vendorHandles: { objectId: string, vendor: string, ttlAt: number }[] = []

  constructor(opts: WardenOptions) {
    // The model invariants (Deleted terminal; LegalHold has NO retention_delete edge) are
    // a boot precondition — a warden running against a broken model must not start.
    validateModel()
    this.dryRun = opts.dryRun
    this.blobs = opts.blobs
    this.audit = new HashChainedAudit(opts.blobs)
    this.governor = new Governor(undefined, this.audit)
    this.store = new CanonicalObjectStore(opts.backend ?? new InMemoryObjectBackend())
    // Masking key for the (default-deny) vendor egress path. Per-boot random unless a
    // stable passphrase is configured — fine, because a handle's lifetime ≤ process
    // lifetime unless operators deliberately configure stable masking.
    const key = StaticKeyProvider.fromPassphrase(opts.maskPassphrase ?? randomBytes(32).toString('hex'))
    this.vendorCache = new VendorCacheManager(this.store, this.governor, key, opts.vendorClients ?? {})
  }

  /** Resume audit chain + governed-object registry from the blob store (boot). */
  async load(): Promise<void> {
    await this.audit.load()
    if (!this.blobs) return
    const raw = await this.blobs.get(REGISTRY_KEY)
    if (!raw) return
    const parsed = JSON.parse(raw.toString('utf8')) as { objects: GovernedObject[] }
    for (const o of parsed.objects) this.registry.set(o.id, o)
  }

  private async persistRegistry(): Promise<void> {
    if (!this.blobs) return
    await this.blobs.put(REGISTRY_KEY, Buffer.from(JSON.stringify({ objects: [...this.registry.values()] })))
  }

  objects(): GovernedObject[] { return [...this.registry.values()] }
  object(id: string): GovernedObject | undefined { return this.registry.get(id) }
  catalogEntry(id: string): CatalogEntry | undefined { return this.store.entry(id) }

  /** Ingest content through the canonical store (bytes → content-addressed backend,
   *  codex seal, catalog@Normalized) and register it for governance. */
  async ingest(id: string, content: string, meta: IngestMeta & {
    ttlAt?: number, retentionDeleteAt?: number, vendorOptIn?: boolean,
  }): Promise<{ entry: CatalogEntry, object: GovernedObject }> {
    if (this.registry.has(id)) throw new Error(`object already governed: ${id}`)
    const entry = await this.store.ingest(id, content, meta)
    const object: GovernedObject = {
      ...this.store.toPolicyObject(id),
      ...(meta.ttlAt !== undefined ? { ttlAt: meta.ttlAt } : {}),
      ...(meta.retentionDeleteAt !== undefined ? { retentionDeleteAt: meta.retentionDeleteAt } : {}),
      ...(meta.vendorOptIn !== undefined ? { vendorOptIn: meta.vendorOptIn } : {}),
    }
    this.registry.set(id, object)
    this.audit.append({ ts: Date.now(), kind: 'ingest', objectId: id, to: object.state, contentHash: entry.contentHash })
    await this.audit.flush()
    await this.persistRegistry()
    return { entry, object }
  }

  /** Apply one lifecycle trigger through the engine Governor — gated (delete/egress
   *  decisions) + audited. Blocked transitions leave the object unchanged. */
  async advance(id: string, trigger: Trigger): Promise<GovernedObject> {
    const o = this.registry.get(id)
    if (!o) throw new Error(`unknown object: ${id}`)
    this.governor.transition(o, trigger)
    this.syncCatalogState(o)
    await this.audit.flush()
    await this.persistRegistry()
    return o
  }

  /** Place a legal hold: policy flag (delete-gate denies while held) + FSM state. */
  async hold(id: string): Promise<GovernedObject> {
    const o = this.registry.get(id)
    if (!o) throw new Error(`unknown object: ${id}`)
    o.legalHold = true
    o.holdReleased = false
    this.governor.transition(o, 'legal_hold')
    this.syncCatalogState(o)
    await this.audit.flush()
    await this.persistRegistry()
    return o
  }

  /** Release a hold back to Served (the only non-delete exit LegalHold has). */
  async releaseHold(id: string): Promise<GovernedObject> {
    const o = this.registry.get(id)
    if (!o) throw new Error(`unknown object: ${id}`)
    o.holdReleased = true
    o.legalHold = false
    this.governor.transition(o, 'hold_release')
    this.syncCatalogState(o)
    await this.audit.flush()
    await this.persistRegistry()
    return o
  }

  /** Vendor materialization (L3) — opt-in egress through the engine's policy gate. */
  async materialize(id: string, vendor: string, opts: { optIn: boolean, ttlMs: number }): Promise<{ ok: boolean, reason?: string }> {
    const res = await this.vendorCache.materialize(id, vendor, { optIn: opts.optIn, ttlMs: opts.ttlMs })
    if (res.ok) {
      this.vendorHandles.push({ objectId: id, vendor, ttlAt: res.handle.ttlAt })
      const o = this.registry.get(id)
      if (o) { o.state = 'VendorMaterialized'; o.ttlAt = res.handle.ttlAt }
      await this.persistRegistry()
    }
    await this.audit.flush()
    return res.ok ? { ok: true } : { ok: false, reason: res.reason }
  }

  /** Catalog state mirrors registry state for objects ingested this boot. */
  private syncCatalogState(o: GovernedObject): void {
    if (this.store.entry(o.id)) this.store.setState(o.id, o.state)
  }

  /**
   * One governance pass — the retention scheduler the engine shipped but nothing ran.
   * Dry-run (default): audit exactly what WOULD happen, mutate nothing, delete nothing.
   * Enforce: Governor.runRetention applies every due transition through the delete-gate
   * (legal hold structurally blocks — LegalHold has no retention_delete edge, and the
   * policy denies delete while held), then VendorCacheManager.gc reaps expired handles.
   */
  async runOnce(now = Date.now()): Promise<RunReport> {
    const runId = randomUUID()
    const planned: PlannedTransition[] = []
    const applied: AppliedTransition[] = []
    const dueByTrigger: Record<string, number> = {}
    let dueCount = 0

    for (const o of this.registry.values()) {
      const due = dueTransitions(o, now)
      dueCount += due.length
      for (const d of due) dueByTrigger[d.trigger] = (dueByTrigger[d.trigger] ?? 0) + 1
      if (due.length === 0) continue
      if (this.dryRun) {
        for (const d of due) {
          // Evaluate the same gates enforcement would apply, without mutating: the
          // policy delete-gate (legal hold, non-negotiable) + the FSM edge/guard.
          const gate = this.governor.decide({ action: 'delete', object: o })
          const would = gate.effect === 'allow' && canTransition(o, d.trigger)
          planned.push({
            objectId: o.id, trigger: d.trigger, to: d.to, wouldApply: would,
            ...(would ? {} : { reason: gate.effect === 'deny' ? gate.reason : 'edge guard fails' }),
          })
          this.audit.append({
            ts: Date.now(), kind: 'planned', objectId: o.id, trigger: d.trigger,
            to: d.to, wouldApply: would, dryRun: true,
          })
        }
      } else {
        const before = o.state
        this.governor.runRetention(o, now)
        if (o.state !== before) {
          applied.push({ objectId: o.id, from: before, to: o.state, trigger: due[0]!.trigger })
          this.syncCatalogState(o)
        }
      }
    }

    // Vendor-cache GC: enforce reaps (vendor delete + handle drop + →ExpiredVendorCache);
    // dry-run only counts what has expired.
    let gcCount = 0
    if (this.dryRun) {
      gcCount = this.vendorHandles.filter((h) => h.ttlAt <= now).length
    } else {
      gcCount = await this.vendorCache.gc(now)
      for (let i = this.vendorHandles.length - 1; i >= 0; i--) {
        if (this.vendorHandles[i]!.ttlAt <= now) this.vendorHandles.splice(i, 1)
      }
      for (const o of this.registry.values()) this.syncCatalogState(o)
    }

    this.audit.append({
      ts: Date.now(), kind: 'run', runId, dryRun: this.dryRun, objectsScanned: this.registry.size,
      dueCount, appliedCount: applied.length, plannedCount: planned.length, gcCount,
    })
    const auditHead = await this.audit.flush()
    if (!this.dryRun) await this.persistRegistry()

    return {
      runId, at: now, dryRun: this.dryRun, objectsScanned: this.registry.size,
      dueCount, dueByTrigger, planned, applied, gcCount, auditHead,
    }
  }
}
