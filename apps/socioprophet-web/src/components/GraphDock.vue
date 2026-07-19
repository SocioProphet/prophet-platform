<template>
  <!-- Global graph dock — the knowledge/person graph as a slide-in panel (mirror
       of the Noetica dock, on the LEFT so both can be open). Context-aware:
       highlights nodes matching what you're looking at. -->
  <Transition name="gdock">
    <aside v-if="open" class="gdock" role="complementary" aria-label="Knowledge graph">
      <header class="gdock-head">
        <span class="gdock-glyph" aria-hidden="true">◈</span>
        <span class="gdock-title">Graph</span>
        <span class="gdock-mode" :class="mode">{{ mode === 'live' ? 'live' : 'fixture' }}</span>
        <RouterLink class="gdock-full" to="/person-graph" @click="$emit('close')">full ↗</RouterLink>
        <button class="gdock-x" type="button" aria-label="Close graph" @click="$emit('close')">✕</button>
      </header>

      <div v-if="ctx.surface" class="gdock-ctx">
        <span class="gdock-ctx-eye">Context</span>
        <span class="gdock-ctx-surface">{{ ctx.surface }}</span>
        <span v-if="ctx.entityLabel" class="gdock-ctx-sep">·</span>
        <span v-if="ctx.entityLabel" class="gdock-ctx-entity">{{ ctx.entityLabel }}</span>
      </div>

      <div class="gdock-body">
        <p v-if="loading" class="gdock-empty">Loading graph…</p>
        <svg v-else class="gdock-svg" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Knowledge graph">
          <line v-for="(e, i) in graphEdges" :key="'e' + i" :x1="e.a!.x" :y1="e.a!.y" :x2="e.b!.x" :y2="e.b!.y" class="gdock-edge" :class="{ hot: e.source === activeId || e.target === activeId }" />
          <g v-for="n in graphNodes" :key="n.id" class="gdock-node" :class="{ self: n.isSelf, ctx: ctxMatch(n.label) }" @click="activeId = activeId === n.id ? '' : n.id">
            <title>{{ n.label }} · {{ n.kind }}</title>
            <circle :cx="n.x" :cy="n.y" :r="n.isSelf ? 4.2 : n.id === activeId || ctxMatch(n.label) ? 3.4 : 2.6" :fill="kindColor(n.kind)" :stroke="n.isSelf || ctxMatch(n.label) ? '#fff' : 'rgba(0,0,0,0.4)'" :stroke-width="n.isSelf || ctxMatch(n.label) ? 0.8 : 0.4" />
            <text v-if="n.isSelf || n.id === activeId || ctxMatch(n.label)" :x="n.x" :y="n.y - 4.5" text-anchor="middle" class="gdock-label">{{ shortLabel(n.label) }}</text>
          </g>
        </svg>
        <p v-if="!loading && graphNodes.length === 0" class="gdock-empty">No graph data.</p>
      </div>

      <footer class="gdock-foot">
        <span>{{ graphNodes.length }} nodes · {{ graphEdges.length }} edges</span>
        <button v-if="activeNode" class="gdock-ask" type="button" @click="askAboutNode">◇ Ask about {{ shortLabel(activeNode.label) }}</button>
      </footer>
    </aside>
  </Transition>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { fetchPersonGraphSnapshotWithFallback, type PersonGraphSnapshot } from '../api/personGraphApi';
import { useCockpit } from '../stores/cockpit';

const props = defineProps<{ open: boolean }>();
defineEmits<{ (e: 'close'): void }>();
const cockpit = useCockpit();
const ctx = computed(() => cockpit.context);

const snapshot = ref<PersonGraphSnapshot | null>(null);
const mode = ref<'live' | 'fixture'>('fixture');
const loading = ref(false);
const loaded = ref(false);
const activeId = ref('');

async function load() {
  loading.value = true;
  const res = await fetchPersonGraphSnapshotWithFallback();
  snapshot.value = res.snapshot;
  mode.value = res.mode;
  loading.value = false;
  loaded.value = true;
}
watch(() => props.open, (o) => { if (o && !loaded.value) load(); }, { immediate: true });

// Radial layout: self at centre, direct neighbours in an inner ring, the rest outer.
const graphNodes = computed(() => {
  const snap = snapshot.value; if (!snap) return [];
  const selfId = snap.self.id;
  const isNeighbor = (id: string) => snap.edges.some((e) => (e.source === selfId && e.target === id) || (e.target === selfId && e.source === id));
  const neighbors = snap.nodes.filter((n) => n.id !== selfId && isNeighbor(n.id));
  const others = snap.nodes.filter((n) => n.id !== selfId && !isNeighbor(n.id));
  const pos = new Map<string, { x: number; y: number }>();
  pos.set(selfId, { x: 50, y: 50 });
  const ring = (arr: typeof neighbors, r: number) => arr.forEach((n, i) => { const a = (i / arr.length) * 2 * Math.PI - Math.PI / 2; pos.set(n.id, { x: 50 + Math.cos(a) * r, y: 50 + Math.sin(a) * r }); });
  ring(neighbors, 26); ring(others, 44);
  return snap.nodes.map((n) => ({ ...n, x: pos.get(n.id)?.x ?? 50, y: pos.get(n.id)?.y ?? 50, isSelf: n.id === selfId }));
});
const graphEdges = computed(() => {
  const byId = new Map(graphNodes.value.map((n) => [n.id, n]));
  return (snapshot.value?.edges ?? []).map((e) => ({ ...e, a: byId.get(e.source), b: byId.get(e.target) })).filter((e) => e.a && e.b);
});
const activeNode = computed(() => graphNodes.value.find((n) => n.id === activeId.value));

const KIND_COLORS: Record<string, string> = { Self: '#2f6bff', Person: '#4bbf73', Organization: '#e3b341', Event: '#c58af9', Document: '#38bdf8', Code: '#f0656a' };
const kindColor = (k: string) => KIND_COLORS[k] ?? '#8b949e';
const shortLabel = (s: string) => (s.length > 18 ? `${s.slice(0, 17)}…` : s);
function ctxMatch(label: string): boolean {
  const e = (ctx.value.entityLabel ?? '').toLowerCase();
  if (!e) return false;
  const l = label.toLowerCase();
  return l.length > 2 && (e.includes(l) || l.includes(e.split('·')[0]!.trim()));
}
function askAboutNode() {
  const n = activeNode.value; if (!n) return;
  cockpit.askAbout(`In the knowledge graph, what is "${n.label}" (${n.kind}) connected to, and why do those relationships matter?`);
}
</script>

<style scoped>
.gdock {
  position: fixed; top: 0; left: 0; bottom: 0; z-index: 1240;
  width: min(26rem, 92vw); display: flex; flex-direction: column;
  background: #16181d; border-right: 1px solid rgba(255, 255, 255, 0.12); box-shadow: 14px 0 48px rgba(0, 0, 0, 0.55);
  color: #ece9e3;
}
.gdock-head { display: flex; align-items: center; gap: 0.5rem; height: 40px; padding: 0 0.9rem; border-bottom: 1px solid rgba(255, 255, 255, 0.08); }
.gdock-glyph { color: #2f6bff; font-size: 1rem; }
.gdock-title { font-size: 13px; font-weight: 600; }
.gdock-mode { font-size: 0.58rem; text-transform: uppercase; letter-spacing: 0.05em; border-radius: 4px; padding: 0.05rem 0.35rem; }
.gdock-mode.live { color: #7ee2a8; background: rgba(75, 191, 115, 0.14); } .gdock-mode.fixture { color: #f0c987; background: rgba(227, 179, 65, 0.14); }
.gdock-full { margin-left: auto; font-size: 0.72rem; color: #93b4ff; text-decoration: none; } .gdock-full:hover { text-decoration: underline; }
.gdock-x { border: none; background: transparent; color: #a8a29e; cursor: pointer; font-size: 0.8rem; } .gdock-x:hover { color: #fff; }
.gdock-ctx { display: flex; align-items: center; gap: 0.4rem; flex-wrap: wrap; padding: 0.4rem 0.85rem; font-size: 0.72rem; background: rgba(47, 107, 255, 0.1); border-bottom: 1px solid rgba(47, 107, 255, 0.22); color: #a8a29e; }
.gdock-ctx-eye { font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.06em; color: #93b4ff; }
.gdock-ctx-surface, .gdock-ctx-entity { color: #ece9e3; font-weight: 600; } .gdock-ctx-sep { color: #78716c; }
.gdock-body { flex: 1; min-height: 0; display: grid; place-items: center; padding: 0.75rem; }
.gdock-svg { width: 100%; height: 100%; }
.gdock-edge { stroke: rgba(255, 255, 255, 0.14); stroke-width: 0.4; } .gdock-edge.hot { stroke: rgba(47, 107, 255, 0.7); stroke-width: 0.7; }
.gdock-node { cursor: pointer; }
.gdock-label { font-size: 3px; fill: #ece9e3; pointer-events: none; }
.gdock-empty { color: #78716c; font-size: 0.85rem; }
.gdock-foot { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; padding: 0.5rem 0.85rem; border-top: 1px solid rgba(255, 255, 255, 0.08); font-size: 0.7rem; color: #78716c; }
.gdock-ask { border: 1px solid rgba(120, 160, 255, 0.4); background: rgba(120, 160, 255, 0.08); color: #93b4ff; border-radius: 7px; padding: 0.2rem 0.55rem; font-size: 0.7rem; cursor: pointer; } .gdock-ask:hover { background: rgba(120, 160, 255, 0.16); color: #fff; }
.gdock-enter-active, .gdock-leave-active { transition: transform 0.24s ease; }
.gdock-enter-from, .gdock-leave-to { transform: translateX(-100%); }
</style>
