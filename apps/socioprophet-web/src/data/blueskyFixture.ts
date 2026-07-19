// Bluesky (ATProto) social source for Prophet News — a client-side model of the
// Mirror-rail output described in the "Bluesky (ATProto) Adapter Contract v0.1".
// Each post is a governed object: it carries its ATProto identity (actor did /
// post uri / cid), its social engagement, and the governance chain the contract
// requires (rail → lane → RootBinding → Grant → Policy), so the feed can always
// explain "why this object exists." No live PDS/AppView call; a future
// bsky-adapter runtime populates these same shapes via bsky.mirror.sync.
import type { FeedSource, FeedItem } from '../features/feed-intelligence/types';

export const blueskySources: FeedSource[] = [
  {
    id: 'src-bsky',
    title: 'Bluesky',
    url: 'https://bsky.app',
    format: 'jsonFeed',
    scope: '/social/bluesky',
    storagePolicy: 'externalAdapter',
    status: 'active',
    lastSeen: '2026-07-03T13:58:00-04:00',
  },
];

export interface BskyActor { handle: string; did: string; displayName: string; }
export type Rail = 'mirror' | 'live' | 'action';
export type Lane = 'ingested' | 'analyzed' | 'published' | 'problematic';

// Social sidecar — the ATProto-specific facets the generic FeedItem doesn't hold.
export interface BskyPost {
  itemId: string;
  actor: BskyActor;
  uri: string;         // at://<did>/app.bsky.feed.post/<rkey>
  cid: string;         // content hash pointer
  text: string;
  replyCount: number;
  repostCount: number;
  likeCount: number;
  threadUri?: string;  // canonical root post (present when this is a reply)
  isReply?: boolean;
  rail: Rail;
  lane: Lane;
  rootType: 'appview' | 'pds' | 'firehose';
  rootBinding: string; // RootBinding id (Root + Grant + Topic + landing namespace)
  grantRef: string;    // sealed CapabilityGrant reference
}

const ACTORS: Record<string, BskyActor> = {
  ada: { handle: 'ada.newhope.social', did: 'did:plc:ada7h0penn3wh0pe', displayName: 'Ada L.' },
  linus: { handle: 'linus.dev', did: 'did:plc:l1nus0urcef0rge00', displayName: 'Linus (local-first)' },
  grace: { handle: 'grace.marketsdesk.io', did: 'did:plc:gr4cem4rketsd3sk1', displayName: 'Grace — Markets Desk' },
  berners: { handle: 'berners.policywatch.org', did: 'did:plc:b3rnersreg0w4tch2', displayName: 'B. Berners' },
  reader: { handle: 'skeptic.reader.bsky.social', did: 'did:plc:sk3pt1creader0099', displayName: 'the skeptic' },
};

let seq = 0;
function post(
  actorKey: keyof typeof ACTORS,
  text: string,
  publishedAt: string,
  topicScope: string,
  engagement: [number, number, number],
  opts: {
    membraneDecision?: FeedItem['membraneDecision'];
    lane?: Lane;
    threadUri?: string;
    isReply?: boolean;
    entities?: string[];
    claims?: string[];
  } = {},
): { item: FeedItem; social: BskyPost } {
  const actor = ACTORS[actorKey];
  const rkey = `3k${(seq += 1).toString(36).padEnd(6, 'a')}`;
  const uri = `at://${actor.did}/app.bsky.feed.post/${rkey}`;
  const cid = `bafyrei${(actor.did + rkey).replace(/[^a-z0-9]/g, '').slice(0, 24).padEnd(24, 'a')}`;
  const id = `bsky-${rkey}`;
  const [replyCount, repostCount, likeCount] = engagement;
  const item: FeedItem = {
    id,
    sourceId: 'src-bsky',
    title: text,
    summary: text,
    canonicalUrl: `https://bsky.app/profile/${actor.handle}/post/${rkey}`,
    publishedAt,
    normalizedAt: publishedAt,
    topicScope,
    membraneDecision: opts.membraneDecision ?? 'admit',
    storagePolicy: 'externalAdapter',
    provenanceHash: `sha256:bsky:${cid}`.slice(0, 40),
    eventRefs: [`ingest.accepted:${id}`, 'mirror.sync.completed'],
    entities: opts.entities ?? [],
    claims: opts.claims ?? [],
  };
  const social: BskyPost = {
    itemId: id,
    actor,
    uri,
    cid,
    text,
    replyCount,
    repostCount,
    likeCount,
    threadUri: opts.threadUri,
    isReply: opts.isReply,
    rail: 'mirror',
    lane: opts.lane ?? 'published',
    rootType: 'appview',
    rootBinding: 'rb:news/social-firehose',
    grantRef: 'grant:sealed:bsky-mirror-ro',
  };
  return { item, social };
}

const ROOT = 'at://did:plc:ada7h0penn3wh0pe/app.bsky.feed.post/3k1aaaaa';

const RECORDS = [
  post('ada', 'New Hope shipped a local-first capture rail today — every mirrored post keeps its at:// uri + cid, so provenance survives even offline. This is what "own your data" should mean.', '2026-07-03T13:40:00-04:00', '/social/bluesky', [12, 34, 210], {
    entities: ['ATProto', 'Local-first'], claims: ['Mirror rail keeps at:// uri + cid per record.'],
  }),
  post('grace', 'Commodities tape: metals firm on restocking, grains ease. Copper bid on electrification demand. Watching the 2Y for the next rates cue.', '2026-07-03T12:10:00-04:00', '/markets/real-assets', [8, 15, 96], {
    entities: ['Copper', 'Commodities', 'US2Y'], claims: ['Copper bid attributed to electrification demand.'],
  }),
  post('berners', 'Draft rule would require verifiable provenance on automated decisions above a risk threshold. This is the disclosure regime the industry has resisted for years. Comment window: 60 days.', '2026-07-03T11:20:00-04:00', '/law/regulatory-watch', [22, 41, 130], {
    membraneDecision: 'hold', entities: ['Provenance Rule'], claims: ['Applies only above the risk threshold.'],
  }),
  post('linus', 'Sovereign forge pattern (self-hosted Git + thin control plane) is quietly becoming the default for teams that want source + CI on-prem without losing ergonomics.', '2026-07-03T10:05:00-04:00', '/news/technology', [5, 9, 61], {
    entities: ['Gitea', 'Local-first', 'CI'],
  }),
  // A short thread (root + two replies) to show Live-rail thread context.
  post('grace', 'Thread 🧵 On why on-device 3B models are closing the gap with server tiers on reasoning benchmarks — and what still separates them.', '2026-07-03T09:30:00-04:00', '/news/technology', [17, 28, 140], {
    entities: ['On-device AI', 'Reasoning'], claims: ['3B models closing gap on reasoning benchmarks.'],
  }),
  post('reader', 'Counterpoint: the benchmark set was revised last quarter. Some of that "closing the gap" is contamination, not capability. Show me held-out results.', '2026-07-03T09:41:00-04:00', '/news/technology', [3, 6, 44], {
    membraneDecision: 'hold', threadUri: ROOT, isReply: true, claims: ['Alleges benchmark contamination after revision.'],
  }),
  post('ada', 'Fair — held-out eval matters. New Hope pins MMLU-STEM with a clean-eval harness precisely to avoid contamination. Verified compute, not vibes.', '2026-07-03T09:52:00-04:00', '/news/technology', [2, 8, 71], {
    threadUri: ROOT, isReply: true, entities: ['Verified compute', 'MMLU'],
  }),
];

export const blueskyItems: FeedItem[] = RECORDS.map((r) => r.item);
export const blueskyMeta = new Map<string, BskyPost>(RECORDS.map((r) => [r.item.id, r.social]));
export const BLUESKY_ROOT_URI = ROOT;
