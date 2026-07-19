import { describe, it, expect, vi, afterEach } from 'vitest';
import { fetchGdelt, parseGdeltDate, GDELT_LIVE_SOURCE } from '../data/adapters/gdeltLive';

const ok = (body: unknown) => Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
afterEach(() => vi.restoreAllMocks());

describe('gdeltLive', () => {
  it('parses GDELT dates to ISO', () => {
    expect(parseGdeltDate('20260708T133000Z')).toBe('2026-07-08T13:30:00Z');
    expect(parseGdeltDate('bad')).toBeNull();
    expect(parseGdeltDate(undefined)).toBeNull();
  });

  it('maps GDELT articles to FeedItems on the GDELT source', async () => {
    vi.stubGlobal('fetch', vi.fn(() => ok({ articles: [
      { url: 'https://reuters.com/a/b-123', title: 'Markets rally', seendate: '20260708T120000Z', domain: 'reuters.com', sourcecountry: 'US' },
      { url: '', title: 'no url' }, // dropped
    ] })));
    const r = await fetchGdelt();
    expect(r).toHaveLength(1);
    expect(r![0]).toMatchObject({ sourceId: GDELT_LIVE_SOURCE.id, title: 'Markets rally', canonicalUrl: 'https://reuters.com/a/b-123', publishedAt: '2026-07-08T12:00:00Z' });
    expect(r![0].summary).toContain('reuters.com');
  });

  it('fails closed on empty, non-200, throw', async () => {
    vi.stubGlobal('fetch', vi.fn(() => ok({ articles: [] })));
    expect(await fetchGdelt()).toBeNull();
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response('', { status: 500 }))));
    expect(await fetchGdelt()).toBeNull();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('net'))));
    expect(await fetchGdelt()).toBeNull();
  });
});
