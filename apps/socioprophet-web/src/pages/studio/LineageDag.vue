<script setup lang="ts">
// A real node-link lineage DAG — not a space-joined string or a flat arrow chain. Steps declare the
// artifacts they consume (inputs) and produce (outputs); we recover the true dependency edges
// (producer.output → consumer.input), lay the graph out in topological layers (longest-path, so
// depth = distance from a source), and draw it left-to-right with curved edges. Nodes are coloured
// by step kind. Pure SVG, no chart lib. This is the "lineage IS the graph" claim made literal.
import { computed } from 'vue';
import type { PipelineStepDef } from '../../services/studioApi';

const props = defineProps<{ steps: PipelineStepDef[] }>();

const NODE_W = 104, NODE_H = 34, DX = 150, DY = 52, PAD = 14;

// kind → token colour (kept to the epistemic/status ramp so it reads as one system).
function kindColor(kind: string): string {
  const k = kind.toLowerCase();
  if (/extract|ingest|load|source/.test(k)) return 'var(--epi-observed)';
  if (/transform|clean|dbt|feature/.test(k)) return 'var(--epi-derived)';
  if (/train|fit|tune|learn/.test(k)) return 'var(--epi-simulated)';
  if (/eval|verify|test|validate/.test(k)) return 'var(--epi-verified)';
  if (/publish|register|export|serve/.test(k)) return 'var(--epi-attested)';
  return 'var(--muted)';
}

type Laid = { step: PipelineStepDef; layer: number; row: number; x: number; y: number; color: string };

const layout = computed(() => {
  const steps = props.steps ?? [];
  const byId = new Map(steps.map((s) => [s.id, s]));
  // producer of each artifact → step id
  const producer = new Map<string, string>();
  for (const s of steps) for (const o of s.outputs ?? []) producer.set(o, s.id);
  // edges: producer step → consumer step (via a shared artifact)
  const edges: { from: string; to: string; via: string }[] = [];
  const parents = new Map<string, Set<string>>();
  for (const s of steps) {
    for (const inp of s.inputs ?? []) {
      const p = producer.get(inp);
      if (p && p !== s.id) {
        edges.push({ from: p, to: s.id, via: inp });
        (parents.get(s.id) ?? parents.set(s.id, new Set()).get(s.id)!).add(p);
      }
    }
  }
  // longest-path layering with a cycle guard (visited stack); sources (no known parent) at layer 0.
  const layerOf = new Map<string, number>();
  function depth(id: string, stack: Set<string>): number {
    if (layerOf.has(id)) return layerOf.get(id)!;
    if (stack.has(id)) return 0; // cycle → treat as source, don't recurse
    stack.add(id);
    const ps = parents.get(id);
    const d = ps && ps.size ? 1 + Math.max(...[...ps].map((p) => depth(p, stack))) : 0;
    stack.delete(id);
    layerOf.set(id, d);
    return d;
  }
  for (const s of steps) depth(s.id, new Set());

  // group by layer, assign rows, center each layer vertically
  const layers = new Map<number, string[]>();
  for (const s of steps) { const l = layerOf.get(s.id) ?? 0; (layers.get(l) ?? layers.set(l, []).get(l)!).push(s.id); }
  const maxRows = Math.max(1, ...[...layers.values()].map((a) => a.length));
  const nodes: Laid[] = [];
  const pos = new Map<string, Laid>();
  for (const [layer, ids] of [...layers.entries()].sort((a, b) => a[0] - b[0])) {
    const offset = (maxRows - ids.length) / 2; // center shorter layers
    ids.forEach((id, i) => {
      const step = byId.get(id)!;
      const n: Laid = {
        step, layer, row: i,
        x: PAD + layer * DX,
        y: PAD + (offset + i) * DY,
        color: kindColor(step.kind),
      };
      nodes.push(n); pos.set(id, n);
    });
  }
  const laidEdges = edges.map((e) => ({ ...e, a: pos.get(e.from)!, b: pos.get(e.to)! })).filter((e) => e.a && e.b);
  const width = PAD * 2 + (Math.max(0, ...[...layers.keys()]) * DX) + NODE_W;
  const height = PAD * 2 + maxRows * DY - (DY - NODE_H);
  return { nodes, edges: laidEdges, width, height };
});

// cubic bezier from a node's right edge to another node's left edge
function edgePath(a: Laid, b: Laid): string {
  const x1 = a.x + NODE_W, y1 = a.y + NODE_H / 2;
  const x2 = b.x, y2 = b.y + NODE_H / 2;
  const mx = (x1 + x2) / 2;
  return `M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`;
}
</script>

<template>
  <div class="dag-wrap">
    <svg v-if="layout.nodes.length" :viewBox="`0 0 ${layout.width} ${layout.height}`"
         :width="layout.width" :height="layout.height" class="dag" role="img" aria-label="Pipeline lineage DAG">
      <g class="edges">
        <path v-for="(e, i) in layout.edges" :key="i" :d="edgePath(e.a, e.b)" class="edge">
          <title>{{ e.from }} → {{ e.to }} · via {{ e.via }}</title>
        </path>
      </g>
      <g v-for="n in layout.nodes" :key="n.step.id" class="node" :transform="`translate(${n.x},${n.y})`">
        <rect :width="NODE_W" :height="NODE_H" rx="5" class="nbox" :style="{ stroke: n.color }" />
        <rect x="0" y="0" :width="3" :height="NODE_H" :fill="n.color" rx="1.5" />
        <text x="11" :y="13" class="nid">{{ n.step.id }}</text>
        <text x="11" :y="26" class="nkind" :style="{ fill: n.color }">{{ n.step.kind }}</text>
        <title>{{ n.step.id }} · {{ n.step.kind }}{{ (n.step.inputs?.length ? ' · in: ' + n.step.inputs.join(', ') : '') }}{{ (n.step.outputs?.length ? ' · out: ' + n.step.outputs.join(', ') : '') }}</title>
      </g>
    </svg>
    <span v-else class="empty">no steps</span>
  </div>
</template>

<style scoped>
.dag-wrap { overflow-x: auto; padding: 4px 0; }
.dag { display: block; }
.edge { fill: none; stroke: var(--hairline-strong); stroke-width: 1.4; opacity: .85; }
.nbox { fill: var(--surface); stroke-width: 1.2; }
.node:hover .nbox { fill: var(--surface-2); }
.nid { fill: var(--ink); font: 600 11px/1 var(--ui); }
.nkind { font: 500 9px/1 var(--ui); text-transform: uppercase; letter-spacing: .04em; opacity: .9; }
.empty { color: var(--faint); font-size: 12px; }
</style>
