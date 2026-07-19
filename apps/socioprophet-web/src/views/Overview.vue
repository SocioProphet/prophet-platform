<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { health, graph, type Health } from '../studio/api'
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
    <p class="desc">Governed program evidence surfaces. Each program opens as its own workbench surface.</p>
    <a class="program-index row" href="#causal">
      <div>
        <b>Causal Valuation — Guzman y Gomez (ASX:GYG)</b>
        <div class="desc">Supply-chain causal graph → economic-prophet value-driver tree → enterprise value.</div>
      </div>
      <span class="pill accent">Open →</span>
    </a>
    <ProphetMeshRuntimeReadinessCard />
    <ChronosEvidenceLoopCard />
  </div>
</template>

<style scoped>
.program-index { justify-content: space-between; gap: 1rem; padding: .8rem .9rem; border: 1px solid var(--border); border-radius: 10px; text-decoration: none; color: inherit; cursor: pointer; transition: border-color .15s, background .15s; }
.program-index:hover { border-color: var(--accent); background: rgba(255,255,255,.02); }
</style>
