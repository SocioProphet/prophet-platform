<template>
  <section class="st" aria-label="Situations">
    <SurfaceHeader title="Situations" eyebrow="Hypergraph · the n-ary moat">
      <template #badge><span class="st-pill">{{ situations.length }} situations</span></template>
      <template #actions>
        <button class="st-ask" type="button" @click="askNoetica">◇ Ask Noetica</button>
      </template>
    </SurfaceHeader>

    <p class="st-lede">
      A <b>situation</b> is one <em>n-ary hyperedge</em> that binds entities of different kinds — a place, a rule,
      people, an event, an instrument, a claim — into a single joint context with provenance.
      <InfoLabel label="Why it's a moat" info="A binary link graph (Palantir-style) can only store pairwise edges, so it fragments a situation into N disconnected links and loses the fact that they're one thing. The n-ary hyperedge keeps the joint context — that's what no single-silo competitor can represent." />
    </p>

    <article v-for="s in situations" :key="s.id" class="st-card">
      <div class="st-card-h">
        <h2>{{ s.label }}</h2>
        <span class="st-conf" :title="`extraction confidence`">◆ {{ Math.round(s.provenance.confidence * 100) }}%</span>
      </div>
      <p class="st-sum">{{ s.summary }}</p>

      <div class="st-body">
        <!-- n-ary hyperedge star -->
        <svg class="st-graph" :viewBox="`0 0 ${GW} ${GH}`" role="img" :aria-label="`${s.label} hyperedge`">
          <line v-for="(m, i) in layout(s)" :key="'e' + i" :x1="GW / 2" :y1="GH / 2" :x2="m.x" :y2="m.y" class="st-spoke" />
          <g v-for="(m, i) in layout(s)" :key="'n' + i" class="st-mnode" :class="{ link: m.ref }" @click="go(m.ref)">
            <circle :cx="m.x" :cy="m.y" r="17" :fill="MEMBER_META[m.type].color" />
            <text :x="m.x" :y="m.y + 4" text-anchor="middle" class="st-micon">{{ MEMBER_META[m.type].icon }}</text>
            <text :x="m.x" :y="m.y - 24" text-anchor="middle" class="st-mrole">{{ m.role }}</text>
            <text :x="m.x" :y="m.y + 32" text-anchor="middle" class="st-mlabel">{{ short(m.label) }}</text>
          </g>
          <g>
            <circle :cx="GW / 2" :cy="GH / 2" r="26" class="st-center" />
            <text :x="GW / 2" :y="GH / 2 + 4" text-anchor="middle" class="st-center-t">⬡</text>
          </g>
        </svg>

        <div class="st-side">
          <div class="st-members">
            <button v-for="(m, i) in s.members" :key="i" class="st-member" :class="{ link: m.ref }" :style="{ '--c': MEMBER_META[m.type].color }" @click="go(m.ref)">
              <span class="st-mtype">{{ MEMBER_META[m.type].label }}</span>
              <span class="st-mname">{{ m.label }}</span>
              <span class="st-mrole2">{{ m.role }}</span>
            </button>
          </div>
          <div class="st-nary">
            <span class="st-nary-a">1 n-ary hyperedge</span>
            <span class="st-nary-vs">vs</span>
            <span class="st-nary-b">{{ binaryEdgeCount(s.members.length) }} binary links</span>
            <span class="st-nary-note">— and the binary version still can't say “these are one situation.”</span>
          </div>
          <div class="st-prov">
            <span class="st-prov-k">Provenance</span>
            <span>{{ s.provenance.source }}</span>
            <span class="st-prov-m">{{ s.provenance.method }}</span>
          </div>
        </div>
      </div>
    </article>
  </section>
</template>

<script setup lang="ts">
import { onMounted } from 'vue';
import { useRouter } from 'vue-router';
import SurfaceHeader from '../components/SurfaceHeader.vue';
import InfoLabel from '../components/InfoLabel.vue';
import { SITUATIONS, MEMBER_META, binaryEdgeCount, type Situation } from '../features/situations/situations';
import { useCockpit } from '../stores/cockpit';

const router = useRouter();
const cockpit = useCockpit();
const situations = SITUATIONS;
const GW = 320;
const GH = 300;

function layout(s: Situation) {
  const cx = GW / 2; const cy = GH / 2; const R = 108;
  return s.members.map((m, i) => {
    const a = (2 * Math.PI * i) / s.members.length - Math.PI / 2;
    return { ...m, x: cx + R * Math.cos(a), y: cy + R * Math.sin(a) };
  });
}
const short = (t: string) => (t.length > 18 ? t.slice(0, 17) + '…' : t);
function go(ref?: string) { if (ref) router.push(ref); }
function askNoetica() {
  cockpit.askAbout(`These are n-ary situation hyperedges binding cross-domain entities (place/rule/person/event/instrument/claim) into one joint context. Why is this representation a moat vs a binary link graph, and what analysis does it unlock?`);
}
onMounted(() => cockpit.setContext({ surface: 'Situations', entityLabel: `${situations.length} situations`, detail: 'n-ary hypergraph', route: '/situations' }));
</script>

<style scoped>
.st { display: flex; flex-direction: column; gap: 1rem; height: 100%; overflow-y: auto; padding: 1rem 1.25rem 1.5rem; }
.st-pill { font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-3); }
.st-ask { border: 1px solid rgba(120, 160, 255, 0.45); background: rgba(120, 160, 255, 0.08); color: #93b4ff; border-radius: 8px; padding: 0.35rem 0.7rem; font-size: 0.76rem; cursor: pointer; } .st-ask:hover { color: #fff; }
.st-lede { margin: 0; max-width: 70ch; font-size: 0.85rem; line-height: 1.6; color: var(--text-2); } .st-lede b { color: var(--text); } .st-lede em { font-style: italic; color: var(--text); }

.st-card { border: 1px solid var(--line-2); border-radius: 14px; padding: 1rem 1.1rem; background: var(--surface, rgba(255, 255, 255, 0.02)); }
.st-card-h { display: flex; align-items: baseline; justify-content: space-between; gap: 0.6rem; }
.st-card-h h2 { margin: 0; font-size: 1rem; font-weight: 650; color: var(--text); }
.st-conf { font-size: 0.72rem; color: var(--up); font-variant-numeric: tabular-nums; }
.st-sum { margin: 0.35rem 0 0.75rem; font-size: 0.8rem; line-height: 1.55; color: var(--text-2); }

.st-body { display: grid; grid-template-columns: 320px 1fr; gap: 1rem; align-items: center; }
@media (max-width: 900px) { .st-body { grid-template-columns: 1fr; } }
.st-graph { width: 100%; height: auto; }
.st-spoke { stroke: var(--line-2); stroke-width: 1.2; }
.st-center { fill: rgba(255, 255, 255, 0.06); stroke: var(--text-3); stroke-width: 1.5; }
.st-center-t { font-size: 20px; fill: var(--text); }
.st-mnode.link { cursor: pointer; }
.st-mnode.link:hover circle { stroke: #fff; stroke-width: 2; }
.st-micon { font-size: 13px; fill: #0b0d10; font-weight: 700; }
.st-mrole { font-size: 8.5px; fill: var(--text-3); text-transform: uppercase; letter-spacing: 0.03em; }
.st-mlabel { font-size: 9.5px; fill: var(--text-2); }

.st-side { display: flex; flex-direction: column; gap: 0.7rem; min-width: 0; }
.st-members { display: flex; flex-wrap: wrap; gap: 0.4rem; }
.st-member { display: flex; flex-direction: column; gap: 0.05rem; text-align: left; border: 1px solid var(--line-2); border-left: 3px solid var(--c); border-radius: 8px; background: transparent; padding: 0.35rem 0.5rem; cursor: default; }
.st-member.link { cursor: pointer; } .st-member.link:hover { border-color: var(--c); }
.st-mtype { font-size: 0.56rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--c); }
.st-mname { font-size: 0.75rem; color: var(--text); }
.st-mrole2 { font-size: 0.62rem; color: var(--text-3); }
.st-nary { display: flex; align-items: baseline; flex-wrap: wrap; gap: 0.4rem; font-size: 0.72rem; padding: 0.5rem 0.6rem; border: 1px dashed var(--line-2); border-radius: 9px; }
.st-nary-a { color: #4bbf73; font-weight: 700; } .st-nary-vs { color: var(--text-3); } .st-nary-b { color: #f0656a; font-weight: 700; } .st-nary-note { color: var(--text-3); flex-basis: 100%; }
.st-prov { display: flex; flex-wrap: wrap; align-items: baseline; gap: 0.4rem; font-size: 0.68rem; color: var(--text-3); }
.st-prov-k { text-transform: uppercase; letter-spacing: 0.05em; } .st-prov-m { font-style: italic; }
</style>
