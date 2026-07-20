<template>
  <section class="news" aria-label="News">
    <!-- Toolbar -->
    <header class="nf-toolbar">
      <div class="nf-title">
        <div>
          <p v-if="scope && !scope.isPrimary" class="nf-eyebrow">{{ scope.domain }}</p>
          <h1>{{ scope && !scope.isPrimary ? scope.label : 'News' }}</h1>
        </div>
        <span class="nf-pill" :class="{ live: liveState === 'live' }">{{ liveState === 'live' ? `live · ${liveItems.length}` : 'fixture' }}</span>
        <!-- Live pulse: streaming state, last-poll tick, and the running News→graph grounding count. -->
        <span v-if="liveState === 'live'" class="nf-pulse" :title="`Auto-refreshing every ${LIVE_POLL_MS / 1000}s · new items grounded into HellGraph`">
          <span class="nf-pulse-dot" :class="{ working: grounding }" />
          streaming<span class="nf-pulse-sep">·</span><span class="nf-pulse-ago">updated {{ liveAgo }}</span>
          <span v-if="groundedFacts" class="nf-pulse-sep">·</span>
          <span v-if="groundedFacts" class="nf-grounded" title="Facts extracted from the live feed and written into the sovereign HellGraph">{{ groundedFacts }} → graph</span>
        </span>
      </div>
      <div class="nf-tools">
        <label class="nf-search">
          <span class="nf-search-icon" aria-hidden="true">⌕</span>
          <input v-model="q" type="search" placeholder="Search news, tags, @handles…" aria-label="Search news" />
        </label>
        <div v-if="mode !== 'calendar'" class="nf-seg" role="tablist" aria-label="Ranking">
          <button role="tab" :class="{ on: sort === 'hot' }" @click="sort = 'hot'">Hot</button>
          <button role="tab" :class="{ on: sort === 'newest' }" @click="sort = 'newest'">Newest</button>
          <button role="tab" :class="{ on: sort === 'active' }" @click="sort = 'active'">Active</button>
        </div>
        <button class="nf-btn" :class="{ on: governedOnly }" title="Only items the membrane held / quarantined / rejected" @click="governedOnly = !governedOnly">Governed</button>
        <LiveToggle :state="liveState" :title="liveState === 'live' ? 'Live Bluesky posts from the public AppView (real DIDs/CIDs)' : 'Pull real Bluesky posts from the public network — no key'" @click="goLive" />
      </div>
    </header>

    <!-- Masthead: flag · dateline · live tick · market ticker (broadsheet + Bloomberg data discipline) -->
    <div v-if="mode !== 'calendar'" class="nf-masthead">
      <div class="nf-flag">The SocioProphet</div>
      <div class="nf-dateline">{{ dateline }}<span v-if="liveState === 'live'" class="nf-dl-live"> · updated {{ liveAgo }}</span></div>
      <div class="nf-ticker" aria-label="Markets">
        <span v-for="t in ticker" :key="t.symbol" class="nf-tk" :class="t.changePct >= 0 ? 'up' : 'down'">
          <b>{{ t.symbol }}</b> {{ t.price }} <i>{{ t.changePct >= 0 ? '▲' : '▼' }}{{ Math.abs(t.changePct).toFixed(1) }}%</i>
        </span>
      </div>
    </div>

    <!-- Body: sources rail · front page · reader overlay -->
    <div class="nf-body">
      <!-- Feedly rail: subscribed sources -->
      <aside class="nf-rail" aria-label="Sources">
        <div class="nf-rail-head">Feeds</div>
        <button class="nf-src" :class="{ on: activeSourceId === 'all' }" @click="setSource('all')">
          <span class="nf-src-name">All feeds</span>
          <span class="nf-src-n">{{ all.length }}</span>
        </button>
        <button v-for="s in sources" :key="s.id" class="nf-src" :class="{ on: activeSourceId === s.id }" @click="setSource(s.id)">
          <span class="nf-dot" :style="{ background: sourceColor(s.id) }" />
          <span class="nf-src-name">{{ s.title }}</span>
          <span class="nf-src-n">{{ countFor(s.id) }}</span>
        </button>
        <div class="nf-rail-head" style="margin-top:0.6rem">Tags</div>
        <button v-for="t in topTags" :key="t" class="nf-tagrow" :class="{ on: activeTag === t }" @click="toggleTag(t)">
          <span class="nf-hash">#</span>{{ t }}
        </button>
        <div class="nf-rail-hint">j/k move · o open · u upvote</div>
      </aside>

      <!-- Lobsters stream -->
      <div ref="listEl" class="nf-list" :class="{ calendar: mode === 'calendar' }" aria-label="Stories">
        <EmptyState v-if="items.length === 0" title="No stories match" hint="Clear the filters or pick “All feeds” to see the full stream." />

        <!-- Event Calendar lens (grouped by day) -->
        <template v-if="mode === 'calendar'">
          <section v-for="g in byDay" :key="g.day" class="nf-day">
            <div class="nf-day-h">{{ g.label }}<span class="nf-day-c">{{ g.items.length }}</span></div>
            <button v-for="it in g.items" :key="it.id" class="nf-agenda" :class="{ on: it.id === selectedId }" @click="select(it.id)">
              <span class="nf-agenda-time">{{ timeLabel(it.publishedAt) }}</span>
              <span class="nf-agenda-title">{{ it.title }}</span>
              <span class="nf-agenda-src" :style="{ color: sourceColor(it.sourceId) }">{{ sourceOf(it)?.title }}</span>
            </button>
          </section>
        </template>

        <!-- Front page: a lead well + a multi-column river (broadsheet + BBG data discipline) -->
        <template v-else>
          <button v-if="pendingNew.length" class="nf-newpill" @click="showPending">
            <span class="nf-newpill-dot" /> {{ pendingNew.length }} new stor{{ pendingNew.length === 1 ? 'y' : 'ies' }} — show
          </button>

          <!-- Lead well — the day's biggest story, broadsheet-scale. -->
          <article v-if="lead" class="nf-lead" :class="{ on: lead.id === selectedId, flash: flashIds.has(lead.id), social: !!bskyOf(lead) }" @click="select(lead.id)">
            <div class="nf-kicker">
              <span class="nf-kick-src" :style="{ color: sourceColor(lead.sourceId) }">{{ bskyOf(lead) ? '@' + bskyOf(lead)!.actor.handle : sourceOf(lead)?.title }}</span>
              <span class="nf-q" :class="metaOf(lead).qualityBand">{{ pct(metaOf(lead).quality) }} truth</span>
              <span v-if="lead.membraneDecision !== 'admit'" class="nf-mem" :class="lead.membraneDecision">{{ lead.membraneDecision }}</span>
              <span class="nf-time">{{ relative(lead.publishedAt) }}</span>
            </div>
            <h2 class="nf-lead-title">{{ bskyOf(lead) ? bskyOf(lead)!.text : lead.title }}</h2>
            <p class="nf-lead-deck">{{ bskyOf(lead) ? bskyOf(lead)!.actor.displayName + (bskyOf(lead)!.actor.did ? ' · verified DID' : '') : lead.summary }}</p>
            <div class="nf-lead-foot">
              <span class="nf-auth">{{ bskyOf(lead) ? 'On Bluesky' : 'By ' + metaOf(lead).submitter }}</span>
              <span class="nf-foot-sep">·</span>
              <button class="nf-link" @click.stop="select(lead.id)">{{ metaOf(lead).comments }} comments</button>
            </div>
          </article>

          <!-- River — the multi-column broadsheet run, hairline column rules. -->
          <div class="nf-river">
            <article v-for="it in river" :key="it.id" class="nf-art" :class="{ on: it.id === selectedId, flash: flashIds.has(it.id), social: !!bskyOf(it) }" @click="select(it.id)">
              <div class="nf-kicker">
                <span class="nf-kick-src" :style="{ color: sourceColor(it.sourceId) }">{{ bskyOf(it) ? '@' + bskyOf(it)!.actor.handle : sourceOf(it)?.title }}</span>
                <span class="nf-time">{{ relative(it.publishedAt) }}</span>
              </div>
              <h3 class="nf-art-title">{{ bskyOf(it) ? bskyOf(it)!.text : it.title }}</h3>
              <p v-if="!bskyOf(it) && it.summary" class="nf-art-deck">{{ it.summary }}</p>
              <div class="nf-art-meta">
                <span class="nf-q sm" :class="metaOf(it).qualityBand" title="Truth rating">{{ pct(metaOf(it).quality) }}</span>
                <span v-if="it.membraneDecision !== 'admit'" class="nf-mem" :class="it.membraneDecision">{{ it.membraneDecision }}</span>
                <button v-for="t in metaOf(it).tags.slice(0, 2)" :key="t" class="nf-tag" @click.stop="toggleTag(t)">{{ t }}</button>
              </div>
            </article>
            <div ref="sentinelEl" class="nf-sentinel" aria-hidden="true"></div>
          </div>

          <div v-if="visibleCount < items.length" class="nf-more" @click="loadMore">Load more ({{ items.length - visibleCount }} more)</div>
          <div v-else-if="liveState === 'live'" class="nf-more streaming"><span class="nf-pulse-dot" /> streaming live — scroll for older stories</div>
          <div v-else-if="items.length" class="nf-more end">· end of feed · <button class="nf-more-live" @click="goLive">go live for more →</button></div>
        </template>
      </div>

      <!-- Reader — slide-over overlay (opens on click; the front page keeps full width). -->
      <transition name="nf-slide">
      <div v-if="selected" class="nf-reader-wrap">
      <div class="nf-reader-scrim" @click="closeReader"></div>
      <article class="nf-reader" aria-label="Reader">
        <div class="nf-reader-meta">
          <span class="nf-src-tag" :style="{ color: sourceColor(selected.sourceId) }">{{ sourceOf(selected)?.title }}</span>
          <span class="nf-time">{{ relative(selected.publishedAt) }}</span>
          <span class="nf-q" :class="metaOf(selected).qualityBand">◆ {{ Math.round(metaOf(selected).quality * 100) }} truth</span>
          <button class="nf-reader-close" type="button" aria-label="Close reader" title="Close (Esc)" @click="closeReader">✕</button>
        </div>
        <h2 class="nf-reader-title">{{ selected.title }}</h2>
        <div class="nf-reader-tags">
          <button v-for="t in metaOf(selected).tags" :key="t" class="nf-tag" @click="toggleTag(t)">{{ t }}</button>
        </div>
        <p v-if="!bskyOf(selected)" class="nf-reader-body">{{ selected.summary }}</p>

        <div class="nf-actions">
          <button class="nf-act" :class="{ on: upvoted.has(selected.id) }" @click="toggleUp(selected.id)">▲ Upvote · {{ scoreOf(selected) }}</button>
          <a class="nf-act primary" :href="selected.canonicalUrl" target="_blank" rel="noreferrer">{{ bskyOf(selected) ? 'Open in Bluesky ↗' : 'Open ↗' }}</a>
          <button class="nf-act nf-act-ask" @click="askNoeticaNews">◇ Ask Noetica</button>
          <button class="nf-act" :class="{ done: saved.has(selected.id) }" :disabled="saved.has(selected.id)" @click="save(selected)">{{ saved.has(selected.id) ? 'Saved ✓' : 'Save' }}</button>
        </div>

        <!-- Bluesky (ATProto) social block: identity, thread (Live rail), provenance chain -->
        <template v-if="bskyOf(selected)">
          <div class="nf-block">
            <div class="nf-block-h">🦋 Bluesky · thread</div>
            <div v-for="p in threadFor(bskyOf(selected)!)" :key="p.uri" class="nf-thread" :class="{ on: p.itemId === selected.id }">
              <div class="nf-bsky-av sm" aria-hidden="true">{{ initials(p.actor.displayName) }}</div>
              <div class="nf-thread-main">
                <div class="nf-thread-id"><b>{{ p.actor.displayName }}</b> <span class="nf-bsky-handle">@{{ p.actor.handle }}</span><span v-if="p.isReply" class="nf-thread-reply">reply</span></div>
                <p class="nf-thread-text">{{ p.text }}</p>
                <div class="nf-bsky-eng small"><span>💬 {{ p.replyCount }}</span><span>🔁 {{ p.repostCount }}</span><span>♥ {{ p.likeCount }}</span></div>
              </div>
            </div>
          </div>
          <div class="nf-block">
            <div class="nf-block-h">ATProto provenance</div>
            <div class="nf-kv"><span>Actor DID</span><code class="nf-hashcode">{{ bskyOf(selected)!.actor.did }}</code></div>
            <div class="nf-kv"><span>Post URI</span><code class="nf-hashcode">{{ bskyOf(selected)!.uri }}</code></div>
            <div class="nf-kv"><span>Record CID</span><code class="nf-hashcode">{{ bskyOf(selected)!.cid }}</code></div>
            <div class="nf-kv"><span>Rail · lane</span><code>{{ bskyOf(selected)!.rail }} → {{ bskyOf(selected)!.lane }}</code></div>
            <div class="nf-kv"><span>Root</span><code>bsky / {{ bskyOf(selected)!.rootType }}</code></div>
            <div class="nf-kv"><span>RootBinding</span><code>{{ bskyOf(selected)!.rootBinding }}</code></div>
            <div class="nf-kv"><span>Grant</span><code>{{ bskyOf(selected)!.grantRef }}</code></div>
          </div>
        </template>

        <div v-if="selected.claims.length" class="nf-block">
          <div class="nf-block-h">Claims</div>
          <ul class="nf-claims"><li v-for="(c, i) in selected.claims" :key="i">{{ c }}</li></ul>
        </div>
        <div class="nf-block">
          <ExtractionPanel :text="`${selected.title}. ${selected.summary}`" :source="sourceOf(selected)?.title" />
        </div>
        <div class="nf-block">
          <ClaimsPanel :text="`${selected.title}. ${selected.summary}`" :source="sourceOf(selected)?.title ?? 'news'" />
        </div>
        <div class="nf-block">
          <div class="nf-block-h">Scope · provenance</div>
          <div class="nf-kv"><span>Topic</span><code>{{ selected.topicScope }}</code></div>
          <div class="nf-kv"><span>Membrane</span><code>{{ selected.membraneDecision }}</code></div>
          <div class="nf-kv"><span>Provenance</span><code class="nf-hashcode">{{ selected.provenanceHash }}</code></div>
        </div>

        <!-- Discussion — comments CAN be downvoted, but only with a reason -->
        <div class="nf-block">
          <div class="nf-block-h">Discussion · {{ metaOf(selected).comments }}</div>
          <div v-for="c in commentsFor(selected)" :key="c.id" class="nf-comment">
            <div class="nf-c-vote" @click.stop>
              <button class="nf-up sm" :class="{ on: cUp.has(c.id) }" title="Upvote" @click="toggleCUp(c.id)">▲</button>
              <button class="nf-down sm" :class="{ on: cDown.has(c.id) }" title="Downvote (reason required)" @click="openDown = openDown === c.id ? '' : c.id">▼</button>
            </div>
            <div class="nf-c-main">
              <div class="nf-c-by">{{ c.author }}<span v-if="c.hat" class="nf-hat" :class="c.hat.kind">{{ c.hat.label }}</span><span class="nf-c-score">{{ c.score + (cUp.has(c.id) ? 1 : 0) - (cDown.has(c.id) ? 1 : 0) }}</span></div>
              <p class="nf-c-body">{{ c.body }}</p>
              <div v-if="cDown.has(c.id)" class="nf-c-reason">downvoted: {{ cDown.get(c.id) }}</div>
              <div v-if="openDown === c.id" class="nf-reasons" @click.stop>
                <span class="nf-reasons-h">reason:</span>
                <button v-for="r in DOWNVOTE_REASONS" :key="r" @click="setCDown(c.id, r)">{{ r }}</button>
              </div>
            </div>
          </div>
        </div>
      </article>
      </div>
      </transition>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue';
import { useRoute } from 'vue-router';
import { navScopeForPath } from '../config/cockpitNav';
import { newsSources, newsItems } from '../data/newsFeedFixture';
import { instruments } from '../data/marketsFixture';
import { blueskySources, blueskyItems, blueskyMeta, type BskyPost } from '../data/blueskyFixture';
import { fetchBlueskyLive, BSKY_LIVE_SOURCE } from '../data/adapters/blueskyLive';
import { fetchHackerNews, HN_LIVE_SOURCE } from '../data/adapters/newsLive';
import { fetchGdelt, GDELT_LIVE_SOURCE } from '../data/adapters/gdeltLive';
import type { FeedItem } from '../features/feed-intelligence/types';
import {
  storyMeta, DOWNVOTE_REASONS, FLAG_REASONS,
  type DownvoteReason, type FlagReason, type Hat,
} from '../features/feed-intelligence/community';
import { useResearch } from '../stores/research';
import { useCockpit } from '../stores/cockpit';
import ExtractionPanel from '../components/ExtractionPanel.vue';
import ClaimsPanel from '../components/ClaimsPanel.vue';
import ReputationBadge from '../components/ReputationBadge.vue';
import LiveToggle from '../components/LiveToggle.vue';
import EmptyState from '../components/EmptyState.vue';
import { toGraph } from '../services/ieApi';

// Bluesky (ATProto) is a first-class social source alongside the RSS/capture feeds.
// Live Bluesky adapter — flip the Bluesky source from fixture to the real public
// AppView feed (no key). Fails closed: on error we stay on fixture.
const liveItems = ref<FeedItem[]>([]);
const liveMeta = ref<Map<string, BskyPost>>(new Map());
const liveState = ref<'idle' | 'loading' | 'live' | 'error'>('idle');
const liveSources = ref<typeof newsSources>([]);

// ── Live newswire: not a one-shot fetch. When live, we poll every LIVE_POLL_MS,
// stage genuinely-new items in a buffer (Twitter-style "N new" pill so the scroll
// position is never yanked), and GROUND each new item into the sovereign HellGraph
// via ie-engine (/svc/ie → /to-graph). That is the News → IE → graph edge of the
// grounding loop, closing continuously as the feed streams. All best-effort: if a
// live source or ie-engine is unreachable we fail closed and stay on what we have.
const LIVE_POLL_MS = 40_000;
let pollTimer: ReturnType<typeof setInterval> | undefined;
let clockTimer: ReturnType<typeof setInterval> | undefined;
const seenIds = new Set<string>();
const pendingNew = ref<FeedItem[]>([]);   // fetched, not yet shown
const flashIds = ref<Set<string>>(new Set()); // freshly-prepended → flash animation
const groundedFacts = ref(0);              // running count of facts written to the graph
const grounding = ref(false);
const lastLiveAt = ref(0);
const nowRef = ref(Date.now());            // reactive clock so live timestamps tick

async function fetchLive(): Promise<FeedItem[]> {
  const [bsky, hn, gdelt] = await Promise.all([fetchBlueskyLive(), fetchHackerNews(), fetchGdelt('world news', 25)]);
  liveMeta.value = new Map([...liveMeta.value, ...(bsky?.meta ?? new Map())]);
  const srcs = [...(bsky?.items.length ? [BSKY_LIVE_SOURCE] : []), ...(hn?.length ? [HN_LIVE_SOURCE] : []), ...(gdelt?.length ? [GDELT_LIVE_SOURCE] : [])];
  for (const s of srcs) if (!liveSources.value.some((x) => x.id === s.id)) liveSources.value = [...liveSources.value, s];
  return [...(bsky?.items ?? []), ...(hn ?? []), ...(gdelt ?? [])];
}

// Ground a batch of items into HellGraph (sequential, capped, best-effort).
async function groundLive(batch: FeedItem[]) {
  if (!batch.length) return;
  grounding.value = true;
  for (const it of batch.slice(0, 8)) {
    try {
      const w = await toGraph(`${it.title}. ${it.summary}`);
      groundedFacts.value += (w.nodes_written ?? 0) + (w.edges_written ?? 0);
    } catch { /* ie-engine unreachable → skip, stay resilient */ }
  }
  grounding.value = false;
}

async function goLive() {
  if (liveState.value === 'loading') return;
  if (liveState.value === 'live') { stopLive(); return; }
  liveState.value = 'loading';
  const items = await fetchLive();
  if (!items.length) { liveState.value = 'error'; return; }
  for (const i of items) seenIds.add(i.id);
  liveItems.value = items;
  liveState.value = 'live';
  lastLiveAt.value = Date.now();
  visibleCount.value = PAGE;
  void groundLive(items);
  pollTimer = setInterval(pollLive, LIVE_POLL_MS);
  clockTimer = setInterval(() => { nowRef.value = Date.now(); }, 15_000);
}
function stopLive() {
  liveState.value = 'idle';
  if (pollTimer) clearInterval(pollTimer); pollTimer = undefined;
  if (clockTimer) clearInterval(clockTimer); clockTimer = undefined;
  pendingNew.value = [];
}
async function pollLive() {
  if (liveState.value !== 'live') return;
  const items = await fetchLive();
  const fresh = items.filter((i) => !seenIds.has(i.id));
  for (const i of fresh) seenIds.add(i.id);
  lastLiveAt.value = Date.now();
  if (!fresh.length) return;
  // If the reader is at the very top and no reader is open, stream straight in;
  // otherwise stage them behind the "N new" pill.
  const atTop = (listEl.value?.scrollTop ?? 1) < 24;
  if (atTop) prependItems(fresh);
  else pendingNew.value = [...fresh, ...pendingNew.value];
  void groundLive(fresh);
}
function prependItems(fresh: FeedItem[]) {
  liveItems.value = [...fresh, ...liveItems.value];
  const fl = new Set(flashIds.value);
  for (const i of fresh) fl.add(i.id);
  flashIds.value = fl;
  visibleCount.value += fresh.length;
  setTimeout(() => {
    const rem = new Set(flashIds.value);
    for (const i of fresh) rem.delete(i.id);
    flashIds.value = rem;
  }, 2400);
}
function showPending() {
  prependItems(pendingNew.value);
  pendingNew.value = [];
  listEl.value?.scrollTo({ top: 0, behavior: 'smooth' });
}
const liveAgo = computed(() => {
  if (liveState.value !== 'live' || !lastLiveAt.value) return '';
  const s = Math.max(0, Math.round((nowRef.value - lastLiveAt.value) / 1000));
  return s < 60 ? `${s}s ago` : `${Math.round(s / 60)}m ago`;
});
const sources = computed(() => [...newsSources, ...blueskySources, ...liveSources.value]);
const all = computed(() => [...newsItems, ...blueskyItems, ...liveItems.value]);
const research = useResearch();
const cockpit = useCockpit();
const route = useRoute();
const bskyOf = (it: FeedItem): BskyPost | undefined => blueskyMeta.get(it.id) ?? liveMeta.value.get(it.id);
const initials = (name: string): string => name.split(/\s+/).slice(0, 2).map((w) => w[0]?.toUpperCase() ?? '').join('');
// A thread = its root post + every reply pointing at that root (Live-rail context).
function threadFor(p: BskyPost): BskyPost[] {
  const rootUri = p.threadUri ?? p.uri;
  const pool = [...blueskyMeta.values(), ...liveMeta.value.values()];
  const root = pool.find((x) => x.uri === rootUri);
  const replies = pool.filter((x) => x.threadUri === rootUri);
  return [...(root ? [root] : []), ...replies];
}
function askNoeticaNews() {
  const it = selected.value; if (!it) return;
  const b = bskyOf(it);
  const who = b ? `@${b.actor.handle}` : (sourceOf(it)?.title ?? 'a source');
  cockpit.askAbout(`About this ${b ? 'Bluesky post' : 'story'} from ${who}: "${it.title}". Membrane decision: ${it.membraneDecision}. Is it credible, what's the provenance, and what matters?`);
}

// Precompute the derived community layer once (deterministic per id).
const META = computed(() => new Map(all.value.map((it) => [it.id, storyMeta(it)] as const)));
const metaOf = (it: FeedItem) => META.value.get(it.id)!;

const activeSourceId = ref<'all' | string>('all');
const activeTag = ref<string>('');
const sort = ref<'hot' | 'newest' | 'active'>('hot');
const governedOnly = ref(false);
const q = ref('');
const selectedId = ref<string>('');
const upvoted = ref<Set<string>>(new Set());
const saved = ref<Set<string>>(new Set());
const flags = ref<Map<string, FlagReason>>(new Map());
const openFlag = ref<string>('');
const cUp = ref<Set<string>>(new Set());
const cDown = ref<Map<string, DownvoteReason>>(new Map());
const openDown = ref<string>('');
const listEl = ref<HTMLElement | null>(null);
const sentinelEl = ref<HTMLElement | null>(null);

// Infinite scroll: reveal the stream progressively (so even the corpus scrolls),
// and when live + near the end, pull an older GDELT page so it never dead-ends.
const PAGE = 14;
const visibleCount = ref(PAGE);
let scrollObserver: IntersectionObserver | undefined;
async function loadMore() {
  if (visibleCount.value < items.value.length) {
    visibleCount.value = Math.min(items.value.length, visibleCount.value + PAGE);
    return;
  }
  if (liveState.value === 'live') {
    // reached the end of the live buffer → fetch an older page and append
    const more = await fetchGdelt('world OR markets OR policy', 25);
    const fresh = (more ?? []).filter((i) => !seenIds.has(i.id));
    for (const i of fresh) seenIds.add(i.id);
    if (fresh.length) { liveItems.value = [...liveItems.value, ...fresh]; visibleCount.value += fresh.length; }
  }
}

const scope = computed(() => navScopeForPath(route.path));
const mode = computed<'feed' | 'calendar'>(() => (route.path.endsWith('/calendar') ? 'calendar' : 'feed'));

const scoreOf = (it: FeedItem) => metaOf(it).score + (upvoted.value.has(it.id) ? 1 : 0);

const items = computed<FeedItem[]>(() => {
  let list = all.value;
  if (activeSourceId.value !== 'all') list = list.filter((i) => i.sourceId === activeSourceId.value);
  if (activeTag.value) list = list.filter((i) => metaOf(i).tags.includes(activeTag.value));
  if (governedOnly.value) list = list.filter((i) => i.membraneDecision !== 'admit');
  const needle = q.value.trim().toLowerCase();
  if (needle) list = list.filter((i) =>
    i.title.toLowerCase().includes(needle)
    || i.summary.toLowerCase().includes(needle)
    || metaOf(i).tags.some((t) => t.toLowerCase().includes(needle))
    || (bskyOf(i)?.actor.handle.toLowerCase().includes(needle) ?? false),
  );
  const byNew = (a: FeedItem, b: FeedItem) => +new Date(b.publishedAt) - +new Date(a.publishedAt);
  if (mode.value === 'calendar') return [...list].sort(byNew);
  const s = [...list];
  if (sort.value === 'newest') s.sort(byNew);
  else if (sort.value === 'active') s.sort((a, b) => metaOf(b).comments - metaOf(a).comments);
  else s.sort((a, b) => scoreOf(b) - scoreOf(a)); // hot
  return s;
});
// Progressive slice shown in the stream (grown by the scroll sentinel).
const visibleItems = computed<FeedItem[]>(() => items.value.slice(0, visibleCount.value));
// Front-page split: a lead well + the multi-column river below it.
const lead = computed<FeedItem | undefined>(() => (mode.value === 'calendar' ? undefined : visibleItems.value[0]));
const river = computed<FeedItem[]>(() => (mode.value === 'calendar' ? [] : visibleItems.value.slice(1)));
const ticker = instruments.slice(0, 9);
const pct = (n: number) => Math.round(n * 100);
// Reset the window when the filter set changes so you always see the top of the new list.
watch([activeSourceId, activeTag, governedOnly, q, sort], () => { visibleCount.value = PAGE; });

// Reader is a slide-over overlay: closed by default (front page uses full width), opens on click.
const readerClosed = ref(true);
const selected = computed<FeedItem | undefined>(() => (readerClosed.value ? undefined : all.value.find((i) => i.id === selectedId.value)));
function focus(id: string) { selectedId.value = id; }

const sourceById = computed(() => new Map(sources.value.map((s) => [s.id, s])));
const sourceOf = (it: FeedItem) => sourceById.value.get(it.sourceId);
const countFor = (sid: string) => all.value.filter((i) => i.sourceId === sid).length;

const topTags = computed(() => {
  const c = new Map<string, number>();
  for (const it of all.value) for (const t of metaOf(it).tags) c.set(t, (c.get(t) ?? 0) + 1);
  return [...c.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8).map(([t]) => t);
});

const SRC_COLORS: Record<string, string> = {
  'src-world': '#58a6ff', 'src-tech': '#c58af9', 'src-markets': 'var(--up)', 'src-reg': '#f0883e', 'src-capture': '#e3b341', 'src-bsky': '#3b9cff', 'src-bsky-live': '#3b9cff', 'src-hn-live': '#ff6600',
};
const sourceColor = (sid: string) => SRC_COLORS[sid] ?? '#8b949e';
function domainOf(url: string): string { try { return new URL(url).hostname.replace(/^www\./, ''); } catch { return 'source'; } }

function select(id: string) { selectedId.value = id; readerClosed.value = false; }
function closeReader() { readerClosed.value = true; }
function setSource(sid: 'all' | string) { activeSourceId.value = sid; }
function toggleTag(t: string) { activeTag.value = activeTag.value === t ? '' : t; }
function toggleUp(id: string) { if (upvoted.value.has(id)) upvoted.value.delete(id); else upvoted.value.add(id); upvoted.value = new Set(upvoted.value); }
function setFlag(id: string, r: FlagReason) { flags.value.set(id, r); flags.value = new Map(flags.value); openFlag.value = ''; }
function toggleCUp(id: string) { if (cUp.value.has(id)) cUp.value.delete(id); else cUp.value.add(id); cUp.value = new Set(cUp.value); }
function setCDown(id: string, r: DownvoteReason) { cDown.value.set(id, r); cDown.value = new Map(cDown.value); openDown.value = ''; }

function save(it?: FeedItem) {
  if (!it || saved.value.has(it.id)) return;
  research.capture({ path: it.canonicalUrl, title: it.title, domain: 'News & Events', openedAt: Date.now() }, 'manual');
  saved.value.add(it.id);
}

// Deterministic discussion stubs so the reasoned-downvote is demonstrable offline.
type CommentVM = { id: string; author: string; hat: Hat | null; body: string; score: number };
const COMMENT_BODIES = [
  'Solid write-up. The provenance chain checks out against the primary source.',
  'This conflates correlation with causation in the third paragraph.',
  'Counterpoint: the underlying dataset was revised last quarter.',
  'Anyone have a mirror? The canonical link is rate-limiting.',
  'The membrane held a near-duplicate of this yesterday — worth merging.',
];
function commentsFor(it: FeedItem): CommentVM[] {
  const n = Math.min(3, metaOf(it).comments === 0 ? 0 : (metaOf(it).comments % 3) + 1);
  const m = metaOf(it);
  return Array.from({ length: n }, (_, i) => ({
    id: `${it.id}-c${i}`,
    author: [m.submitter, 'reader', 'skeptic'][i] ?? 'reader',
    hat: i === 0 ? m.hat : null,
    body: COMMENT_BODIES[(it.title.length + i) % COMMENT_BODIES.length]!,
    score: ((it.title.length + i * 7) % 24) - 4,
  }));
}

const NOW = new Date('2026-07-03T14:00:00-04:00').getTime();
const dateline = new Date(NOW).toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });
function relative(iso: string): string {
  // When streaming, measure against the live reactive clock so times tick; otherwise
  // against the fixture's frozen "now" so the corpus reads consistently.
  const base = liveState.value === 'live' ? nowRef.value : NOW;
  const mins = Math.max(0, Math.round((base - new Date(iso).getTime()) / 60000));
  if (mins < 1) return 'now';
  if (mins < 60) return `${mins}m`;
  const h = Math.round(mins / 60);
  return h < 24 ? `${h}h` : `${Math.round(h / 24)}d`;
}

const byDay = computed(() => {
  const groups: Array<{ day: string; label: string; items: FeedItem[] }> = [];
  for (const it of items.value) {
    const day = it.publishedAt.slice(0, 10);
    let g = groups.find((x) => x.day === day);
    if (!g) { g = { day, label: dayLabel(it.publishedAt), items: [] }; groups.push(g); }
    g.items.push(it);
  }
  return groups;
});
function dayLabel(iso: string): string { return new Date(iso).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }); }
function timeLabel(iso: string): string { return new Date(iso).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }); }

function onKey(e: KeyboardEvent) {
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  const tag = (e.target as HTMLElement | null)?.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA') return;
  if (e.key === 'Escape') { if (!readerClosed.value) { e.preventDefault(); closeReader(); } return; }
  const list = visibleItems.value;
  if (!list.length) return;
  const idx = list.findIndex((i) => i.id === selectedId.value);
  const cur = all.value.find((i) => i.id === selectedId.value);
  if (e.key === 'j') { e.preventDefault(); const n = Math.min(list.length - 1, idx + 1); if (n === list.length - 1) void loadMore(); focus(list[n]!.id); }
  else if (e.key === 'k') { e.preventDefault(); focus(list[Math.max(0, idx < 0 ? 0 : idx - 1)]!.id); }
  else if (e.key === 'Enter') { e.preventDefault(); if (selectedId.value) select(selectedId.value); }
  else if (e.key === 'o') { if (cur) window.open(cur.canonicalUrl, '_blank', 'noreferrer'); }
  else if (e.key === 'u') { if (cur) toggleUp(cur.id); }
}

watch(selectedId, async () => { await nextTick(); listEl.value?.querySelector('.nf-art.on, .nf-lead.on')?.scrollIntoView({ block: 'nearest' }); });
watch(mode, (m) => { if (m === 'feed' && route.path.endsWith('/recent')) sort.value = 'newest'; }, { immediate: true });
watch(selectedId, (id) => {
  const it = all.value.find((i) => i.id === id);
  if (!it) return;
  const b = bskyOf(it);
  cockpit.setContext({ surface: 'News', entityLabel: b ? `@${b.actor.handle}` : (sourceOf(it)?.title ?? 'story'), detail: it.title.slice(0, 60), route: route.path });
}, { immediate: true });

onMounted(() => {
  if (route.path.endsWith('/recent')) sort.value = 'newest';
  const deep = typeof route.query.item === 'string' ? route.query.item : '';
  selectedId.value = (deep && all.value.some((i) => i.id === deep)) ? deep : (items.value[0]?.id ?? '');
  window.addEventListener('keydown', onKey);
  nextTick(() => {
    if (!sentinelEl.value) return;
    scrollObserver = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) void loadMore();
    }, { root: listEl.value, rootMargin: '400px' });
    scrollObserver.observe(sentinelEl.value);
  });
});
onUnmounted(() => {
  window.removeEventListener('keydown', onKey);
  scrollObserver?.disconnect();
  if (pollTimer) clearInterval(pollTimer);
  if (clockTimer) clearInterval(clockTimer);
});
</script>

<style scoped>
.news { height: 100%; min-height: 0; display: grid; grid-template-rows: auto 1fr; gap: 0.75rem; padding: 1rem 1.25rem 1.25rem; background: var(--bg); color: rgba(255, 255, 255, 0.92); }
.nf-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 1rem; flex-wrap: wrap; }
.nf-title { display: flex; align-items: baseline; gap: 0.6rem; } .nf-title h1 { margin: 0; font-size: 1.3rem; }
.nf-eyebrow { margin: 0 0 0.1rem; font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--text-3); }
.nf-pill { font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--amber); background: var(--amber-soft); border-radius: 5px; padding: 0.1rem 0.35rem; }
.nf-pill.live { color: var(--live); background: var(--live-soft); }
/* Live pulse (Bloomberg-terminal cue): streaming state + tick + running graph-grounding count */
.nf-pulse { display: inline-flex; align-items: center; gap: 0.3rem; font-size: 0.64rem; color: var(--text-3); letter-spacing: 0.02em; }
.nf-pulse-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--live); flex: 0 0 auto; animation: nfPulse 1.8s ease-in-out infinite; }
.nf-pulse-dot.working { background: var(--accent); animation-duration: 0.8s; }
.nf-pulse-sep { opacity: 0.4; }
.nf-pulse-ago { font-variant-numeric: tabular-nums; }
.nf-grounded { color: var(--accent); font-weight: 700; font-variant-numeric: tabular-nums; }
@keyframes nfPulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.35; transform: scale(0.7); } }

/* Streaming "N new" pill (Twitter-style) */
.nf-newpill { position: sticky; top: 0.3rem; z-index: 3; display: block; margin: 0.4rem auto; padding: 0.3rem 0.9rem; border: 1px solid color-mix(in srgb, var(--live) 45%, transparent); background: color-mix(in srgb, var(--live) 14%, var(--surface)); color: var(--live); border-radius: 999px; font-size: 0.74rem; font-weight: 650; cursor: pointer; box-shadow: 0 3px 12px rgba(0,0,0,0.28); }
.nf-newpill:hover { background: color-mix(in srgb, var(--live) 22%, var(--surface)); }
.nf-newpill-dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: var(--live); margin-right: 0.35rem; animation: nfPulse 1.6s ease-in-out infinite; }

/* Freshly-streamed rows flash in */
.nf-story.flash { animation: nfFlash 2.4s ease; }
@keyframes nfFlash { 0% { background: color-mix(in srgb, var(--live) 16%, transparent); } 100% { background: transparent; } }

/* Scroll sentinel + footer */
.nf-sentinel { height: 1px; }
.nf-more { display: flex; align-items: center; justify-content: center; gap: 0.35rem; padding: 0.85rem; font-size: 0.74rem; color: var(--text-3); cursor: pointer; border-top: 1px solid var(--line); }
.nf-more:hover { color: var(--text-2); }
.nf-more.streaming, .nf-more.end { cursor: default; }
.nf-more.streaming .nf-pulse-dot { margin-right: 0.15rem; }
.nf-more-live { border: none; background: transparent; color: var(--accent); font: inherit; cursor: pointer; padding: 0; }
.nf-more-live:hover { text-decoration: underline; }
@media (prefers-reduced-motion: reduce) { .nf-pulse-dot, .nf-newpill-dot { animation: none; } .nf-story.flash { animation: none; } }
.nf-live.on { border-color: #4bbf73; color: #4bbf73; background: rgba(75, 191, 115, 0.14); }
.nf-live.err { border-color: rgba(240, 101, 106, 0.5); color: #f0656a; }
.nf-btn:disabled { opacity: 0.6; cursor: default; }
.nf-tools { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
.nf-search { display: inline-flex; align-items: center; gap: 0.4rem; border: 1px solid var(--line-2); border-radius: 8px; padding: 0.25rem 0.6rem; background: var(--surface-2); min-width: 15rem; }
.nf-search:focus-within { border-color: #58a6ff; }
.nf-search-icon { color: var(--text-3); font-size: 0.9rem; }
.nf-search input { flex: 1; min-width: 0; border: none; background: transparent; color: var(--text); font: inherit; font-size: 0.82rem; outline: none; }
.nf-search input::placeholder { color: var(--text-3); }
.nf-seg { display: inline-flex; border: 1px solid var(--line-2); border-radius: 8px; overflow: hidden; }
.nf-seg button { border: none; background: transparent; color: rgba(255, 255, 255, 0.6); padding: 0.3rem 0.7rem; font-size: 0.78rem; cursor: pointer; } .nf-seg button.on { background: rgba(88, 166, 255, 0.18); color: #58a6ff; }
.nf-btn { border: 1px solid var(--line-2); background: transparent; color: rgba(255, 255, 255, 0.7); border-radius: 8px; padding: 0.3rem 0.6rem; font-size: 0.76rem; cursor: pointer; } .nf-btn.on { border-color: #58a6ff; color: #58a6ff; background: rgba(88, 166, 255, 0.12); }

.nf-body { min-height: 0; display: grid; grid-template-columns: 176px 1fr; gap: 0; position: relative; }
@media (max-width: 900px) { .nf-body { grid-template-columns: 1fr; } .nf-rail { display: none; } }

/* Masthead — broadsheet flag + dateline + Bloomberg ticker strip */
.nf-masthead { display: grid; grid-template-columns: auto 1fr auto; align-items: baseline; gap: 1rem; padding: 0.2rem 0.25rem 0.5rem; border-bottom: 2px solid var(--text); }
.nf-flag { font-family: Georgia, 'Times New Roman', serif; font-size: 1.45rem; font-weight: 700; letter-spacing: -0.02em; color: var(--text); }
.nf-dateline { font-size: 0.72rem; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.06em; } .nf-dl-live { color: var(--live); text-transform: none; letter-spacing: 0; }
.nf-ticker { display: flex; gap: 0.9rem; overflow: hidden; justify-content: flex-end; font-variant-numeric: tabular-nums; }
.nf-tk { font-size: 0.68rem; color: var(--text-2); white-space: nowrap; } .nf-tk b { font-weight: 700; color: var(--text); margin-right: 0.15rem; } .nf-tk i { font-style: normal; font-size: 0.62rem; }
.nf-tk.up i { color: var(--up); } .nf-tk.down i { color: var(--down); }

/* Tufte pass: de-box the three panels — no rounded borders/fills; columns read from content
   + quiet hairline dividers in the grid gap (data-ink, not chartjunk). */
.nf-rail { min-height: 0; overflow-y: auto; border-right: 1px solid var(--line); padding: 0.25rem 0.85rem 0.25rem 0.1rem; display: flex; flex-direction: column; gap: 0.12rem; }
.nf-rail-head { font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.1em; color: rgba(255, 255, 255, 0.4); padding: 0.3rem 0.5rem; }
.nf-src { display: flex; align-items: center; gap: 0.5rem; border: none; background: transparent; color: rgba(255, 255, 255, 0.78); border-radius: 8px; padding: 0.4rem 0.5rem; font-size: 0.82rem; cursor: pointer; text-align: left; } .nf-src:hover { background: rgba(255, 255, 255, 0.05); } .nf-src.on { background: rgba(88, 166, 255, 0.14); color: #fff; }
.nf-dot { width: 8px; height: 8px; border-radius: 50%; flex: 0 0 auto; }
.nf-src-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.nf-src-n { font-size: 0.66rem; color: rgba(255, 255, 255, 0.4); }
.nf-tagrow { display: flex; align-items: center; gap: 0.15rem; border: none; background: transparent; color: rgba(255, 255, 255, 0.7); border-radius: 8px; padding: 0.28rem 0.5rem; font-size: 0.8rem; cursor: pointer; text-align: left; } .nf-tagrow:hover { background: rgba(255, 255, 255, 0.05); } .nf-tagrow.on { background: rgba(88, 166, 255, 0.14); color: #58a6ff; }
.nf-hash { color: var(--text-3); }
.nf-rail-hint { margin-top: auto; padding: 0.5rem; font-size: 0.64rem; color: var(--text-3); line-height: 1.5; }

.nf-list { min-height: 0; overflow-y: auto; padding: 0.6rem 1.3rem 1rem; }

/* Shared editorial kicker (source · truth · time) */
.nf-kicker { display: flex; align-items: baseline; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 0.3rem; }
.nf-kick-src { font-size: 0.64rem; text-transform: uppercase; letter-spacing: 0.07em; font-weight: 700; }

/* Lead well — the day's dominant story */
.nf-lead { border-bottom: 2px solid var(--line-2); padding: 0.4rem 0 1.1rem; margin-bottom: 1rem; cursor: pointer; }
.nf-lead:hover .nf-lead-title, .nf-lead.on .nf-lead-title { color: var(--accent); }
.nf-lead-title { font-family: Georgia, 'Times New Roman', serif; font-size: 2.3rem; line-height: 1.1; letter-spacing: -0.02em; font-weight: 700; color: var(--text); margin: 0.1rem 0 0.45rem; text-wrap: balance; }
.nf-lead.social .nf-lead-title { font-size: 1.7rem; font-style: italic; }
.nf-lead-deck { font-size: 1.02rem; line-height: 1.55; color: var(--text-2); margin: 0 0 0.6rem; max-width: 62ch; }
.nf-lead-foot { font-size: 0.74rem; color: var(--text-3); display: flex; align-items: center; gap: 0.5rem; } .nf-lead-foot .nf-auth { font-weight: 600; color: var(--text-2); } .nf-foot-sep { opacity: 0.5; }

/* River — the multi-column broadsheet run with hairline column rules */
.nf-river { columns: 3 300px; column-gap: 1.6rem; column-rule: 1px solid var(--line); }
@media (max-width: 1400px) { .nf-river { columns: 2 300px; } }
.nf-art { break-inside: avoid; -webkit-column-break-inside: avoid; padding: 0.7rem 0 0.8rem; border-top: 1px solid var(--line); cursor: pointer; }
.nf-art:hover .nf-art-title, .nf-art.on .nf-art-title { color: var(--accent); }
.nf-art.on { box-shadow: inset 3px 0 0 var(--accent); padding-left: 0.5rem; }
.nf-art-title { font-family: Georgia, 'Times New Roman', serif; font-size: 1.08rem; line-height: 1.25; font-weight: 700; color: var(--text); margin: 0 0 0.25rem; text-wrap: pretty; }
.nf-art.social .nf-art-title { font-size: 0.95rem; font-style: italic; font-weight: 600; color: var(--text-2); }
.nf-art-deck { font-size: 0.82rem; line-height: 1.5; color: var(--text-3); margin: 0 0 0.35rem; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.nf-art-meta { display: flex; align-items: center; gap: 0.4rem; flex-wrap: wrap; }
.nf-q.sm { font-size: 0.62rem; padding: 0.02rem 0.28rem; }

/* Reader → slide-over overlay + scrim */
.nf-reader-wrap { position: absolute; inset: 0; z-index: 20; display: grid; grid-template-columns: 1fr minmax(420px, 40%); }
.nf-reader-scrim { background: rgba(0,0,0,0.4); }
.nf-slide-enter-active, .nf-slide-leave-active { transition: opacity 0.18s ease; } .nf-slide-enter-from, .nf-slide-leave-to { opacity: 0; }
@media (prefers-reduced-motion: reduce) { .nf-slide-enter-active, .nf-slide-leave-active { transition: none; } }

/* Lobsters story row */
.nf-story { display: flex; gap: 0.7rem; padding: 0.7rem 0.85rem; border-bottom: 1px solid var(--line); cursor: pointer; } .nf-story:hover { background: rgba(255, 255, 255, 0.03); } .nf-story.on { background: color-mix(in srgb, var(--accent) 7%, transparent); box-shadow: inset 2px 0 0 var(--accent); }
.nf-vote { display: flex; flex-direction: column; align-items: center; gap: 0.1rem; flex: 0 0 2rem; padding-top: 0.1rem; }
.nf-up { border: none; background: transparent; color: var(--text-3); font-size: 0.9rem; line-height: 1; cursor: pointer; padding: 0.1rem; } .nf-up:hover { color: var(--text-2); } .nf-up.on { color: var(--up); }
.nf-up.sm, .nf-down.sm { font-size: 0.72rem; }
.nf-down { border: none; background: transparent; color: var(--text-3); font-size: 0.9rem; line-height: 1; cursor: pointer; padding: 0.1rem; } .nf-down:hover { color: var(--down); } .nf-down.on { color: var(--down); }
.nf-score { font-size: 0.82rem; font-weight: 700; color: rgba(255, 255, 255, 0.75); font-variant-numeric: tabular-nums; }
.nf-story-main { min-width: 0; flex: 1; }

/* Bluesky (ATProto) social card — author-forward, feed-like (not an inbox row) */
.nf-story.social { padding: 0.8rem 0.95rem; }
.nf-story.social.on { box-shadow: inset 2px 0 0 var(--accent); background: color-mix(in srgb, var(--accent) 7%, transparent); }
.nf-bsky { display: flex; gap: 0.7rem; width: 100%; min-width: 0; }
/* Editorial pass: flat institutional monogram, not a social gradient avatar. */
.nf-bsky-av { flex: 0 0 auto; width: 30px; height: 30px; border-radius: 7px; display: grid; place-items: center; font-size: 0.68rem; font-weight: 600; color: var(--text-2); background: var(--surface-2); border: 1px solid var(--line-2); }
.nf-bsky-av.sm { width: 28px; height: 28px; font-size: 0.66rem; }
.nf-bsky-main { min-width: 0; flex: 1; }
.nf-bsky-id { display: flex; align-items: center; gap: 0.4rem; flex-wrap: wrap; font-size: 0.8rem; }
.nf-bsky-name { font-weight: 700; color: #fff; }
.nf-bsky-handle { color: rgba(255, 255, 255, 0.45); font-size: 0.76rem; }
.nf-bsky-did { font-size: 0.56rem; text-transform: uppercase; letter-spacing: 0.06em; font-weight: 700; color: var(--live); background: color-mix(in srgb, var(--live) 14%, transparent); border-radius: 4px; padding: 0.03rem 0.3rem; }
.nf-bsky-reply { margin: 0.15rem 0 0; font-size: 0.68rem; color: rgba(255, 255, 255, 0.4); }
.nf-bsky-text { margin: 0.35rem 0 0.5rem; font-size: 0.92rem; line-height: 1.5; color: rgba(255, 255, 255, 0.9); white-space: pre-wrap; }
/* Engagement demoted to a quiet metrics line; the truth rating + source lead. */
.nf-bsky-eng { display: flex; align-items: center; gap: 0.7rem; font-size: 0.68rem; color: var(--text-3); flex-wrap: wrap; margin-top: 0.15rem; }
.nf-bsky-eng.small { gap: 0.6rem; font-size: 0.64rem; margin-top: 0.2rem; }
.nf-bsky-rail { color: var(--text-3); }
.nf-eng-n { color: var(--text-3); font-variant-numeric: tabular-nums; }

/* Thread (Live-rail context) in the reader */
.nf-thread { display: flex; gap: 0.55rem; padding: 0.5rem 0; border-top: 1px solid var(--line); }
.nf-thread:first-child { border-top: none; }
.nf-thread.on { background: rgba(59, 156, 255, 0.07); border-radius: 8px; }
.nf-thread-main { min-width: 0; flex: 1; }
.nf-thread-id { font-size: 0.76rem; color: rgba(255, 255, 255, 0.85); } .nf-thread-id b { color: #fff; }
.nf-thread-reply { margin-left: 0.4rem; font-size: 0.56rem; text-transform: uppercase; letter-spacing: 0.05em; color: #3b9cff; background: rgba(59, 156, 255, 0.14); border-radius: 4px; padding: 0.03rem 0.3rem; }
.nf-thread-text { margin: 0.2rem 0 0; font-size: 0.82rem; line-height: 1.5; color: rgba(255, 255, 255, 0.8); }
.nf-act-ask { color: var(--accent) !important; border-color: color-mix(in srgb, var(--accent) 45%, transparent) !important; }
.nf-act-ask:hover { background: rgba(120, 160, 255, 0.14); }
.nf-story-head { display: flex; align-items: baseline; gap: 0.5rem; flex-wrap: wrap; }
/* Headline is the hero — editorial, not a link in a stream. */
.nf-story-title { font-size: 1.02rem; font-weight: 650; line-height: 1.28; letter-spacing: -0.01em; color: var(--text); text-decoration: none; } .nf-story-title:hover { color: var(--accent); }
.nf-domain { font-size: 0.7rem; color: rgba(255, 255, 255, 0.4); }
.nf-story-meta { display: flex; align-items: center; gap: 0.4rem; flex-wrap: wrap; margin-top: 0.35rem; }
.nf-tag { font-size: 0.66rem; color: var(--text-2); background: transparent; border: 1px solid var(--line-2); border-radius: 4px; padding: 0.05rem 0.4rem; cursor: pointer; } .nf-tag:hover { border-color: var(--accent); color: var(--accent); }
.nf-q { font-size: 0.68rem; font-weight: 700; border-radius: 5px; padding: 0.03rem 0.34rem; } .nf-q.high { color: var(--up); background: rgba(63, 185, 80, 0.14); } .nf-q.medium { color: #e3b341; background: rgba(227, 179, 65, 0.16); } .nf-q.low { color: var(--down); background: rgba(248, 81, 73, 0.16); }
.nf-mem { font-size: 0.58rem; text-transform: uppercase; letter-spacing: 0.06em; border-radius: 4px; padding: 0.03rem 0.3rem; font-weight: 700; }
.nf-mem.hold { color: #e3b341; background: rgba(227, 179, 65, 0.16); } .nf-mem.quarantine { color: var(--down); background: rgba(248, 81, 73, 0.16); } .nf-mem.reject { color: #8b949e; background: rgba(139, 148, 158, 0.16); } .nf-mem.admit { color: var(--up); background: rgba(63, 185, 80, 0.14); }
.nf-story-by { display: flex; align-items: center; gap: 0.7rem; flex-wrap: wrap; margin-top: 0.35rem; font-size: 0.72rem; color: rgba(255, 255, 255, 0.45); }
.nf-src-tag { font-weight: 700; } .nf-time { color: rgba(255, 255, 255, 0.4); }
.nf-auth { color: rgba(255, 255, 255, 0.5); }
.nf-hat { margin-left: 0.3rem; font-size: 0.58rem; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700; border-radius: 4px; padding: 0.03rem 0.3rem; } .nf-hat.mod { color: #f0883e; background: rgba(240, 136, 62, 0.16); } .nf-hat.sme { color: #58a6ff; background: rgba(88, 166, 255, 0.16); } .nf-hat.source { color: var(--up); background: rgba(63, 185, 80, 0.14); }
.nf-link, .nf-flag { border: none; background: transparent; color: rgba(255, 255, 255, 0.5); font-size: 0.72rem; cursor: pointer; padding: 0; } .nf-link:hover { color: #58a6ff; } .nf-flag:hover { color: var(--down); } .nf-flag.done { color: var(--down); }
.nf-reasons { display: flex; align-items: center; gap: 0.35rem; flex-wrap: wrap; margin-top: 0.4rem; }
.nf-reasons-h { font-size: 0.68rem; color: var(--text-3); }
.nf-reasons button { border: 1px solid var(--line-2); background: var(--surface-2); color: rgba(255, 255, 255, 0.75); border-radius: 6px; padding: 0.12rem 0.45rem; font-size: 0.7rem; cursor: pointer; } .nf-reasons button:hover { border-color: var(--down); color: var(--down); }

/* Event Calendar lens */
.nf-list.calendar { padding: 0.35rem 0; }
.nf-day { border-bottom: 1px solid var(--line); } .nf-day:last-child { border-bottom: none; }
.nf-day-h { position: sticky; top: 0; z-index: 1; display: flex; align-items: baseline; gap: 0.5rem; padding: 0.45rem 0.85rem; background: var(--surface); border-bottom: 1px solid var(--line); font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-2); font-weight: 700; }
.nf-day-c { font-size: 0.62rem; color: var(--text-3); background: var(--surface-2); border-radius: 999px; padding: 0.02rem 0.4rem; }
.nf-agenda { width: 100%; display: flex; align-items: baseline; gap: 0.7rem; border: none; border-bottom: 1px solid var(--line); background: transparent; color: inherit; padding: 0.55rem 0.85rem; cursor: pointer; text-align: left; } .nf-agenda:hover { background: var(--surface-2); } .nf-agenda.on { background: rgba(88, 166, 255, 0.1); box-shadow: inset 3px 0 0 #58a6ff; }
.nf-agenda-time { flex: 0 0 4rem; font-size: 0.72rem; color: var(--text-3); font-variant-numeric: tabular-nums; }
.nf-agenda-title { flex: 1; min-width: 0; font-size: 0.86rem; color: rgba(255, 255, 255, 0.85); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.nf-agenda-src { flex: 0 0 auto; font-size: 0.72rem; }

/* Reader */
.nf-reader { min-height: 0; overflow-y: auto; padding: 0.9rem 1.15rem 1.4rem; background: var(--bg); border-left: 1px solid var(--line-2); box-shadow: -14px 0 44px rgba(0,0,0,0.38); }
.nf-reader-meta { display: flex; align-items: center; gap: 0.6rem; font-size: 0.72rem; }
.nf-reader-close { margin-left: auto; display: grid; place-items: center; width: 1.55rem; height: 1.55rem; border-radius: 8px; border: 1px solid var(--line-2); background: transparent; color: var(--text-2); font-size: 0.8rem; cursor: pointer; transition: background 0.12s ease, color 0.12s ease; }
.nf-reader-close:hover { background: rgba(255, 255, 255, 0.08); color: var(--text); }
.nf-reader-title { margin: 0.5rem 0 0.5rem; font-size: 1.35rem; line-height: 1.25; letter-spacing: -0.02em; }
.nf-reader-tags { display: flex; flex-wrap: wrap; gap: 0.35rem; margin-bottom: 0.8rem; }
.nf-reader-body { margin: 0 0 1rem; font-size: 0.95rem; line-height: 1.6; color: rgba(255, 255, 255, 0.82); }
.nf-actions { display: flex; gap: 0.5rem; margin-bottom: 0.4rem; flex-wrap: wrap; }
.nf-act { border: 1px solid var(--line-2); background: transparent; color: rgba(255, 255, 255, 0.8); border-radius: 8px; padding: 0.4rem 0.8rem; font-size: 0.8rem; cursor: pointer; text-decoration: none; } .nf-act:hover { border-color: var(--text-3); } .nf-act.on { color: var(--up); border-color: rgba(63, 185, 80, 0.4); } .nf-act.primary { background: var(--surface-2); border-color: var(--line-2); color: var(--text); } .nf-act.done { color: var(--up); border-color: rgba(63, 185, 80, 0.4); cursor: default; }
.nf-block { border-top: 1px solid var(--line-2); padding: 0.8rem 0; }
.nf-block-h { font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.1em; color: rgba(255, 255, 255, 0.4); margin-bottom: 0.5rem; }
.nf-claims { margin: 0; padding-left: 1.1rem; color: rgba(255, 255, 255, 0.72); font-size: 0.82rem; line-height: 1.6; }
.nf-kv { display: grid; grid-template-columns: 6rem 1fr; gap: 0.5rem; font-size: 0.76rem; padding: 0.15rem 0; } .nf-kv span { color: rgba(255, 255, 255, 0.4); } .nf-kv code { color: rgba(255, 255, 255, 0.75); font-family: ui-monospace, monospace; overflow-wrap: anywhere; } .nf-hashcode { color: rgba(255, 255, 255, 0.5) !important; font-size: 0.68rem; }
.nf-comment { display: flex; gap: 0.55rem; padding: 0.5rem 0; border-top: 1px solid var(--line); }
.nf-c-vote { display: flex; flex-direction: column; align-items: center; }
.nf-c-main { min-width: 0; flex: 1; }
.nf-c-by { font-size: 0.72rem; color: rgba(255, 255, 255, 0.6); font-weight: 600; } .nf-c-score { margin-left: 0.4rem; color: var(--text-3); font-weight: 700; }
.nf-c-body { margin: 0.2rem 0 0; font-size: 0.82rem; line-height: 1.5; color: rgba(255, 255, 255, 0.78); }
.nf-c-reason { margin-top: 0.25rem; font-size: 0.68rem; color: var(--down); }
</style>
