<script setup lang="ts">
// Data catalog — a dense, scannable inventory of the project's datasets. Every row carries the two
// things a sovereign catalog has that a bolt-on catalog (Purview/Collibra) doesn't: an epistemic
// stripe (the row's proof-status, the moat made visible) and provenance-native fields. Density +
// tabular alignment (Tufte), an inline ingest-volume sparkline per row, and a real connector facet.
// Backed by the live catalog (studioApi.loadCatalog → /svc dashboard-bff) with a fixture fallback.
import { ref, computed, onMounted, watch } from 'vue';
import { loadCatalog, EPISTEMIC_COLORS, type Dataset } from '../../services/studioApi';
import Sparkline from '../../components/Sparkline.vue';
import FactsheetDrawer from './FactsheetDrawer.vue';

const props = defineProps<{ project: string }>();

const datasets = ref<Dataset[]>([]);
const loading = ref(true);
const err = ref('');
const facet = ref<string>('all');       // connector filter
const sheet = ref<Dataset | null>(null); // dataset whose factsheet drawer is open

async function load() {
  loading.value = true; err.value = '';
  try { datasets.value = (await loadCatalog(props.project)).datasets; }
  catch (e) { err.value = e instanceof Error ? e.message : 'failed to load catalog'; }
  finally { loading.value = false; }
}
onMounted(load);
watch(() => props.project, load);

function color(mode?: string): string { return EPISTEMIC_COLORS[mode || 'observed'] || 'var(--epi-unknown)'; }

// Distinct connectors present → a real facet bar (not invented).
const connectors = computed(() => {
  const s = new Set<string>();
  for (const d of datasets.value) if (d.connector) s.add(d.connector);
  return [...s].sort();
});
// Epistemic modes present → a legend built from the actual data.
const modes = computed(() => {
  const s = new Set<string>();
  for (const d of datasets.value) s.add(d.epistemic_mode || 'observed');
  return [...s];
});
const shown = computed(() => facet.value === 'all' ? datasets.value : datasets.value.filter((d) => d.connector === facet.value));

// Ingest-volume series: live from volume_trend when the backend provides it, else a deterministic
// demo series derived from the dataset id (stable across renders, clearly marked ~ in the header).
function demoSeries(id: string): number[] {
  let h = 2166136261;
  for (let i = 0; i < id.length; i++) { h ^= id.charCodeAt(i); h = Math.imul(h, 16777619); }
  const out: number[] = []; let v = 40 + (Math.abs(h) % 40);
  for (let i = 0; i < 14; i++) { h = Math.imul(h ^ (h >>> 13), 16777619); v = Math.max(6, v + ((Math.abs(h) % 21) - 9)); out.push(v); }
  return out;
}
function series(d: Dataset): number[] { return d.volume_trend?.length ? d.volume_trend : demoSeries(d.id); }
function isLive(d: Dataset): boolean { return !!d.volume_trend?.length; }
function last(s: number[]): number { return s[s.length - 1] ?? 0; }
function openSheet(d: Dataset) { sheet.value = d; }

// Attested factsheet — a deterministic, recomputable summary built from the dataset's OWN facts
// (not model-generated prose), with a content-id receipt = a hash of those facts. Honest "attested
// AI": the attestation is real (recompute the hash to verify), the text is extractive/templated.
function djb2(s: string): string { let h = 5381; for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) & 0xffffffff; return (h >>> 0).toString(16).padStart(8, '0'); }
function attest(d: Dataset): { summary: string; receipt: string; live: boolean } {
  const s = series(d);
  const dir = s.length > 1 ? (s[s.length - 1] > s[0] ? 'rising' : s[s.length - 1] < s[0] ? 'falling' : 'flat') : 'flat';
  const summary = `${d.name} is a ${d.epistemic_mode} dataset${d.connector ? ` ingested via ${d.connector}` : ''} with ${d.columns.length} column${d.columns.length === 1 ? '' : 's'}${d.labels.length ? ` (${d.labels.join(', ')})` : ''}. Ingest volume is ${dir} across the ${s.length} most recent snapshots.`;
  const receipt = `fs-${djb2([d.id, d.connector || '', d.epistemic_mode, String(d.columns.length), dir].join('|'))}`;
  return { summary, receipt, live: isLive(d) };
}
</script>

<template>
  <div class="cat">
    <div class="cbar">
      <div class="facets">
        <button class="facet" :class="{ on: facet === 'all' }" @click="facet = 'all'">All <i>{{ datasets.length }}</i></button>
        <button v-for="c in connectors" :key="c" class="facet" :class="{ on: facet === c }" @click="facet = c">{{ c }}</button>
      </div>
      <div class="legend">
        <span v-for="m in modes" :key="m" class="lg"><i class="epi-dot" :style="{ '--epi': color(m) }" />{{ m }}</span>
      </div>
      <button class="ghost" @click="load" :disabled="loading" title="reload" aria-label="Reload catalog">↻</button>
    </div>

    <p v-if="err" class="msg err">{{ err }}</p>
    <p v-else-if="loading" class="msg">Loading catalog…</p>
    <p v-else-if="!shown.length" class="msg">No datasets{{ facet !== 'all' ? ' for ' + facet : '' }}.</p>

    <div v-else class="ctbl" role="table" aria-label="Datasets">
      <div class="chead" role="row">
        <span role="columnheader">Dataset</span>
        <span role="columnheader">Connector</span>
        <span role="columnheader" class="num">Cols</span>
        <span role="columnheader">Status</span>
        <span role="columnheader" class="num">Ingest volume</span>
      </div>
      <div v-for="d in shown" :key="d.id" class="crow-wrap">
        <div class="crow epi-stripe" role="row" :style="{ '--epi': color(d.epistemic_mode) }">
          <span class="c-nm" role="cell">
            <button class="nm-btn" @click="openSheet(d)" title="Open factsheet">
              <b>{{ d.name }}</b>
              <span class="labels"><i v-for="l in d.labels" :key="l" class="lbl">{{ l }}</i></span>
            </button>
          </span>
          <span class="c-cn" role="cell"><span v-if="d.connector" class="pill">{{ d.connector }}</span><span v-else class="dash">—</span></span>
          <span class="c-co num tnum" role="cell">{{ d.columns.length }}</span>
          <span class="c-ep" role="cell"><span class="epi-chip" :style="{ '--epi': color(d.epistemic_mode), '--epi-wash': 'transparent' }">{{ d.epistemic_mode }}</span></span>
          <span class="c-sp num" role="cell">
            <Sparkline :series="series(d)" :w="72" :h="20" tone="accent" />
            <span class="spv tnum" :title="isLive(d) ? 'live ingest volume' : 'demo series — backend volume_trend not yet supplied'">{{ isLive(d) ? '' : '~' }}{{ last(series(d)) }}</span>
          </span>
        </div>
      </div>
    </div>

    <FactsheetDrawer :open="!!sheet" :title="sheet?.name" :eyebrow="sheet?.connector ? ('dataset · ' + sheet.connector) : 'dataset'" @close="sheet = null">
      <template v-if="sheet">
        <div class="fs-top">
          <span class="epi-chip" :style="{ '--epi': color(sheet.epistemic_mode), '--epi-wash': 'transparent' }">{{ sheet.epistemic_mode }}</span>
          <code class="fs-id">{{ sheet.id }}</code>
        </div>
        <div class="fs-facts">
          <div class="fct"><span class="fk">Connector</span><span class="fv">{{ sheet.connector || '—' }}</span></div>
          <div class="fct"><span class="fk">Columns</span><span class="fv tnum">{{ sheet.columns.length }}</span></div>
          <div class="fct"><span class="fk">Labels</span><span class="fv">{{ sheet.labels.join(', ') || '—' }}</span></div>
          <div class="fct"><span class="fk">Ingest</span><span class="fv sp"><Sparkline :series="series(sheet)" :w="90" :h="22" tone="accent" /><b class="tnum">{{ isLive(sheet) ? '' : '~' }}{{ last(series(sheet)) }}</b></span></div>
        </div>
        <div class="fs-sec"><h4>Schema</h4><div class="fs-cols"><code v-for="c in sheet.columns" :key="c">{{ c }}</code></div></div>
        <div class="fs-sec attested">
          <h4>Attested factsheet <span class="att-chip" title="deterministic · recomputable">▪ {{ attest(sheet).receipt }}</span></h4>
          <p class="att-text">{{ attest(sheet).summary }}</p>
          <span class="att-note">Computed from the dataset's own facts — deterministic + recomputable (the receipt is a hash of those facts), not model-generated prose. {{ attest(sheet).live ? 'Ingest volume is live.' : 'Ingest volume is a demo series until the backend supplies volume_trend.' }}</span>
        </div>
      </template>
    </FactsheetDrawer>

    <p class="foot">Datasets are proof-carrying graph nodes — provenance + epistemic status are native fields, not a bolt-on catalog. The stripe on each row is its epistemic mode; the sparkline is ingest volume ({{ '~' }} = demo until the backend supplies <code>volume_trend</code>).</p>
  </div>
</template>

<style scoped>
.cat { font: 14px/1.5 var(--ui); color: var(--ink); }
.cat :focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: var(--r-1); }
.cbar { display: flex; align-items: center; gap: var(--sp-3); margin-bottom: var(--sp-3); flex-wrap: wrap; }
.facets { display: flex; gap: var(--sp-1); flex-wrap: wrap; }
.facet { border: 1px solid var(--hairline); background: var(--surface); color: var(--muted); border-radius: var(--pill); padding: 3px 10px; font-size: 12px; cursor: pointer; }
.facet:hover { color: var(--ink); border-color: var(--hairline-strong); }
.facet.on { color: var(--accent-ink); background: var(--accent-wash); border-color: var(--accent); }
.facet i { font-style: normal; color: var(--faint); margin-left: 4px; font-variant-numeric: tabular-nums; }
.legend { display: flex; gap: var(--sp-3); margin-left: auto; flex-wrap: wrap; }
.lg { display: inline-flex; align-items: center; gap: 5px; font-size: 11px; color: var(--muted); text-transform: capitalize; }
.ghost { border: 1px solid var(--hairline-strong); background: var(--surface); color: var(--ink-2); border-radius: var(--r-2); width: 30px; height: 30px; cursor: pointer; }

.msg { color: var(--muted); } .msg.err { color: var(--fail); }

.ctbl { border: 1px solid var(--hairline); border-radius: var(--r-3); overflow: hidden; }
.chead, .crow { display: grid; grid-template-columns: minmax(200px, 2fr) 1fr 64px 1.1fr 1.3fr; align-items: center; gap: var(--sp-3); }
.chead { padding: var(--sp-2) var(--sp-4); background: var(--sunken); border-bottom: 1px solid var(--hairline); }
.chead span { font-size: 10.5px; text-transform: uppercase; letter-spacing: .07em; color: var(--faint); }
.chead .num, .crow .num { text-align: right; justify-self: end; }
.crow-wrap { border-bottom: 1px solid var(--hairline); }
.crow-wrap:last-child { border-bottom: 0; }
.crow { padding: var(--sp-2) var(--sp-4) var(--sp-2) calc(var(--sp-4) + 3px); min-height: 34px; } /* +3px clears the epi-stripe */
.crow:hover { background: var(--surface-2); }
.nm-btn { display: flex; align-items: baseline; gap: var(--sp-2); background: none; border: 0; padding: 0; color: inherit; cursor: pointer; text-align: left; min-width: 0; }
.nm-btn b { font-size: 13px; font-weight: 600; }
.labels { display: inline-flex; gap: 4px; flex-wrap: wrap; }
.lbl { font-style: normal; font-size: 9.5px; text-transform: uppercase; letter-spacing: .04em; color: var(--faint); border: 1px solid var(--hairline); border-radius: var(--r-1); padding: 0 4px; }
.pill { font-size: 10.5px; background: var(--hairline); border-radius: var(--r-2); padding: 1px 7px; color: var(--ink-2); }
.dash { color: var(--faint); }
.c-co { color: var(--ink-2); font-size: 12.5px; }
.c-sp { display: inline-flex; align-items: center; gap: 6px; justify-content: flex-end; }
.spv { font-size: 11.5px; color: var(--muted); min-width: 30px; text-align: right; }
.foot { color: var(--muted); font-size: 12px; margin: var(--sp-3) 0 0; } .foot code { font-family: var(--mono); font-size: 11px; color: var(--ink-2); }

/* factsheet drawer content */
.fs-top { display: flex; align-items: center; gap: var(--sp-2); flex-wrap: wrap; margin-bottom: var(--sp-4); }
.fs-id { font-family: var(--mono); font-size: 10.5px; color: var(--faint); word-break: break-all; }
.fs-facts { display: grid; grid-template-columns: 1fr 1fr; gap: var(--sp-3); margin-bottom: var(--sp-4); }
.fct { display: flex; flex-direction: column; gap: 2px; border: 1px solid var(--hairline); border-radius: var(--r-2); padding: 7px 10px; background: var(--surface); }
.fk { font-size: 10px; text-transform: uppercase; letter-spacing: .05em; color: var(--faint); }
.fv { font-size: 13px; color: var(--ink); } .fv.sp { display: flex; align-items: center; gap: 6px; } .fv.sp b { font-size: 12px; color: var(--muted); }
.fs-sec { margin-bottom: var(--sp-4); }
.fs-sec h4 { margin: 0 0 var(--sp-2); font-size: 11px; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); display: flex; align-items: center; gap: 8px; }
.fs-cols { display: flex; flex-wrap: wrap; gap: 5px; }
.fs-cols code { font-family: var(--mono); font-size: 11px; color: var(--ink-2); background: var(--surface); border: 1px solid var(--hairline); border-radius: var(--r-1); padding: 1px 6px; }
.attested { border: 1px solid color-mix(in srgb, var(--epi-attested) 30%, var(--hairline)); border-radius: var(--r-3); padding: var(--sp-3) var(--sp-4); background: var(--epi-attested-wash, var(--sunken)); }
.att-chip { font-family: var(--mono); font-size: 10px; color: var(--epi-attested); background: color-mix(in srgb, var(--epi-attested) 12%, transparent); border-radius: var(--r-1); padding: 1px 6px; letter-spacing: 0; text-transform: none; }
.att-text { font-size: 13px; line-height: 1.55; color: var(--ink); margin: 0 0 8px; }
.att-note { font-size: 11px; color: var(--muted); line-height: 1.5; }
</style>
