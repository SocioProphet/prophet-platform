import { fetchT } from './http';
// Live news adapter — flips a tech news source off FIXTURE using the Algolia
// Hacker News API (hn.algolia.com): public, no key, CORS-enabled. (Raw RSS can't
// be fetched from the browser — no CORS — so HN's JSON firehose is the clean
// no-proxy source.) Maps each story into the FeedItem shape the feed uses, with
// the HN object id as real provenance. Fails closed (null) → stays on fixture.
import type { FeedItem, FeedSource } from '../../features/feed-intelligence/types';

export const HN_LIVE_SOURCE: FeedSource = {
  id: 'src-hn-live',
  title: 'Hacker News · live',
  url: 'https://news.ycombinator.com',
  format: 'jsonFeed',
  scope: '/news/technology',
  storagePolicy: 'externalAdapter',
  status: 'active',
  lastSeen: new Date().toISOString(),
};

interface HnHit {
  objectID: string;
  title?: string;
  url?: string;
  author?: string;
  points?: number;
  num_comments?: number;
  created_at?: string;
  story_text?: string;
}

export async function fetchHackerNews(query = '', limit = 20): Promise<FeedItem[] | null> {
  try {
    const q = query ? `&query=${encodeURIComponent(query)}` : '';
    const url = `https://hn.algolia.com/api/v1/search_by_date?tags=story${q}&hitsPerPage=${limit}`;
    const res = await fetchT(url, { headers: { accept: 'application/json' } });
    if (!res.ok) return null;
    const j = (await res.json()) as { hits?: HnHit[] };
    const hits = (j.hits ?? []).filter((h) => h.title && h.objectID);
    if (!hits.length) return null;
    const now = new Date().toISOString();
    return hits.map((h) => {
      const id = `hn-${h.objectID}`;
      const hnUrl = `https://news.ycombinator.com/item?id=${h.objectID}`;
      return {
        id,
        sourceId: HN_LIVE_SOURCE.id,
        title: h.title!,
        summary: (h.story_text ? h.story_text.replace(/<[^>]+>/g, ' ').slice(0, 400) : h.title!),
        canonicalUrl: h.url || hnUrl,
        publishedAt: h.created_at ?? now,
        normalizedAt: now,
        topicScope: '/news/technology',
        membraneDecision: 'admit',
        storagePolicy: 'externalAdapter',
        provenanceHash: `sha256:hn:${h.objectID}`.slice(0, 40),
        eventRefs: [`ingest.accepted:${id}`, `hn.points:${h.points ?? 0}`, `hn.comments:${h.num_comments ?? 0}`],
        entities: [],
        claims: [],
      } satisfies FeedItem;
    });
  } catch {
    return null;
  }
}
