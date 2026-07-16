/**
 * gateway.ts — the public read-only search fan-out for socioprophet.ai.
 *
 * A single query is fanned out IN PARALLEL to the estate's hosted engines and blended into one cited result set:
 *   - SearXNG        (web meta-search)        → source: "web"
 *   - commons-search (the sovereign commons)  → source: "commons"  (already redacted + injection-stripped there)
 *
 * READ-ONLY by construction: this gateway never writes. It only reads the already-safe corpora, so it is safe to
 * expose publicly (with CORS) while the commons /publish path stays gated. Graceful degradation is a feature, not
 * an afterthought — Promise.allSettled means a down engine returns *partial* results, never a failed query (the
 * chaos-resilience posture, applied to the product surface itself).
 */

export type Source = 'web' | 'commons'

export interface SearchResult {
  title: string
  url: string
  snippet: string
  source: Source
  engine: string
  publishedDate?: string
}

export interface BlendedResults {
  query: string
  results: SearchResult[]
  counts: { web: number; commons: number }
  /** Present when an engine failed — the UI can note "web results unavailable" without the whole query failing. */
  degraded?: { web?: string; commons?: string }
}

const WEB_URL = process.env['SEARXNG_URL'] ?? 'http://searxng.socioprophet.svc.cluster.local:8080'
const COMMONS_URL = process.env['COMMONS_SEARCH_URL'] ?? 'http://commons-search.socioprophet.svc.cluster.local:8080'
const TIMEOUT_MS = Number(process.env['SEARCH_TIMEOUT_MS'] ?? 6000)
const PER_SOURCE_LIMIT = Number(process.env['SEARCH_PER_SOURCE_LIMIT'] ?? 8)

async function getJson(url: string): Promise<unknown> {
  const res = await fetch(url, { headers: { accept: 'application/json' }, signal: AbortSignal.timeout(TIMEOUT_MS) })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

async function searchWeb(query: string): Promise<SearchResult[]> {
  const u = `${WEB_URL.replace(/\/$/, '')}/search?q=${encodeURIComponent(query)}&format=json`
  const data = (await getJson(u)) as { results?: Array<{ title?: string; url?: string; content?: string; engine?: string }> }
  return (data.results ?? [])
    .filter((r) => r.url?.startsWith('http') && (r.engine ?? '') !== 'noetica commons') // commons comes from the commons call, not via searxng
    .slice(0, PER_SOURCE_LIMIT)
    .map((r) => ({ title: r.title ?? r.url ?? '', url: r.url!, snippet: r.content ?? '', source: 'web' as const, engine: r.engine ?? 'web' }))
}

async function searchCommons(query: string): Promise<SearchResult[]> {
  const u = `${COMMONS_URL.replace(/\/$/, '')}/api/open-chats/search?q=${encodeURIComponent(query)}`
  const data = (await getJson(u)) as { results?: Array<{ title?: string; url?: string; content?: string; publishedDate?: string }> }
  return (data.results ?? [])
    .slice(0, PER_SOURCE_LIMIT)
    .map((r) => ({ title: r.title ?? '', url: r.url ?? '', snippet: r.content ?? '', source: 'commons' as const, engine: 'noetica-commons', publishedDate: r.publishedDate }))
}

/** Fan out, blend, de-dupe by url. Commons results lead (the sovereign corpus is the differentiator), then web. */
export async function blendedSearch(query: string): Promise<BlendedResults> {
  const q = String(query ?? '').trim()
  if (!q) return { query: '', results: [], counts: { web: 0, commons: 0 } }

  const [commonsR, webR] = await Promise.allSettled([searchCommons(q), searchWeb(q)])
  const commons = commonsR.status === 'fulfilled' ? commonsR.value : []
  const web = webR.status === 'fulfilled' ? webR.value : []

  const seen = new Set<string>()
  const results: SearchResult[] = []
  for (const r of [...commons, ...web]) {
    const key = r.url.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    results.push(r)
  }

  const degraded: { web?: string; commons?: string } = {}
  if (commonsR.status === 'rejected') degraded.commons = String((commonsR.reason as Error)?.message ?? 'commons unavailable')
  if (webR.status === 'rejected') degraded.web = String((webR.reason as Error)?.message ?? 'web unavailable')

  return {
    query: q,
    results,
    counts: { web: web.length, commons: commons.length },
    ...(Object.keys(degraded).length ? { degraded } : {}),
  }
}
