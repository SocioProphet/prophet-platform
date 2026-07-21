<script setup lang="ts">
// The unified Studio workspace inside the cockpit — a Foundry/Databricks-class shell with
// governed Notebooks + Universal Compute Plane (from app-vue) and the full knowledge-engineering
// bench (Graph Explorer, Query, Analytics, GraphRAG, Resource Browser, Reasoner, Entity Resolution,
// Ontology — from Prophet Studio). One surface, one design system (.studio-scope), reading the
// canonical hellgraph-service / owl-reasoner / entity-resolution backends via /svc/*.
import { ref, computed, watch, markRaw } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import './studio/studio-tokens.css';
import StudioNotebooks from './studio/StudioNotebooks.vue';
import StudioCompute from './studio/StudioCompute.vue';
import StudioCatalog from './studio/StudioCatalog.vue';
import GraphExplorer from './studio/GraphExplorer.vue';
import QueryConsole from './studio/QueryConsole.vue';
import Analytics from './studio/Analytics.vue';
import GraphRAG from './studio/GraphRAG.vue';
import ResourceBrowser from './studio/ResourceBrowser.vue';
import Reasoner from './studio/Reasoner.vue';
import EntityResolution from './studio/EntityResolution.vue';
import Ontology from './studio/Ontology.vue';
import StudioExperiments from './studio/StudioExperiments.vue';
import StudioOps from './studio/StudioOps.vue';
import StudioGovernance from './studio/StudioGovernance.vue';
import StudioCommons from './studio/StudioCommons.vue';

type Sec = { id: string; label: string; ic: string; comp: any; sub: string; project?: boolean };
const GROUPS: { group: string; items: Sec[] }[] = [
  { group: 'Workbench', items: [
    { id: 'notebooks', label: 'Notebooks', ic: '⬢', comp: markRaw(StudioNotebooks), project: true, sub: 'Ray-backed governed notebooks — receipt per cell' },
    { id: 'compute', label: 'Compute Plane', ic: '⛩', comp: markRaw(StudioCompute), project: true, sub: 'Universal Compute Plane — one governed, proof-carrying door' },
    { id: 'catalog', label: 'Data Catalog', ic: '▤', comp: markRaw(StudioCatalog), project: true, sub: 'Datasets as proof-carrying nodes — epistemic status + ingest volume' },
  ]},
  { group: 'Knowledge engineering', items: [
    { id: 'graph', label: 'Graph Explorer', ic: '⟡', comp: markRaw(GraphExplorer), sub: 'Force-directed graph + provenance inspector' },
    { id: 'query', label: 'Query Console', ic: '⌘', comp: markRaw(QueryConsole), sub: 'SPARQL · Cypher · Gremlin over the live kernel' },
    { id: 'analytics', label: 'Analytics', ic: '📈', comp: markRaw(Analytics), sub: 'PageRank / components on the Rust kernel' },
    { id: 'graphrag', label: 'GraphRAG', ic: '✦', comp: markRaw(GraphRAG), sub: 'Ask the graph, cited answers' },
    { id: 'resource', label: 'Resource Browser', ic: '◈', comp: markRaw(ResourceBrowser), sub: 'Dereferenceable Linked Data' },
  ]},
  { group: 'Reason & Resolve', items: [
    { id: 'reasoner', label: 'Reasoner', ic: '⊢', comp: markRaw(Reasoner), sub: 'RDFS/OWL entailment + proof trees' },
    { id: 'er', label: 'Entity Resolution', ic: '⚭', comp: markRaw(EntityResolution), sub: 'Proof-carrying record linkage' },
    { id: 'ontology', label: 'Ontology', ic: '❖', comp: markRaw(Ontology), sub: 'Docs + TBox graph' },
  ]},
  { group: 'Operations & Governance', items: [
    { id: 'experiments', label: 'Experiments', ic: '⚗', comp: markRaw(StudioExperiments), project: true, sub: 'Runs as proof-carrying graph facts' },
    { id: 'operations', label: 'Operations', ic: '⚙', comp: markRaw(StudioOps), project: true, sub: 'Pipelines · registry · catalog · communities' },
    { id: 'governance', label: 'Governance', ic: '🛡', comp: markRaw(StudioGovernance), project: true, sub: 'Ontology · SHACL actions · GAIA membrane' },
    { id: 'commons', label: 'Commons', ic: '❖', comp: markRaw(StudioCommons), project: true, sub: 'Proof-carrying knowledge commons' },
  ]},
];
const flat = GROUPS.flatMap((g) => g.items);

const route = useRoute();
const router = useRouter();
const project = ref('Untitled project');
const current = ref(sectionFromQuery());
function sectionFromQuery(): string {
  const s = (route.query.section as string) || (route.query.tab === 'compute' ? 'compute' : 'notebooks');
  return flat.some((i) => i.id === s) ? s : 'notebooks';
}
watch(() => route.query.section, () => { current.value = sectionFromQuery(); });
const active = computed(() => flat.find((i) => i.id === current.value) ?? flat[0]);
function go(id: string) { current.value = id; router.replace({ query: { ...route.query, section: id, tab: undefined } }); }
</script>

<template>
  <div class="studio-scope studio-shell">
    <aside class="st-rail">
      <div class="st-brand">
        <span class="st-brand-mark">◈</span>
        <span class="st-brand-txt"><b>Studio</b><small>sovereign data + AI workbench</small></span>
      </div>
      <nav class="st-nav" aria-label="Studio sections">
        <template v-for="g in GROUPS" :key="g.group">
          <div class="st-group">{{ g.group }}</div>
          <a
            v-for="i in g.items" :key="i.id" class="st-link" :class="{ on: current === i.id }"
            role="button" tabindex="0" :aria-current="current === i.id ? 'page' : undefined"
            @click="go(i.id)" @keydown.enter.prevent="go(i.id)" @keydown.space.prevent="go(i.id)"
          >
            <span class="st-ic">{{ i.ic }}</span><span class="st-link-t">{{ i.label }}</span>
          </a>
        </template>
      </nav>
    </aside>
    <section class="st-main">
      <header class="st-top">
        <span class="st-top-ic">{{ active.ic }}</span>
        <div class="st-top-h"><h1>{{ active.label }}</h1><span class="st-sub">{{ active.sub }}</span></div>
        <span class="pill accent st-top-badge">proof-carrying · sovereign</span>
      </header>
      <div class="st-view">
        <component :is="active.comp" :key="active.id" v-bind="active.project ? { project } : {}" />
      </div>
    </section>
  </div>
</template>

<style scoped>
/* Carbon UI-Shell chrome, driven entirely by studio-tokens: a dark shell bar (--bar) for the
   SideNav + header, content on --bg, and the signature Carbon active treatment (accent-wash fill
   + a 3px accent left indicator). Square-ish chrome, token spacing, real focus rings. */
.studio-shell { display: grid; grid-template-columns: 256px 1fr; height: calc(100vh - 7rem); min-height: 520px; border: 1px solid var(--hairline); border-radius: var(--r-3); overflow: hidden; background: var(--bg); color: var(--text); }

/* SideNav */
.st-rail { background: var(--bar); border-right: 1px solid var(--bar-line); display: flex; flex-direction: column; overflow: hidden; }
.st-brand { display: flex; align-items: center; gap: var(--sp-3); height: 3rem; padding: 0 var(--sp-4); border-bottom: 1px solid var(--bar-line); flex: 0 0 auto; }
.st-brand-mark { color: var(--accent); font-size: 1rem; }
.st-brand-txt { display: flex; flex-direction: column; line-height: 1.1; }
.st-brand-txt b { font-size: .9rem; color: var(--bar-ink); letter-spacing: .01em; }
.st-brand-txt small { color: var(--faint); font-size: .58rem; text-transform: uppercase; letter-spacing: .09em; margin-top: 2px; }
.st-nav { padding: var(--sp-2) 0 var(--sp-3); overflow-y: auto; flex: 1; }
.st-group { color: var(--faint); font-size: .6rem; text-transform: uppercase; letter-spacing: .1em; padding: var(--sp-4) var(--sp-4) var(--sp-1); }
.st-group:first-child { padding-top: var(--sp-2); }
.st-link { display: flex; align-items: center; gap: var(--sp-3); min-height: 2rem; padding: var(--sp-2) var(--sp-4); color: var(--bar-muted); cursor: pointer; font-size: .82rem; user-select: none; border-left: 2px solid transparent; transition: background .08s ease, color .08s ease; }
.st-link:hover { background: var(--surface); color: var(--ink); }
.st-link:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
.st-link.on { background: var(--accent-wash); color: var(--accent-ink); border-left-color: var(--accent); }
.st-ic { width: 16px; text-align: center; opacity: .9; flex: 0 0 auto; }
.st-link-t { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* Header + content */
.st-main { display: flex; flex-direction: column; overflow: hidden; background: var(--bg); }
.st-top { display: flex; align-items: center; gap: var(--sp-3); min-height: 3rem; padding: .4rem var(--sp-5); border-bottom: 1px solid var(--hairline); background: var(--bar); flex: 0 0 auto; }
.st-top-ic { color: var(--accent); font-size: 1rem; flex: 0 0 auto; }
.st-top-h { display: flex; flex-direction: column; line-height: 1.15; min-width: 0; }
.st-top h1 { font-size: .95rem; margin: 0; font-weight: 600; color: var(--bar-ink); white-space: nowrap; }
.st-sub { color: var(--bar-muted); font-size: .72rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.st-top-badge { margin-left: auto; flex: 0 0 auto; }
.st-view { flex: 1; overflow: auto; padding: var(--sp-5); background: var(--bg); }

@media (max-width: 900px) { .studio-shell { grid-template-columns: 200px 1fr; } }
</style>
