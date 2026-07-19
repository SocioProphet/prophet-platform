<template>
  <section class="uv" aria-label="Universe viewer">
    <SurfaceHeader title="Universe Viewer" eyebrow="Epistemology · discovering what's known">
      <template #badge><span class="uv-stat">{{ claims.claims.length }} claims</span></template>
      <template #actions>
        <div class="uv-modes">
          <button v-for="m in MODES" :key="m.id" class="uv-mode" :class="{ on: mode === m.id }" type="button" @click="mode = m.id">{{ m.label }}</button>
        </div>
        <button class="uv-ask" type="button" @click="askNoetica">◇ Ask Noetica</button>
      </template>
    </SurfaceHeader>

    <EmptyState v-if="claims.claims.length === 0" icon="◈" title="No knowledge yet" hint="Open News or a Law docket — extracted claims accumulate here across link, temporal and statistical views." />

    <!-- LINK — the claim graph -->
    <div v-else-if="mode === 'link'" class="uv-body">
      <svg class="uv-graph" :viewBox="`0 0 ${GW} ${GH}`" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Claim graph">
        <line v-for="(e, i) in graph.edges" :key="'e' + i" :x1="e.a.x" :y1="e.a.y" :x2="e.b.x" :y2="e.b.y" class="uv-edge" />
        <g v-for="n in graph.nodes" :key="n.id" @click="activeNode = activeNode === n.id ? '' : n.id">
          <title>{{ n.id }} · degree {{ n.deg }}</title>
          <circle :cx="n.x" :cy="n.y" :r="3 + Math.min(4, n.deg)" :fill="nodeColor(n.deg)" :stroke="n.id === activeNode ? '#fff' : 'rgba(0,0,0,0.4)'" :stroke-width="n.id === activeNode ? 1 : 0.4" class="uv-node" />
          <text v-if="n.deg > 1 || n.id === activeNode" :x="n.x" :y="n.y - 6" text-anchor="middle" class="uv-glabel">{{ short(n.id) }}</text>
        </g>
      </svg>
      <p class="uv-cap">Subjects &amp; objects as nodes, claims as edges — the knowledge graph the corpus induced.</p>
    </div>

    <!-- TEMPORAL — claims over time -->
    <div v-else-if="mode === 'temporal'" class="uv-body uv-scroll">
      <div v-for="g in byTime" :key="g.day" class="uv-tl-day">
        <div class="uv-tl-date">{{ g.day }}</div>
        <div class="uv-tl-items">
          <div v-for="c in g.items" :key="c.id" class="uv-tl-item">
            <span class="uv-tl-dot" :style="{ background: statusColor(c.status) }" />
            <span class="uv-tl-spo"><b>{{ c.subject }}</b> <i>{{ c.predicate }}</i> {{ c.object }}</span>
            <span class="uv-tl-src">{{ c.provenance.source }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- STATISTICAL — distributions -->
    <div v-else class="uv-body uv-scroll">
      <div class="uv-stats-grid">
        <div class="uv-stat-card">
          <div class="uv-stat-h">Claims by relation</div>
          <div v-for="r in ontology.relations" :key="r.predicate" class="uv-bar-row">
            <span class="uv-bar-l">{{ r.predicate }}</span>
            <span class="uv-bar"><span class="uv-bar-f blue" :style="{ width: pct(r.count, maxRel) + '%' }" /></span>
            <span class="uv-bar-n">{{ r.count }}</span>
          </div>
        </div>
        <div class="uv-stat-card">
          <div class="uv-stat-h">Claims by status</div>
          <div v-for="s in statusDist" :key="s.status" class="uv-bar-row">
            <span class="uv-bar-l">{{ s.status }}</span>
            <span class="uv-bar"><span class="uv-bar-f" :style="{ width: pct(s.n, claims.claims.length) + '%', background: statusColor(s.status) }" /></span>
            <span class="uv-bar-n">{{ s.n }}</span>
          </div>
        </div>
        <div class="uv-stat-card">
          <div class="uv-stat-h">Entities by class</div>
          <div v-for="c in ontology.classes.filter((x) => x.instances.length)" :key="c.class" class="uv-bar-row">
            <span class="uv-bar-l">{{ c.label }}</span>
            <span class="uv-bar"><span class="uv-bar-f" :style="{ width: pct(c.instances.length, maxClass) + '%', background: c.color }" /></span>
            <span class="uv-bar-n">{{ c.instances.length }}</span>
          </div>
        </div>
        <div class="uv-stat-card">
          <div class="uv-stat-h">Top topics</div>
          <div v-for="t in ontology.topics.slice(0, 8)" :key="t.topic" class="uv-bar-row">
            <span class="uv-bar-l">{{ t.topic }}</span>
            <span class="uv-bar"><span class="uv-bar-f green" :style="{ width: pct(t.count, maxTopic) + '%' }" /></span>
            <span class="uv-bar-n">{{ t.count }}</span>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue';
import SurfaceHeader from '../components/SurfaceHeader.vue';
import EmptyState from '../components/EmptyState.vue';
import { useClaims } from '../stores/claims';
import { useOntology } from '../stores/ontology';
import { useCockpit } from '../stores/cockpit';
import { reify } from '../features/claims/reify';
import { STATUS_META, type ClaimStatus } from '../features/claims/types';
import { newsItems } from '../data/newsFeedFixture';
import { dockets } from '../data/lawFixture';

const claims = useClaims();
const ontology = useOntology();
const cockpit = useCockpit();
const MODES = [{ id: 'link', label: 'Link' }, { id: 'temporal', label: 'Temporal' }, { id: 'stats', label: 'Statistical' }] as const;
const mode = ref<'link' | 'temporal' | 'stats'>('link');
const activeNode = ref('');
const GW = 340; const GH = 240;

// Seed the universe from the corpus so it's populated for review.
onMounted(() => {
  if (claims.claims.length === 0) {
    for (const it of newsItems) claims.assert(reify(`${it.title}. ${it.summary}`, 'news'));
    for (const d of dockets) claims.assert(reify(`${d.title}. ${d.summary} ${d.impact}`, d.cite));
  }
  cockpit.setContext({ surface: 'Universe Viewer', entityLabel: `${claims.claims.length} claims`, detail: mode.value, route: '/universe' });
});

// LINK — degree-radial graph of subjects/objects.
const graph = computed(() => {
  const deg = new Map<string, number>();
  for (const c of claims.claims) { deg.set(c.subject, (deg.get(c.subject) ?? 0) + 1); deg.set(c.object, (deg.get(c.object) ?? 0) + 1); }
  const top = [...deg.entries()].sort((a, b) => b[1] - a[1]).slice(0, 28);
  const ids = new Set(top.map(([id]) => id));
  const pos = new Map<string, { x: number; y: number; deg: number }>();
  top.forEach(([id, d], i) => {
    if (i === 0) { pos.set(id, { x: GW / 2, y: GH / 2, deg: d }); return; }
    const ring = i <= 10 ? 1 : 2; const r = ring === 1 ? 70 : 108;
    const idx = ring === 1 ? i - 1 : i - 11; const count = ring === 1 ? Math.min(10, top.length - 1) : top.length - 11;
    const a = (idx / Math.max(1, count)) * 2 * Math.PI - Math.PI / 2;
    pos.set(id, { x: GW / 2 + Math.cos(a) * r, y: GH / 2 + Math.sin(a) * r, deg: d });
  });
  const nodes = top.map(([id]) => ({ id, ...pos.get(id)! }));
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const edges = claims.claims.filter((c) => ids.has(c.subject) && ids.has(c.object)).map((c) => ({ a: byId.get(c.subject)!, b: byId.get(c.object)! }));
  return { nodes, edges };
});
const nodeColor = (d: number) => (d >= 4 ? '#2f6bff' : d >= 2 ? '#58a6ff' : '#8b949e');
const short = (s: string) => (s.length > 16 ? `${s.slice(0, 15)}…` : s);

// TEMPORAL
const byTime = computed(() => {
  const groups: Array<{ day: string; items: typeof claims.claims }> = [];
  for (const c of [...claims.claims].sort((a, b) => b.provenance.timeObserved.localeCompare(a.provenance.timeObserved))) {
    const day = new Date(c.provenance.timeObserved).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
    let g = groups.find((x) => x.day === day); if (!g) { g = { day, items: [] }; groups.push(g); }
    g.items.push(c);
  }
  return groups.slice(0, 12);
});

// STATISTICAL
const statusDist = computed(() => (['asserted', 'attested', 'disputed', 'revised'] as ClaimStatus[]).map((status) => ({ status, n: claims.claims.filter((c) => c.status === status).length })).filter((s) => s.n));
const maxRel = computed(() => Math.max(1, ...ontology.relations.map((r) => r.count)));
const maxClass = computed(() => Math.max(1, ...ontology.classes.map((c) => c.instances.length)));
const maxTopic = computed(() => Math.max(1, ...ontology.topics.map((t) => t.count)));
const pct = (n: number, max: number) => Math.max(4, (n / max) * 100);
const statusColor = (s: ClaimStatus) => STATUS_META[s].color;
function askNoetica() {
  cockpit.askAbout(`Explore the knowledge universe: ${claims.claims.length} reified claims. What clusters, contradictions, or emerging relations stand out across the link / temporal / statistical views?`);
}
</script>

<style scoped>
.uv { height: 100%; min-height: 0; display: flex; flex-direction: column; gap: 0.9rem; padding: 1rem 1.25rem 1.25rem; background: var(--bg); color: var(--text); }
.uv-stat { font-size: 0.66rem; color: var(--text-3); }
.uv-modes { display: inline-flex; border: 1px solid var(--line-2); border-radius: 8px; overflow: hidden; }
.uv-mode { border: none; background: transparent; color: var(--text-2); padding: 0.3rem 0.7rem; font-size: 0.76rem; cursor: pointer; } .uv-mode.on { background: rgba(47, 107, 255, 0.18); color: #93b4ff; }
.uv-ask { border: 1px solid rgba(120, 160, 255, 0.45); background: rgba(120, 160, 255, 0.08); color: #93b4ff; border-radius: 8px; padding: 0.35rem 0.7rem; font-size: 0.76rem; cursor: pointer; } .uv-ask:hover { background: rgba(120, 160, 255, 0.16); color: #fff; }
.uv-body { flex: 1; min-height: 0; border: 1px solid var(--line-2); border-radius: 12px; background: var(--surface); padding: 0.8rem; display: flex; flex-direction: column; }
.uv-scroll { overflow-y: auto; }
.uv-graph { flex: 1; width: 100%; min-height: 0; }
.uv-edge { stroke: rgba(255, 255, 255, 0.12); stroke-width: 0.5; }
.uv-node { cursor: pointer; } .uv-glabel { font-size: 5.5px; fill: var(--text-2); pointer-events: none; }
.uv-cap { margin: 0.3rem 0 0; font-size: 0.72rem; color: var(--text-3); text-align: center; }
.uv-tl-day { display: grid; grid-template-columns: 8rem 1fr; gap: 0.6rem; padding: 0.4rem 0; border-bottom: 1px solid var(--line); }
.uv-tl-date { font-size: 0.7rem; color: var(--text-3); font-variant-numeric: tabular-nums; }
.uv-tl-items { display: flex; flex-direction: column; gap: 0.3rem; }
.uv-tl-item { display: flex; align-items: baseline; gap: 0.5rem; font-size: 0.78rem; }
.uv-tl-dot { width: 7px; height: 7px; border-radius: 50%; flex: 0 0 auto; }
.uv-tl-spo { flex: 1; color: var(--text-2); } .uv-tl-spo b { color: #fff; } .uv-tl-spo i { color: #93b4ff; }
.uv-tl-src { font-size: 0.66rem; color: var(--text-3); }
.uv-stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr)); gap: 0.9rem; }
.uv-stat-card { border: 1px solid var(--line-2); border-radius: 10px; padding: 0.7rem 0.8rem; background: var(--surface-2); }
.uv-stat-h { font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.07em; color: var(--text-3); margin-bottom: 0.6rem; }
.uv-bar-row { display: grid; grid-template-columns: 7rem 1fr 2rem; align-items: center; gap: 0.5rem; margin-bottom: 0.3rem; font-size: 0.74rem; }
.uv-bar-l { color: var(--text-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.uv-bar { height: 8px; border-radius: 999px; background: rgba(255, 255, 255, 0.06); overflow: hidden; }
.uv-bar-f { display: block; height: 100%; background: #58a6ff; } .uv-bar-f.blue { background: linear-gradient(90deg, #1f6feb, #58a6ff); } .uv-bar-f.green { background: #4bbf73; }
.uv-bar-n { text-align: right; color: var(--text-3); font-variant-numeric: tabular-nums; }
</style>
