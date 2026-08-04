<script setup lang="ts">
// EvidenceGraph — the reusable ego-network. Radial focus+context: an ego node centered, its
// 1-hop neighbours on a ring, typed by colour, edges labelled by relation and STYLED BY PROVENANCE
// (solid = record/org, dashed = news-derived, dotted = personal). Click a node to re-centre, click
// an edge to open its evidence. This is the moat applied to any entity: LinkedIn/Palantir show
// connections; we show why to believe each one. Powers both the People associates graph and the Law
// citation panel (cites / cited-by). Pure SVG, no graph lib.
import { computed } from 'vue';

export interface EgoNode { id: string; label: string; type?: string }
export interface EgoLink { node: EgoNode; rel?: string; provenance?: 'record' | 'news' | 'personal' | 'derived'; evidence?: string; dir?: 'in' | 'out' }

const props = withDefaults(
  defineProps<{ center: EgoNode; links: EgoLink[]; w?: number; h?: number }>(),
  { w: 320, h: 240 },
);
const emit = defineEmits<{ (e: 'select', node: EgoNode): void; (e: 'evidence', link: EgoLink): void }>();

const TYPE_COLORS: Record<string, string> = {
  person: '#5aa9ff', org: '#c9a3ff', company: '#c9a3ff', gov: '#e3b341', place: '#6fbf8b',
  topic: '#a3e635', rule: '#8fb0ff', law: '#d8a250', money: '#e3b341', default: '#8b949e',
};
const col = (t?: string) => TYPE_COLORS[(t || 'default').toLowerCase()] || TYPE_COLORS.default;
const initials = (s: string) => s.split(/\s+/).slice(0, 2).map((w) => w[0]?.toUpperCase() ?? '').join('');
const short = (s: string) => (s.length > 14 ? s.slice(0, 13) + '…' : s);
const dash = (p?: string) => (p === 'news' || p === 'derived' ? '5 4' : p === 'personal' ? '1.5 4' : '0');

const layout = computed(() => {
  const cx = props.w / 2, cy = props.h / 2;
  const R = Math.min(props.w, props.h) * 0.34;
  const n = props.links.length || 1;
  return {
    cx, cy,
    nodes: props.links.map((lk, i) => {
      const ang = -Math.PI / 2 + (i / n) * Math.PI * 2;
      return { lk, x: +(cx + R * Math.cos(ang)).toFixed(1), y: +(cy + R * Math.sin(ang)).toFixed(1) };
    }),
  };
});
</script>

<template>
  <svg class="eg" :viewBox="`0 0 ${w} ${h}`" role="img" aria-label="Evidence-backed relationship graph">
    <g v-for="(nd, i) in layout.nodes" :key="'e' + i">
      <line class="eg-edge" :x1="layout.cx" :y1="layout.cy" :x2="nd.x" :y2="nd.y" :stroke-dasharray="dash(nd.lk.provenance)"
            @click.stop="emit('evidence', nd.lk)" />
      <text v-if="nd.lk.rel" class="eg-rel" :x="(layout.cx + nd.x) / 2" :y="(layout.cy + nd.y) / 2 - 3" text-anchor="middle">{{ nd.lk.rel }}</text>
    </g>
    <g v-for="(nd, i) in layout.nodes" :key="'n' + i" class="eg-node" @click.stop="emit('select', nd.lk.node)">
      <title>{{ nd.lk.node.label }}{{ nd.lk.evidence ? ' · evidence: ' + nd.lk.evidence : '' }}</title>
      <circle :cx="nd.x" :cy="nd.y" r="13" :fill="col(nd.lk.node.type)" />
      <text :x="nd.x" :y="nd.y + 3.5" text-anchor="middle" class="eg-init">{{ initials(nd.lk.node.label) }}</text>
      <text :x="nd.x" :y="nd.y + 27" text-anchor="middle" class="eg-lab">{{ short(nd.lk.node.label) }}</text>
    </g>
    <circle :cx="layout.cx" :cy="layout.cy" r="18" :fill="col(center.type)" stroke="#fff" stroke-width="1.5" />
    <text :x="layout.cx" :y="layout.cy + 4.5" text-anchor="middle" class="eg-init ego">{{ initials(center.label) }}</text>
  </svg>
</template>

<style scoped>
.eg { width: 100%; height: auto; display: block; }
.eg-edge { stroke: rgba(237, 238, 242, 0.28); stroke-width: 1.3; cursor: pointer; }
.eg-edge:hover { stroke: var(--accent); }
.eg-rel { fill: rgba(237, 238, 242, 0.42); font-size: 7.5px; text-transform: uppercase; letter-spacing: 0.04em; pointer-events: none; }
.eg-node { cursor: pointer; }
.eg-node:hover circle { stroke: #fff; stroke-width: 1.2; }
.eg-init { fill: #0d0f13; font-size: 9px; font-weight: 700; pointer-events: none; }
.eg-init.ego { fill: #0d0f13; font-size: 11px; }
.eg-lab { fill: rgba(237, 238, 242, 0.6); font-size: 8.5px; pointer-events: none; }
</style>
