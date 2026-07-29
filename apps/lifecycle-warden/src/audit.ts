/**
 * Hash-chained, append-only governance audit.
 *
 * Why not the engine's InMemoryAuditLog: it is a bounded RING buffer — append past the
 * cap and `shift()` silently drops the oldest entry. Right call for a DoS-exposed
 * super-peer, structurally wrong for an L5 governance executor, where "the audit log
 * is append-only" is the property the service exists to provide. This log is the
 * warden's replacement: every entry carries `prev` = sha256(canonical(previous entry)),
 * sealed chunks persist to the object store (MinIO), and only the un-flushed tail plus
 * the chain head live in memory — so the log can grow forever without either dropping
 * entries or eating the heap.
 *
 * Chunks self-link (each records `prevChunk`), so the whole history is walkable from
 * `audit/head.json` alone — no index object that would itself grow without bound.
 * Tampering with any persisted entry breaks the recomputed chain at that point and
 * `verify()` says so, with the seq where continuity died.
 */
import { createHash } from 'node:crypto'

/** Minimal blob persistence the audit needs — MinIO in prod, in-memory in tests. */
export interface BlobStore {
  put(key: string, body: Buffer): Promise<void>
  get(key: string): Promise<Buffer | undefined>
}

export class MemoryBlobStore implements BlobStore {
  private readonly blobs = new Map<string, Buffer>()
  async put(key: string, body: Buffer): Promise<void> { this.blobs.set(key, Buffer.from(body)) }
  async get(key: string): Promise<Buffer | undefined> { const b = this.blobs.get(key); return b ? Buffer.from(b) : undefined }
  keys(): string[] { return [...this.blobs.keys()] }
}

export interface AuditEntry {
  seq: number
  ts: number
  /** sha256(canonical(previous entry)); GENESIS_PREV for seq 0. */
  prev: string
  /** The audited event — engine AuditEvents (decision/transition/blocked) and warden events (planned/run/…). */
  event: object
}

export interface ChainHead { seq: number, hash: string }

interface Chunk {
  firstSeq: number
  lastSeq: number
  /** Key of the previous chunk, or null for the first chunk — the walkable spine. */
  prevChunk: string | null
  entries: AuditEntry[]
}

interface HeadDoc extends ChainHead { lastChunk: string | null }

export const GENESIS_PREV = createHash('sha256').update('lifecycle-warden-audit-genesis').digest('hex')

/** Deterministic JSON: object keys sorted at every depth, so hashing is stable. */
export function canonicalJson(v: unknown): string {
  if (v === null || typeof v !== 'object') return JSON.stringify(v)
  if (Array.isArray(v)) return `[${v.map(canonicalJson).join(',')}]`
  const o = v as Record<string, unknown>
  const keys = Object.keys(o).filter((k) => o[k] !== undefined).sort()
  return `{${keys.map((k) => `${JSON.stringify(k)}:${canonicalJson(o[k])}`).join(',')}}`
}

export function entryHash(e: AuditEntry): string {
  return createHash('sha256').update(canonicalJson(e)).digest('hex')
}

const HEAD_KEY = 'audit/head.json'
const chunkKey = (firstSeq: number, lastSeq: number): string =>
  `audit/chunk-${String(firstSeq).padStart(12, '0')}-${String(lastSeq).padStart(12, '0')}.json`

export type VerifyResult =
  | { ok: true, entries: number, chunks: number, head: ChainHead | null }
  | { ok: false, reason: string, atSeq?: number }

/** Pure forward verification of a contiguous entry run (used by verify() and tests). */
export function verifyEntries(entries: AuditEntry[], expectHead?: ChainHead): VerifyResult {
  let prev = GENESIS_PREV
  let expectSeq = 0
  for (const e of entries) {
    if (e.seq !== expectSeq) return { ok: false, reason: `seq gap: expected ${expectSeq}, got ${e.seq}`, atSeq: e.seq }
    if (e.prev !== prev) return { ok: false, reason: 'prev-hash mismatch — chain broken (tamper or loss)', atSeq: e.seq }
    prev = entryHash(e)
    expectSeq += 1
  }
  if (expectHead) {
    if (entries.length === 0) return { ok: false, reason: 'head present but no entries' }
    const last = entries[entries.length - 1]!
    if (last.seq !== expectHead.seq || entryHash(last) !== expectHead.hash) {
      return { ok: false, reason: 'head does not match last entry (tamper or truncation)', atSeq: last.seq }
    }
  }
  return { ok: true, entries: entries.length, chunks: 0, head: expectHead ?? null }
}

export class HashChainedAudit {
  private store: BlobStore | null
  private pending: AuditEntry[] = []
  private nextSeq = 0
  private prevHash = GENESIS_PREV
  private lastChunk: string | null = null
  private headDoc: HeadDoc | null = null

  constructor(store: BlobStore | null) {
    this.store = store
  }

  /** Resume the chain from a persisted head (call once at boot, before any append). */
  async load(): Promise<ChainHead | null> {
    if (!this.store) return null
    const raw = await this.store.get(HEAD_KEY)
    if (!raw) return null
    const head = JSON.parse(raw.toString('utf8')) as HeadDoc
    this.nextSeq = head.seq + 1
    this.prevHash = head.hash
    this.lastChunk = head.lastChunk
    this.headDoc = head
    return { seq: head.seq, hash: head.hash }
  }

  /**
   * Append one event. Satisfies the engine's AuditSink contract (policy.ts), so a
   * Governor constructed over this sink chains every decision/transition/blocked
   * event it emits. Synchronous by contract; persistence happens at flush().
   */
  append(event: object): void {
    const entry: AuditEntry = { seq: this.nextSeq, ts: Date.now(), prev: this.prevHash, event }
    this.prevHash = entryHash(entry)
    this.nextSeq += 1
    this.pending.push(entry)
  }

  head(): ChainHead | null {
    if (this.pending.length > 0) return { seq: this.nextSeq - 1, hash: this.prevHash }
    if (this.headDoc) return { seq: this.headDoc.seq, hash: this.headDoc.hash }
    return null
  }

  pendingCount(): number { return this.pending.length }

  /**
   * Seal the pending tail as one chunk and advance the persisted head. Nothing is
   * dropped on failure: the tail stays pending and the next flush retries, so a
   * storage outage delays durability but never truncates the chain.
   */
  async flush(): Promise<ChainHead | null> {
    if (!this.store || this.pending.length === 0) return this.head()
    const first = this.pending[0]!, last = this.pending[this.pending.length - 1]!
    const key = chunkKey(first.seq, last.seq)
    const chunk: Chunk = { firstSeq: first.seq, lastSeq: last.seq, prevChunk: this.lastChunk, entries: this.pending }
    await this.store.put(key, Buffer.from(JSON.stringify(chunk)))
    const head: HeadDoc = { seq: last.seq, hash: entryHash(last), lastChunk: key }
    await this.store.put(HEAD_KEY, Buffer.from(JSON.stringify(head)))
    this.headDoc = head
    this.lastChunk = key
    this.pending = []
    return { seq: head.seq, hash: head.hash }
  }

  /**
   * Walk every persisted chunk back from the head, then re-verify the whole chain
   * forward: contiguous seqs, each prev = sha256(canonical previous), head matches
   * the final entry. Any tampered/lost persisted entry fails with the seq.
   */
  async verify(): Promise<VerifyResult> {
    if (!this.store) return verifyEntries(this.pending)
    const raw = await this.store.get(HEAD_KEY)
    if (!raw) return this.pending.length === 0
      ? { ok: true, entries: 0, chunks: 0, head: null }
      : verifyEntries(this.pending)
    const head = JSON.parse(raw.toString('utf8')) as HeadDoc
    const entries: AuditEntry[] = []
    let chunks = 0
    for (let key = head.lastChunk; key !== null;) {
      const blob = await this.store.get(key)
      if (!blob) return { ok: false, reason: `missing chunk ${key}` }
      const chunk = JSON.parse(blob.toString('utf8')) as Chunk
      entries.unshift(...chunk.entries)
      chunks += 1
      key = chunk.prevChunk
    }
    const res = verifyEntries(entries, { seq: head.seq, hash: head.hash })
    return res.ok ? { ...res, chunks } : res
  }
}
