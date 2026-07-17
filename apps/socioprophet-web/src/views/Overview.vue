<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { health, graph, type Health } from '../studio/api'
import GygCausalValuationCard from '../components/GygCausalValuationCard.vue'
import ProphetMeshRuntimeReadinessCard from '../components/ProphetMeshRuntimeReadinessCard.vue'
import ChronosEvidenceLoopCard from '../components/ChronosEvidenceLoopCard.vue'

const svc = ref<Health[]>([])
const stats = ref<{ nodes: number; edges: number } | null>(null)
const loading = ref(true)

async function load() {
  loading.value = true
  svc.value = await health()
  try { stats.value = await graph.stats() } catch { stats.value = null }
  loading.value = false
}
onMounted(load)
</script>

<template>
  <div class="grid cols-3">
    <div class="card"><div class="kpi">{{ stats?.nodes ?? '—' }}</div><div class="kpi-l">graph nodes</div></div>
    <div class="card"><div class="kpi">{{ stats?.edges ?? '—' }}</div><div class="kpi-l">graph edges</div></div>
    <div class="card"><div class="kpi">{{ svc.filter(s=>s.ok).length }}/{{ svc.length }}</div><div class="kpi-l">services healthy</div></div>
  </div>

  <div class="card">
    <div class="row" style="justify-content:space-between"><h3>Platform services</h3><button class="btn ghost" @click="load">{{ loading ? '…' : 'Refresh' }}</button></div>
    <p class="desc">Live health of the workbench backends. Every capability below is a real service — not a mock.</p>
    <div class="grid cols-2">
      <div v-for="s in svc" :key="s.name" class="row" style="justify-content:space-between; padding:.5rem .7rem; border:1px solid var(--border); border-radius:8px">
        <span class="mono">{{ s.name }}</span>
        <span class="pill" :class="s.ok ? 'good' : 'bad'">{{ s.ok ? 'healthy' : 'unreachable' }}</span>
      </div>
    </div>
  </div>

  <div class="card">
    <h3>Program readouts</h3>
    <p class="desc">Governed program evidence surfaces.</p>
    <GygCausalValuationCard />
    <ProphetMeshRuntimeReadinessCard />
    <ChronosEvidenceLoopCard />
  </div>
</template>
