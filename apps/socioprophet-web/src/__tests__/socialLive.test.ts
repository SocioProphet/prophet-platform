import { describe, it, expect } from 'vitest';
import { classifySentiment, blueskyToSignals, type LiveBskyLike } from '../data/socialFixture';

describe('on-device sentiment heuristic', () => {
  it('scores clear polarity and is honest about neutral/empty', () => {
    expect(classifySentiment('Strong growth, record gains and a rally')).toBe('pos');
    expect(classifySentiment('Selloff on recession fears and sanctions')).toBe('neg');
    expect(classifySentiment('The meeting is scheduled for Tuesday')).toBe('neu');
    expect(classifySentiment('')).toBe('neu');
  });

  it('cancels balanced polarity to neutral (no false confidence)', () => {
    expect(classifySentiment('gains offset by losses')).toBe('neu');
  });
});

describe('Bluesky → SocialSignal mapping (live overlay)', () => {
  const posts: LiveBskyLike[] = [
    { id: 'bsky-live-abc', text: 'Disinflation progress is real; equities rally.', createdAt: '2026-07-09T12:00:00Z', likeCount: 12, repostCount: 3, actor: { handle: 'alice.bsky.social', displayName: 'Alice' }, canonicalUrl: 'https://bsky.app/profile/alice.bsky.social/post/abc' },
    { id: 'bsky-live-def', text: 'Supply shortage risk and delayed shipments.', createdAt: '2026-07-09T11:00:00Z', likeCount: 5, repostCount: 1, actor: { handle: 'bob.bsky.social', displayName: '' } },
  ];

  it('maps real posts preserving provenance (handle + canonical url) and real engagement', () => {
    const sigs = blueskyToSignals(posts);
    expect(sigs).toHaveLength(2);
    expect(sigs[0].platform).toBe('bluesky');
    expect(sigs[0].live?.handle).toBe('@alice.bsky.social');
    expect(sigs[0].live?.url).toBe('https://bsky.app/profile/alice.bsky.social/post/abc');
    expect(sigs[0].likes).toBe(12);
    expect(sigs[0].reposts).toBe(3);
    expect(sigs[0].sentiment).toBe('pos');
    expect(sigs[1].sentiment).toBe('neg');
  });

  it('falls back to handle for display name and synthesizes a profile url when none given', () => {
    const sigs = blueskyToSignals(posts);
    expect(sigs[1].live?.displayName).toBe('bob.bsky.social');
    expect(sigs[1].live?.url).toBe('https://bsky.app/profile/bob.bsky.social');
  });
});
