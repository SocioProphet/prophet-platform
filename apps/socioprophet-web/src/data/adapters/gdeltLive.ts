import { fetchT } from './http';
// Live global-news adapter — GDELT DOC 2.0 API (api.gdeltproject.org): public, no key,
// CORS-enabled, a firehose of worldwide news articles. Maps each article into the
// FeedItem shape the feed uses. Complements the Bluesky/HN live sources with real
// global coverage. Fails closed (null) → stays on fixture.
import type { FeedItem, FeedSource } from '../../features/feed-intelligence/types';

export const GDELT_LIVE_SOURCE: FeedSource = {
  id: 'src-gdelt-live',
  title: 'GDELT · global news',
  url: 'https://www.gdeltproject.org',
  format: 'jsonFeed',
  scope: '/news',
  storagePolicy: 'externalAdapter',
  status: 'active',
  lastSeen: new Date().toISOString(),
};

interface GdeltArt { url?: string; title?: string; seendate?: string; domain?: string; sourcecountry?: string }

// GDELT dates look like "20260708T133000Z" → ISO 8601.
export function parseGdeltDate(d?: string): string | null {
  if (!d || !/^\d{8}T\d{6}Z$/.test(d)) return null;
  return `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}T${d.slice(9, 11)}:${d.slice(11, 13)}:${d.slice(13, 15)}Z`;
}

export async function fetchGdelt(query = 'world news', limit = 20): Promise<FeedItem[] | null> {
  try {
    const url = `https://api.gdeltproject.org/api/v2/doc/doc?query=${encodeURIComponent(query)}&mode=artlist&format=json&maxrecords=${limit}&sort=datedesc`;
    const res = await fetchT(url, { headers: { accept: 'application/json' } });
    if (!res.ok) return null;
    const j = (await res.json()) as { articles?: GdeltArt[] };
    const arts = (j.articles ?? []).filter((a) => a.url && a.title);
    if (!arts.length) return null;
    const now = new Date().toISOString();
    return arts.map((a) => {
      const id = `gdelt-${a.url!.replace(/[^a-z0-9]+/gi, '').slice(-24)}`;
      return {
        id,
        sourceId: GDELT_LIVE_SOURCE.id,
        title: a.title!,
        summary: `${a.domain ?? 'source'}${a.sourcecountry ? ` · ${a.sourcecountry}` : ''}`,
        canonicalUrl: a.url!,
        publishedAt: parseGdeltDate(a.seendate) ?? now,
        normalizedAt: now,
        topicScope: '/news',
        membraneDecision: 'admit',
        storagePolicy: 'externalAdapter',
        provenanceHash: `sha256:gdelt:${id}`.slice(0, 40),
        eventRefs: [`ingest.accepted:${id}`, `gdelt.domain:${a.domain ?? ''}`],
        entities: [],
        claims: [],
      } satisfies FeedItem;
    });
  } catch {
    return null;
  }
}
