// Fixture for the People → Social Networks signal board (/people/social-networks).
// UI-only. Signals reference peopleFixture entities; a future social-collection
// lane (scope-governed) can populate the same shapes.
import type { Platform } from './peopleFixture';

export type Sentiment = 'pos' | 'neg' | 'neu';
export interface SocialSignal {
  id: string;
  entityId: string;      // peopleFixture id
  platform: Platform;
  kind: 'post' | 'mention';
  text: string;
  likes: number;
  reposts: number;
  time: string;
  sentiment: Sentiment;
  // Present only on LIVE signals pulled from a real source (e.g. Bluesky/ATProto).
  // Carries the real handle + canonical post URL so provenance is not synthesized
  // and the row can resolve a display name without a peopleFixture entity.
  live?: { handle: string; displayName: string; url: string };
}

export interface Trend { topic: string; volume: number; changePct: number }

// On-device sentiment heuristic — a small polarity lexicon, NOT a trained model.
// Deliberately transparent: live posts get a labeled heuristic sentiment so we never
// paint a model-grade classification we didn't compute. Ties/empty → neutral.
const POS_LEX = ['gain', 'gains', 'up', 'growth', 'strong', 'beat', 'beats', 'record', 'surge', 'rally', 'win', 'wins', 'good', 'great', 'progress', 'resilience', 'stability', 'improve', 'improved', 'recover', 'recovery', 'optimistic', 'positive', 'success', 'boost', 'tighten', 'tightened', 'reopened', 'agree', 'aligns', 'breakthrough'];
const NEG_LEX = ['loss', 'losses', 'down', 'fall', 'falls', 'weak', 'miss', 'missed', 'crash', 'slump', 'selloff', 'risk', 'risks', 'fear', 'fears', 'cut', 'cuts', 'lag', 'lagging', 'pressure', 'decline', 'drop', 'concern', 'concerns', 'warning', 'warn', 'crisis', 'default', 'sanction', 'sanctions', 'conflict', 'dispute', 'delay', 'delayed', 'shortage', 'recession'];

export function classifySentiment(text: string): Sentiment {
  const words = text.toLowerCase().match(/[a-z']+/g) ?? [];
  let score = 0;
  for (const w of words) {
    if (POS_LEX.includes(w)) score += 1;
    else if (NEG_LEX.includes(w)) score -= 1;
  }
  return score > 0 ? 'pos' : score < 0 ? 'neg' : 'neu';
}

// Map a live Bluesky post (blueskyLive.BskyPost) to a SocialSignal. Kept adapter-shaped
// (structural typing) so socialFixture stays free of adapter imports.
export interface LiveBskyLike {
  id: string; text: string; createdAt: string;
  likeCount: number; repostCount: number;
  actor: { handle: string; displayName: string };
  canonicalUrl?: string;
}
export function blueskyToSignals(posts: LiveBskyLike[]): SocialSignal[] {
  return posts.map((p) => ({
    id: `live-${p.id}`,
    entityId: `bsky:${p.actor.handle}`,
    platform: 'bluesky' as Platform,
    kind: 'post' as const,
    text: p.text,
    likes: p.likeCount,
    reposts: p.repostCount,
    time: p.createdAt,
    sentiment: classifySentiment(p.text),
    live: { handle: `@${p.actor.handle}`, displayName: p.actor.displayName || p.actor.handle, url: p.canonicalUrl ?? `https://bsky.app/profile/${p.actor.handle}` },
  }));
}

export const socialSignals: SocialSignal[] = [
  { id: 's-01', entityId: 'p-avery', platform: 'x', kind: 'post', text: 'Disinflation is real but services stay sticky — watch shelter and wages before calling the cut.', likes: 2140, reposts: 388, time: '2026-07-04T00:35:00-04:00', sentiment: 'neu' },
  { id: 's-02', entityId: 'g-odg', platform: 'mastodon', kind: 'post', text: 'Comment period is open on the model-provenance disclosure rule. Attach verifiable provenance above the risk threshold.', likes: 910, reposts: 512, time: '2026-07-04T00:10:00-04:00', sentiment: 'neu' },
  { id: 's-03', entityId: 'p-lindqvist', platform: 'x', kind: 'post', text: 'Phase I of the shared interconnect within 24 months. Resilience and price stability drove the timeline.', likes: 1330, reposts: 240, time: '2026-07-03T23:50:00-04:00', sentiment: 'pos' },
  { id: 's-04', entityId: 'p-rao', platform: 'x', kind: 'post', text: 'IG spreads tightened after a heavy supply week absorbed cleanly. Curve steepening into quarter-end.', likes: 870, reposts: 131, time: '2026-07-03T23:20:00-04:00', sentiment: 'pos' },
  { id: 's-05', entityId: 'p-okafor', platform: 'mastodon', kind: 'mention', text: 'Cross-jurisdiction working group aligns audit-trail guidance with existing evidence frameworks — @tokafor cited.', likes: 420, reposts: 96, time: '2026-07-03T22:40:00-04:00', sentiment: 'neu' },
  { id: 's-06', entityId: 'g-fed', platform: 'x', kind: 'post', text: 'On hold. The cut path remains data-dependent; we will let the data lead.', likes: 5820, reposts: 1440, time: '2026-07-03T22:05:00-04:00', sentiment: 'neu' },
  { id: 's-07', entityId: 'p-mercer', platform: 'telegram', kind: 'post', text: 'Corridor reopened under the Annex B inspection protocol. Convoys moving; more updates to follow.', likes: 260, reposts: 74, time: '2026-07-03T21:30:00-04:00', sentiment: 'pos' },
  { id: 's-08', entityId: 'o-meridian', platform: 'x', kind: 'post', text: 'New brief: cross-border data flows framework is provisional pending ratification. Thread on the safeguards.', likes: 3110, reposts: 902, time: '2026-07-03T20:55:00-04:00', sentiment: 'neu' },
  { id: 's-09', entityId: 'p-rao', platform: 'x', kind: 'post', text: 'Rate-sensitive sectors lagging — utilities and REITs under pressure as yields compete for flows.', likes: 640, reposts: 88, time: '2026-07-03T20:15:00-04:00', sentiment: 'neg' },
  { id: 's-10', entityId: 'p-avery', platform: 'x', kind: 'mention', text: 'Panel pushback: @averysloan is too dovish on shelter inflation. Sticky components argue for patience.', likes: 510, reposts: 143, time: '2026-07-03T19:40:00-04:00', sentiment: 'neg' },
  { id: 's-11', entityId: 'g-odg', platform: 'mastodon', kind: 'post', text: 'Audit-trail guidance recommends hash-sealed, replayable trails for high-stakes automation.', likes: 780, reposts: 305, time: '2026-07-03T19:05:00-04:00', sentiment: 'pos' },
  { id: 's-12', entityId: 'p-lindqvist', platform: 'x', kind: 'mention', text: 'Grid operators broadly welcome the interconnect directive — @mlindqvist credited for the phased approach.', likes: 300, reposts: 61, time: '2026-07-03T18:30:00-04:00', sentiment: 'pos' },
];

export const trends: Trend[] = [
  { topic: '#ProvenanceRule', volume: 12400, changePct: 120 },
  { topic: '#DataFlows', volume: 9800, changePct: 64 },
  { topic: '#Disinflation', volume: 8600, changePct: 38 },
  { topic: '#GridInterconnect', volume: 5100, changePct: 22 },
  { topic: '#RatePath', volume: 14200, changePct: 5 },
  { topic: '#CreditSpreads', volume: 3300, changePct: -8 },
];

export const asOf = '2026-07-04T00:40:00-04:00';
