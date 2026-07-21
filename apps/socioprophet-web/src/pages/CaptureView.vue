<script setup lang="ts">
// Capture — "talk, it writes the note; snap, it pulls the film." Voice dictation (Web Speech API) → a
// note in the record; camera/photo/document → a hash-sealed media record. Each lands with provenance +
// an epistemic tier. v1: dictation + capture flow real; clinical-grade ambient ASR + OCR/vision are the
// depth follow-on. Non-diagnostic; synthetic/local only.
import { ref, computed } from 'vue';
import { capture, type Captured } from '../services/healthTwinApi';

const items = ref<Captured[]>([]);
const noteText = ref('');
const listening = ref(false);
const busy = ref('');
const previews = ref<Record<string, string>>({});

const SR = typeof window !== 'undefined' ? ((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition) : null;
const speechOk = computed(() => !!SR);
let rec: any = null;
function toggleMic() {
  if (!SR) return;
  if (listening.value) { rec && rec.stop(); return; }
  rec = new SR(); rec.continuous = true; rec.interimResults = true; rec.lang = 'en-US';
  rec.onresult = (e: any) => {
    let final = '';
    for (let i = e.resultIndex; i < e.results.length; i++) if (e.results[i].isFinal) final += e.results[i][0].transcript;
    if (final) noteText.value = (noteText.value + ' ' + final.trim()).trim();
  };
  rec.onend = () => { listening.value = false; };
  rec.start(); listening.value = true;
}
async function saveNote() {
  const t = noteText.value.trim(); if (!t) return;
  busy.value = 'note';
  try {
    const caption = t.split(/\s+/).slice(0, 6).join(' ') + (t.split(/\s+/).length > 6 ? '…' : '');
    const r = await capture({ kind: 'note', by: 'clinician', caption, text: t });
    items.value.unshift(r.captured); noteText.value = '';
  } finally { busy.value = ''; }
}
function djb2(s: string) { let h = 5381; for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) & 0xffffffff; return (h >>> 0).toString(16); }
async function onFile(e: Event, kind: 'photo' | 'document') {
  const f = (e.target as HTMLInputElement).files?.[0]; if (!f) return;
  busy.value = kind;
  try {
    const hash = djb2(`${f.name}|${f.size}|${f.lastModified}`);
    const r = await capture({ kind, by: 'patient', caption: f.name, contentHash: hash });
    if (kind === 'photo') previews.value[r.captured.id] = URL.createObjectURL(f);
    items.value.unshift(r.captured);
  } finally { busy.value = ''; (e.target as HTMLInputElement).value = ''; }
}
</script>

<template>
  <div class="cap">
    <div class="cap-h"><span class="cap-mark">◉</span><div><h2>Capture</h2><span class="cap-sub">talk, it writes the note · snap or upload, it lands in the record — hash-sealed, tier-tagged</span></div></div>

    <div class="cap-grid">
      <!-- VOICE NOTE -->
      <section class="card">
        <div class="card-h"><h3>Voice note</h3><span class="tier attested">clinician-attested</span></div>
        <textarea v-model="noteText" rows="4" class="ta" placeholder="Dictate or type the encounter note…"></textarea>
        <div class="row">
          <button v-if="speechOk" class="mic" :class="{ on: listening }" @click="toggleMic">{{ listening ? '● recording — stop' : '🎙 dictate' }}</button>
          <span v-else class="nospeech">dictation unavailable in this browser — type the note</span>
          <button class="save" :disabled="busy === 'note' || !noteText.trim()" @click="saveNote">Save note</button>
        </div>
      </section>

      <!-- MEDIA -->
      <section class="card">
        <div class="card-h"><h3>Photo &amp; media</h3><span class="tier observed">self-reported</span></div>
        <div class="drops">
          <label class="drop">
            <input type="file" accept="image/*" capture="environment" @change="(e) => onFile(e, 'photo')" hidden />
            <span class="d-ic">📷</span><span>Camera / photo</span>
          </label>
          <label class="drop">
            <input type="file" accept="image/*,application/pdf" @change="(e) => onFile(e, 'document')" hidden />
            <span class="d-ic">📄</span><span>Document / PDF</span>
          </label>
        </div>
        <p class="hint">X-ray / MRI / CT arrive via the DICOM connector (Sources). Point-of-care camera, ECG &amp; scope are the same capture path.</p>
      </section>
    </div>

    <!-- CAPTURED LIST -->
    <section v-if="items.length" class="captured">
      <div class="captured-h">Captured this session · {{ items.length }}</div>
      <div v-for="it in items" :key="it.id" class="cap-item">
        <img v-if="previews[it.id]" :src="previews[it.id]" class="thumb" alt="capture preview" />
        <span v-else class="ic">{{ it.kind === 'note' ? '🗒' : it.kind === 'photo' ? '🖼' : '📄' }}</span>
        <div class="ci-body">
          <b>{{ it.caption }}</b>
          <small v-if="it.text">{{ it.text }}</small>
          <div class="ci-meta"><span class="tier" :class="it.tier === 'attested' ? 'attested' : 'observed'">{{ it.tier }}</span><span class="by">{{ it.by }}</span><span class="hash mono">{{ it.contentHash }}</span></div>
          <div v-if="it.coded && it.coded.length" class="coded">
            <span v-for="c in it.coded" :key="c.code" class="code-chip" :class="{ neg: c.negated }" :title="`${c.codeSystem} ${c.code}${c.negated ? ' · negated' : ''}`">{{ c.negated ? '∅ ' : '' }}{{ c.display }} <i>{{ c.codeSystem }}</i></span>
          </div>
        </div>
      </div>
    </section>

    <p class="cap-foot">⚕ Everything captured is hash-sealed with provenance + a trust tier. Non-diagnostic; synthetic/local only.</p>
  </div>
</template>

<style scoped>
.cap { font: 14px/1.55 var(--ui); color: var(--ink); max-width: 720px; }
.cap-h { display: flex; align-items: center; gap: var(--sp-3); margin-bottom: var(--sp-3); }
.cap-mark { color: var(--accent); font-size: 1.15rem; } .cap-h h2 { margin: 0; font-size: 1.15rem; } .cap-sub { color: var(--muted); font-size: .78rem; }
.cap-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--sp-3); }
@media (max-width: 620px) { .cap-grid { grid-template-columns: 1fr; } }
.card { border: 1px solid var(--hairline); border-radius: var(--r-3); background: var(--surface); padding: var(--sp-3); }
.card-h { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; } .card-h h3 { margin: 0; font-size: 13px; }
.tier { font-size: 9.5px; text-transform: uppercase; letter-spacing: .04em; border-radius: var(--pill); padding: 1px 8px; }
.tier.attested { color: var(--epi-attested, var(--accent-ink)); background: var(--accent-wash); } .tier.observed { color: var(--muted); background: var(--sunken); }
.ta { width: 100%; box-sizing: border-box; border: 1px solid var(--hairline-strong); border-radius: var(--r-2); padding: 8px 10px; font: inherit; font-size: 13px; background: var(--sunken); color: var(--ink); resize: vertical; }
.row { display: flex; align-items: center; gap: 8px; margin-top: 8px; flex-wrap: wrap; }
.mic { border: 1px solid var(--hairline-strong); background: var(--surface); color: var(--ink-2); border-radius: var(--pill); padding: 5px 14px; font: inherit; font-size: 12.5px; cursor: pointer; } .mic.on { border-color: var(--fail); color: var(--fail); }
.nospeech { font-size: 11.5px; color: var(--faint); }
.save { margin-left: auto; background: var(--accent); color: #04122e; border: 0; border-radius: var(--r-2); padding: 6px 14px; font: inherit; font-weight: 600; cursor: pointer; } .save:disabled { opacity: .5; }
.drops { display: flex; gap: 8px; }
.drop { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 4px; border: 1px dashed var(--hairline-strong); border-radius: var(--r-2); padding: 14px 8px; cursor: pointer; color: var(--ink-2); font-size: 12px; } .drop:hover { border-color: var(--accent); background: var(--sunken); }
.d-ic { font-size: 22px; }
.hint { font-size: 11px; color: var(--faint); margin: 8px 0 0; }
.captured { margin-top: var(--sp-4); }
.captured-h { font-size: 10.5px; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); margin-bottom: 8px; }
.cap-item { display: flex; gap: 10px; align-items: flex-start; padding: 8px 0; border-top: 1px solid var(--hairline); } .cap-item:first-of-type { border-top: 0; }
.thumb { width: 44px; height: 44px; object-fit: cover; border-radius: var(--r-2); border: 1px solid var(--hairline); } .ic { font-size: 22px; width: 44px; text-align: center; }
.ci-body { min-width: 0; } .ci-body b { font-size: 13px; } .ci-body small { display: block; color: var(--muted); font-size: 11.5px; margin: 1px 0 3px; }
.ci-meta { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; font-size: 10px; } .by { color: var(--faint); text-transform: uppercase; letter-spacing: .04em; } .hash { color: var(--faint); } .mono { font-family: var(--mono); }
.coded { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 5px; }
.code-chip { font-size: 10.5px; color: var(--accent-ink); background: var(--accent-wash); border: 1px solid var(--accent); border-radius: var(--pill); padding: 1px 8px; } .code-chip i { font-style: normal; color: var(--muted); font-size: 9px; }
.code-chip.neg { color: var(--muted); background: var(--sunken); border-color: var(--hairline); text-decoration: line-through; }
.cap-foot { font-size: 11px; color: var(--faint); border-top: 1px solid var(--hairline); padding-top: 10px; margin-top: var(--sp-4); }
</style>
