<script setup lang="ts">
// My SourceOS builds — ported from app-vue into the cockpit. Lists builds via the shared
// buildsApi, polls for status, offers the finished ISO. Honest empty/error states.
import { ref, onMounted, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import SurfaceHeader from '../components/SurfaceHeader.vue';
import EmptyState from '../components/EmptyState.vue';
import { listBuilds } from '../services/buildsApi';

interface Build { id: string; status: string; artifact?: string; spec?: { edition?: string; arch?: string; hostname?: string; packages?: string[] } }
const builds = ref<Build[]>([]);
const err = ref(''); const loaded = ref(false);
let timer: ReturnType<typeof setInterval> | null = null;
const router = useRouter();

async function refresh() {
  try { builds.value = ((await listBuilds()) as { builds?: Build[] }).builds ?? []; err.value = ''; }
  catch (e: any) { err.value = e?.message ? String(e.message) : 'Could not reach the builder service.'; }
  finally { loaded.value = true; }
}
const gsToHttps = (u?: string) => (u?.startsWith('gs://') ? 'https://storage.googleapis.com/' + u.slice(5) : u);

onMounted(() => { refresh(); timer = setInterval(refresh, 8000); });
onUnmounted(() => { if (timer) clearInterval(timer); });
</script>

<template>
  <section class="bl" aria-label="SourceOS builds">
    <SurfaceHeader title="My Builds" eyebrow="SourceOS · Builder">
      <template #actions>
        <button class="bl-new" type="button" @click="router.push('/sourceos/image-builder')">+ New build</button>
      </template>
    </SurfaceHeader>

    <p v-if="err" class="bl-err" role="alert">{{ err }}</p>
    <EmptyState v-if="loaded && !builds.length && !err" title="No builds yet" hint="Compose a SourceOS image and it'll appear here with live status and a download link." icon="◇">
      <template #action><button class="bl-new" type="button" @click="router.push('/sourceos/image-builder')">Build your first image</button></template>
    </EmptyState>

    <ul v-else class="bl-list">
      <li v-for="b in builds" :key="b.id" class="bl-row">
        <div class="bl-spec">
          <strong>{{ b.spec?.edition }}</strong> · {{ b.spec?.arch }} · {{ b.spec?.hostname }}
          <div class="bl-pkgs">{{ (b.spec?.packages || []).join(', ') || 'no extra packages' }}</div>
        </div>
        <div class="bl-status">
          <span class="bl-badge" :class="b.status">{{ b.status }}</span>
          <a v-if="b.status === 'complete' && b.artifact" class="bl-dl" :href="gsToHttps(b.artifact)">Download ISO ↓</a>
        </div>
      </li>
    </ul>
  </section>
</template>

<style scoped>
/* Annealed epistemic-Carbon conformance: ONE hairline panel of dense rows separated by
   var(--line), 0.56rem uppercase badges, accent action w/ #17130a ink (db-* vocabulary). */
.bl { height: 100%; min-height: 0; overflow-y: auto; padding: 1rem 1.25rem 2rem; background: var(--bg); color: var(--text); }
.bl-new { font-size: 0.78rem; border: none; color: #17130a; background: var(--accent); border-radius: 8px; padding: 0.4rem 0.85rem; font-weight: 700; cursor: pointer; } .bl-new:hover { filter: brightness(1.06); }
.bl-err { font-size: 0.78rem; color: var(--amber); border: 1px solid rgba(227,179,65,0.3); background: rgba(227,179,65,0.05); border-radius: 8px; padding: 0.5rem 0.7rem; }
.bl-list { list-style: none; margin: 0.9rem 0 0; padding: 0; max-width: 760px; border: 1px solid var(--line); border-radius: var(--radius, 12px); background: var(--surface); overflow: hidden; }
.bl-row { display: flex; align-items: center; justify-content: space-between; gap: 1rem; border-bottom: 1px solid var(--line); padding: 0.55rem 0.85rem; }
.bl-row:last-child { border-bottom: none; } .bl-row:hover { background: var(--surface-2, rgba(255,255,255,0.02)); }
.bl-spec { font-size: 0.85rem; } .bl-spec strong { text-transform: capitalize; }
.bl-pkgs { font-size: 0.72rem; color: var(--text-3); margin-top: 0.15rem; }
.bl-status { text-align: right; display: flex; flex-direction: column; align-items: flex-end; gap: 0.3rem; }
.bl-badge { font-size: 0.56rem; text-transform: uppercase; letter-spacing: 0.03em; font-weight: 700; padding: 0.03rem 0.3rem; border-radius: 4px; color: var(--text-3); border: 1px solid var(--line-2); }
.bl-badge.complete { color: var(--live); border-color: rgba(63,185,80,0.4); background: var(--live-soft); }
.bl-badge.building, .bl-badge.queued { color: var(--amber); border-color: rgba(227,179,65,0.4); }
.bl-badge.failed, .bl-badge.error { color: var(--down); border-color: rgba(240,101,106,0.4); }
.bl-dl { font-size: 0.74rem; color: var(--accent); text-decoration: none; font-weight: 600; } .bl-dl:hover { text-decoration: underline; }
</style>
