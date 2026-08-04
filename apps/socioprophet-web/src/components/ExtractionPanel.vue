<template>
  <!-- First-class information extraction: entities / topics / claims pulled from the
       current item (Holmes stand-in), each linkable into the graph or to a Sherlock
       evidence search. Schema is definable in features/extraction/schema.ts. -->
  <div class="xp">
    <div class="xp-head">
      <span class="xp-title">Extraction</span>
      <ProvenanceBadge :p="extractProv" compact />
      <span class="xp-schema">{{ ex.entities.length }} entities · {{ ex.topics.length }} topics · {{ ex.claims.length }} claims</span>
    </div>

    <div v-if="ex.topics.length" class="xp-block">
      <div class="xp-block-h">Topics</div>
      <div class="xp-chips">
        <span v-for="t in ex.topics" :key="t" class="xp-topic">{{ t }}</span>
      </div>
    </div>

    <div v-if="ex.entities.length" class="xp-block">
      <div class="xp-block-h">Entities</div>
      <div class="xp-chips">
        <button v-for="(e, i) in ex.entities" :key="i" class="xp-ent" :style="{ '--ec': color(e.class) }" :title="`${e.class} · ${Math.round(e.confidence * 100)}%`" @click="onEntity(e)">
          <span class="xp-ent-dot" />{{ e.text }}
        </button>
      </div>
    </div>

    <div v-if="ex.claims.length" class="xp-block">
      <div class="xp-block-h">Claims <span class="xp-hint">→ verify with Sherlock</span></div>
      <div class="xp-claims">
        <button v-for="(c, i) in ex.claims" :key="i" class="xp-claim" @click="onClaim(c)">
          <span class="xp-claim-text">{{ c.text }}</span>
          <span class="xp-claim-act">⌕ evidence</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue';
import { extract, entityColor, type ExtractedEntity, type ExtractedClaim, type EntityClass } from '../features/extraction/schema';
import { prov } from '../features/provenance/types';
import ProvenanceBadge from './ProvenanceBadge.vue';
import { useCockpit } from '../stores/cockpit';
import { useOntology } from '../stores/ontology';

const props = defineProps<{ text: string; source?: string }>();
const cockpit = useCockpit();
const ontology = useOntology();
const ex = computed(() => extract(props.text || ''));
// NLP → ontology induction: what we read grows the living ontology.
watch(ex, (e) => { if (e.entities.length || e.topics.length) ontology.observe(e.entities, [], e.topics); }, { immediate: true });
// Local regex/pattern stand-in, not the real Holmes adapter — so 'fixture'/unassayed,
// not 'verified'. Flips to 'computed' when a live Holmes adapter swaps in behind the shape.
const extractProv = prov('fixture', { verifier: 'Holmes (local pattern stand-in)', sources: [props.source ?? 'current item'], note: 'Schema-defined extraction by a local pattern stand-in — not yet the live Holmes adapter; treat entities/claims as illustrative.' });
const color = (c: EntityClass) => entityColor(c);

// Entity → surface it in the graph (open the contextual graph dock).
function onEntity(e: ExtractedEntity) {
  cockpit.setContext({ surface: cockpit.context.surface || 'Extraction', entityLabel: e.text, detail: e.class, route: cockpit.context.route });
  cockpit.toggleGraph();
}
// Claim → Sherlock evidence search via the assistant.
function onClaim(c: ExtractedClaim) {
  cockpit.askAbout(`Run a Sherlock evidence search on this claim: "${c.text}". Is it corroborated, contradicted, or unverified — and by what sources?`);
}
</script>

<style scoped>
.xp { display: flex; flex-direction: column; gap: 0.6rem; }
.xp-head { display: flex; align-items: center; gap: 0.5rem; }
.xp-title { font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.1em; color: rgba(255, 255, 255, 0.5); font-weight: 700; }
.xp-schema { margin-left: auto; font-size: 0.66rem; color: rgba(255, 255, 255, 0.4); }
.xp-block-h { font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.06em; color: rgba(255, 255, 255, 0.4); margin-bottom: 0.3rem; }
.xp-hint { text-transform: none; letter-spacing: 0; color: var(--text-3); }
.xp-chips { display: flex; flex-wrap: wrap; gap: 0.3rem; }
.xp-topic { font-size: 0.7rem; color: #a3e635; background: rgba(163, 230, 53, 0.12); border: 1px solid rgba(163, 230, 53, 0.3); border-radius: 999px; padding: 0.08rem 0.5rem; }
.xp-ent { display: inline-flex; align-items: center; gap: 0.3rem; font-size: 0.72rem; color: var(--ec); background: color-mix(in srgb, var(--ec) 12%, transparent); border: 1px solid color-mix(in srgb, var(--ec) 40%, transparent); border-radius: 6px; padding: 0.08rem 0.45rem; cursor: pointer; }
.xp-ent:hover { background: color-mix(in srgb, var(--ec) 22%, transparent); }
.xp-ent-dot { width: 5px; height: 5px; border-radius: 50%; background: var(--ec); }
.xp-claims { display: flex; flex-direction: column; gap: 0.3rem; }
.xp-claim { display: flex; align-items: baseline; justify-content: space-between; gap: 0.6rem; text-align: left; border: 1px solid var(--line-2); background: var(--surface-2); border-radius: 8px; padding: 0.4rem 0.6rem; cursor: pointer; }
.xp-claim:hover { border-color: #58a6ff; }
.xp-claim-text { font-size: 0.76rem; color: rgba(255, 255, 255, 0.82); line-height: 1.45; }
.xp-claim-act { flex: 0 0 auto; font-size: 0.66rem; color: #58a6ff; }
</style>
