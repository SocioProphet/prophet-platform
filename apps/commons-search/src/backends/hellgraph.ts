/**
 * hellgraph.ts — the SOVEREIGN CommonsStore: append-only, no central point.
 *
 * Follows the PROVEN regis-writer contract (see prophet-platform regis HellGraphBackend + hellgraph
 * ts/src/regis-writer.ts): writes are emitted as JSONL `graph_delta` lines to an OUTBOX; a separate federation
 * tailer (the Phase-2 wiring — a hellgraph participant that appends the outbox to its own Hypercore log, Autobase
 * merges to every peer, super-peer serves /query) turns them into a sovereign shared corpus that no node can forge
 * or rewrite. Until that tailer runs, this backend reads back from its OWN local materialized view (read-after-write),
 * exactly the "compatible halves, federation is deployment-wiring" posture the regis audit documented — NOT a bug,
 * a phase boundary. The write contract emitted here is the real one; only the cross-instance transport is deferred.
 *
 * Only redacted text is ever emitted (the floor gate runs at the HTTP boundary first). Revocation is an author-
 * scoped tombstone delta + immediate removal from the local view, so search never returns a revoked entry.
 *
 * Env: COMMONS_HELLGRAPH_OUTBOX (delta JSONL the tailer consumes), COMMONS_HELLGRAPH_VIEW (local materialized JSONL).
 */
import * as fs from 'node:fs'
import * as path from 'node:path'
import * as os from 'node:os'
import type { CommonsStore, RedactedOpenChat, OpenChatHit } from '../store.js'
import { lexicalSearch } from '../store.js'

type Delta =
  | { op: 'UPSERT_OPEN_CHAT'; author: string; sessionId: string; entry: RedactedOpenChat; ts: string }
  | { op: 'REVOKE_OPEN_CHAT'; author: string; sessionId: string; ts: string }

const mk = (author: string, sessionId: string): string => `${author} ${sessionId}`

export class HellgraphStore implements CommonsStore {
  kind = 'hellgraph'
  private view = new Map<string, RedactedOpenChat>()
  private constructor(private outbox: string, private viewFile: string) {}

  static async create(): Promise<HellgraphStore> {
    const base = process.env['COMMONS_HELLGRAPH_STORE_DIR'] ?? path.join(os.homedir(), '.commons-search')
    const outbox = process.env['COMMONS_HELLGRAPH_OUTBOX'] ?? path.join(base, 'commons-delta.jsonl')
    const viewFile = process.env['COMMONS_HELLGRAPH_VIEW'] ?? path.join(base, 'commons-view.jsonl')
    fs.mkdirSync(path.dirname(outbox), { recursive: true })
    fs.mkdirSync(path.dirname(viewFile), { recursive: true })
    const store = new HellgraphStore(outbox, viewFile)
    store.hydrate()
    return store
  }

  /** Rebuild the local materialized view by replaying the view log (UPSERT/REVOKE, latest-wins per author+session). */
  private hydrate(): void {
    if (!fs.existsSync(this.viewFile)) return
    for (const line of fs.readFileSync(this.viewFile, 'utf8').split('\n')) {
      if (!line.trim()) continue
      try {
        const d = JSON.parse(line) as Delta
        const key = mk(d.author, d.sessionId)
        if (d.op === 'UPSERT_OPEN_CHAT') this.view.set(key, d.entry)
        else this.view.delete(key)
      } catch { /* skip corrupt line */ }
    }
  }
  private emit(delta: Delta): void {
    const line = JSON.stringify(delta) + '\n'
    fs.appendFileSync(this.outbox, line)     // the sovereign write contract the federation tailer consumes
    fs.appendFileSync(this.viewFile, line)   // local materialized view for read-after-write search
  }

  async put(e: RedactedOpenChat): Promise<void> {
    this.emit({ op: 'UPSERT_OPEN_CHAT', author: e.author, sessionId: e.sessionId, entry: e, ts: new Date().toISOString() })
    this.view.set(mk(e.author, e.sessionId), e)
  }
  async revoke(author: string, sessionId: string): Promise<{ removed: boolean }> {
    const key = mk(author, sessionId)
    const removed = this.view.delete(key)
    this.emit({ op: 'REVOKE_OPEN_CHAT', author, sessionId, ts: new Date().toISOString() })
    return { removed }
  }
  async search(query: string, limit: number): Promise<OpenChatHit[]> { return lexicalSearch(this.view.values(), query, limit) }
  async count(): Promise<number> { return this.view.size }
}
