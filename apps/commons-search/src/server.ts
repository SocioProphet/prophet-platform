/**
 * server.ts — the open-chat commons aggregator HTTP surface.
 *
 * Instances PUBLISH already-redacted open chats here (the aggregator re-runs the FLOOR gate on ingest as defense
 * against a rogue node); SearXNG's json_engine SEARCHES the redacted corpus. No web framework — Node's http is enough.
 *
 *   GET  /healthz                          liveness + active store kind + count
 *   POST /publish                          { sessionId, title, redacted }  (author from X-Sovereign-Id; token-gated)
 *   DELETE /api/open-chats/publish?session= revoke, author-scoped by the token principal
 *   GET  /api/open-chats/search?q=         the json_engine-shaped, sanitized corpus search (public)
 *
 * Every exposure path is downstream of: (1) redacted-only storage, (2) the floor gate on ingest, (3) snippet
 * injection-strip on egress, (4) author-scoped revocation, (5) per-author publish rate + size caps.
 */
import * as http from 'node:http'
import { getStore, type CommonsStore } from './store.js'
import { floorGate } from './gate.js'
import { authenticatePublish } from './auth.js'
import { RateLimiter } from './ratelimit.js'
import { sanitizeSnippet } from './sanitize.js'

const PORT = Number(process.env['PORT'] ?? 8080)
const MAX_BODY = 512 * 1024                                   // 512 KiB request cap
const MAX_REDACTED = Number(process.env['COMMONS_MAX_REDACTED'] ?? 200_000)  // per-entry text cap

function json(res: http.ServerResponse, code: number, body: unknown): void {
  res.writeHead(code, { 'content-type': 'application/json' })
  res.end(JSON.stringify(body))
}
function readBody(req: http.IncomingMessage): Promise<string> {
  return new Promise((resolve, reject) => {
    let d = ''
    req.on('data', (c: Buffer) => { d += c.toString(); if (d.length > MAX_BODY) { req.destroy(); reject(new Error('request too large')) } })
    req.on('end', () => resolve(d))
    req.on('error', reject)
  })
}

export function makeServer(store: CommonsStore): http.Server {
  // Constructed per-server (not at module load) so config env set by callers/tests is honoured.
  const limiter = new RateLimiter(Number(process.env['COMMONS_RATE_PER_MIN'] ?? 30), Number(process.env['COMMONS_RATE_BURST'] ?? 10))
  // Search is unauthenticated (a commons is meant to be searchable) and lexicalSearch is O(corpus) per query, so
  // an un-throttled flood is a CPU-DoS. Cap per client IP — generous, just a brake on abuse.
  const searchLimiter = new RateLimiter(Number(process.env['COMMONS_SEARCH_RATE_PER_MIN'] ?? 120), Number(process.env['COMMONS_SEARCH_BURST'] ?? 40))
  return http.createServer((req, res) => {
    void (async () => {
      const url = new URL(req.url ?? '/', `http://localhost:${PORT}`)
      try {
        // ── liveness ──
        if (req.method === 'GET' && url.pathname === '/healthz') {
          return json(res, 200, { ok: true, store: store.kind, count: await store.count() })
        }

        // ── publish (open a chat into the commons) ──
        if (req.method === 'POST' && url.pathname === '/publish') {
          const auth = authenticatePublish(req)
          if (!auth.ok) return json(res, 401, { ok: false, error: auth.error })
          const author = auth.principal!.author
          if (!limiter.allow(author)) return json(res, 429, { ok: false, error: 'publish rate exceeded' })
          const body = JSON.parse(await readBody(req)) as { sessionId?: string; title?: string; redacted?: string }
          const sessionId = String(body.sessionId ?? '').trim().slice(0, 128)
          if (!sessionId) return json(res, 400, { ok: false, error: 'sessionId required' })
          // Treat the incoming text as UNTRUSTED and re-run the floor gate — a well-behaved instance already
          // redacted (this is a no-op), a rogue/buggy one gets its raw PII masked here before anything is stored.
          const incoming = String(body.redacted ?? '').slice(0, MAX_REDACTED)
          const gated = floorGate(incoming)
          await store.put({ author, sessionId, title: String(body.title ?? 'Untitled').slice(0, 200), redacted: gated.redacted, publishedAt: new Date().toISOString(), findings: gated.findings })
          return json(res, 200, { ok: true, findings: gated.findings })
        }

        // ── revoke (author-scoped) ──
        if (req.method === 'DELETE' && url.pathname === '/api/open-chats/publish') {
          const auth = authenticatePublish(req)
          if (!auth.ok) return json(res, 401, { ok: false, error: auth.error })
          const sessionId = url.searchParams.get('session') ?? ''
          if (!sessionId) return json(res, 400, { ok: false, error: 'session required' })
          const r = await store.revoke(auth.principal!.author, sessionId)   // author from token — can't revoke others'
          return json(res, 200, { ok: true, ...r })
        }

        // ── search (public, json_engine shape) ──
        if (req.method === 'GET' && url.pathname === '/api/open-chats/search') {
          const ip = (req.headers['x-forwarded-for']?.toString().split(',')[0]?.trim()) || req.socket.remoteAddress || 'unknown'
          if (!searchLimiter.allow(ip)) return json(res, 429, { query: '', number_of_results: 0, results: [], error: 'search rate exceeded' })
          const q = url.searchParams.get('q') ?? ''
          const hits = await store.search(q, 6)
          const results = hits.map((h) => ({
            title: h.title,
            url: `noetica://open-chat/${h.author}/${h.sessionId}`,
            content: sanitizeSnippet(h.snippet),     // strip injection from untrusted commons content
            publishedDate: h.publishedAt,
            engine: 'noetica-commons',
          }))
          return json(res, 200, { query: q, number_of_results: results.length, results })
        }

        json(res, 404, { error: 'not found' })
      } catch (e) {
        json(res, 400, { error: e instanceof Error ? e.message : 'bad request' })
      }
    })()
  })
}

// Boot (skipped under test via COMMONS_NO_LISTEN).
if (process.env['COMMONS_NO_LISTEN'] !== '1') {
  void getStore().then((store) => {
    makeServer(store).listen(PORT, () => console.log(`[commons-search] listening on :${PORT} (store=${store.kind})`))
  })
}
