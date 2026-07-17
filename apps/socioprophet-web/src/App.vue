<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import './studio/studio.css'
import Overview from './views/Overview.vue'
import GraphExplorer from './views/GraphExplorer.vue'
import QueryConsole from './views/QueryConsole.vue'
import Analytics from './views/Analytics.vue'
import GraphRAG from './views/GraphRAG.vue'
import Reasoner from './views/Reasoner.vue'
import EntityResolution from './views/EntityResolution.vue'
import ResourceBrowser from './views/ResourceBrowser.vue'
import Ontology from './views/Ontology.vue'

const NAV = [
  { group: 'Explore', items: [
    { id: 'overview', label: 'Overview', ic: '◱', comp: Overview, sub: 'Platform health & program readouts' },
    { id: 'explorer', label: 'Graph Explorer', ic: '⟡', comp: GraphExplorer, sub: 'Force-directed graph + provenance inspector' },
    { id: 'resource', label: 'Resource Browser', ic: '◈', comp: ResourceBrowser, sub: 'Dereferenceable Linked Data' },
  ]},
  { group: 'Query & Analyze', items: [
    { id: 'query', label: 'Query Console', ic: '⌘', comp: QueryConsole, sub: 'SPARQL · Cypher · Gremlin' },
    { id: 'analytics', label: 'Analytics', ic: '📈', comp: Analytics, sub: 'PageRank / components on the Rust kernel' },
    { id: 'graphrag', label: 'GraphRAG', ic: '✦', comp: GraphRAG, sub: 'Ask the graph, cited answers' },
  ]},
  { group: 'Reason & Resolve', items: [
    { id: 'reasoner', label: 'Reasoner', ic: '⊢', comp: Reasoner, sub: 'RDFS/OWL entailment + proof trees' },
    { id: 'er', label: 'Entity Resolution', ic: '⚭', comp: EntityResolution, sub: 'Proof-carrying record linkage' },
    { id: 'ontology', label: 'Ontology', ic: '❖', comp: Ontology, sub: 'Docs + TBox graph' },
  ]},
]
const flat = NAV.flatMap((g) => g.items)
const current = ref('overview')
const active = computed(() => flat.find((i) => i.id === current.value) ?? flat[0])

function route() {
  const id = location.hash.replace(/^#/, '').split(':')[0]
  if (flat.some((i) => i.id === id)) current.value = id
}
function go(id: string) { location.hash = id; current.value = id }
onMounted(() => { route(); window.addEventListener('hashchange', route) })
onBeforeUnmount(() => window.removeEventListener('hashchange', route))
</script>

<template>
  <div class="studio">
    <aside class="sidebar">
      <div class="brand">
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="var(--accent)" stroke-width="1.6"/><path d="M7 12h10M12 7v10" stroke="var(--accent)" stroke-width="1.6"/></svg>
        <div><b>Prophet Studio</b><br><small>sovereign data + AI platform</small></div>
      </div>
      <nav class="nav">
        <template v-for="g in NAV" :key="g.group">
          <div class="nav-group">{{ g.group }}</div>
          <a v-for="i in g.items" :key="i.id" :class="{ active: current === i.id }" @click="go(i.id)">
            <span class="ic">{{ i.ic }}</span>{{ i.label }}
          </a>
        </template>
      </nav>
      <div class="foot">Every panel is a live service — proof-carrying, sovereign.</div>
    </aside>

    <div class="main">
      <div class="topbar">
        <h1>{{ active.label }}</h1>
        <span class="sub">{{ active.sub }}</span>
        <span class="spacer"></span>
        <span class="pill accent">prophet-platform</span>
      </div>
      <div class="view"><component :is="active.comp" :key="active.id" /></div>
    </div>
  </div>
</template>
