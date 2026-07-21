<script setup lang="ts">
// Agora — the work + knowledge plane, on the token spine. A kanban board (the Jira side) + a wiki
// page list (the Confluence side) + teams, all read live from the deployed agora service. Every card
// and page is a proof-carrying graph fact, so each card carries its epistemic stripe and the whole
// plane is citable/preservable via the commons — the sovereign difference from Jira/Confluence.
// Reads are open; creating a work item uses the agora-write-token (Bearer).
import { ref, onMounted, computed } from 'vue';
import { loadAgora, createWork, WORK_STATUSES, WORK_TYPES, type AgoraBundle, type WorkItem } from '../services/agoraApi';
import { EPISTEMIC_COLORS } from '../services/studioApi';
import './studio/studio-tokens.css';

const bundle = ref<AgoraBundle | null>(null);
const loading = ref(true);
const err = ref('');
const token = ref('');
const flash = ref('');
function say(m: string) { flash.value = m; setTimeout(() => (flash.value = ''), 2800); }

async function load() {
  loading.value = true; err.value = '';
  try { bundle.value = await loadAgora('default'); }
  catch (e) { err.value = e instanceof Error ? e.message : 'failed to load Agora'; }
  finally { loading.value = false; }
}
onMounted(load);

const STATUS_LABEL: Record<string, string> = { backlog: 'Backlog', todo: 'To do', in_progress: 'In progress', in_review: 'In review', done: 'Done', cancelled: 'Cancelled' };
function epi(mode?: string): string { return EPISTEMIC_COLORS[mode || 'attested'] || 'var(--epi-unknown)'; }
function col(status: string): WorkItem[] { return bundle.value?.board.columns[status] ?? []; }
const activeStatuses = computed(() => WORK_STATUSES.filter((s) => s !== 'cancelled' || col('cancelled').length));

// create
const nwOpen = ref(false);
const nw = ref<{ title: string; type: string; status: string }>({ title: '', type: 'task', status: 'backlog' });
const creating = ref(false);
async function addWork() {
  if (!nw.value.title.trim()) return;
  creating.value = true;
  try {
    const r = await createWork({ title: nw.value.title.trim(), type: nw.value.type, status: nw.value.status, actor: 'cockpit' }, token.value);
    say(`Created ${r.title} → ${r.status}`); nw.value.title = ''; nwOpen.value = false; await load();
  } catch (e) { say(e instanceof Error ? e.message : 'create failed'); }
  finally { creating.value = false; }
}
</script>

<template>
  <div class="studio-scope agora">
    <header class="ag-top">
      <div class="ag-h">
        <span class="ag-mark">▤</span>
        <div><h1>Agora</h1><span class="ag-sub">work + knowledge plane · sovereign, proof-carrying</span></div>
      </div>
      <div class="ag-stats" v-if="bundle">
        <span class="stat"><b class="tnum">{{ bundle.stats.work_items }}</b> work</span>
        <span class="stat"><b class="tnum">{{ bundle.stats.pages }}</b> pages</span>
        <span class="stat"><b class="tnum">{{ bundle.stats.teams }}</b> teams</span>
      </div>
      <div class="ag-actions">
        <input v-model="token" type="password" class="tok" placeholder="write token" title="agora-write-token — required to create" />
        <button class="btn" @click="nwOpen = !nwOpen">+ New work</button>
        <button class="ghost" @click="load" :disabled="loading" aria-label="Reload">↻</button>
      </div>
    </header>

    <p v-if="flash" class="flash">{{ flash }}</p>
    <div v-if="nwOpen" class="nw">
      <input v-model="nw.title" class="j" placeholder="work item title…" @keyup.enter="addWork" />
      <select v-model="nw.type" class="j"><option v-for="t in WORK_TYPES" :key="t" :value="t">{{ t }}</option></select>
      <select v-model="nw.status" class="j"><option v-for="s in WORK_STATUSES" :key="s" :value="s">{{ STATUS_LABEL[s] }}</option></select>
      <button class="btn" @click="addWork" :disabled="creating || !nw.title.trim()">{{ creating ? '…' : 'Add' }}</button>
    </div>

    <p v-if="err" class="msg err">{{ err }}</p>
    <p v-else-if="loading" class="msg">Loading Agora…</p>

    <template v-else-if="bundle">
      <p v-if="bundle.degraded" class="msg warn">Degraded: {{ bundle.degraded }}</p>

      <!-- Kanban board -->
      <div class="board" role="list">
        <section v-for="s in activeStatuses" :key="s" class="lane" role="listitem">
          <header class="lane-h"><span>{{ STATUS_LABEL[s] }}</span><span class="lane-n tnum">{{ col(s).length }}</span></header>
          <div class="lane-body">
            <article v-for="w in col(s)" :key="w.work_id" class="wcard epi-stripe" :style="{ '--epi': epi(w.epistemic_mode) }">
              <div class="wc-top"><span class="wtype" :class="w.type">{{ w.type }}</span><span v-if="w.priority" class="wprio">{{ w.priority }}</span></div>
              <div class="wc-title">{{ w.title }}</div>
              <div class="wc-meta">
                <span v-if="w.assignee" class="wa" :title="'assignee'">{{ w.assignee }}</span>
                <span v-if="w.team" class="wteam">{{ w.team }}</span>
                <span class="epi-chip wc-epi" :style="{ '--epi': epi(w.epistemic_mode), '--epi-wash': 'transparent' }">{{ w.epistemic_mode }}</span>
              </div>
              <div v-if="w.tags.length" class="wc-tags"><i v-for="t in w.tags" :key="t">{{ t }}</i></div>
            </article>
            <p v-if="!col(s).length" class="lane-empty">—</p>
          </div>
        </section>
      </div>

      <!-- Wiki + teams -->
      <div class="ag-lower">
        <section class="panel">
          <header class="p-h">Wiki<span class="p-n tnum">{{ bundle.pages.length }}</span></header>
          <ul class="pages" v-if="bundle.pages.length">
            <li v-for="pg in bundle.pages" :key="pg.page_id">
              <span class="pg-t">{{ pg.title }}</span>
              <span v-if="pg.parent" class="pg-p">⌐ {{ pg.parent }}</span>
              <span class="pg-u">{{ pg.updated_at }}</span>
            </li>
          </ul>
          <p v-else class="lane-empty">No pages yet.</p>
        </section>
        <section class="panel">
          <header class="p-h">Teams<span class="p-n tnum">{{ bundle.teams.length }}</span></header>
          <ul class="teams" v-if="bundle.teams.length">
            <li v-for="t in bundle.teams" :key="t.team_id"><b>{{ t.name }}</b><span class="tm">{{ t.members.join(', ') || 'no members' }}</span></li>
          </ul>
          <p v-else class="lane-empty">No teams yet.</p>
        </section>
      </div>

      <p class="commons">◈ {{ bundle.commons.note }}.</p>
    </template>
  </div>
</template>

<style scoped>
.agora { font: 14px/1.5 var(--ui); color: var(--ink); background: var(--bg); min-height: 100%; padding: var(--sp-4) var(--sp-5); }
.agora :focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: var(--r-1); }
.ag-top { display: flex; align-items: center; gap: var(--sp-4); flex-wrap: wrap; margin-bottom: var(--sp-4); }
.ag-h { display: flex; align-items: center; gap: var(--sp-3); }
.ag-mark { color: var(--accent); font-size: 1.2rem; }
.ag-h h1 { margin: 0; font-size: 1.15rem; } .ag-sub { color: var(--muted); font-size: .78rem; }
.ag-stats { display: flex; gap: var(--sp-3); }
.stat { font-size: 12px; color: var(--muted); } .stat b { color: var(--ink); font-size: 15px; margin-right: 3px; }
.ag-actions { display: flex; gap: 6px; align-items: center; margin-left: auto; }
.tok { border: 1px solid var(--hairline-strong); border-radius: var(--r-2); padding: 6px 8px; font-size: 13px; width: 120px; background: var(--surface); color: var(--ink); }
.btn { border: 1px solid var(--accent); background: var(--accent); color: #04122e; border-radius: var(--r-2); padding: 6px 12px; font-size: 13px; font-weight: 600; cursor: pointer; } .btn:disabled { opacity: .55; }
.ghost { border: 1px solid var(--hairline-strong); background: var(--surface); color: var(--ink-2); border-radius: var(--r-2); width: 30px; height: 30px; cursor: pointer; }
.flash { background: var(--ok-wash); color: var(--ok); border-radius: var(--r-2); padding: 6px 11px; font-size: 12.5px; margin: 0 0 10px; }
.nw { display: flex; gap: 6px; margin-bottom: var(--sp-3); flex-wrap: wrap; }
.j { border: 1px solid var(--hairline-strong); border-radius: var(--r-2); padding: 6px 8px; font-size: 13px; background: var(--surface); color: var(--ink); } .nw .j:first-child { flex: 1; min-width: 180px; }
.msg { color: var(--muted); } .msg.err { color: var(--fail); } .msg.warn { color: var(--warn); }

.board { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(210px, 1fr); gap: var(--sp-3); overflow-x: auto; padding-bottom: var(--sp-2); }
.lane { background: var(--sunken); border: 1px solid var(--hairline); border-radius: var(--r-3); display: flex; flex-direction: column; min-height: 120px; }
.lane-h { display: flex; align-items: center; justify-content: space-between; padding: 8px 10px; border-bottom: 1px solid var(--hairline); font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: var(--muted); }
.lane-n { background: var(--surface); border-radius: var(--pill); padding: 0 7px; color: var(--ink-2); }
.lane-body { display: flex; flex-direction: column; gap: 6px; padding: 8px; overflow-y: auto; }
.wcard { background: var(--surface); border: 1px solid var(--hairline); border-radius: var(--r-2); padding: 8px 10px 8px 12px; }
.wcard:hover { border-color: var(--hairline-strong); }
.wc-top { display: flex; align-items: center; gap: 6px; margin-bottom: 3px; }
.wtype { font-size: 9.5px; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); border: 1px solid var(--hairline-strong); border-radius: var(--r-1); padding: 0 5px; }
.wtype.bug { color: var(--fail); border-color: color-mix(in srgb, var(--fail) 40%, var(--hairline)); }
.wtype.epic { color: var(--epi-derived); border-color: color-mix(in srgb, var(--epi-derived) 40%, var(--hairline)); }
.wtype.milestone { color: var(--epi-attested); border-color: color-mix(in srgb, var(--epi-attested) 40%, var(--hairline)); }
.wprio { margin-left: auto; font-size: 9.5px; color: var(--warn); text-transform: uppercase; }
.wc-title { font-size: 13px; font-weight: 600; color: var(--ink); line-height: 1.35; }
.wc-meta { display: flex; align-items: center; gap: 6px; margin-top: 5px; flex-wrap: wrap; }
.wa { font-size: 10.5px; color: var(--ink-2); background: var(--sunken); border-radius: var(--pill); padding: 0 7px; }
.wteam { font-size: 10.5px; color: var(--muted); }
.wc-epi { margin-left: auto; }
.wc-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 5px; }
.wc-tags i { font-style: normal; font-size: 9.5px; color: var(--muted); background: var(--sunken); border-radius: var(--r-1); padding: 0 5px; }
.lane-empty { color: var(--faint); font-size: 12px; text-align: center; padding: 6px; }

.ag-lower { display: grid; grid-template-columns: 2fr 1fr; gap: var(--sp-3); margin-top: var(--sp-4); }
@media (max-width: 820px) { .ag-lower { grid-template-columns: 1fr; } }
.panel { border: 1px solid var(--hairline); border-radius: var(--r-3); background: var(--surface); }
.p-h { display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; border-bottom: 1px solid var(--hairline); font-size: 12px; font-weight: 600; }
.p-n { color: var(--muted); font-weight: 400; }
.pages, .teams { list-style: none; margin: 0; padding: 6px; display: flex; flex-direction: column; gap: 2px; }
.pages li { display: flex; align-items: baseline; gap: 8px; padding: 5px 8px; border-radius: var(--r-2); } .pages li:hover { background: var(--sunken); }
.pg-t { font-size: 13px; color: var(--ink); } .pg-p { font-size: 10.5px; color: var(--muted); } .pg-u { margin-left: auto; font-size: 10px; color: var(--faint); }
.teams li { display: flex; flex-direction: column; padding: 5px 8px; } .teams b { font-size: 13px; } .tm { font-size: 11px; color: var(--muted); }
.commons { margin-top: var(--sp-4); font-size: 12px; color: var(--muted); border-top: 1px solid var(--hairline); padding-top: var(--sp-3); }
</style>
