import { describe, it, expect, vi, afterEach } from 'vitest';
import { fetchHackerNews, HN_LIVE_SOURCE } from '../data/adapters/newsLive';

const sample = {
  hits: [
    { objectID: '40123', title: 'Show HN: a local-first sync engine', url: 'https://example.com/x', author: 'ada', points: 214, num_comments: 33, created_at: '2026-07-08T09:00:00Z' },
    { objectID: '40124', title: 'Ask HN: provenance in agents?', author: 'linus', points: 12, num_comments: 4, created_at: '2026-07-08T08:00:00Z' }, // no url → HN item link
    { objectID: '40125' }, // no title → filtered
  ],
};
const mockFetch = (ok: boolean, body: unknown) => vi.fn().mockResolvedValue({ ok, json: () => Promise.resolve(body) });
afterEach(() => vi.restoreAllMocks());

describe('news live (Hacker News) adapter', () => {
  it('maps HN stories into FeedItems with the object id as provenance', async () => {
    vi.stubGlobal('fetch', mockFetch(true, sample));
    const r = await fetchHackerNews();
    expect(r).not.toBeNull();
    expect(r!).toHaveLength(2); // untitled dropped
    expect(r![0]).toMatchObject({ id: 'hn-40123', sourceId: HN_LIVE_SOURCE.id, title: 'Show HN: a local-first sync engine', canonicalUrl: 'https://example.com/x' });
    expect(r![0]!.provenanceHash).toContain('hn:40123');
    // url-less story falls back to the HN item link
    expect(r![1]!.canonicalUrl).toBe('https://news.ycombinator.com/item?id=40124');
  });

  it('fails closed on non-200, throw, and empty', async () => {
    vi.stubGlobal('fetch', mockFetch(false, sample));
    expect(await fetchHackerNews()).toBeNull();
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
    expect(await fetchHackerNews()).toBeNull();
    vi.stubGlobal('fetch', mockFetch(true, { hits: [] }));
    expect(await fetchHackerNews()).toBeNull();
  });
});
