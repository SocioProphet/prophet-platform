<script setup lang="ts">
// The physician's chart — built for an iPad at the bedside. The complete AUTHORIZED record (what the
// patient granted), presented as a clinical chart: problems / meds / allergies up top, vitals with
// one-tap voice/keyboard entry, labs with trends, and the full history as far back as it goes. Noetica's
// intelligence, focused on the clinician. Non-diagnostic; a clinician decides.
import { ref, computed, onMounted } from 'vue';
import { loadTwin, addReading, type TwinBundle } from '../services/healthTwinApi';
import Sparkline from '../components/Sparkline.vue';

const twin = ref<TwinBundle | null>(null);
const loading = ref(false);
const err = ref('');
const flash = ref('');
async function load() {
  loading.value = true; err.value = '';
  try { twin.value = await loadTwin(); } catch (e) { err.value = e instanceof Error ? e.message : 'chart unreachable'; }
  finally { loading.value = false; }
}
onMounted(load);

const conditions = computed(() => twin.value?.systems.flatMap((s) => s.conditions) ?? []);
const meds = computed(() => twin.value?.medications ?? []);
const allergies = computed(() => twin.value?.allergies ?? []);
const labs = computed(() => twin.value?.systems.flatMap((s) => s.observations) ?? []);
const readings = computed(() => twin.value?.readings ?? []);
const history = computed(() => [...(twin.value?.timeline ?? [])].sort((a, b) => (a.date < b.date ? 1 : -1)));
const careTeam = computed(() => twin.value?.careTeam ?? []);
const subj = computed(() => twin.value?.subject);
function oor(o: { value: number; refHigh?: number; refLow?: number }) { return (o.refHigh != null && o.value > o.refHigh) || (o.refLow != null && o.value < o.refLow); }

// quick reading entry — voice or keyboard
const entry = ref('');
const listening = ref(false);
const busy = ref(false);
const SR = typeof window !== 'undefined' ? ((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition) : null;
let rec: any = null;
function toggleMic() {
  if (!SR) return;
  if (listening.value) { rec && rec.stop(); return; }
  rec = new SR(); rec.continuous = true; rec.interimResults = true; rec.lang = 'en-US';
  rec.onresult = (e: any) => { let f = ''; for (let i = e.resultIndex; i < e.results.length; i++) if (e.results[i].isFinal) f += e.results[i][0].transcript; if (f) entry.value = (entry.value + ' ' + f.trim()).trim(); };
  rec.onend = () => { listening.value = false; };
  rec.start(); listening.value = true;
}
async function submitReading() {
  const t = entry.value.trim(); if (!t) return;
  busy.value = true;
  try { const r = await addReading(t, 'clinician', listening.value ? 'voice' : 'keyboard'); entry.value = ''; flash.value = `Recorded ${r.created.length} reading(s)`; setTimeout(() => (flash.value = ''), 2600); await load(); }
  catch (e) { flash.value = e instanceof Error ? e.message : 'entry failed'; }
  finally { busy.value = false; }
}
</script>

<template>
  <div class="dc">
    <p class="dc-dx">⚕ Clinician chart — the patient's authorized record. Not a diagnosis; a clinician decides. Synthetic demo data.</p>
    <p v-if="err" class="dc-err">{{ err }}</p>
    <p v-else-if="loading && !twin" class="dc-msg">Loading chart…</p>

    <template v-if="twin">
      <!-- patient header + care team -->
      <header class="dc-head">
        <div class="dc-who">
          <h1>{{ subj?.label }}</h1>
          <span class="dc-demo">{{ subj?.ageBand }} · {{ subj?.sex }} · authorized record</span>
        </div>
        <div class="dc-team">
          <span class="dc-team-h">Care team</span>
          <div class="dc-team-list">
            <span v-for="p in careTeam" :key="p.id" class="dc-doc" :title="`${p.credentials} · ${p.org} · ${p.location} · NPI ${p.npi || '—'}`">
              <b>{{ p.name }}</b><i>{{ p.specialty }} · {{ p.yearsInPractice }}y</i><em v-if="p.verified" class="vf">✓</em>
            </span>
          </div>
        </div>
      </header>

      <!-- chart summary: what matters now -->
      <section class="dc-grid3">
        <div class="dc-card">
          <div class="dc-card-h">Active problems</div>
          <div v-for="c in conditions" :key="c.id" class="dc-line"><b>{{ c.display }}</b><span class="dc-sub">{{ c.codeSystem }} {{ c.code }} · {{ c.clinicalStatus }}</span></div>
          <p v-if="!conditions.length" class="dc-empty">none recorded</p>
        </div>
        <div class="dc-card">
          <div class="dc-card-h">Medications</div>
          <div v-for="m in meds" :key="m.id" class="dc-line"><b>{{ m.display }}</b><span class="dc-sub">{{ m.dose }} · {{ m.status }}</span></div>
          <p v-if="!meds.length" class="dc-empty">none recorded</p>
        </div>
        <div class="dc-card danger">
          <div class="dc-card-h">Allergies</div>
          <div v-for="a in allergies" :key="a.id" class="dc-line"><b>{{ a.display }}</b><span class="dc-sub">{{ a.reaction }} · {{ a.criticality }}</span></div>
          <p v-if="!allergies.length" class="dc-empty">no known allergies</p>
        </div>
      </section>

      <!-- vitals + one-tap entry -->
      <section class="dc-card">
        <div class="dc-card-h">Vitals &amp; readings <span class="dc-flash" v-if="flash">{{ flash }}</span></div>
        <div class="dc-entry">
          <input v-model="entry" class="dc-in" placeholder="Type or speak a reading — e.g. BP 138/85, HR 72, glucose 110" @keydown.enter="submitReading" />
          <button v-if="SR" class="dc-mic" :class="{ on: listening }" @click="toggleMic">{{ listening ? '● stop' : '🎙' }}</button>
          <button class="dc-add" :disabled="busy || !entry.trim()" @click="submitReading">Add</button>
        </div>
        <div v-if="readings.length" class="dc-vitals">
          <span v-for="r in readings" :key="r.id" class="dc-vital"><b>{{ r.value }}</b> <i>{{ r.unit }}</i><small>{{ r.display }} · {{ r.source }}</small></span>
        </div>
      </section>

      <!-- labs with trends -->
      <section class="dc-card">
        <div class="dc-card-h">Labs</div>
        <div v-for="o in labs" :key="o.id" class="dc-lab">
          <span class="dc-lab-nm">{{ o.display }}</span>
          <span class="dc-lab-v" :class="{ oor: oor(o) }">{{ o.value }} <i>{{ o.unit }}</i></span>
          <Sparkline v-if="o.trend" :series="o.trend" :w="120" :h="26" :tone="oor(o) ? 'down' : 'accent'" />
          <span class="dc-lab-ref">ref {{ o.refLow ?? '—' }}–{{ o.refHigh ?? '—' }}</span>
          <span class="dc-lab-d">{{ o.effective }}</span>
        </div>
      </section>

      <!-- full history, as far back as it goes -->
      <section class="dc-card">
        <div class="dc-card-h">History <span class="dc-sub">longitudinal · earliest {{ history[history.length - 1]?.date }}</span></div>
        <div v-for="e in history" :key="e.id" class="dc-hx">
          <span class="dc-hx-d">{{ e.date }}</span>
          <span class="dc-hx-dot" />
          <span class="dc-hx-c"><b>{{ e.type }}</b><small>{{ e.provider }} — {{ e.note }}</small></span>
        </div>
      </section>

      <p class="dc-foot">Intelligence for clinicians: coding, guideline guidance, grounded knowledge, and blinded community consults live on the Ask · Capture · Consults tabs — all over this same authorized record.</p>
    </template>
  </div>
</template>

<style scoped>
.dc { font: 15px/1.55 var(--ui); color: var(--ink); max-width: 1100px; }
.dc-dx { font-size: 12px; color: var(--warn); background: var(--warn-wash); border-radius: var(--r-2); padding: 6px 12px; margin: 0 0 var(--sp-3); }
.dc-err { color: var(--fail); } .dc-msg { color: var(--muted); }
.dc-head { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--sp-4); flex-wrap: wrap; margin-bottom: var(--sp-4); }
.dc-who h1 { margin: 0; font-size: 1.5rem; } .dc-demo { color: var(--muted); font-size: .85rem; }
.dc-team { min-width: 260px; } .dc-team-h { font-size: 10.5px; text-transform: uppercase; letter-spacing: .06em; color: var(--faint); }
.dc-team-list { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
.dc-doc { display: inline-flex; align-items: baseline; gap: 6px; background: var(--sunken); border: 1px solid var(--hairline); border-radius: var(--pill); padding: 4px 12px; font-size: 12.5px; } .dc-doc b { font-weight: 600; } .dc-doc i { font-style: normal; color: var(--muted); font-size: 11px; } .dc-doc .vf { color: var(--ok); font-style: normal; }
.dc-grid3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--sp-3); margin-bottom: var(--sp-3); }
@media (max-width: 820px) { .dc-grid3 { grid-template-columns: 1fr; } }
.dc-card { border: 1px solid var(--hairline); border-radius: var(--r-3); background: var(--surface); padding: var(--sp-3) var(--sp-4); margin-bottom: var(--sp-3); }
.dc-card.danger { border-color: color-mix(in srgb, var(--fail) 30%, var(--hairline)); }
.dc-card-h { font-size: 11px; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); font-weight: 700; margin-bottom: 10px; display: flex; align-items: center; gap: 10px; }
.dc-flash { font-weight: 400; color: var(--ok); text-transform: none; letter-spacing: 0; }
.dc-line { padding: 6px 0; border-top: 1px solid var(--hairline); } .dc-line:first-of-type { border-top: 0; } .dc-line b { font-size: 14px; } .dc-sub { display: block; color: var(--muted); font-size: 11.5px; }
.dc-empty { color: var(--faint); font-size: 12.5px; }
.dc-entry { display: flex; gap: 8px; margin-bottom: 10px; }
.dc-in { flex: 1; min-height: 44px; border: 1px solid var(--hairline-strong); border-radius: var(--r-2); padding: 0 14px; font: inherit; font-size: 15px; background: var(--sunken); color: var(--ink); }
.dc-in:focus { outline: 0; border-color: var(--accent); }
.dc-mic { min-width: 52px; min-height: 44px; border: 1px solid var(--hairline-strong); background: var(--surface); border-radius: var(--r-2); font-size: 16px; cursor: pointer; } .dc-mic.on { border-color: var(--fail); color: var(--fail); }
.dc-add { min-height: 44px; padding: 0 20px; background: var(--accent); color: #04122e; border: 0; border-radius: var(--r-2); font: inherit; font-weight: 600; font-size: 15px; cursor: pointer; } .dc-add:disabled { opacity: .5; }
.dc-vitals { display: flex; flex-wrap: wrap; gap: 8px; }
.dc-vital { display: flex; flex-direction: column; align-items: center; background: var(--sunken); border: 1px solid var(--hairline); border-radius: var(--r-2); padding: 8px 14px; min-width: 96px; } .dc-vital b { font-size: 20px; font-variant-numeric: tabular-nums; } .dc-vital i { font-style: normal; font-size: 11px; color: var(--muted); } .dc-vital small { color: var(--faint); font-size: 10.5px; margin-top: 2px; text-align: center; }
.dc-lab { display: grid; grid-template-columns: 1fr auto 120px auto auto; align-items: center; gap: var(--sp-3); padding: 8px 0; border-top: 1px solid var(--hairline); } .dc-lab:first-of-type { border-top: 0; }
@media (max-width: 820px) { .dc-lab { grid-template-columns: 1fr auto; } .dc-lab :deep(svg), .dc-lab-ref, .dc-lab-d { display: none; } }
.dc-lab-nm { font-weight: 600; font-size: 14px; } .dc-lab-v { font-variant-numeric: tabular-nums; font-size: 15px; } .dc-lab-v.oor { color: var(--fail); font-weight: 600; } .dc-lab-v i { font-style: normal; font-size: 11px; color: var(--muted); }
.dc-lab-ref { font-size: 11px; color: var(--faint); } .dc-lab-d { font-size: 11px; color: var(--faint); }
.dc-hx { display: grid; grid-template-columns: 96px 12px 1fr; align-items: start; gap: 10px; padding: 7px 0; }
.dc-hx-d { font-size: 12px; color: var(--muted); text-align: right; } .dc-hx-dot { width: 9px; height: 9px; border-radius: 50%; background: var(--accent); margin-top: 5px; } .dc-hx-c b { font-size: 13.5px; } .dc-hx-c small { display: block; color: var(--muted); font-size: 12px; }
.dc-foot { font-size: 12px; color: var(--faint); border-top: 1px solid var(--hairline); padding-top: 10px; margin-top: var(--sp-3); }
</style>
