<script setup lang="ts">
// Ask-my-agent — the patient's magic. Ask in plain words; the twin recalls from a lifetime of records
// and answers WITH the sources cited + their trust tier. Local-first (sovereign); non-diagnostic.
import { ref } from 'vue';
import { askTwin, guidance, type AskAnswer, type GuidanceItem } from '../services/healthTwinApi';

const q = ref('');
const ans = ref<AskAnswer | null>(null);
const busy = ref(false);
const err = ref('');
const guide = ref<GuidanceItem[] | null>(null);
const gBusy = ref(false);
async function loadGuidance() {
  gBusy.value = true; err.value = '';
  try { guide.value = (await guidance()).items; }
  catch (e) { err.value = e instanceof Error ? e.message : 'guidance failed'; }
  finally { gBusy.value = false; }
}
const examples = [
  'where did I hurt my knee as a kid',
  'are my cholesterol numbers going up',
  'what about my heart',
  'what imaging have I had',
];
async function ask(x?: string) {
  const query = (x ?? q.value).trim();
  if (!query) return;
  q.value = query; busy.value = true; err.value = '';
  try { ans.value = await askTwin(query); }
  catch (e) { err.value = e instanceof Error ? e.message : 'ask failed'; }
  finally { busy.value = false; }
}
const kindIcon: Record<string, string> = { lab: '🧪', condition: '⚕', encounter: '🗓', imaging: '🩻' };
</script>

<template>
  <div class="ask">
    <div class="ask-h">
      <span class="ask-mark">✦</span>
      <div><h2>Ask my twin</h2><span class="ask-sub">recall a lifetime of your records, in plain words — cited, never a diagnosis</span></div>
    </div>

    <div class="ask-box">
      <input v-model="q" class="ask-in" placeholder="e.g. where did I hurt my knee as a kid?" @keydown.enter="ask()" />
      <button class="ask-go" :disabled="busy || !q.trim()" @click="ask()">{{ busy ? '…' : 'Ask' }}</button>
    </div>
    <div class="ask-ex">
      <button v-for="e in examples" :key="e" class="ex" @click="ask(e)">{{ e }}</button>
      <button class="ex guide-btn" @click="loadGuidance">{{ gBusy ? 'checking…' : '⟢ what do the guidelines say about my numbers?' }}</button>
    </div>

    <p v-if="err" class="ask-err">{{ err }}</p>

    <!-- guideline-grounded, cited, non-diagnostic guidance over the twin's own numbers -->
    <div v-if="guide" class="guide">
      <div class="guide-h">What the guidelines say about your numbers <span>cited · not a diagnosis</span></div>
      <div v-for="(g, i) in guide" :key="i" class="g-item">
        <div class="g-top"><span class="g-str" :data-s="g.strength">{{ g.strength }}</span><b>{{ g.finding }}</b></div>
        <p class="g-says">{{ g.says }}</p>
        <span class="g-src">⟢ {{ g.source }}</span>
      </div>
      <p v-if="!guide.length" class="ask-err" style="color:var(--muted)">Your numbers don't trigger any guideline flags right now.</p>
    </div>

    <div v-if="ans" class="ans">
      <p class="ans-q">“{{ ans.question }}”</p>
      <p class="ans-a">{{ ans.answer }}</p>
      <div v-if="ans.citations.length" class="cites">
        <div class="cites-h">From your records</div>
        <div v-for="c in ans.citations" :key="c.id" class="cite">
          <span class="c-ic">{{ kindIcon[c.kind] || '•' }}</span>
          <span class="c-tx">{{ c.text }}</span>
          <span v-if="c.tier" class="c-tier">{{ c.tier }}</span>
        </div>
      </div>
      <p class="ans-foot">Recalled from your own records ({{ ans.retrieval }}) — not medical advice.</p>
    </div>
  </div>
</template>

<style scoped>
.ask { font: 14px/1.55 var(--ui); color: var(--ink); max-width: 640px; }
.ask-h { display: flex; align-items: center; gap: var(--sp-3); margin-bottom: var(--sp-3); }
.ask-mark { color: var(--accent); font-size: 1.2rem; } .ask-h h2 { margin: 0; font-size: 1.15rem; } .ask-sub { color: var(--muted); font-size: .78rem; }
.ask-box { display: flex; gap: 8px; }
.ask-in { flex: 1; border: 1px solid var(--hairline-strong); border-radius: var(--r-2); padding: 10px 12px; font: inherit; font-size: 14px; background: var(--surface); color: var(--ink); }
.ask-in:focus { outline: 0; border-color: var(--accent); }
.ask-go { background: var(--accent); color: #04122e; border: 0; border-radius: var(--r-2); padding: 0 18px; font: inherit; font-weight: 600; cursor: pointer; } .ask-go:disabled { opacity: .5; }
.ask-ex { display: flex; flex-wrap: wrap; gap: 6px; margin: 10px 0 0; }
.ex { border: 1px solid var(--hairline); background: var(--sunken); color: var(--ink-2); border-radius: var(--pill); padding: 4px 12px; font: inherit; font-size: 12px; cursor: pointer; } .ex:hover { border-color: var(--accent); color: var(--accent-ink); }
.ask-err { color: var(--fail); font-size: 12.5px; }
.ans { margin-top: var(--sp-4); border-top: 1px solid var(--hairline); padding-top: var(--sp-3); }
.ans-q { color: var(--muted); font-style: italic; margin: 0 0 .5em; }
.ans-a { white-space: pre-wrap; font-size: 14.5px; line-height: 1.6; margin: 0 0 var(--sp-3); }
.cites { border: 1px solid var(--hairline); border-radius: var(--r-3); background: var(--sunken); padding: var(--sp-3); }
.cites-h { font-size: 10.5px; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); margin-bottom: 8px; }
.cite { display: grid; grid-template-columns: 18px 1fr auto; align-items: baseline; gap: 8px; padding: 5px 0; border-top: 1px solid var(--hairline); font-size: 13px; } .cite:first-of-type { border-top: 0; }
.c-ic { text-align: center; } .c-tx { color: var(--ink-2); } .c-tier { font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; }
.ans-foot { font-size: 11px; color: var(--faint); margin: var(--sp-3) 0 0; }
.guide-btn { border-style: dashed; border-color: var(--accent); color: var(--accent-ink); }
.guide { margin-top: var(--sp-4); border-top: 1px solid var(--hairline); padding-top: var(--sp-3); }
.guide-h { font-size: 12px; font-weight: 600; margin-bottom: 10px; } .guide-h span { font-weight: 400; color: var(--muted); font-size: 10.5px; margin-left: 6px; }
.g-item { border: 1px solid var(--hairline); border-radius: var(--r-3); background: var(--sunken); padding: var(--sp-3); margin-bottom: 8px; }
.g-top { display: flex; align-items: baseline; gap: 8px; margin-bottom: 4px; } .g-top b { font-size: 13px; }
.g-str { font-size: 9.5px; text-transform: uppercase; letter-spacing: .05em; border-radius: var(--pill); padding: 1px 8px; background: var(--sunken); color: var(--muted); border: 1px solid var(--hairline-strong); }
.g-str[data-s="confirm"] { color: var(--warn); border-color: var(--warn); } .g-str[data-s="discuss"] { color: var(--accent-ink); background: var(--accent-wash); border-color: var(--accent); } .g-str[data-s="screen"] { color: var(--ok); border-color: var(--ok); }
.g-says { font-size: 13px; line-height: 1.55; color: var(--ink-2); margin: 0 0 6px; }
.g-src { font-size: 11px; color: var(--faint); }
</style>
