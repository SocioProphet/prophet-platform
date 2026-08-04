<script setup lang="ts">
// Catalog operations dashboard — the panel a data steward reads, and the thing WKC /
// Collibra / Waterline / watsonx.governance show as a vendor chart WE back with a real
// service. Every number here is a FOLD of crystallized operational events (catalog.*.v0)
// served by catalog-gateway (/svc/catalog): the resolve hit-rate + DCAT coverage + cold
// sources KPIs (the readout) and the Assay verdict over them (the SLO). Not a dashboard
// bolted onto a metastore — the operational plane of a proof-carrying catalog.
//
// Best-effort + fail-soft: if catalog-gateway is unreachable the panel collapses to a
// single muted line and the catalog table above it still works. It never blocks the page.
import { ref, onMounted, computed } from 'vue';
import { catalog, type CatalogReadout, type CatalogSlo, type SloVerdict } from './api';

const readout = ref<CatalogReadout | null>(null);
const slo = ref<CatalogSlo | null>(null);
const loading = ref(true);
const connected = ref(true);

async function load() {
  loading.value = true;
  try {
    const [r, s] = await Promise.all([catalog.readout(), catalog.slo()]);
    readout.value = r; slo.value = s; connected.value = true;
  } catch {
    // catalog-gateway not reachable (dev without the service, or a 502 pre-deploy) —
    // degrade to a quiet note rather than an error banner. The catalog still renders.
    connected.value = false;
  } finally { loading.value = false; }
}
onMounted(load);

const pct = (v: number | null | undefined) => (v === null || v === undefined ? '—' : `${Math.round(v * 1000) / 10}%`);
const VERDICT_LABEL: Record<SloVerdict, string> = { ok: 'OK', sad: 'SAD', bad: 'BAD', insufficient_data: 'n/a' };
const verdict = computed<SloVerdict>(() => slo.value?.verdict ?? 'insufficient_data');
</script>

<template>
  <section class="ops" aria-label="Catalog operations">
    <div v-if="loading" class="ops-note">Loading catalog operations…</div>
    <div v-else-if="!connected" class="ops-note muted">
      Catalog operations plane not connected — <code>/svc/catalog</code> unreachable. KPIs appear once catalog-gateway is deployed.
    </div>
    <template v-else-if="readout">
      <div class="ops-head">
        <span class="ops-title">Catalog operations</span>
        <span class="verdict" :class="'v-' + verdict" :title="'SLO verdict (Assay): ' + verdict">
          <i class="dot" /> {{ VERDICT_LABEL[verdict] }}
        </span>
        <span class="ops-win" :title="'events folded into this readout'">{{ readout.window.events_scanned }} events</span>
        <button class="ghost" @click="load" title="reload operations" aria-label="Reload operations">↻</button>
      </div>

      <div class="kpis">
        <div class="kpi">
          <span class="kv tnum">{{ pct(readout.resolve.hit_rate) }}</span>
          <span class="kk">Resolve hit-rate</span>
          <span class="kd">{{ readout.resolve.hits }}/{{ readout.resolve.total }} resolves</span>
        </div>
        <div class="kpi">
          <span class="kv tnum">{{ pct(readout.dcat.coverage_of_resolved_assets) }}</span>
          <span class="kk">DCAT coverage</span>
          <span class="kd">{{ readout.dcat.distinct_assets }} asset{{ readout.dcat.distinct_assets === 1 ? '' : 's' }} exported</span>
        </div>
        <div class="kpi">
          <span class="kv tnum">{{ readout.sources.cold.length }}</span>
          <span class="kk">Cold sources</span>
          <span class="kd">{{ readout.sources.read_in_window }}/{{ readout.sources.cataloged }} read</span>
        </div>
        <div class="kpi">
          <span class="kv tnum">{{ readout.resolve.misses }}</span>
          <span class="kk">Resolve misses</span>
          <span class="kd">{{ readout.top_misses.length }} distinct absent</span>
        </div>
      </div>

      <div class="ops-cols">
        <div class="ops-list" v-if="readout.hot_entries.length">
          <h5>Hot entries</h5>
          <div v-for="h in readout.hot_entries.slice(0, 6)" :key="h.kind + '/' + h.entry_id" class="li">
            <span class="lk">{{ h.kind }}</span><code class="lid">{{ h.entry_id }}</code><span class="ln tnum">{{ h.resolves }}</span>
          </div>
        </div>
        <div class="ops-list" v-if="readout.top_misses.length">
          <h5>Registration candidates <span class="hint" title="entries callers ask for that don't exist yet">?</span></h5>
          <div v-for="m in readout.top_misses.slice(0, 6)" :key="m.kind + '/' + m.entry_id" class="li">
            <span class="lk miss">{{ m.kind }}</span><code class="lid">{{ m.entry_id }}</code><span class="ln tnum">{{ m.misses }}</span>
          </div>
        </div>
        <div class="ops-list" v-if="slo && slo.objectives.length">
          <h5>SLO objectives</h5>
          <div v-for="o in slo.objectives" :key="o.name" class="li">
            <span class="obj-v" :class="'v-' + o.verdict"><i class="dot" /></span>
            <span class="lk">{{ o.name.replace(/_/g, ' ') }}</span>
            <span class="ln tnum" :title="'n=' + o.n + (o.note ? ' · ' + o.note : '')">{{ o.value === null ? '—' : (o.thresholds.direction === 'high' && o.value <= 1 ? pct(o.value) : o.value) }}</span>
          </div>
        </div>
      </div>
    </template>
  </section>
</template>

<style scoped>
.ops { border: 1px solid var(--hairline); border-radius: var(--r-3); padding: var(--sp-3) var(--sp-4); margin-bottom: var(--sp-4); background: var(--surface); font: 14px/1.5 var(--ui); color: var(--ink); }
.ops-note { color: var(--muted); font-size: 12.5px; } .ops-note.muted code { font-family: var(--mono); font-size: 11px; color: var(--ink-2); }
.ops-head { display: flex; align-items: center; gap: var(--sp-3); margin-bottom: var(--sp-3); flex-wrap: wrap; }
.ops-title { font-size: 11px; text-transform: uppercase; letter-spacing: .07em; color: var(--faint); }
.ops-win { font-size: 11px; color: var(--muted); font-variant-numeric: tabular-nums; }
.ghost { border: 1px solid var(--hairline-strong); background: var(--surface); color: var(--ink-2); border-radius: var(--r-2); width: 28px; height: 28px; cursor: pointer; margin-left: auto; }

.verdict { display: inline-flex; align-items: center; gap: 6px; font-size: 11px; font-weight: 600; letter-spacing: .04em; border-radius: var(--pill); padding: 2px 10px; border: 1px solid var(--hairline-strong); }
.verdict .dot, .obj-v .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--vc, var(--faint)); display: inline-block; }
.v-ok { --vc: var(--ok, #17864a); color: var(--ok, #17864a); background: color-mix(in srgb, var(--ok, #17864a) 10%, transparent); border-color: color-mix(in srgb, var(--ok, #17864a) 30%, transparent); }
.v-sad { --vc: var(--warn, #b7791f); color: var(--warn, #b7791f); background: color-mix(in srgb, var(--warn, #b7791f) 10%, transparent); border-color: color-mix(in srgb, var(--warn, #b7791f) 30%, transparent); }
.v-bad { --vc: var(--fail, #c0392b); color: var(--fail, #c0392b); background: color-mix(in srgb, var(--fail, #c0392b) 10%, transparent); border-color: color-mix(in srgb, var(--fail, #c0392b) 30%, transparent); }
.v-insufficient_data { --vc: var(--faint); color: var(--muted); }

.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: var(--sp-3); margin-bottom: var(--sp-3); }
.kpi { border: 1px solid var(--hairline); border-radius: var(--r-2); padding: 8px 12px; background: var(--sunken); display: flex; flex-direction: column; gap: 1px; }
.kv { font-size: 20px; font-weight: 650; color: var(--ink); line-height: 1.1; }
.kk { font-size: 10.5px; text-transform: uppercase; letter-spacing: .05em; color: var(--faint); }
.kd { font-size: 11px; color: var(--muted); }

.ops-cols { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: var(--sp-4); }
.ops-list h5 { margin: 0 0 var(--sp-2); font-size: 10.5px; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); display: flex; align-items: center; gap: 6px; }
.hint { font-size: 9px; color: var(--faint); border: 1px solid var(--hairline); border-radius: 50%; width: 13px; height: 13px; display: inline-flex; align-items: center; justify-content: center; cursor: help; }
.li { display: flex; align-items: center; gap: 8px; padding: 2px 0; font-size: 12px; }
.lk { font-size: 9.5px; text-transform: uppercase; letter-spacing: .04em; color: var(--faint); min-width: 46px; }
.lk.miss { color: var(--fail, #c0392b); }
.lid { font-family: var(--mono); font-size: 11px; color: var(--ink-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.ln { margin-left: auto; color: var(--muted); font-size: 12px; }
.obj-v { display: inline-flex; }
</style>
