<template>
  <div class="gt">
    <div class="gt-head">
      <span class="gt-title">Grounded Tutor</span>
      <span v-if="course" class="gt-persona">in the voice of {{ course.teacher }}</span>
    </div>
    <p class="gt-blurb">{{ course ? 'Ask about the course.' : 'Ask about this standard.' }} Every answer is <b>quoted and cited</b> to captured material — it never invents.</p>

    <form class="gt-ask" @submit.prevent="ask">
      <input v-model="qText" class="gt-input" type="text" placeholder="e.g. why doesn't a ball fall faster if you throw it sideways?" aria-label="Ask the tutor" />
      <button class="gt-go" type="submit" :disabled="!qText.trim() || loading">Ask</button>
    </form>

    <!-- Engine switch — the local+cloud seam: Auto tries cloud academy ingest → local Noetica → Commons. -->
    <div class="gt-src" role="group" aria-label="Retrieval engine">
      <span class="gt-src-h">engine</span>
      <button v-for="s in SOURCES" :key="s.v" type="button" class="gt-src-btn" :class="{ on: source === s.v }" @click="source = s.v">{{ s.label }}</button>
    </div>

    <div v-if="loading" class="gt-loading"><span class="gt-load-dot" /> grounding…</div>

    <div v-else-if="!answer" class="gt-seeds">
      <span class="gt-seeds-h">try:</span>
      <button v-for="s in SEEDS" :key="s" class="gt-seed" @click="qText = s; ask()">{{ s }}</button>
    </div>

    <div v-else class="gt-answer" :class="{ nomatch: !answer.cited }">
      <template v-if="answer.cited">
        <p class="gt-persona-line">{{ answer.intro }}</p>
        <blockquote class="gt-quote">“{{ answer.quote }}”</blockquote>
        <!-- Commons: jump to the in-app lecture. Cloud/local with a URL: open it. Else: static ref. -->
        <button v-if="answer.lessonId" class="gt-cite" @click="$emit('jump', answer.lessonId)">
          <span class="gt-cite-g">◆</span>
          <span>Lecture {{ answer.lessonN }} · {{ answer.title }}</span>
          <code>{{ answer.chunkRef }}</code>
          <span class="gt-cite-open">open →</span>
        </button>
        <a v-else-if="answer.uri" class="gt-cite" :href="answer.uri" target="_blank" rel="noreferrer">
          <span class="gt-cite-g">◆</span><span>{{ answer.title }}</span><code>{{ answer.chunkRef }}</code><span class="gt-cite-open">open ↗</span>
        </a>
        <div v-else class="gt-cite static">
          <span class="gt-cite-g">◆</span><span>{{ answer.title }}</span><code>{{ answer.chunkRef }}</code>
        </div>
        <div class="gt-prov">
          <span class="gt-prov-tag">extractive · quoted, not generated</span>
          <span class="gt-origin" :class="answer.origin" :title="originMeta[answer.origin].label">{{ originMeta[answer.origin].glyph }} {{ originMeta[answer.origin].label }}</span>
          <span v-if="answer.concepts.length" class="gt-prov-concepts">on {{ answer.concepts.join(', ') }}</span>
        </div>
      </template>
      <template v-else>
        <p class="gt-nomatch">I answer only from the captured corpus, and I don’t find this yet. This standard’s material isn’t captured — the Commons is still filling in.<span v-if="topConcepts.length"> Try: <b>{{ topConcepts.join(', ') }}</b>.</span></p>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import type { Course } from '../data/courseFixture';
import { retrievePassages, ORIGIN_META, type AcademySource, type PassageOrigin } from '../services/academyApi';

// `course` is optional: with it, Commons falls back to the in-app lecture transcripts; without it
// (e.g. the Homeschool planner teaching a standard) the tutor grounds purely on the live academy
// ingest / local Noetica. `seed` prefills + auto-asks a question — used to teach a specific standard.
const props = defineProps<{ course?: Course; seed?: string }>();
defineEmits<{ (e: 'jump', lessonId: string): void }>();

const qText = ref('');
const SEEDS = [
  'what is the difference between velocity and acceleration?',
  'why do action and reaction forces not cancel?',
  'is there a centrifugal force?',
];

const STOP = new Set(['the', 'a', 'an', 'is', 'are', 'of', 'to', 'in', 'on', 'and', 'or', 'do', 'does', 'why', 'what', 'how', 'if', 'you', 'your', 'it', 'its', 'be', 'for', 'that', 'this', 'at', 'as', 'with', 'not', 'no', 'they', 'them', 'from', 'by', 'can', 'we', 'i', 'me', 'my']);
function tokens(s: string): string[] {
  return s.toLowerCase().replace(/[^a-z0-9\s]/g, ' ').split(/\s+/).filter((t) => t.length > 1 && !STOP.has(t));
}

const topConcepts = computed(() => {
  const all = (props.course?.lessons ?? []).flatMap((l) => l.concepts);
  return [...new Set(all)].slice(0, 5);
});

interface Answer { cited: boolean; intro: string; quote: string; lessonId: string; lessonN: number; title: string; chunkRef: string; concepts: string[]; origin: PassageOrigin; uri?: string }
const answer = ref<Answer | null>(null);
const loading = ref(false);
const source = ref<AcademySource>('auto');
const SOURCES: { v: AcademySource; label: string }[] = [
  { v: 'auto', label: 'Auto' }, { v: 'cloud', label: 'Cloud' }, { v: 'local', label: 'Local' }, { v: 'fixture', label: 'Commons' },
];
const originMeta = ORIGIN_META;

// Pick the single most query-relevant sentence from a passage (tightest quote).
function sentenceOf(text: string, qt: string[]): string {
  const sentences = text.split(/(?<=[.!?])\s+/).filter((s) => s.trim().length > 0);
  let best = sentences[0] ?? text; let sc = -1;
  for (const s of sentences) {
    const st = new Set(tokens(s));
    const overlap = qt.reduce((n, t) => n + (st.has(t) ? 1 : 0), 0);
    if (overlap > sc) { sc = overlap; best = s; }
  }
  return best.trim();
}

// Commons grounding — extractive over the in-app captured transcripts (the guaranteed fallback).
function fixtureAnswer(qt: string[]): Answer {
  const lessons = props.course?.lessons ?? [];
  if (lessons.length === 0) return { cited: false, intro: '', quote: '', lessonId: '', lessonN: 0, title: '', chunkRef: '', concepts: [], origin: 'fixture' };
  let best: { lesson: typeof lessons[number]; score: number } | null = null;
  for (const lesson of lessons) {
    const conceptToks = new Set(lesson.concepts.flatMap(tokens));
    const titleToks = new Set(tokens(lesson.title));
    const bodyToks = new Set(tokens(lesson.transcript));
    let score = 0;
    for (const t of qt) {
      if (conceptToks.has(t)) score += 3;
      if (titleToks.has(t)) score += 2;
      if (bodyToks.has(t)) score += 1;
    }
    if (!best || score > best.score) best = { lesson, score };
  }
  if (!best || best.score === 0) {
    return { cited: false, intro: '', quote: '', lessonId: '', lessonN: 0, title: '', chunkRef: '', concepts: [], origin: 'fixture' };
  }
  const hitConcepts = best.lesson.concepts.filter((c) => tokens(c).some((t) => qt.includes(t)));
  return {
    cited: true,
    intro: `Here's what ${props.course?.teacher ?? 'the source'} says on this:`,
    quote: sentenceOf(best.lesson.transcript, qt),
    lessonId: best.lesson.id, lessonN: best.lesson.n, title: best.lesson.title, chunkRef: best.lesson.chunkRef,
    concepts: hitConcepts.length ? hitConcepts : best.lesson.concepts.slice(0, 2),
    origin: 'fixture',
  };
}

async function ask() {
  const query = qText.value.trim();
  if (!query) return;
  const qt = tokens(query);
  if (qt.length === 0) { answer.value = fixtureAnswer(qt); return; }
  loading.value = true;
  try {
    // Try the live engine(s) first (cloud academy ingest / local Noetica), unless Commons is forced.
    if (source.value !== 'fixture') {
      const { passages, origin } = await retrievePassages(query, source.value);
      if (passages.length) {
        const top = passages[0]!;
        answer.value = {
          cited: true,
          intro: `From the ${originMeta[origin].label}:`,
          quote: sentenceOf(top.text, qt) || top.text,
          lessonId: '', lessonN: 0, title: top.title, chunkRef: top.chunkRef, concepts: [],
          origin, uri: top.uri,
        };
        return;
      }
    }
    // Nothing live (or Commons forced) → extractive over the captured transcripts.
    answer.value = fixtureAnswer(qt);
  } finally {
    loading.value = false;
  }
}

// Teach a specific standard/topic: when `seed` changes, prefill and ask against the live corpus.
watch(() => props.seed, (s) => { if (s) { qText.value = s; void ask(); } }, { immediate: true });
</script>

<style scoped>
.gt { border: 1px solid var(--line-2); border-radius: 12px; background: var(--surface); padding: 0.85rem; display: flex; flex-direction: column; gap: 0.6rem; }
.gt-head { display: flex; align-items: baseline; gap: 0.5rem; flex-wrap: wrap; }
.gt-title { font-size: 0.9rem; font-weight: 700; color: var(--text); }
.gt-persona { font-size: 0.7rem; color: var(--accent); }
.gt-blurb { margin: 0; font-size: 0.74rem; color: var(--text-3); line-height: 1.5; } .gt-blurb b { color: var(--text-2); }
.gt-ask { display: flex; gap: 0.5rem; }
.gt-input { flex: 1; min-width: 0; border: 1px solid var(--line-2); background: var(--surface-2, rgba(255,255,255,0.02)); color: var(--text); border-radius: 8px; padding: 0.45rem 0.6rem; font-size: 0.82rem; }
.gt-input:focus { outline: none; border-color: var(--accent); }
.gt-go { border: 1px solid var(--accent); background: var(--accent-soft, rgba(120,160,255,0.14)); color: var(--accent); border-radius: 8px; padding: 0.45rem 0.9rem; font-size: 0.8rem; font-weight: 600; cursor: pointer; } .gt-go:disabled { opacity: 0.5; cursor: default; }
.gt-seeds { display: flex; flex-wrap: wrap; gap: 0.35rem; align-items: center; }
.gt-seeds-h { font-size: 0.68rem; color: var(--text-3); }
.gt-seed { border: 1px solid var(--line-2); background: transparent; color: var(--text-2); border-radius: 999px; padding: 0.18rem 0.55rem; font-size: 0.7rem; cursor: pointer; text-align: left; } .gt-seed:hover { border-color: var(--accent); color: var(--accent); }

.gt-answer { border-top: 1px solid var(--line); padding-top: 0.6rem; }
.gt-persona-line { margin: 0 0 0.4rem; font-size: 0.78rem; color: var(--text-2); }
.gt-quote { margin: 0 0 0.55rem; padding: 0.5rem 0.7rem; border-left: 3px solid var(--accent); background: var(--surface-2, rgba(255,255,255,0.015)); border-radius: 0 8px 8px 0; font-size: 0.9rem; line-height: 1.6; color: var(--text); }
.gt-cite { display: flex; align-items: center; gap: 0.5rem; width: 100%; text-align: left; border: 1px solid var(--line-2); border-radius: 8px; padding: 0.4rem 0.6rem; background: transparent; color: var(--text-2); cursor: pointer; font-size: 0.76rem; } .gt-cite:hover { border-color: var(--accent); }
.gt-cite-g { color: var(--accent); } .gt-cite code { font-family: ui-monospace, monospace; font-size: 0.68rem; color: var(--text-3); } .gt-cite-open { margin-left: auto; color: var(--accent); }
.gt-prov { display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center; margin-top: 0.4rem; }
.gt-prov-tag { font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700; color: var(--up); background: rgba(63,185,80,0.12); border: 1px solid rgba(63,185,80,0.35); border-radius: 4px; padding: 0.05rem 0.4rem; }
.gt-prov-concepts { font-size: 0.68rem; color: var(--text-3); }
.gt-nomatch { margin: 0; font-size: 0.8rem; color: var(--text-2); line-height: 1.55; } .gt-nomatch b { color: var(--text); }

/* Engine switch (local + cloud seam) */
.gt-src { display: flex; align-items: center; gap: 0.3rem; }
.gt-src-h { font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-3); margin-right: 0.15rem; }
.gt-src-btn { border: 1px solid var(--line-2); background: transparent; color: var(--text-3); border-radius: 6px; padding: 0.14rem 0.5rem; font-size: 0.68rem; cursor: pointer; } .gt-src-btn.on { border-color: var(--accent); color: var(--accent); background: var(--accent-soft, rgba(120,160,255,0.12)); }
.gt-loading { display: flex; align-items: center; gap: 0.4rem; font-size: 0.76rem; color: var(--text-3); padding: 0.3rem 0; }
.gt-load-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--accent); animation: gtPulse 0.9s ease-in-out infinite; }
@keyframes gtPulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
@media (prefers-reduced-motion: reduce) { .gt-load-dot { animation: none; } }
.gt-cite.static { cursor: default; }
.gt-origin { display: inline-flex; align-items: center; gap: 0.25rem; font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.04em; font-weight: 700; border-radius: 4px; padding: 0.05rem 0.4rem; border: 1px solid var(--line-2); color: var(--text-3); }
.gt-origin.cloud { color: #58a6ff; border-color: rgba(88,166,255,0.4); }
.gt-origin.local { color: #6ee7b7; border-color: rgba(63,185,80,0.4); }
.gt-origin.fixture { color: var(--text-3); }
</style>
