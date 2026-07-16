/**
 * server.ts — the public HTTP surface for the socioprophet.ai search gateway.
 *
 *   GET /healthz         liveness
 *   GET /search?q=       blended web + commons results (read-only, CORS-enabled)
 *
 * CORS is allowlist-based (SEARCH_CORS_ORIGINS) so only the .ai surfaces can call it from a browser; server-side
 * callers (no Origin) are allowed. No write routes exist — the commons /publish path is not proxied here.
 */
import * as http from 'node:http'
import { blendedSearch } from './gateway.js'

const PORT = Number(process.env['PORT'] ?? 8080)
// Comma-separated allowlist. Defaults cover the .ai surface + its Firebase dev site; override per environment.
const CORS_ORIGINS = (process.env['SEARCH_CORS_ORIGINS'] ??
  'https://socioprophet.ai,https://www.socioprophet.ai,https://socioprophet-builder-dev.web.app')
  .split(',').map((s) => s.trim()).filter(Boolean)

function corsHeadersFor(origin: string | undefined): Record<string, string> {
  const allow = origin && CORS_ORIGINS.includes(origin) ? origin : ''
  return allow
    ? { 'access-control-allow-origin': allow, 'access-control-allow-methods': 'GET, OPTIONS', 'access-control-allow-headers': 'content-type', 'vary': 'Origin' }
    : {}
}

function json(res: http.ServerResponse, code: number, body: unknown, extra: Record<string, string> = {}): void {
  res.writeHead(code, { 'content-type': 'application/json', ...extra })
  res.end(JSON.stringify(body))
}

export function makeServer(): http.Server {
  return http.createServer((req, res) => {
    void (async () => {
      const origin = Array.isArray(req.headers.origin) ? req.headers.origin[0] : req.headers.origin
      const cors = corsHeadersFor(origin)
      if (req.method === 'OPTIONS') { res.writeHead(204, cors); res.end(); return }
      try {
        const url = new URL(req.url ?? '/', `http://localhost:${PORT}`)
        if (req.method === 'GET' && url.pathname === '/healthz') {
          return json(res, 200, { ok: true, service: 'search-gateway' }, cors)
        }
        if (req.method === 'GET' && url.pathname === '/search') {
          const q = url.searchParams.get('q') ?? ''
          const blended = await blendedSearch(q)
          return json(res, 200, blended, cors)
        }
        json(res, 404, { error: 'not found' }, cors)
      } catch (e) {
        json(res, 500, { error: e instanceof Error ? e.message : 'failed' }, cors)
      }
    })()
  })
}

if (process.env['SEARCH_NO_LISTEN'] !== '1') {
  makeServer().listen(PORT, () => console.log(`[search-gateway] listening on :${PORT} → web=${process.env['SEARXNG_URL'] ?? 'searxng'} commons=${process.env['COMMONS_SEARCH_URL'] ?? 'commons-search'}`))
}
