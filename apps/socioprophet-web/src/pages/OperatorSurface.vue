<template>
  <section class="op" aria-label="Operator surface">
    <template v-if="def">
      <SurfaceHeader :title="def.title" :eyebrow="def.eyebrow">
        <template #badge>
          <span class="op-status" :class="def.status">{{ statusLabel(def.status) }}</span>
        </template>
        <template #actions>
          <button class="op-ask" type="button" @click="askNoetica">◇ Ask Noetica</button>
        </template>
      </SurfaceHeader>

      <p class="op-blurb">{{ def.blurb }}</p>

      <div class="op-served">
        <InfoLabel label="Served by" info="Where this surface actually runs. Operator/compute/identity surfaces live in the Noetica app + standalone repos; this cockpit surfaces them in one place." />
        <code>{{ def.servedBy }}</code>
        <a v-if="def.repo" class="op-repo" :href="`https://github.com/${def.repo}`" target="_blank" rel="noreferrer">{{ def.repo }} ↗</a>
      </div>

      <div class="op-caps">
        <article v-for="c in def.capabilities" :key="c.label" class="op-cap">
          <div class="op-cap-h">{{ c.label }}</div>
          <p class="op-cap-d">{{ c.detail }}</p>
        </article>
      </div>

      <!-- Data Catalog: every source registered with its live-adapter status -->
      <div v-if="def.id === 'data-catalog'" class="op-catalog">
        <div class="op-cat-summary">
          <span class="op-cat-pill live">{{ liveCount }} live</span>
          <span class="op-cat-pill fixture">{{ fixtureCount }} fixture</span>
          <span class="op-cat-pill planned">{{ plannedCount }} planned adapter</span>
        </div>
        <div class="op-table-wrap">
          <table class="op-table">
            <thead><tr><th>Source</th><th>Domain</th><th>Upstream</th><th>Feeds</th><th>Status</th></tr></thead>
            <tbody>
              <tr v-for="s in sources" :key="s.id">
                <td class="op-td-name">{{ s.name }}</td>
                <td>{{ s.domain }}</td>
                <td class="op-td-up">{{ s.upstream }}</td>
                <td class="op-td-feeds">{{ s.feeds.join(', ') }}</td>
                <td><span class="op-src-status" :class="s.status">{{ s.status }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <p class="op-note">
        <template v-if="def.status === 'in-noetica'">This surface is implemented in the Noetica app and reachable from here; a native cockpit port is on the roadmap.</template>
        <template v-else-if="def.status === 'standalone'">This capability lives in a standalone repo. It's referenced by the platform but not yet embedded in the cockpit.</template>
        <template v-else>Wired natively into the cockpit.</template>
      </p>
    </template>

    <EmptyState v-else icon="◇" title="Unknown surface" hint="That operator surface isn't registered. Pick one from the Operator & Infra menu." />
  </section>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue';
import { useRoute } from 'vue-router';
import SurfaceHeader from '../components/SurfaceHeader.vue';
import InfoLabel from '../components/InfoLabel.vue';
import EmptyState from '../components/EmptyState.vue';
import { operatorSurfaceById, type SurfaceStatus } from '../data/operatorSurfaces';
import { DATA_SOURCES } from '../data/dataSources';
import { useCockpit } from '../stores/cockpit';

const route = useRoute();
const cockpit = useCockpit();
const def = computed(() => operatorSurfaceById(String(route.params.id ?? '')));
const sources = DATA_SOURCES;
const liveCount = sources.filter((s) => s.status === 'live').length;
const fixtureCount = sources.filter((s) => s.status === 'fixture').length;
const plannedCount = sources.filter((s) => s.status === 'planned').length;
const statusLabel = (s: SurfaceStatus): string => (s === 'in-noetica' ? 'in Noetica' : s === 'standalone' ? 'standalone repo' : 'wired');
function askNoetica() {
  if (!def.value) return;
  cockpit.askAbout(`Explain the ${def.value.title} surface (${def.value.eyebrow}): ${def.value.blurb} What can I do with it and how does it connect to the rest of the platform?`);
}
watch(def, (d) => { if (d) cockpit.setContext({ surface: d.title, entityLabel: d.eyebrow, detail: d.servedBy, route: route.path }); }, { immediate: true });
</script>

<style scoped>
.op { height: 100%; min-height: 0; overflow-y: auto; display: flex; flex-direction: column; gap: 1rem; padding: 1rem 1.25rem 1.5rem; background: var(--bg); color: var(--text); }
.op-status { font-size: 0.58rem; text-transform: uppercase; letter-spacing: 0.06em; font-weight: 700; border-radius: 5px; padding: 0.1rem 0.4rem; }
.op-status.in-noetica { color: #93c5fd; background: rgba(88, 166, 255, 0.16); }
.op-status.standalone { color: #e3b341; background: rgba(227, 179, 65, 0.16); }
.op-status.wired { color: var(--up); background: rgba(63, 185, 80, 0.16); }
.op-ask { border: 1px solid rgba(120, 160, 255, 0.45); background: rgba(120, 160, 255, 0.08); color: #93b4ff; border-radius: 8px; padding: 0.35rem 0.7rem; font-size: 0.76rem; cursor: pointer; } .op-ask:hover { background: rgba(120, 160, 255, 0.16); color: #fff; }
.op-blurb { margin: 0; max-width: 68ch; font-size: 0.95rem; line-height: 1.6; color: var(--text-2); }
.op-served { display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap; font-size: 0.78rem; color: var(--text-3); border: 1px solid var(--line-2); border-radius: 10px; padding: 0.6rem 0.85rem; background: var(--surface); }
.op-served code { color: var(--text); font-family: ui-monospace, monospace; }
.op-repo { color: var(--accent); text-decoration: none; margin-left: auto; } .op-repo:hover { text-decoration: underline; }
.op-caps { display: grid; grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr)); gap: 0.7rem; }
.op-cap { border: 1px solid var(--line-2); border-radius: 12px; padding: 0.8rem 0.9rem; background: var(--surface); }
.op-cap-h { font-size: 0.86rem; font-weight: 640; color: var(--text); }
.op-cap-d { margin: 0.3rem 0 0; font-size: 0.8rem; line-height: 1.5; color: var(--text-2); }
.op-note { margin: 0; font-size: 0.76rem; color: var(--text-3); line-height: 1.5; border-top: 1px solid var(--line); padding-top: 0.8rem; }
.op-catalog { display: flex; flex-direction: column; gap: 0.6rem; }
.op-cat-summary { display: flex; gap: 0.4rem; }
.op-cat-pill { font-size: 0.64rem; text-transform: uppercase; letter-spacing: 0.04em; font-weight: 700; border-radius: 999px; padding: 0.15rem 0.55rem; }
.op-cat-pill.live { color: #7ee2a8; background: rgba(75, 191, 115, 0.14); } .op-cat-pill.fixture { color: #f0c987; background: rgba(227, 179, 65, 0.14); } .op-cat-pill.planned { color: #93b4ff; background: rgba(120, 160, 255, 0.14); }
.op-table-wrap { overflow-x: auto; border: 1px solid var(--line-2); border-radius: 10px; }
.op-table { width: 100%; border-collapse: collapse; font-size: 0.76rem; }
.op-table th { text-align: left; padding: 0.5rem 0.7rem; font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-3); border-bottom: 1px solid var(--line-2); background: var(--surface-2); position: sticky; top: 0; }
.op-table td { padding: 0.5rem 0.7rem; border-bottom: 1px solid var(--line); color: var(--text-2); vertical-align: top; }
.op-td-name { color: var(--text); font-weight: 600; white-space: nowrap; }
.op-td-up, .op-td-feeds { color: var(--text-3); font-size: 0.72rem; }
.op-src-status { font-size: 0.58rem; text-transform: uppercase; letter-spacing: 0.04em; font-weight: 700; border-radius: 5px; padding: 0.05rem 0.4rem; white-space: nowrap; }
.op-src-status.live { color: #7ee2a8; background: rgba(75, 191, 115, 0.14); } .op-src-status.fixture { color: #f0c987; background: rgba(227, 179, 65, 0.14); } .op-src-status.planned { color: #93b4ff; background: rgba(120, 160, 255, 0.14); }
</style>
