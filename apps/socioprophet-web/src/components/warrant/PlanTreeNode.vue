<template>
  <!-- One typed action node. Recursive: a binding whose `kind === 'action'` carries a
       sub-plan in `via`, and that sub-plan is rendered by this same component. -->
  <li class="pt-node" :class="{ 'pt-ungrounded': node.grounding.kind === 'ungrounded' }">
    <div class="pt-row">
      <button
        v-if="children.length"
        class="pt-twist"
        type="button"
        :aria-expanded="open"
        :aria-label="open ? `Collapse ${node.actionName}` : `Expand ${node.actionName}`"
        @click="open = !open"
      >
        {{ open ? '▾' : '▸' }}
      </button>
      <span v-else class="pt-twist pt-leaf" aria-hidden="true">·</span>

      <span class="pt-id mono">{{ node.nodeId }}</span>
      <span class="pt-name">{{ node.actionName }}</span>

      <span class="pt-type mono" :title="node.outputTypeRef">
        → {{ shortRef(node.outputTypeRef) }}<span class="pt-card">{{ node.outputCardinality === 'many' ? '[]' : '' }}</span>
      </span>

      <!-- An effect-request leaf is a PROPOSAL. Never executed at search time; an
           EffectDecision must precede any world change. Flag it loudly. -->
      <span v-if="node.sideEffects === 'effect-request'" class="pt-effect" title="Proposed effect — requires an EffectDecision before execution">
        effect-request
      </span>

      <Warrant class="pt-warrant" :w="warrantFor(node)" compact />
    </div>

    <div v-if="open && node.bindings.length" class="pt-bindings">
      <div v-for="b in node.bindings" :key="b.input" class="pt-bind" :class="{ 'pt-unbound': b.kind === 'unbound' }">
        <span class="pt-bind-name mono">{{ b.input }}</span>
        <span class="pt-bind-type mono" :title="b.typeRef">
          {{ shortRef(b.typeRef) }}<span v-if="b.cardinality === 'many'">[]</span>
        </span>
        <span class="pt-bind-kind" :class="`k-${b.kind}`">{{ b.kind }}</span>
        <span v-if="b.required" class="pt-req" title="Required input">req</span>

        <span v-if="b.literal !== undefined" class="pt-bind-val">
          literal “<mark>{{ b.literal }}</mark
          >”
        </span>
        <span v-else-if="b.defaultLabel" class="pt-bind-val">default: {{ b.defaultLabel }}</span>
        <span v-else-if="b.conceptRef && b.kind !== 'action'" class="pt-bind-val mono">{{ shortRef(b.conceptRef) }}</span>

        <span
          v-if="b.subsumption && !b.subsumption.direct"
          class="pt-subsume mono"
          :title="`${b.subsumption.concept} ⊑ ${b.subsumption.satisfies} — subsumption licensed this bind`"
        >
          ⊑ {{ shortRef(b.subsumption.satisfies) }}
        </span>
      </div>
    </div>

    <ul v-if="open && children.length" class="pt-children">
      <PlanTreeNode
        v-for="c in children"
        :key="c.nodeId"
        :node="c"
        :provenance="provenance"
        :seal="seal"
        :walk="walk"
        :depth="depth + 1"
      />
    </ul>
  </li>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import Warrant from './Warrant.vue';
import type {
  NodeProvenance,
  PlanNode,
  ReceiptVerifyWalk,
  SealOutcome,
  WarrantInput,
} from '../../features/warrant/types';

const props = withDefaults(
  defineProps<{
    node: PlanNode;
    /** The variant's per-node provenance, keyed by nodeId. */
    provenance: NodeProvenance[];
    /** Compilation-level seal — an unsealed compilation makes EVERY node unsealed. */
    seal?: SealOutcome | null;
    walk?: ReceiptVerifyWalk | null;
    depth?: number;
  }>(),
  { seal: null, walk: null, depth: 0 },
);

// Open by default. The compiler's DEFAULT_MAX_DEPTH is 4, so a plan is at most a handful of
// levels — and this surface exists to make the plan VISIBLE. Collapsing by default would hide
// exactly the leaf detail (literals, subsumption witnesses) that the proof lives in. The user
// can collapse what they don't want; the default must not do the hiding for them.
const open = ref(true);

const children = computed(() =>
  props.node.bindings.map((b) => b.via).filter((v): v is PlanNode => v !== undefined),
);

/** Trim a URI to its last path/# segment for display; the full ref stays in the title attr. */
function shortRef(ref: string): string {
  const tail = ref.split(/[#/:]/).filter(Boolean).pop();
  return tail || ref;
}

/**
 * Build the node's warrant. The claim is what the node ASSERTS; the grounding is the
 * compiler's own account of why the node is in the plan; the seal is inherited from the
 * compilation, because a node cannot be more proven than the run that produced it.
 */
function warrantFor(n: PlanNode): WarrantInput {
  const prov = props.provenance.find((p) => p.nodeId === n.nodeId);
  const via =
    n.grounding.kind === 'token-span'
      ? `grounded in “${n.grounding.tokenSpan?.text ?? ''}”`
      : n.grounding.kind === 'registry-default'
        ? `supplied by registry default ${n.grounding.defaultLabel ?? ''}`
        : 'invented — nothing in the question evoked it';
  const weight = prov ? ` (weight ${prov.weight.toFixed(2)})` : '';
  return {
    claim: `${n.actionName} produces ${shortRef(n.outputTypeRef)} — ${via}${weight}`,
    grounding: n.grounding,
    seal: props.seal ?? undefined,
    walk: props.walk ?? undefined,
  };
}
</script>

<style scoped>
.pt-node {
  list-style: none;
  margin: 0;
  padding: 0;
}
.pt-row {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
  padding: 3px 4px;
  border-radius: var(--r-1, 3px);
  font-size: 0.74rem;
}
.pt-row:hover {
  background: var(--surface-2, #18202a);
}
.pt-twist {
  width: 1rem;
  flex: 0 0 auto;
  background: none;
  border: 0;
  color: var(--muted, #8a97a5);
  cursor: pointer;
  font-size: 0.7rem;
  padding: 0;
  line-height: 1;
  font-family: inherit;
}
.pt-twist:focus-visible {
  outline: 1px solid var(--accent, #5b95f9);
}
.pt-leaf {
  cursor: default;
  color: var(--faint, #5d6a78);
  text-align: center;
}
.pt-id {
  color: var(--faint, #5d6a78);
  font-family: var(--mono, ui-monospace, monospace);
  font-size: 0.64rem;
}
.pt-name {
  color: var(--ink, #e8eef5);
  font-weight: 600;
}
.pt-type {
  color: var(--epi-derived, #a082f8);
  font-family: var(--mono, ui-monospace, monospace);
  font-size: 0.66rem;
}
.pt-card {
  color: var(--faint, #5d6a78);
}
.pt-effect {
  color: var(--warn, #d29922);
  background: var(--warn-wash, #241d0a);
  border: 1px solid color-mix(in srgb, var(--warn, #d29922) 38%, transparent);
  border-radius: var(--r-1, 3px);
  padding: 0 5px;
  font-size: 0.6rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.pt-warrant {
  margin-left: auto;
}
.pt-ungrounded > .pt-row .pt-name {
  color: var(--epi-hypothesis, #8592a3);
  font-style: italic;
}

.pt-bindings {
  display: grid;
  gap: 2px;
  margin: 2px 0 3px 1.4rem;
  padding-left: 0.5rem;
  border-left: 1px dashed var(--hairline, #232c38);
}
.pt-bind {
  display: flex;
  align-items: baseline;
  gap: 0.4rem;
  flex-wrap: wrap;
  font-size: 0.66rem;
  color: var(--muted, #8a97a5);
}
.pt-bind-name {
  color: var(--ink-2, #b4c0cd);
  font-family: var(--mono, ui-monospace, monospace);
}
.pt-bind-type {
  color: var(--faint, #5d6a78);
  font-family: var(--mono, ui-monospace, monospace);
}
.pt-bind-kind {
  font-size: 0.58rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 0 4px;
  border-radius: var(--r-1, 3px);
  border: 1px solid var(--hairline-strong, #33404f);
}
.k-annotation {
  color: var(--epi-observed, #5b95f9);
}
.k-action {
  color: var(--epi-derived, #a082f8);
}
.k-default {
  color: var(--epi-simulated, #e0975a);
}
.k-unbound {
  color: var(--fail, #e5534b);
  border-color: color-mix(in srgb, var(--fail, #e5534b) 40%, transparent);
}
.pt-unbound {
  color: var(--fail, #e5534b);
}
.pt-req {
  color: var(--warn, #d29922);
  font-size: 0.58rem;
  text-transform: uppercase;
}
.pt-bind-val mark {
  background: color-mix(in srgb, var(--epi-observed, #5b95f9) 24%, transparent);
  color: var(--ink, #e8eef5);
  border-radius: 2px;
  padding: 0 2px;
}
.pt-subsume {
  color: var(--epi-derived, #a082f8);
  font-family: var(--mono, ui-monospace, monospace);
  font-size: 0.62rem;
}
.pt-children {
  list-style: none;
  margin: 0 0 0 1.4rem;
  padding-left: 0.5rem;
  border-left: 1px solid var(--hairline, #232c38);
}
.mono {
  font-family: var(--mono, ui-monospace, monospace);
}
</style>
