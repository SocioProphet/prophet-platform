<script setup lang="ts">
// Digital Health Twin — the "Digital Health Self" (walking skeleton). An OPT-IN, local-first,
// sovereign view of a person's own records, indexed by organ system (the anatomical diagram as the
// interface). Reuses the design-language components: Sparkline (lab trends), FactsheetDrawer (an
// attested, NON-DIAGNOSTIC record factsheet), the epistemic stripe (record trust). Plus the sovereign
// difference: a governed-sharing panel where a designated agent gets a scoped, revocable, RECEIPTED
// read grant — revoke and the next read is blocked. Synthetic data only in this skeleton.
//
// Guardrails, enforced in the UI: opt-in gate before anything renders · non-diagnostic framing ·
// nothing shared without an explicit grant · every access receipted.
import { ref, computed, onMounted, watch, onBeforeUnmount } from 'vue';
import { loadTwin, grantAccess, revokeAccess, agentRead, listConnectors, ingestConnector, reconcile, serviceHealth, type TwinBundle, type SystemBundle, type Observation, type Condition, type ConnectorMeta, type IngestSummary, type ServiceHealth, type ReconcileReport } from '../services/healthTwinApi';
import { EPISTEMIC_COLORS } from '../services/studioApi';
import Sparkline from '../components/Sparkline.vue';
import SpineOverlay from './SpineOverlay.vue';
import ConsultView from './ConsultView.vue';
import { plateFor, ATLAS_CREDIT } from '../data/anatomyAtlas';
import './studio/studio-tokens.css';

const OPTIN_KEY = 'health-twin-optin-v1';
const optedIn = ref(localStorage.getItem(OPTIN_KEY) === '1');
function optIn() { localStorage.setItem(OPTIN_KEY, '1'); optedIn.value = true; load(); }
function optOut() { localStorage.removeItem(OPTIN_KEY); optedIn.value = false; twin.value = null; }

const twin = ref<TwinBundle | null>(null);
const loading = ref(false);
const err = ref('');
const selected = ref<string>('cardiovascular');
const view = ref<'systems' | 'spine' | 'sources' | 'consults'>('systems');
const flash = ref('');
function say(m: string) { flash.value = m; setTimeout(() => (flash.value = ''), 2800); }

async function load() {
  loading.value = true; err.value = '';
  try {
    twin.value = await loadTwin();
    if (!twin.value.systems.some((s) => s.id === selected.value)) selected.value = twin.value.systems[0]?.id ?? '';
  } catch (e) { err.value = e instanceof Error ? e.message : 'failed to load health twin'; }
  finally { loading.value = false; }
}
onMounted(() => { if (optedIn.value) load(); });

// Sources & reconciliation — the ingest → reconcile → estate-services chain, made visible. The twin
// ORCHESTRATES existing services (entity-resolution, ie-engine, holmes, hellgraph, owl-reasoner); it
// never rebuilds them. Every call degrades gracefully.
const connectors = ref<ConnectorMeta[]>([]);
const ingestSummary = ref<IngestSummary | null>(null);
const services = ref<ServiceHealth[]>([]);
const recon = ref<ReconcileReport | null>(null);
const busy = ref<string>('');
async function loadSources() {
  try {
    const [c, s] = await Promise.all([listConnectors(), serviceHealth()]);
    connectors.value = c.connectors; ingestSummary.value = c.summary; services.value = s.services;
  } catch (e) { say(e instanceof Error ? e.message : 'sources unreachable'); }
}
async function doIngest(id: string) {
  busy.value = id;
  try { const r = await ingestConnector(id); ingestSummary.value = r.summary; say(`Ingested ${r.added.total} record(s) · receipt ${r.receipt.id}`); }
  catch (e) { say(e instanceof Error ? e.message : 'ingest failed'); }
  finally { busy.value = ''; }
}
async function doReconcile() {
  busy.value = 'reconcile';
  try { recon.value = await reconcile(); say(recon.value.service === 'entity-resolution' ? `Reconciled ${recon.value.before}→${recon.value.after} (${recon.value.merged} merged)` : `Reconcile ${recon.value.reason ?? 'degraded'}`); }
  catch (e) { say(e instanceof Error ? e.message : 'reconcile failed'); }
  finally { busy.value = ''; }
}
const ingestedCount = (id: string): number => ingestSummary.value?.sources.find((s) => s.source === id)?.count ?? 0;
watch(view, (v) => { if (v === 'sources' && connectors.value.length === 0) loadSources(); });

function epi(mode: string): string { return EPISTEMIC_COLORS[mode] || 'var(--epi-unknown)'; }
function recordCount(s: SystemBundle): number { return s.observations.length + s.conditions.length + s.encounters.length + s.imaging.length; }
const sys = computed<SystemBundle | null>(() => twin.value?.systems.find((s) => s.id === selected.value) ?? null);
function outOfRange(o: Observation): boolean { return (o.refHigh != null && o.value > o.refHigh) || (o.refLow != null && o.value < o.refLow); }

// organs that carry records — the Spine overlay links only those back to the twin.
const recordOrgans = computed<string[]>(() => {
  const set = new Set<string>();
  for (const s of twin.value?.systems ?? []) {
    for (const o of s.observations) if (o.organ) set.add(o.organ);
    for (const c of s.conditions) if (c.organ) set.add(c.organ);
  }
  return [...set];
});
function onSpineOrgan(organ: string) {
  const owner = twin.value?.systems.find((s) => s.organs.includes(organ));
  if (owner) { selected.value = owner.id; view.value = 'systems'; }
}

// Anatomy atlas plate for the selected system: vendored (sovereign) → remote CC-BY → placeholder.
const plate = computed(() => plateFor(selected.value));
const plateStage = ref<'vendored' | 'remote' | 'none'>('vendored');
watch(selected, () => { plateStage.value = 'vendored'; });
const plateSrc = computed(() => {
  const p = plate.value; if (!p) return '';
  if (plateStage.value === 'vendored' && p.vendored) return `${import.meta.env.BASE_URL}${p.vendored}`;
  if (plateStage.value !== 'none' && p.remote) return p.remote;
  return '';
});
function onPlateError() {
  const p = plate.value;
  if (plateStage.value === 'vendored' && p?.remote) plateStage.value = 'remote';
  else plateStage.value = 'none';
}

// factsheet (attested, deterministic, non-diagnostic)
function djb2(s: string): string { let h = 5381; for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) & 0xffffffff; return (h >>> 0).toString(16).padStart(8, '0'); }
type Sheet = { title: string; eyebrow: string; epistemic: string; summary: string; receipt: string; facts: { k: string; v: string }[]; trend?: number[] };
const sheet = ref<Sheet | null>(null);
function obsSheet(o: Observation) {
  const dir = o.trend && o.trend.length > 1 ? (o.trend[o.trend.length - 1] > o.trend[0] ? 'rising' : o.trend[o.trend.length - 1] < o.trend[0] ? 'falling' : 'stable') : 'stable';
  const pos = o.refHigh != null && o.value > o.refHigh ? 'above' : o.refLow != null && o.value < o.refLow ? 'below' : 'within';
  sheet.value = {
    title: o.display, eyebrow: `lab · ${o.codeSystem} ${o.code}`, epistemic: o.epistemic,
    summary: `${o.display} measured ${o.value} ${o.unit} on ${o.effective}, ${dir} over ${o.trend?.length ?? 1} results. Reference ${o.refLow ?? '—'}–${o.refHigh ?? '—'} ${o.unit}; this value is ${pos} range. Verified by lab. A record, not a diagnosis.`,
    receipt: `ht-${djb2([o.id, String(o.value), o.effective, pos, dir].join('|'))}`,
    facts: [{ k: 'Value', v: `${o.value} ${o.unit}` }, { k: 'Reference', v: `${o.refLow ?? '—'}–${o.refHigh ?? '—'} ${o.unit}` }, { k: 'Date', v: o.effective }, { k: 'Code', v: `${o.codeSystem} ${o.code}` }, { k: 'Localized to', v: o.organ ?? '—' }, { k: 'Type', v: 'hdt:Observation' }],
    trend: o.trend,
  };
}
function condSheet(c: Condition) {
  sheet.value = {
    title: c.display, eyebrow: `condition · ${c.codeSystem} ${c.code}`, epistemic: c.epistemic,
    summary: `${c.display} (${c.codeSystem} ${c.code}), ${c.clinicalStatus}, onset ${c.onset}. Trust level: ${c.epistemic}. This is a stored record; it is not re-diagnosed here.`,
    receipt: `ht-${djb2([c.id, c.clinicalStatus, c.onset].join('|'))}`,
    facts: [{ k: 'Status', v: c.clinicalStatus }, { k: 'Onset', v: c.onset }, { k: 'Code', v: `${c.codeSystem} ${c.code}` }, { k: 'Trust', v: c.epistemic }, { k: 'Localized to', v: c.organ ?? '—' }, { k: 'Type', v: 'health:Condition' }],
  };
}
// self-contained drawer: ESC closes (kept local so the health twin doesn't couple to Studio components)
function onSheetKey(e: KeyboardEvent) { if (e.key === 'Escape') sheet.value = null; }
watch(sheet, (s) => { if (s) document.addEventListener('keydown', onSheetKey); else document.removeEventListener('keydown', onSheetKey); });
onBeforeUnmount(() => document.removeEventListener('keydown', onSheetKey));

// governed sharing
const ng = ref<{ agent: string; scope: string; ttl: number }>({ agent: '', scope: '', ttl: 30 });
async function doGrant() {
  if (!ng.value.agent.trim()) return;
  try { await grantAccess(ng.value.agent.trim(), ng.value.scope.trim() || 'all systems', ng.value.ttl); say('Grant issued — receipted'); ng.value.agent = ''; ng.value.scope = ''; await load(); }
  catch (e) { say(e instanceof Error ? e.message : 'grant failed'); }
}
async function doRevoke(id: string) { try { await revokeAccess(id); say('Revoked — future reads blocked'); await load(); } catch (e) { say(e instanceof Error ? e.message : 'revoke failed'); } }
async function doAgentRead(id: string) {
  const r = await agentRead(id);
  if (r.blocked) say(`🔒 ${r.reason}`); else say(`Agent read ✓ receipt ${r.receipt?.id} (read #${r.reads})`);
  await load();
}
</script>

<template>
  <div class="studio-scope htwin">
    <!-- OPT-IN GATE — nothing renders until the person explicitly enables their twin -->
    <div v-if="!optedIn" class="gate">
      <div class="gate-card">
        <span class="gate-mark">◈</span>
        <h1>Your Digital Health Self</h1>
        <p class="gate-lead">A private, <b>opt-in</b> place to gather a lifetime of your medical records — notes, labs, imaging — indexed by your body's systems, so you and the people you designate can make sense of it.</p>
        <ul class="gate-points">
          <li><b>Local-first &amp; sovereign.</b> Your records stay on your own node, encrypted. No vendor cloud; export and leave anytime.</li>
          <li><b>You control access.</b> A designated person or agent can only read a slice you grant — scoped, time-boxed, revocable, and every access leaves a receipt.</li>
          <li><b>Not a diagnosis.</b> This organises and retrieves your records. It never diagnoses or gives medical advice — that's your clinician.</li>
          <li><b>This preview uses synthetic sample data</b> — not a real person, not real records.</li>
        </ul>
        <button class="btn big" @click="optIn">Enable my health twin</button>
        <p class="gate-fine">Opt-in only. You can turn this off and clear it at any time.</p>
      </div>
    </div>

    <!-- THE TWIN -->
    <template v-else>
      <header class="ht-top">
        <div class="ht-h"><span class="ht-mark">◈</span><div><h1>Digital Health Self</h1><span class="ht-sub">{{ twin?.subject.label }} · organ-system index</span></div></div>
        <div class="ht-views">
          <button class="vbtn" :class="{ on: view === 'systems' }" @click="view = 'systems'">Systems</button>
          <button class="vbtn" :class="{ on: view === 'spine' }" @click="view = 'spine'">Spine</button>
          <button class="vbtn" :class="{ on: view === 'sources' }" @click="view = 'sources'">Sources</button>
          <button class="vbtn" :class="{ on: view === 'consults' }" @click="view = 'consults'">Consults</button>
        </div>
        <button class="ghost" @click="load" :disabled="loading" aria-label="Reload">↻</button>
        <button class="ghost txt" @click="optOut">Turn off</button>
      </header>
      <p class="disclaimer">⚕ Not medical advice · organises records, does not diagnose · <b>synthetic sample data</b>.</p>
      <p class="credit">{{ ATLAS_CREDIT }}</p>
      <p v-if="flash" class="flash">{{ flash }}</p>
      <p v-if="err" class="msg err">{{ err }}</p>
      <p v-else-if="loading && !twin" class="msg">Loading your twin…</p>

      <div v-else-if="twin && view === 'systems'" class="ht-body">
        <!-- Anatomical system index -->
        <aside class="ht-index" aria-label="Body systems">
          <div class="idx-h">Body systems</div>
          <button v-for="s in twin.systems" :key="s.id" class="idx-row" :class="{ on: selected === s.id }" @click="selected = s.id">
            <span class="idx-label"><b>{{ s.label }}</b><small>{{ s.organs.join(' · ') }}</small></span>
            <span class="idx-n tnum">{{ recordCount(s) }}</span>
          </button>
        </aside>

        <!-- Selected system detail -->
        <section class="ht-detail" v-if="sys">
          <h2 class="det-h">{{ sys.label }} <span>{{ sys.organs.join(' · ') }}</span></h2>

          <figure v-if="plate" class="plate">
            <img v-if="plateSrc" :src="plateSrc" :alt="plate.title + ' — anatomical illustration'" loading="lazy" @error="onPlateError" />
            <div v-else class="plate-ph">
              <i class="plate-ic">▤</i>
              <span>Illustration pending — {{ plate.license }}</span>
              <a :href="plate.sourceUrl" target="_blank" rel="noopener" class="plate-src">review the source →</a>
            </div>
            <figcaption>{{ plate.attribution }}</figcaption>
          </figure>

          <div v-if="sys.observations.length" class="det-sec">
            <h3>Labs</h3>
            <div v-for="o in sys.observations" :key="o.id" class="obs epi-stripe" :style="{ '--epi': epi(o.epistemic) }">
              <button class="obs-nm" @click="obsSheet(o)">{{ o.display }}</button>
              <span class="obs-v tnum" :class="{ oor: outOfRange(o) }">{{ o.value }} <i>{{ o.unit }}</i></span>
              <Sparkline v-if="o.trend" :series="o.trend" :w="88" :h="22" :tone="outOfRange(o) ? 'down' : 'accent'" />
              <span class="obs-ref">ref {{ o.refLow ?? '—' }}–{{ o.refHigh ?? '—' }}</span>
              <span v-if="o.organ" class="organ-chip" title="localized to (health:localizedTo)"><i>◍</i>{{ o.organ }}</span>
              <span class="epi-chip" :style="{ '--epi': epi(o.epistemic), '--epi-wash': 'transparent' }">{{ o.epistemic }}</span>
            </div>
          </div>

          <div v-if="sys.conditions.length" class="det-sec">
            <h3>Conditions</h3>
            <button v-for="c in sys.conditions" :key="c.id" class="cond epi-stripe" :style="{ '--epi': epi(c.epistemic) }" @click="condSheet(c)">
              <b>{{ c.display }}</b><span class="cond-s">{{ c.clinicalStatus }}</span><span class="cond-o">onset {{ c.onset }}</span>
              <span v-if="c.organ" class="organ-chip" title="localized to"><i>◍</i>{{ c.organ }}</span>
              <span class="epi-chip" :style="{ '--epi': epi(c.epistemic), '--epi-wash': 'transparent' }">{{ c.epistemic }}</span>
            </button>
          </div>

          <div v-if="sys.imaging.length" class="det-sec">
            <h3>Imaging</h3>
            <div v-for="im in sys.imaging" :key="im.id" class="img-row"><span class="mod">{{ im.modality }}</span><span>{{ im.description }}</span><span class="img-d">{{ im.date }}</span></div>
          </div>

          <div v-if="sys.encounters.length" class="det-sec">
            <h3>History</h3>
            <div class="tl">
              <div v-for="e in sys.encounters" :key="e.id" class="tl-row"><span class="tl-d tnum">{{ e.date }}</span><span class="tl-dot" /><span class="tl-c"><b>{{ e.type }}</b><small>{{ e.provider }} — {{ e.note }}</small></span></div>
            </div>
          </div>

          <p v-if="!recordCount(sys)" class="msg">No records for this system.</p>
        </section>

        <!-- Governed sharing -->
        <aside class="ht-share" aria-label="Governed sharing">
          <div class="sh-h">Who can read this</div>
          <p class="sh-lead">Grant a designated person or agent a <b>scoped, time-boxed, revocable</b> read. Every access is a receipt.</p>
          <div class="sh-form">
            <input v-model="ng.agent" class="j" placeholder="agent / person id" />
            <input v-model="ng.scope" class="j" placeholder="scope (e.g. cardiovascular 2024–2026)" />
            <div class="sh-ttl"><label>expires in</label><input v-model.number="ng.ttl" type="number" min="1" max="365" class="j ttl" /><span>days</span></div>
            <button class="btn" @click="doGrant" :disabled="!ng.agent.trim()">Grant read</button>
          </div>
          <div class="grants">
            <div v-for="g in twin.grants" :key="g.id" class="grant" :class="{ revoked: g.revoked, expired: !g.active && !g.revoked }">
              <div class="g-top"><b>{{ g.agent }}</b><span class="g-state">{{ g.revoked ? 'revoked' : g.active ? 'active' : 'expired' }}</span></div>
              <div class="g-scope">{{ g.scope }}</div>
              <div class="g-meta"><span>reads <b class="tnum">{{ g.reads }}</b></span><span class="g-exp">exp {{ g.expires_at.slice(0, 10) }}</span><span class="g-rcpt mono">{{ g.receipt }}</span></div>
              <div class="g-actions">
                <button class="mini" @click="doAgentRead(g.id)">simulate agent read</button>
                <button v-if="!g.revoked" class="mini danger" @click="doRevoke(g.id)">revoke</button>
              </div>
            </div>
            <p v-if="!twin.grants.length" class="sh-empty">No grants — your records are private.</p>
          </div>
        </aside>
      </div>

      <!-- Spine view: the three-lens spinal correspondence chart -->
      <div v-else-if="twin && view === 'spine'" class="ht-spine">
        <SpineOverlay :record-organs="recordOrgans" @organ="onSpineOrgan" />
      </div>

      <!-- Blinded second opinions (wall 4 — the moat): consent-scoped, double-blind, non-diagnostic -->
      <div v-else-if="twin && view === 'consults'" class="ht-consults">
        <ConsultView />
      </div>

      <!-- Sources & reconciliation: the ingest → reconcile → estate-services chain, made visible -->
      <div v-else-if="twin && view === 'sources'" class="ht-sources">
        <section class="src-main">
          <div class="src-h">Connect a source <small>each connector proves out on the real API schema (fixture); going live needs only a credential</small></div>
          <div class="conns">
            <div v-for="c in connectors" :key="c.id" class="conn">
              <div class="conn-t"><b>{{ c.name }}</b><span class="conn-kind">{{ c.kind }}</span><span v-if="ingestedCount(c.id)" class="conn-in">✓ {{ ingestedCount(c.id) }}</span></div>
              <div class="conn-u"><span v-for="u in c.uscdiClasses" :key="u" class="uchip">{{ u }}</span></div>
              <div class="conn-meta"><span class="mono">{{ c.sourceShape }}</span></div>
              <button class="mini" :disabled="busy === c.id" @click="doIngest(c.id)">{{ busy === c.id ? 'ingesting…' : 'Ingest (fixture)' }}</button>
            </div>
            <p v-if="!connectors.length" class="sh-empty">Connecting to the twin engine…</p>
          </div>
          <div v-if="ingestSummary && ingestSummary.counts.total" class="src-cov">
            <span class="cov-n tnum">{{ ingestSummary.counts.total }}</span> records ingested · USCDI coverage:
            <span v-for="u in ingestSummary.uscdiCoverage" :key="u" class="uchip on">{{ u }}</span>
          </div>
        </section>

        <aside class="src-rail" aria-label="Reconciliation">
          <div class="sh-h">What's connected</div>
          <p class="sh-lead">The twin <b>orchestrates existing estate services</b> — it never rebuilds NLP / entity-resolution / vector / reasoning. A service that's down degrades gracefully.</p>
          <div class="svcs">
            <div v-for="s in services" :key="s.service" class="svc"><span class="dot" :class="{ up: s.up }" /><span>{{ s.service }}</span></div>
          </div>
          <div class="recon">
            <button class="btn" :disabled="busy === 'reconcile'" @click="doReconcile">{{ busy === 'reconcile' ? 'reconciling…' : 'Reconcile across sources' }}</button>
            <div v-if="recon" class="recon-r">
              <template v-if="recon.service === 'entity-resolution'">
                <div class="recon-stat"><b class="tnum">{{ recon.before }}→{{ recon.after }}</b> records · <b class="tnum">{{ recon.merged }}</b> cross-source merge(s)</div>
                <div v-for="g in recon.golden.filter((x) => x.size > 1)" :key="g.entity_id" class="merged">
                  <b>{{ g.name }}</b>
                  <span class="src-chips"><span v-for="s in g.contributingSources" :key="s" class="schip">{{ s }}</span></span>
                </div>
              </template>
              <p v-else class="sh-empty">Reconciliation service {{ recon.reason || 'offline' }} — records held locally.</p>
            </div>
          </div>
          <p class="src-fine">⚕ Non-diagnostic. Every record carries provenance + an epistemic tier — merges are proof-carrying.</p>
        </aside>
      </div>

      <!-- self-contained record factsheet drawer (attested, non-diagnostic) -->
      <Teleport to="body">
        <Transition name="fd">
          <div v-if="sheet" class="fd studio-scope" @click.self="sheet = null">
            <div class="fd-panel" role="dialog" aria-modal="true" :aria-label="sheet.title">
              <header class="fd-h">
                <div class="fd-h-t"><span class="fd-eyebrow">{{ sheet.eyebrow }}</span><h2>{{ sheet.title }}</h2></div>
                <button class="fd-x" @click="sheet = null" aria-label="Close">✕</button>
              </header>
              <div class="fd-body">
                <div class="fs-top"><span class="epi-chip" :style="{ '--epi': epi(sheet.epistemic), '--epi-wash': 'transparent' }">{{ sheet.epistemic }}</span></div>
                <Sparkline v-if="sheet.trend" :series="sheet.trend" :w="220" :h="40" tone="accent" />
                <div class="fs-facts">
                  <div v-for="f in sheet.facts" :key="f.k" class="fct"><span class="fk">{{ f.k }}</span><span class="fv">{{ f.v }}</span></div>
                </div>
                <div class="fs-att">
                  <h4>Attested record <span class="att-chip">▪ {{ sheet.receipt }}</span></h4>
                  <p>{{ sheet.summary }}</p>
                  <span class="att-note">Deterministic summary of the record's own fields (recomputable via the receipt) — not model-generated prose, and not a diagnosis.</span>
                </div>
              </div>
            </div>
          </div>
        </Transition>
      </Teleport>
    </template>
  </div>
</template>

<style scoped>
.htwin { font: 14px/1.5 var(--ui); color: var(--ink); background: var(--bg); min-height: 100%; padding: var(--sp-4) var(--sp-5); }
.htwin :focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: var(--r-1); }

/* opt-in gate */
.gate { display: grid; place-items: center; min-height: 70vh; }
.gate-card { max-width: 560px; border: 1px solid var(--hairline); border-radius: var(--r-3); background: var(--surface); padding: var(--sp-6); text-align: center; }
.gate-mark { font-size: 2rem; color: var(--accent); }
.gate-card h1 { margin: var(--sp-2) 0; font-size: 1.5rem; }
.gate-lead { color: var(--ink-2); font-size: .95rem; margin: 0 0 var(--sp-4); }
.gate-points { list-style: none; margin: 0 0 var(--sp-4); padding: 0; text-align: left; display: flex; flex-direction: column; gap: var(--sp-2); }
.gate-points li { font-size: .85rem; color: var(--ink-2); border-left: 2px solid var(--accent); padding-left: var(--sp-3); } .gate-points b { color: var(--ink); }
.gate-fine { color: var(--faint); font-size: .72rem; margin: var(--sp-3) 0 0; }
.btn { border: 1px solid var(--accent); background: var(--accent); color: #04122e; border-radius: var(--r-2); padding: 8px 16px; font-weight: 600; cursor: pointer; font-size: 13px; } .btn:disabled { opacity: .55; }
.btn.big { font-size: 15px; padding: 10px 22px; }

/* header */
.ht-top { display: flex; align-items: center; gap: var(--sp-3); margin-bottom: var(--sp-2); }
.ht-h { display: flex; align-items: center; gap: var(--sp-3); margin-right: auto; }
.ht-mark { color: var(--accent); font-size: 1.2rem; } .ht-h h1 { margin: 0; font-size: 1.15rem; } .ht-sub { color: var(--muted); font-size: .78rem; }
.ghost { border: 1px solid var(--hairline-strong); background: var(--surface); color: var(--ink-2); border-radius: var(--r-2); height: 30px; min-width: 30px; padding: 0 8px; cursor: pointer; } .ghost.txt { font-size: 12px; }
.ht-views { display: flex; gap: 3px; background: var(--sunken); border-radius: var(--pill); padding: 3px; }
.vbtn { border: 0; background: transparent; color: var(--muted); border-radius: var(--pill); padding: 4px 14px; font-size: 12.5px; cursor: pointer; }
.vbtn.on { background: var(--accent-wash); color: var(--accent-ink); }
.organ-chip { display: inline-flex; align-items: center; gap: 3px; font-size: 10.5px; color: var(--ink-2); background: var(--sunken); border-radius: var(--pill); padding: 1px 8px; } .organ-chip i { font-style: normal; color: var(--accent); font-size: 9px; }
.ht-spine { border: 1px solid var(--hairline); border-radius: var(--r-3); background: var(--surface); padding: var(--sp-4); }
.ht-consults { border: 1px solid var(--hairline); border-radius: var(--r-3); background: var(--surface); padding: var(--sp-4); }

/* sources & reconciliation */
.ht-sources { display: grid; grid-template-columns: minmax(0, 1fr) 300px; gap: var(--sp-3); }
@media (max-width: 1080px) { .ht-sources { grid-template-columns: 1fr; } }
.src-main { border: 1px solid var(--hairline); border-radius: var(--r-3); background: var(--surface); padding: var(--sp-4); }
.src-h { font-size: 12px; font-weight: 600; } .src-h small { font-weight: 400; color: var(--muted); display: block; font-size: 11px; margin: 2px 0 var(--sp-3); }
.conns { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 8px; }
.conn { border: 1px solid var(--hairline); border-radius: var(--r-2); background: var(--sunken); padding: 10px; display: flex; flex-direction: column; gap: 6px; }
.conn-t { display: flex; align-items: center; gap: 6px; } .conn-t b { font-size: 12.5px; }
.conn-kind { font-size: 9.5px; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); background: var(--surface); border-radius: var(--pill); padding: 1px 7px; }
.conn-in { margin-left: auto; font-size: 10.5px; color: var(--ok); }
.conn-u { display: flex; flex-wrap: wrap; gap: 3px; }
.uchip { font-size: 9.5px; color: var(--ink-2); background: var(--surface); border: 1px solid var(--hairline); border-radius: var(--pill); padding: 1px 6px; } .uchip.on { background: var(--accent-wash); color: var(--accent-ink); border-color: var(--accent); }
.conn-meta { font-size: 10px; color: var(--faint); } .conn .mini { align-self: flex-start; }
.src-cov { margin-top: var(--sp-3); font-size: 11.5px; color: var(--muted); display: flex; align-items: center; gap: 4px; flex-wrap: wrap; } .cov-n { font-size: 14px; color: var(--ink); }
.src-rail { border: 1px solid var(--hairline); border-radius: var(--r-3); background: var(--sunken); padding: var(--sp-3); align-self: start; }
.svcs { display: flex; flex-direction: column; gap: 4px; margin-bottom: var(--sp-3); }
.svc { display: flex; align-items: center; gap: 7px; font-size: 12px; color: var(--ink-2); } .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--faint); } .dot.up { background: var(--ok); }
.recon-r { margin-top: 8px; } .recon-stat { font-size: 12px; margin-bottom: 6px; }
.merged { display: flex; flex-direction: column; gap: 3px; border: 1px solid var(--hairline); border-radius: var(--r-2); background: var(--surface); padding: 6px 8px; margin-bottom: 5px; } .merged b { font-size: 12px; }
.src-chips { display: flex; gap: 3px; flex-wrap: wrap; } .schip { font-size: 9.5px; color: var(--accent-ink); background: var(--accent-wash); border-radius: var(--pill); padding: 1px 7px; }
.src-fine { font-size: 10.5px; color: var(--faint); margin: var(--sp-3) 0 0; }
.disclaimer { font-size: 11.5px; color: var(--warn); background: var(--warn-wash); border-radius: var(--r-2); padding: 5px 10px; margin: 0 0 var(--sp-3); } .disclaimer b { color: var(--ink); }
.flash { background: var(--ok-wash); color: var(--ok); border-radius: var(--r-2); padding: 6px 11px; font-size: 12.5px; margin: 0 0 10px; }
.msg { color: var(--muted); } .msg.err { color: var(--fail); }

.ht-body { display: grid; grid-template-columns: 220px minmax(0, 1fr) 280px; gap: var(--sp-3); }
@media (max-width: 1080px) { .ht-body { grid-template-columns: 1fr; } }

/* index */
.ht-index { border: 1px solid var(--hairline); border-radius: var(--r-3); background: var(--sunken); padding: var(--sp-2); display: flex; flex-direction: column; gap: 3px; align-self: start; }
.idx-h { font-size: 10.5px; text-transform: uppercase; letter-spacing: .07em; color: var(--faint); padding: 6px 8px; }
.idx-row { display: flex; align-items: center; gap: 8px; background: transparent; border: 1px solid transparent; border-radius: var(--r-2); padding: 8px 10px; cursor: pointer; text-align: left; color: inherit; }
.idx-row:hover { background: var(--surface); } .idx-row.on { background: var(--accent-wash); border-color: var(--accent); }
.idx-label { display: flex; flex-direction: column; min-width: 0; } .idx-label b { font-size: 13px; } .idx-label small { color: var(--muted); font-size: 10.5px; }
.idx-n { margin-left: auto; font-size: 11px; color: var(--ink-2); background: var(--surface); border-radius: var(--pill); padding: 0 7px; }

/* detail */
.ht-detail { border: 1px solid var(--hairline); border-radius: var(--r-3); background: var(--surface); padding: var(--sp-4); min-width: 0; }
.det-h { margin: 0 0 var(--sp-3); font-size: 1.05rem; } .det-h span { color: var(--muted); font-size: .8rem; font-weight: 400; }
.plate { margin: 0 0 var(--sp-4); }
.plate img { display: block; width: 100%; max-height: 300px; object-fit: contain; background: #fff; border: 1px solid var(--hairline); border-radius: var(--r-3); }
.plate-ph { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px; height: 160px; border: 1px dashed var(--hairline-strong); border-radius: var(--r-3); background: var(--sunken); color: var(--muted); font-size: 12px; }
.plate-ph .plate-ic { font-size: 22px; color: var(--faint); font-style: normal; }
.plate-ph .plate-src { color: var(--accent); font-size: 12px; text-decoration: none; } .plate-ph .plate-src:hover { text-decoration: underline; }
.plate figcaption { margin-top: 4px; font-size: 10.5px; color: var(--faint); }
.credit { margin: 0 0 var(--sp-3); font-size: 10.5px; color: var(--faint); }
.det-sec { margin-bottom: var(--sp-4); } .det-sec h3 { margin: 0 0 var(--sp-2); font-size: 11px; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); }
.obs { display: flex; align-items: center; gap: var(--sp-3); padding: 7px 10px 7px 12px; border: 1px solid var(--hairline); border-radius: var(--r-2); margin-bottom: 6px; background: var(--sunken); flex-wrap: wrap; }
.obs-nm { background: none; border: 0; color: var(--ink); font-weight: 600; font-size: 13px; cursor: pointer; padding: 0; text-align: left; }
.obs-v { font-size: 14px; color: var(--ink); font-variant-numeric: tabular-nums; } .obs-v i { font-style: normal; font-size: 11px; color: var(--muted); } .obs-v.oor { color: var(--fail); }
.obs-ref { font-size: 10.5px; color: var(--faint); } .obs .epi-chip { margin-left: auto; }
.cond { display: flex; align-items: center; gap: var(--sp-3); padding: 8px 10px 8px 12px; border: 1px solid var(--hairline); border-radius: var(--r-2); margin-bottom: 6px; background: var(--sunken); width: 100%; text-align: left; color: inherit; cursor: pointer; }
.cond b { font-size: 13px; } .cond-s { font-size: 10.5px; color: var(--warn); text-transform: uppercase; } .cond-o { font-size: 11px; color: var(--muted); } .cond .epi-chip { margin-left: auto; }
.img-row { display: flex; align-items: center; gap: var(--sp-3); padding: 6px 10px; border-bottom: 1px solid var(--hairline); font-size: 12.5px; }
.mod { font-size: 10px; text-transform: uppercase; letter-spacing: .05em; color: var(--epi-attested); border: 1px solid color-mix(in srgb, var(--epi-attested) 40%, var(--hairline)); border-radius: var(--r-1); padding: 0 6px; } .img-d { margin-left: auto; color: var(--faint); font-size: 11px; }
.tl { display: flex; flex-direction: column; }
.tl-row { display: grid; grid-template-columns: 84px 12px 1fr; align-items: start; gap: 8px; padding: 5px 0; }
.tl-d { font-size: 11px; color: var(--muted); text-align: right; } .tl-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent); margin-top: 5px; }
.tl-c { display: flex; flex-direction: column; } .tl-c b { font-size: 12.5px; } .tl-c small { color: var(--muted); font-size: 11px; }

/* sharing */
.ht-share { border: 1px solid var(--hairline); border-radius: var(--r-3); background: var(--sunken); padding: var(--sp-3); align-self: start; }
.sh-h { font-size: 12px; font-weight: 600; margin-bottom: 4px; } .sh-lead { font-size: 11.5px; color: var(--muted); margin: 0 0 var(--sp-3); } .sh-lead b { color: var(--ink-2); }
.sh-form { display: flex; flex-direction: column; gap: 6px; margin-bottom: var(--sp-3); }
.j { border: 1px solid var(--hairline-strong); border-radius: var(--r-2); padding: 6px 8px; font-size: 12.5px; background: var(--surface); color: var(--ink); width: 100%; }
.sh-ttl { display: flex; align-items: center; gap: 6px; font-size: 11.5px; color: var(--muted); } .j.ttl { width: 64px; }
.grants { display: flex; flex-direction: column; gap: 6px; }
.grant { border: 1px solid var(--hairline); border-radius: var(--r-2); padding: 7px 9px; background: var(--surface); }
.grant.revoked { opacity: .6; } .grant.expired { opacity: .7; }
.g-top { display: flex; align-items: center; justify-content: space-between; } .g-top b { font-size: 12.5px; }
.g-state { font-size: 9.5px; text-transform: uppercase; letter-spacing: .04em; border-radius: var(--pill); padding: 1px 7px; background: var(--ok-wash); color: var(--ok); }
.grant.revoked .g-state { background: var(--fail-wash); color: var(--fail); } .grant.expired .g-state { background: var(--sunken); color: var(--muted); }
.g-scope { font-size: 11px; color: var(--ink-2); margin: 2px 0; }
.g-meta { display: flex; gap: 8px; font-size: 10px; color: var(--muted); align-items: center; flex-wrap: wrap; } .g-rcpt { color: var(--faint); } .mono { font-family: var(--mono); }
.g-actions { display: flex; gap: 5px; margin-top: 5px; }
.mini { border: 1px solid var(--hairline-strong); background: var(--surface); color: var(--ink-2); border-radius: var(--r-2); padding: 2px 8px; font-size: 11px; cursor: pointer; } .mini.danger { border-color: var(--fail); color: var(--fail); }
.sh-empty { font-size: 11.5px; color: var(--faint); }

/* factsheet content */
.fs-top { margin-bottom: var(--sp-3); }
.fs-facts { display: grid; grid-template-columns: 1fr 1fr; gap: var(--sp-2); margin: var(--sp-3) 0; }
.fct { display: flex; flex-direction: column; gap: 2px; border: 1px solid var(--hairline); border-radius: var(--r-2); padding: 7px 10px; background: var(--surface); }
.fk { font-size: 10px; text-transform: uppercase; letter-spacing: .05em; color: var(--faint); } .fv { font-size: 13px; color: var(--ink); }
.fs-att { border: 1px solid color-mix(in srgb, var(--epi-attested) 30%, var(--hairline)); border-radius: var(--r-3); padding: var(--sp-3); background: var(--epi-attested-wash, var(--sunken)); }
.fs-att h4 { margin: 0 0 6px; font-size: 11px; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); display: flex; gap: 8px; align-items: center; }
.att-chip { font-family: var(--mono); font-size: 10px; color: var(--epi-attested); text-transform: none; }
.fs-att p { font-size: 13px; line-height: 1.55; color: var(--ink); margin: 0 0 8px; }
.att-note { font-size: 11px; color: var(--muted); line-height: 1.5; }

/* self-contained drawer chrome */
.fd { position: fixed; inset: 0; z-index: 200; display: flex; justify-content: flex-end; background: color-mix(in srgb, #000 55%, transparent); }
.fd-panel { width: min(440px, 92vw); height: 100%; background: var(--ground); border-left: 1px solid var(--hairline-strong); box-shadow: var(--e-3); display: flex; flex-direction: column; }
.fd-h { display: flex; align-items: flex-start; gap: var(--sp-3); padding: var(--sp-4) var(--sp-4) var(--sp-3); border-bottom: 1px solid var(--hairline); background: var(--bar); }
.fd-h-t { min-width: 0; flex: 1; } .fd-eyebrow { display: block; font-size: 10px; text-transform: uppercase; letter-spacing: .08em; color: var(--faint); margin-bottom: 2px; }
.fd-h h2 { margin: 0; font-size: 1.05rem; color: var(--bar-ink); font-weight: 600; word-break: break-word; }
.fd-x { flex: 0 0 auto; width: 28px; height: 28px; border: 1px solid var(--hairline-strong); background: var(--surface); color: var(--ink-2); border-radius: var(--r-2); cursor: pointer; }
.fd-body { flex: 1; overflow-y: auto; padding: var(--sp-4); color: var(--ink); }
.fd-enter-active, .fd-leave-active { transition: opacity .18s ease; }
.fd-enter-active .fd-panel, .fd-leave-active .fd-panel { transition: transform .22s cubic-bezier(.22,.61,.36,1); }
.fd-enter-from, .fd-leave-to { opacity: 0; } .fd-enter-from .fd-panel, .fd-leave-to .fd-panel { transform: translateX(100%); }
@media (prefers-reduced-motion: reduce) { .fd-enter-active .fd-panel, .fd-leave-active .fd-panel { transition: none; } .fd-enter-from .fd-panel, .fd-leave-to .fd-panel { transform: none; } }
</style>
