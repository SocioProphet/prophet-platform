/**
 * socbase.ts — CommonsStore over the socbase/PostgREST plane (the Firebase-replacement we already run).
 *
 * A single table `open_chats(session_id, author, title, redacted, published_at, revoked)`. No SDK — PostgREST is
 * plain HTTP. Redaction already happened upstream (local gate) and at ingest (floor gate); this only persists the
 * redacted rows. Author-scoped revoke sets revoked=true; search reads revoked=false rows and ranks them locally
 * (keeps ranking identical to the other backends via the shared lexicalSearch).
 *
 * Env: COMMONS_SOCBASE_URL (PostgREST base, e.g. https://socbase.socioprophet.ai/rest/v1),
 *      COMMONS_SOCBASE_TOKEN (service-role JWT — write access to the table).
 */
import type { CommonsStore, RedactedOpenChat, OpenChatHit } from '../store.js'
import { rankSearch } from '../store.js'

interface Row { session_id: string; author: string; title: string; redacted: string; published_at: string; revoked: boolean }

export class SocbaseStore implements CommonsStore {
  kind = 'socbase'
  private constructor(private base: string, private token: string) {}

  static async create(): Promise<SocbaseStore> {
    const base = (process.env['COMMONS_SOCBASE_URL'] ?? '').replace(/\/$/, '')
    const token = process.env['COMMONS_SOCBASE_TOKEN'] ?? ''
    if (!base || !token) throw new Error('COMMONS_SOCBASE_URL and COMMONS_SOCBASE_TOKEN required')
    const s = new SocbaseStore(base, token)
    // fail fast if the table/endpoint isn't reachable — the soft-degrade in getStore() turns this into memory.
    const r = await s.req('GET', '/open_chats?limit=1', undefined, { Prefer: 'count=none' })
    if (!r.ok) throw new Error(`socbase unreachable: HTTP ${r.status}`)
    return s
  }

  private headers(extra: Record<string, string> = {}): Record<string, string> {
    return { apikey: this.token, authorization: `Bearer ${this.token}`, 'content-type': 'application/json', ...extra }
  }
  private req(method: string, pathAndQuery: string, body?: unknown, extra?: Record<string, string>): Promise<Response> {
    return fetch(`${this.base}${pathAndQuery}`, { method, headers: this.headers(extra), body: body === undefined ? undefined : JSON.stringify(body) })
  }

  async put(e: RedactedOpenChat): Promise<void> {
    // upsert on (author, session_id); resolution=merge-duplicates so a re-publish refreshes + clears revoked.
    const row: Row = { session_id: e.sessionId, author: e.author, title: e.title, redacted: e.redacted, published_at: e.publishedAt, revoked: false }
    const r = await this.req('POST', '/open_chats', row, { Prefer: 'resolution=merge-duplicates,return=minimal' })
    if (!r.ok) throw new Error(`socbase put failed: HTTP ${r.status}`)
  }

  async revoke(author: string, sessionId: string): Promise<{ removed: boolean }> {
    const q = `/open_chats?author=eq.${encodeURIComponent(author)}&session_id=eq.${encodeURIComponent(sessionId)}`
    const r = await this.req('PATCH', q, { revoked: true }, { Prefer: 'return=representation' })
    if (!r.ok) throw new Error(`socbase revoke failed: HTTP ${r.status}`)
    const rows = (await r.json()) as unknown[]
    return { removed: Array.isArray(rows) && rows.length > 0 }
  }

  async search(query: string, limit: number): Promise<OpenChatHit[]> {
    // Pull live (non-revoked) rows; rank locally so scoring matches every other backend. A DB-side full-text
    // index is a Phase-2 optimisation — correctness (and the revoked filter) lives here regardless.
    const r = await this.req('GET', '/open_chats?revoked=eq.false&select=session_id,author,title,redacted,published_at&limit=500')
    if (!r.ok) throw new Error(`socbase search failed: HTTP ${r.status}`)
    const rows = (await r.json()) as Row[]
    const entries: RedactedOpenChat[] = rows.map((x) => ({ sessionId: x.session_id, author: x.author, title: x.title, redacted: x.redacted, publishedAt: x.published_at }))
    return rankSearch(entries, query, limit)
  }

  async count(): Promise<number> {
    const r = await this.req('HEAD', '/open_chats?revoked=eq.false', undefined, { Prefer: 'count=exact' })
    const range = r.headers.get('content-range') ?? '*/0'
    const n = Number(range.split('/')[1] ?? 0)
    return Number.isFinite(n) ? n : 0
  }
}
