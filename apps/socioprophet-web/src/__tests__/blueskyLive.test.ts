import { describe, it, expect, vi, afterEach } from 'vitest';
import { fetchBlueskyLive, BSKY_LIVE_SOURCE } from '../data/adapters/blueskyLive';

const sample = {
  posts: [
    {
      uri: 'at://did:plc:abc123/app.bsky.feed.post/3kzz9live1',
      cid: 'bafyreihellotestcidvalue0001',
      author: { did: 'did:plc:abc123', handle: 'ada.example', displayName: 'Ada Example' },
      record: { text: 'Local-first capture keeps the at:// uri and cid. Provenance survives offline.', createdAt: '2026-07-08T10:00:00Z' },
      replyCount: 3, repostCount: 7, likeCount: 22, indexedAt: '2026-07-08T10:01:00Z',
    },
    // malformed — missing record.text — must be filtered out
    { uri: 'at://did:plc:x/app.bsky.feed.post/bad', cid: 'c', author: { did: 'did:plc:x', handle: 'x' } },
  ],
};

function mockFetch(ok: boolean, body: unknown) {
  return vi.fn().mockResolvedValue({ ok, json: () => Promise.resolve(body) });
}

afterEach(() => { vi.restoreAllMocks(); });

describe('bluesky live adapter', () => {
  it('maps real posts into FeedItem + BskyPost, carrying the real cid/uri/did', async () => {
    vi.stubGlobal('fetch', mockFetch(true, sample));
    const r = await fetchBlueskyLive('q', 5);
    expect(r).not.toBeNull();
    expect(r!.items).toHaveLength(1); // malformed post filtered
    const item = r!.items[0]!;
    expect(item.sourceId).toBe(BSKY_LIVE_SOURCE.id);
    expect(item.provenanceHash).toContain('bafyreihellotestcid'); // REAL cid, not synthesized
    expect(item.canonicalUrl).toBe('https://bsky.app/profile/ada.example/post/3kzz9live1');
    expect(item.title.length).toBeLessThanOrEqual(item.summary.length);
    const post = r!.meta.get(item.id)!;
    expect(post.uri).toBe('at://did:plc:abc123/app.bsky.feed.post/3kzz9live1');
    expect(post.actor.did).toBe('did:plc:abc123');
    expect(post.likeCount).toBe(22);
    expect(post.rootType).toBe('appview');
  });

  it('fails closed on non-200, on throw, and on empty results', async () => {
    vi.stubGlobal('fetch', mockFetch(false, sample));
    expect(await fetchBlueskyLive()).toBeNull();
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
    expect(await fetchBlueskyLive()).toBeNull();
    vi.stubGlobal('fetch', mockFetch(true, { posts: [] }));
    expect(await fetchBlueskyLive()).toBeNull();
  });
});
