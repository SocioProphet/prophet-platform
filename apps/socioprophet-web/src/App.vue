<script setup lang="ts">
import { ref, onMounted } from 'vue'

const status = ref<'idle'|'ok'|'err'>('idle')
const pong = ref('')

async function check() {
  try {
    const res = await fetch('/api/health')
    const j = await res.json()
    status.value = j.ok ? 'ok' : 'err'
    pong.value = j.pong || ''
  } catch (e) {
    status.value = 'err'
    pong.value = ''
  }
}
onMounted(check)
</script>

<template>
  <main style="font-family: ui-sans-serif, system-ui; padding: 2rem; max-width: 920px; margin: 0 auto;">
    <header style="display:flex; align-items:center; gap:0.75rem; margin-bottom: 1rem;">
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="1.5"/>
        <path d="M7 12h10M12 7v10" stroke="currentColor" stroke-width="1.5"/>
      </svg>
      <h1 style="font-size: 1.5rem; font-weight: 700;">SocioProphet</h1>
      <span v-if="status==='ok'" style="margin-left:auto; padding:0.2rem 0.5rem; border-radius:999px; border:1px solid #cbd5e1;">Connected</span>
      <span v-else-if="status==='err'" style="margin-left:auto; padding:0.2rem 0.5rem; border-radius:999px; border:1px solid #cbd5e1;">Disconnected</span>
      <span v-else style="margin-left:auto; padding:0.2rem 0.5rem; border-radius:999px; border:1px solid #cbd5e1;">Checking…</span>
    </header>

    <section style="border:1px solid #e2e8f0; border-radius: 12px; padding: 1rem;">
      <h2 style="font-size:1.1rem; font-weight:600; margin:0 0 .5rem 0;">Health</h2>
      <p style="margin:0 0 1rem 0;">Gateway → TritRPC/UDS check. Expect <code>PONG</code>.</p>
      <div style="display:flex; gap:.5rem; align-items:center;">
        <button @click="check" style="padding:.4rem .8rem; border:1px solid #cbd5e1; border-radius:8px; background:white;">Recheck</button>
        <code>{{ pong.trim() }}</code>
      </div>
    </section>
  </main>
</template>
