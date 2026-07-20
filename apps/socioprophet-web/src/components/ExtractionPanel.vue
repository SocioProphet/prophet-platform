<template>
  <!-- First-class information extraction, wired to the LIVE ie-engine (/svc/ie): entities are real
       spaCy NER, claims are assert/hedge over sentences. Each entity links into the graph, each claim
       to a Sherlock evidence search, and the whole extraction can be PROMOTED into the sovereign
       HellGraph (⇪ graph → /to-graph). Falls back to the local pattern stand-in when ie-engine is
       unreachable, so the panel always renders. -->
  <div class="xp">
    <div class="xp-head">
      <span class="xp-title">Extraction</span>
      <ProvenanceBadge :p="extractProv" compact />
      <span v-if="loading" class="xp-loading">extracting…</span>
      <span class="xp-schema">{{ view.entities.length }} entities · {{ view.topics.length }} topics · {{ view.claims.length }} claims</span>
      <button
        class="xp-graph"
        :disabled="promoting || !props.text"
        title="Extract entities + relations into the sovereign HellGraph"
        @click="promote"
      >{{ promoting ? '…' : '⇪ graph' }}</button>
    </div>

    <p v-if="receipt" class="xp-receipt">✓ wrote {{ receipt.nodes_written }} nodes · {{ receipt.edges_written }} edges → {{ receipt.graph }}</p>
    <p v-else-if="promoteErr" class="xp-err">graph write failed — {{ promoteErr }}</p>

    <div v-if="view.topics.length" class="xp-block">
      <div class="xp-block-h">Topics</div>
      <div class="xp-chips">
        <span v-for="t in view.topics" :key="t" class="xp-topic">{{ t }}</span>
      </div>
    </div>

    <div v-if="view.entities.length" class="xp-block">
      <div class="xp-block-h">Entities</div>
      <div class="xp-chips">
        <button v-for="(e, i) in view.entities" :key="i" class="xp-ent" :style="{ '--ec': color(e.cls) }" :title="e.title" @click="onEntity(e)">
          <span class="xp-ent-dot" />{{ e.text }}
        </button>
      </div>
    </div>

    <div v-if="view.claims.length" class="xp-block">
      <div class="xp-block-h">Claims <span class="xp-hint">→ verify with Sherlock</span></div>
      <div class="xp-claims">
        <button v-for="(c, i) in view.claims" :key="i" class="xp-claim" @click="onClaim(c)">
          <span class="xp-claim-text">{{ c.text }}</span>
          <span v-if="c.verifiable" class="xp-claim-badge">verifiable</span>
          <span class="xp-claim-act">⌕ evidence</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { extract as mockExtract, entityColor, type EntityClass } from '../features/extraction/schema';
import * as ie from '../services/ieApi';
import { prov } from '../features/provenance/types';
import ProvenanceBadge from './ProvenanceBadge.vue';
import { useCockpit } from '../stores/cockpit';
import { useOntology } from '../stores/ontology';

const props = defineProps<{ text: string; source?: string }>();
const cockpit = useCockpit();
const ontology = useOntology();

const live = ref<ie.Extraction | null>(null);
const loading = ref(false);
const isLive = computed(() => live.value !== null);

// Live spaCy label → our EntityClass (drives colour + ontology induction).
function toClass(type: string): EntityClass {
  const t = (type || '').toLowerCase();
  if (t === 'person') return 'person';
  if (t === 'org') return 'org';
  if (t === 'place' || t === 'gpe' || t === 'loc') return 'place';
  if (t === 'money') return 'money';
  if (t === 'percent' || t === 'metric' || t === 'quantity' || t === 'cardinal') return 'metric';
  if (t === 'date' || t === 'time') return 'date';
  if (t === 'law') return 'law';
  return 'topic';
}

interface ViewEnt { text: string; cls: EntityClass; title: string }
interface ViewClaim { text: string; verifiable: boolean }

// Unified view: live extraction when reachable, else the local mock (so the panel never blanks).
const view = computed<{ entities: ViewEnt[]; topics: string[]; claims: ViewClaim[] }>(() => {
  const l = live.value;
  if (l) {
    const isTopic = (e: ie.Entity) => (e.type || '').toLowerCase() === 'topic';
    const ner = l.entities.filter((e) => !isTopic(e));
    const topicList = (l.topics?.length ? l.topics : l.entities.filter(isTopic)).map((t) => t.text);
    return {
      entities: ner.map((e) => ({ text: e.text, cls: toClass(e.type), title: `${e.type}${e.spacy_label ? ' · ' + e.spacy_label : ''}` })),
      topics: topicList,
      claims: l.claims.map((c) => ({ text: c.text, verifiable: !!c.verifiable })),
    };
  }
  const m = mockExtract(props.text || '');
  return {
    entities: m.entities.map((e) => ({ text: e.text, cls: e.class, title: `${e.class} · ${Math.round(e.confidence * 100)}%` })),
    topics: m.topics,
    claims: m.claims.map((c) => ({ text: c.text, verifiable: false })),
  };
});

// Live extraction on text change; on any error, fall back to the mock (live = null).
watch(
  () => props.text,
  async (text) => {
    live.value = null;
    receipt.value = null;
    promoteErr.value = '';
    if (!text || !text.trim()) return;
    loading.value = true;
    try {
      live.value = await ie.extract(text);
    } catch {
      live.value = null;
    } finally {
      loading.value = false;
    }
  },
  { immediate: true },
);

// What we read grows the living ontology (from whichever source is showing).
watch(
  view,
  (v) => {
    if (v.entities.length || v.topics.length) {
      ontology.observe(v.entities.map((e) => ({ text: e.text, class: e.cls, confidence: 1 })), [], v.topics);
    }
  },
  { immediate: true },
);

const extractProv = computed(() =>
  isLive.value
    ? prov('computed', { verifier: 'ie-engine (spaCy NER + dependency parse)', sources: [props.source ?? 'current item'], note: 'Live extraction from the ie-engine: entities are real spaCy NER, claims are assert/hedge over sentences.' })
    : prov('fixture', { verifier: 'local pattern stand-in', sources: [props.source ?? 'current item'], note: 'ie-engine unreachable — showing the local pattern stand-in; treat as illustrative.' }),
);

const color = (c: EntityClass) => entityColor(c);

// Promote → extract + upsert entities/relations into the canonical HellGraph (closes the News→KE loop).
const receipt = ref<ie.GraphWrite | null>(null);
const promoteErr = ref('');
const promoting = ref(false);
async function promote() {
  if (!props.text || promoting.value) return;
  promoting.value = true;
  receipt.value = null;
  promoteErr.value = '';
  try {
    receipt.value = await ie.toGraph(props.text);
  } catch (e) {
    promoteErr.value = e instanceof Error ? e.message : 'failed';
  } finally {
    promoting.value = false;
  }
}

// Entity → surface it in the graph (open the contextual graph dock).
function onEntity(e: ViewEnt) {
  cockpit.setContext({ surface: cockpit.context.surface || 'Extraction', entityLabel: e.text, detail: e.cls, route: cockpit.context.route });
  cockpit.toggleGraph();
}
// Claim → Sherlock evidence search via the assistant.
function onClaim(c: ViewClaim) {
  cockpit.askAbout(`Run a Sherlock evidence search on this claim: "${c.text}". Is it corroborated, contradicted, or unverified — and by what sources?`);
}
</script>

<style scoped>
.xp { display: flex; flex-direction: column; gap: 0.6rem; }
.xp-head { display: flex; align-items: center; gap: 0.5rem; }
.xp-title { font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.1em; color: rgba(255, 255, 255, 0.5); font-weight: 700; }
.xp-loading { font-size: 0.62rem; color: var(--accent); }
.xp-schema { margin-left: auto; font-size: 0.66rem; color: rgba(255, 255, 255, 0.4); }
.xp-graph { flex: 0 0 auto; border: 1px solid color-mix(in srgb, var(--accent) 45%, transparent); background: color-mix(in srgb, var(--accent) 12%, transparent); color: var(--accent); border-radius: 6px; padding: 0.1rem 0.5rem; font-size: 0.66rem; font-weight: 700; cursor: pointer; }
.xp-graph:hover:not(:disabled) { background: color-mix(in srgb, var(--accent) 22%, transparent); }
.xp-graph:disabled { opacity: 0.5; cursor: default; }
.xp-receipt { margin: 0; font-size: 0.68rem; color: var(--up); }
.xp-err { margin: 0; font-size: 0.68rem; color: var(--down); }
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
.xp-claim-text { font-size: 0.76rem; color: rgba(255, 255, 255, 0.82); line-height: 1.45; flex: 1; }
.xp-claim-badge { flex: 0 0 auto; font-size: 0.58rem; text-transform: uppercase; letter-spacing: 0.03em; color: var(--up); background: rgba(75, 191, 115, 0.15); border-radius: 4px; padding: 0.03rem 0.3rem; }
.xp-claim-act { flex: 0 0 auto; font-size: 0.66rem; color: #58a6ff; }
</style>
