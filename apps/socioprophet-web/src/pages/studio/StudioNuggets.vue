<script setup lang="ts">
// W11.5 — the nugget feed. JustIN delivery (DARPA TA-D) against the cockpit's pull-only reality.
//
// The three JustIN axes, and exactly how far each one actually gets today:
//   just-in-time   PARTIAL. The graph read is real, but it is a POLL. There is no nugget
//                  stream to subscribe to, so "push" is not claimed anywhere on this surface.
//   just-enough    YES. W11.6 depth drives how much of each nugget renders.
//   just-for-me    CLIENT-SIDE ONLY. The filters below are a view, not access control —
//                  there is no grant plumbing to scope this feed. Said on screen, not hidden.
//
// Every nugget shows its warrant through the existing <Warrant> primitive, and a direct-quote
// is built to read differently from a model-generated one at a glance — stripe, badge, and a
// standing banner, none of which depth can switch off.
import { computed, onMounted, ref } from 'vue';
import NuggetCard from '../../components/nuggets/NuggetCard.vue';
import DepthControl from '../../components/depth/DepthControl.vue';
import { fetchNuggets, type NuggetFeedResult } from '../../services/nuggetApi';
import { refLabel, type FeedItem, type NuggetWarrantType } from '../../features/nuggets/types';
import { isSourceWarranted } from '../../features/warrant/types';
import { useSettings } from '../../stores/settings';
import type { Expertise } from '../../features/depth/expertise';

const settings = useSettings();
const level = computed<Expertise>(() => settings.expertise as Expertise);

const feed = ref<NuggetFeedResult | null>(null);
const busy = ref(false);
const lastPolled = ref<string | null>(null);

const WARRANT_TYPES: NuggetWarrantType[] = ['direct-quote', 'computed', 'inferred', 'model-generated'];
/** Subscription: which warrant classes this reader wants. All on by default — hiding by
 *  default would be a filter that quietly suppresses the weakest evidence. */
const subscribed = ref<Set<NuggetWarrantType>>(new Set(WARRANT_TYPES));
const query = ref('');

async function load() {
  busy.value = true;
  try {
    feed.value = await fetchNuggets();
    lastPolled.value = new Date().toISOString().slice(11, 19);
  } finally {
    busy.value = false;
  }
}
onMounted(load);

function toggle(t: NuggetWarrantType) {
  const next = new Set(subscribed.value);
  if (next.has(t)) next.delete(t);
  else next.add(t);
  subscribed.value = next;
}

const ok = computed<FeedItem[]>(() => (feed.value?.items ?? []).filter((i) => i.ok));
const unreadable = computed(() => (feed.value?.items ?? []).filter((i) => !i.ok));

const visible = computed(() =>
  ok.value.flatMap((i) => {
    if (!i.ok) return [];
    if (!subscribed.value.has(i.nugget.warrant.type)) return [];
    const q = query.value.trim().toLowerCase();
    if (q && !i.nugget.text.toLowerCase().includes(q) && !i.nugget.sourceRef.docRef.toLowerCase().includes(q)) {
      return [];
    }
    return [i.nugget];
  }),
);

/** How many readable nuggets the subscription is currently hiding. Always disclosed. */
const filteredOut = computed(() => ok.value.length - visible.value.length);

const counts = computed(() => {
  const c: Record<string, number> = {};
  for (const i of ok.value) if (i.ok) c[i.nugget.warrant.type] = (c[i.nugget.warrant.type] ?? 0) + 1;
  return c;
});

/**
 * The split that actually matters, over what is CURRENTLY VISIBLE — so the headline number
 * tracks the filters instead of quietly describing a larger set the reader cannot see.
 */
const split = computed(() => {
  const source = visible.value.filter((n) => isSourceWarranted(n.warrant.type)).length;
  return { source, model: visible.value.length - source };
});
</script>

<template>
  <div class="nf">
    <!-- Provenance of the surface itself, first, above everything it renders. -->
    <div v-if="feed" class="nf-mode" :class="`m-${feed.mode}`">
      <span class="nf-mode-tag">{{ feed.mode }}</span>
      <span v-if="feed.mode === 'live'">
        Read from the graph:
        <code class="mono">GET /api/graph/query?label=KnowledgeNugget</code> on hellgraph-service,
        where <code class="mono">apps/nugget-extractor</code> writes each nugget with its full
        canonical JSON on the node.
      </span>
      <span v-else>
        These nuggets are a FIXTURE, not live data. The live read failed and fixtures were shown
        rather than an empty page — nothing below came off a graph.
        <b class="nf-why">{{ feed.error }}</b>
      </span>
    </div>

    <div class="card">
      <div class="nf-head">
        <div>
          <h3>Nugget feed</h3>
          <p class="desc">
            The L2 content grain — warrant-typed fragments lifted from governed sources. Each one
            states where it came from and how it is warranted.
          </p>
        </div>
        <button class="btn ghost" type="button" :disabled="busy" @click="load">
          {{ busy ? 'Polling…' : 'Poll' }}
        </button>
      </div>

      <!-- Honest about the delivery model. -->
      <p class="nf-pull">
        <b>Pull, not push.</b> hellgraph-service exposes no nugget stream, so this is a manual
        poll<span v-if="lastPolled"> — last read {{ lastPolled }}</span
        >. Just-in-time delivery is not wired; calling this a live feed would overstate it.
      </p>

      <div class="nf-controls">
        <div class="nf-subs">
          <span class="nf-l">subscription</span>
          <button
            v-for="t in WARRANT_TYPES"
            :key="t"
            class="nf-sub"
            type="button"
            :class="[{ on: subscribed.has(t) }, `w-${t}`]"
            :aria-pressed="subscribed.has(t)"
            @click="toggle(t)"
          >
            {{ t }}<span class="nf-n tnum">{{ counts[t] ?? 0 }}</span>
          </button>
        </div>
        <input v-model="query" type="text" class="nf-q" aria-label="Filter nuggets" placeholder="filter text or source…" />
      </div>

      <DepthControl />

      <!-- Not access control. Stated where the filters are, so it cannot be mistaken. -->
      <p class="nf-grant">
        <b>Scope:</b> these filters are a client-side VIEW over everything the graph returned —
        not grant scoping and not access control. Per-reader grant scoping (the Memory
        Distribution Grant plane) is not reachable from this app: no grant service base is
        configured, nuggets carry no grant claim, and hellgraph-service does not filter by one.
        Wiring it is a follow-on.
      </p>
    </div>

    <!-- The split, over what is on screen. Model-generated is never folded into a total. -->
    <p v-if="visible.length" class="nf-split">
      <span class="nf-split-src"
        ><b class="tnum">{{ split.source }}</b> source-warranted</span
      >
      <span class="nf-split-mod"
        ><b class="tnum">{{ split.model }}</b> model-generated</span
      >
      <span v-if="filteredOut > 0" class="nf-hidden">
        · {{ filteredOut }} readable nugget{{ filteredOut === 1 ? '' : 's' }} hidden by your
        subscription or filter
      </span>
    </p>
    <p v-else-if="filteredOut > 0" class="nf-hidden">
      All {{ filteredOut }} readable nugget{{ filteredOut === 1 ? '' : 's' }} hidden by your
      subscription or filter.
    </p>

    <!-- Reachable and genuinely empty. Fixtures are NOT substituted here. -->
    <div v-if="feed && feed.mode === 'live' && feed.emptyLive" class="card nf-empty">
      <h3>No nuggets on this graph</h3>
      <p class="desc">
        The graph answered and holds no <code class="mono">KnowledgeNugget</code> nodes. That is a
        real, empty result — not a loading state, and not a reason to show you fixtures. Run
        <code class="mono">apps/nugget-extractor</code> against a document to populate it.
      </p>
    </div>

    <div class="nf-list">
      <NuggetCard v-for="n in visible" :key="n.id" :nugget="n" :level="level" />
    </div>

    <!-- Unreadable payloads: kept and counted, never dropped. -->
    <div v-if="unreadable.length" class="card nf-bad">
      <h3>{{ unreadable.length }} unreadable payload{{ unreadable.length === 1 ? '' : 's' }}</h3>
      <p class="desc">
        These did not parse against KnowledgeNugget 0.1.0, so they are not rendered as nuggets.
        Unreadable is <b>unknown</b>, not invalid — nothing here was checked and found wanting;
        it could not be read at all. They are listed because a silently dropped item would make
        this feed look cleaner than the data is.
      </p>
      <ul class="nf-badlist">
        <li v-for="(u, i) in unreadable" :key="i">
          <code class="mono">{{ u.nodeId ? refLabel(u.nodeId) : '(no node id)' }}</code>
          <span class="nf-badwhy">{{ u.ok ? '' : u.reason }}</span>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.nf {
  display: grid;
  gap: 1rem;
}
.nf-mode {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  flex-wrap: wrap;
  padding: 0.5rem 0.7rem;
  border-radius: var(--r-2);
  font-size: 0.72rem;
  line-height: 1.5;
  color: var(--ink-2);
  background: var(--warn-wash);
  border: 1px solid color-mix(in srgb, var(--warn) 34%, transparent);
}
.nf-mode.m-live {
  background: var(--ok-wash);
  border-color: color-mix(in srgb, var(--ok) 34%, transparent);
}
.nf-mode-tag {
  color: var(--warn);
  text-transform: uppercase;
  letter-spacing: 0.07em;
  font-size: 0.62rem;
  font-weight: 700;
  flex: 0 0 auto;
}
.m-live .nf-mode-tag {
  color: var(--ok);
}
.nf-why {
  display: block;
  margin-top: 0.2rem;
  color: var(--warn);
  font-family: var(--mono);
  font-size: 0.66rem;
  font-weight: 400;
  overflow-wrap: anywhere;
}
.nf-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}
.nf-head h3 {
  margin: 0 0 0.3rem;
}
.nf-pull,
.nf-grant {
  margin: 0 0 0.7rem;
  padding: 0.4rem 0.55rem;
  border-radius: var(--r-1);
  background: var(--sunken);
  border: 1px solid var(--hairline);
  color: var(--faint);
  font-size: 0.66rem;
  line-height: 1.5;
}
.nf-grant {
  margin: 0.7rem 0 0;
}
.nf-pull b,
.nf-grant b {
  color: var(--ink-2);
}
.nf-controls {
  display: flex;
  gap: 0.7rem;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 0.7rem;
}
.nf-subs {
  display: flex;
  gap: 0.35rem;
  align-items: center;
  flex-wrap: wrap;
}
.nf-l {
  color: var(--faint);
  font-size: 0.6rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.nf-sub {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  background: transparent;
  color: var(--muted);
  border: 1px solid var(--border-2);
  border-radius: var(--pill);
  padding: 1px 9px;
  font-size: 0.66rem;
  cursor: pointer;
  font-family: inherit;
  opacity: 0.55;
}
.nf-sub.on {
  opacity: 1;
  color: var(--ink);
  border-color: var(--hairline-strong);
  background: var(--surface);
}
.nf-sub:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}
/* Each subscription pill wears its own rung of the ramp. */
.nf-sub.w-direct-quote.on {
  color: var(--epi-observed);
  border-color: color-mix(in srgb, var(--epi-observed) 50%, transparent);
}
.nf-sub.w-computed.on,
.nf-sub.w-inferred.on {
  color: var(--epi-derived);
  border-color: color-mix(in srgb, var(--epi-derived) 50%, transparent);
}
.nf-sub.w-model-generated.on {
  color: var(--epi-hypothesis);
  border-color: color-mix(in srgb, var(--epi-hypothesis) 50%, transparent);
}
.nf-n {
  color: var(--faint);
  font-size: 0.6rem;
}
.nf-q {
  flex: 1 1 14rem;
  max-width: 22rem;
}
.nf-hidden {
  margin: 0;
  color: var(--faint);
  font-size: 0.66rem;
}
.nf-split {
  display: flex;
  gap: 0.6rem;
  flex-wrap: wrap;
  align-items: baseline;
  margin: 0;
  font-size: 0.66rem;
  color: var(--muted);
}
.nf-split-src b {
  color: var(--epi-observed);
}
.nf-split-mod b {
  color: var(--epi-hypothesis);
}
.nf-list {
  display: grid;
  gap: 0.7rem;
}
.nf-empty h3,
.nf-bad h3 {
  margin: 0 0 0.3rem;
}
.nf-bad {
  border-color: color-mix(in srgb, var(--epi-hypothesis) 40%, transparent);
}
.nf-badlist {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.3rem;
}
.nf-badlist li {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  align-items: baseline;
  font-size: 0.66rem;
  padding: 0.3rem 0.4rem;
  border-radius: var(--r-1);
  background: var(--sunken);
  border-left: 3px solid var(--epi-unknown);
}
.nf-badwhy {
  color: var(--epi-hypothesis);
}
.mono {
  font-family: var(--mono);
}
.tnum {
  font-variant-numeric: tabular-nums;
}
</style>
