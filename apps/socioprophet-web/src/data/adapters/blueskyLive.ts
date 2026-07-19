import { fetchT } from './http';
// Live Bluesky adapter — flips the News feed's Bluesky source from FIXTURE to a
// real public AppView feed. No auth / API key: public.api.bsky.app is
// unauthenticated and CORS-enabled. Each real post is mapped into the SAME
// FeedItem + BskyPost shape the fixture uses, carrying its genuine at:// uri and
// cid so provenance is real, not synthesized. Fails closed (returns null) so the
// surface falls back to fixture whenever the network is offline/blocked.
import type { FeedItem, FeedSource } from '../../features/feed-intelligence/types';
import type { BskyPost } from '../blueskyFixture';

export const BSKY_LIVE_SOURCE: FeedSource = {
  id: 'src-bsky-live',
  title: 'Bluesky · live',
  url: 'https://bsky.app',
  format: 'jsonFeed',
  scope: '/social/bluesky',
  storagePolicy: 'externalAdapter',
  status: 'active',
  lastSeen: new Date().toISOString(),
};

const ENDPOINT = 'https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts';

interface RawPost {
  uri: string;
  cid: string;
  author: { did: string; handle: string; displayName?: string };
  record?: { text?: string; createdAt?: string };
  replyCount?: number;
  repostCount?: number;
  likeCount?: number;
  indexedAt?: string;
}

export interface LiveBsky { items: FeedItem[]; meta: Map<string, BskyPost> }

const rkeyOf = (uri: string) => uri.split('/').pop() ?? uri;
const firstSentence = (t: string) => {
  const s = t.replace(/\s+/g, ' ').trim();
  const m = s.match(/^.{0,140}?[.!?](\s|$)/);
  return ((m ? m[0] : s.slice(0, 140)).trim()) || s.slice(0, 80);
};

export async function fetchBlueskyLive(
  query = 'local-first OR sovereign OR provenance OR "own your data"',
  limit = 15,
): Promise<LiveBsky | null> {
  try {
    const url = `${ENDPOINT}?q=${encodeURIComponent(query)}&limit=${limit}&sort=latest`;
    const res = await fetchT(url, { headers: { accept: 'application/json' } });
    if (!res.ok) return null;
    const j = (await res.json()) as { posts?: RawPost[] };
    const posts = (j.posts ?? []).filter((p) => p && p.uri && p.cid && p.author?.handle && p.record?.text);
    if (!posts.length) return null;
    const items: FeedItem[] = [];
    const meta = new Map<string, BskyPost>();
    for (const p of posts) {
      const rkey = rkeyOf(p.uri);
      const id = `bsky-live-${rkey}`;
      const text = p.record!.text!.trim();
      const when = p.record!.createdAt ?? p.indexedAt ?? new Date().toISOString();
      const handle = p.author.handle;
      items.push({
        id,
        sourceId: BSKY_LIVE_SOURCE.id,
        title: firstSentence(text),
        summary: text,
        canonicalUrl: `https://bsky.app/profile/${handle}/post/${rkey}`,
        publishedAt: when,
        normalizedAt: new Date().toISOString(),
        topicScope: '/social/bluesky',
        membraneDecision: 'admit',
        storagePolicy: 'externalAdapter',
        provenanceHash: `sha256:bsky:${p.cid}`.slice(0, 40),
        eventRefs: [`ingest.accepted:${id}`, 'mirror.sync.completed'],
        entities: [],
        claims: [],
      });
      meta.set(id, {
        itemId: id,
        actor: { handle, did: p.author.did, displayName: p.author.displayName || handle },
        uri: p.uri,
        cid: p.cid,
        text,
        replyCount: p.replyCount ?? 0,
        repostCount: p.repostCount ?? 0,
        likeCount: p.likeCount ?? 0,
        rail: 'mirror',
        lane: 'published',
        rootType: 'appview',
        rootBinding: 'rb:live:bsky-appview',
        grantRef: 'grant:live:public-appview-ro',
      });
    }
    return { items, meta };
  } catch {
    return null;
  }
}
