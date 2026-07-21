<template>
  <section class="cvw" aria-label="Course">
    <SurfaceHeader :title="course.title" :eyebrow="`Academy · ${course.program}`">
      <template #badge><span class="cvw-pill">{{ course.code }} · {{ course.license }}</span></template>
    </SurfaceHeader>

    <div class="cvw-body">
      <!-- Lessons rail -->
      <aside class="cvw-rail" aria-label="Lessons">
        <div class="cvw-rail-h">{{ course.teacher }} · {{ course.lessons.length }} lectures</div>
        <button v-for="l in course.lessons" :key="l.id" class="cvw-lrow" :class="{ on: l.id === selectedId && tab === 'lesson' }" @click="openLesson(l.id)">
          <span class="cvw-ln">{{ l.n }}</span>
          <span class="cvw-lt"><b>{{ l.title }}</b><small>{{ l.durationMin }} min</small></span>
        </button>
        <button class="cvw-lrow quiz" :class="{ on: tab === 'quiz' }" @click="tab = 'quiz'">
          <span class="cvw-ln">✓</span>
          <span class="cvw-lt"><b>Mastery check</b><small>board · {{ course.assessment.length }} items</small></span>
        </button>
      </aside>

      <!-- Main: lesson OR mastery check -->
      <div class="cvw-main">
        <template v-if="tab === 'lesson' && lesson">
          <div class="cvw-lesson-h">Lecture {{ lesson.n }} · <span>{{ lesson.chunkRef }}</span></div>
          <h2 class="cvw-lesson-title">{{ lesson.title }}</h2>
          <div class="cvw-obj">
            <div class="cvw-obj-h">You'll be able to</div>
            <ul><li v-for="o in lesson.objectives" :key="o">{{ o }}</li></ul>
          </div>
          <p class="cvw-transcript" ref="transcriptEl">{{ lesson.transcript }}</p>
          <div class="cvw-concepts">
            <span v-for="c in lesson.concepts" :key="c" class="cvw-concept">{{ c }}</span>
          </div>
          <p class="cvw-src">Captured from {{ course.source }} · {{ course.license }} · quoted verbatim by the tutor, never paraphrased.</p>
        </template>

        <template v-else-if="tab === 'quiz'">
          <div class="cvw-lesson-h">Mastery check <span>board engine · server-scored · receipts</span></div>
          <div class="cvw-score" :class="{ done: answered === course.assessment.length }">
            <b>{{ correct }}</b> / {{ course.assessment.length }} correct
            <span v-if="answered < course.assessment.length">· {{ course.assessment.length - answered }} to go</span>
            <template v-else>
              <span class="cvw-score-tag">{{ board?.mastered ? 'mastered' : 'keep going' }}</span>
              <span v-if="board" class="cvw-receipt" :title="board.receipt.formula">▪ {{ board.receipt.id }}</span>
            </template>
          </div>
          <div v-for="item in course.assessment" :key="item.id" class="cvw-q">
            <div class="cvw-q-text">{{ item.q }}</div>
            <div class="cvw-opts">
              <button
                v-for="(opt, i) in item.options" :key="i"
                class="cvw-opt"
                :class="optClass(item, i)"
                :disabled="picks[item.id] !== undefined"
                @click="pick(item.id, i)"
              >
                <span class="cvw-opt-mark">{{ optMark(item, i) }}</span>{{ opt }}
              </button>
            </div>
            <div v-if="grading[item.id]" class="cvw-explain">Grading on the board engine…</div>
            <div v-else-if="unavailable[item.id]" class="cvw-explain unavail">Board engine unavailable — click an option to retry.</div>
            <div v-else-if="verdicts[item.id]" class="cvw-explain" :class="{ ok: verdicts[item.id].correct }">
              {{ verdicts[item.id].correct ? '✓ ' : '✗ ' }}{{ verdicts[item.id].explain }}
              <span class="cvw-receipt" :title="verdicts[item.id].receipt.formula">▪ {{ verdicts[item.id].receipt.id }} · {{ verdicts[item.id].chunkRef }}</span>
            </div>
          </div>
        </template>
      </div>

      <!-- Grounded tutor -->
      <aside class="cvw-tutor" aria-label="Tutor">
        <GroundedTutor :course="course" @jump="openLesson" />
      </aside>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from 'vue';
import { useRoute } from 'vue-router';
import SurfaceHeader from '../components/SurfaceHeader.vue';
import GroundedTutor from '../components/GroundedTutor.vue';
import { useCockpit } from '../stores/cockpit';
import { getCourse, type AssessmentItem } from '../data/courseFixture';
import { gradeItem, gradeBoard, type ItemVerdict, type BoardVerdict } from '../services/academyBoard';

const route = useRoute();
const cockpit = useCockpit();
const course = computed(() => getCourse(typeof route.params.id === 'string' ? route.params.id : ''));

const tab = ref<'lesson' | 'quiz'>('lesson');
const selectedId = ref<string>(course.value.lessons[0]?.id ?? '');
const lesson = computed(() => course.value.lessons.find((l) => l.id === selectedId.value));
const transcriptEl = ref<HTMLElement | null>(null);

function openLesson(id: string) {
  selectedId.value = id;
  tab.value = 'lesson';
  nextTick(() => transcriptEl.value?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }));
}

// Mastery check state. The correct answer is NOT in this bundle — every verdict comes from the
// academy-board service, so `picks` only records which option the learner chose; the graded
// verdict (with its receipt + the authoritative answer index) lands in `verdicts`.
const picks = ref<Record<string, number>>({});
const verdicts = ref<Record<string, ItemVerdict>>({});
const grading = ref<Record<string, boolean>>({});
const unavailable = ref<Record<string, boolean>>({});
const board = ref<BoardVerdict | null>(null);

async function pick(itemId: string, i: number) {
  if (picks.value[itemId] !== undefined) return;
  picks.value = { ...picks.value, [itemId]: i };
  unavailable.value = { ...unavailable.value, [itemId]: false };
  grading.value = { ...grading.value, [itemId]: true };
  const v = await gradeItem(course.value.id, itemId, i);
  grading.value = { ...grading.value, [itemId]: false };
  if (v) {
    verdicts.value = { ...verdicts.value, [itemId]: v };
  } else {
    // Board engine unreachable — degrade honestly, never fake a verdict. Re-enable for retry.
    unavailable.value = { ...unavailable.value, [itemId]: true };
    const { [itemId]: _drop, ...rest } = picks.value;
    picks.value = rest;
  }
}

const answered = computed(() => Object.keys(verdicts.value).length);
const correct = computed(() => Object.values(verdicts.value).filter((v) => v.correct).length);
function optClass(item: AssessmentItem, i: number) {
  const v = verdicts.value[item.id];
  if (!v) return '';
  if (i === v.answer) return 'correct';
  if (i === picks.value[item.id]) return 'wrong';
  return 'muted';
}
function optMark(item: AssessmentItem, i: number): string {
  const v = verdicts.value[item.id];
  if (!v) return '○';
  if (i === v.answer) return '✓';
  if (i === picks.value[item.id]) return '✗';
  return '○';
}

// Once every item is graded, fetch the board-level receipt that binds the per-item verdicts —
// so a "mastered" claim is itself checkable, not just a client-side count.
watch(answered, async (n) => {
  if (n === course.value.assessment.length && !board.value) {
    board.value = await gradeBoard(course.value.id, Object.entries(picks.value).map(([itemId, p]) => ({ itemId, pick: p })));
  }
});

watch(course, (c) => {
  selectedId.value = c.lessons[0]?.id ?? '';
  tab.value = 'lesson';
  picks.value = {}; verdicts.value = {}; grading.value = {}; unavailable.value = {}; board.value = null;
});
watch([() => route.path, tab, selectedId], () => {
  cockpit.setContext({ surface: 'Academy · Course', entityLabel: course.value.title, detail: tab.value === 'quiz' ? 'mastery check' : (lesson.value?.title ?? ''), route: route.path });
}, { immediate: true });
onMounted(() => { if (route.path.endsWith('/tutor')) { /* land on flagship with tutor visible */ } });
</script>

<style scoped>
.cvw { height: 100%; min-height: 0; display: grid; grid-template-rows: auto 1fr; gap: 0.75rem; padding: 0.85rem 1rem 1rem; background: var(--bg); color: var(--text); }
.cvw-pill { font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--up); background: rgba(63,185,80,0.14); border-radius: 5px; padding: 0.1rem 0.4rem; }
.cvw-body { min-height: 0; display: grid; grid-template-columns: 220px minmax(360px, 1.5fr) minmax(300px, 1fr); gap: 0.75rem; }
@media (max-width: 1100px) { .cvw-body { grid-template-columns: 190px 1fr; } .cvw-tutor { display: none; } }

.cvw-rail { min-height: 0; overflow-y: auto; border: 1px solid var(--line-2); border-radius: 12px; padding: 0.3rem; display: flex; flex-direction: column; gap: 0.15rem; }
.cvw-rail-h { font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-3); padding: 0.4rem 0.5rem; }
.cvw-lrow { display: flex; align-items: center; gap: 0.55rem; border: none; background: transparent; color: inherit; border-radius: 8px; padding: 0.45rem 0.5rem; cursor: pointer; text-align: left; } .cvw-lrow:hover { background: rgba(255,255,255,0.03); } .cvw-lrow.on { background: color-mix(in srgb, var(--accent) 10%, transparent); box-shadow: inset 2px 0 0 var(--accent); }
.cvw-lrow.quiz { margin-top: 0.3rem; border-top: 1px solid var(--line); border-radius: 0 0 8px 8px; padding-top: 0.55rem; }
.cvw-ln { width: 1.5rem; height: 1.5rem; flex: 0 0 auto; display: grid; place-items: center; border-radius: 50%; border: 1px solid var(--line-2); font-size: 0.72rem; color: var(--text-3); }
.cvw-lrow.on .cvw-ln { border-color: var(--accent); color: var(--accent); }
.cvw-lt { display: flex; flex-direction: column; min-width: 0; } .cvw-lt b { font-size: 0.8rem; font-weight: 600; } .cvw-lt small { font-size: 0.64rem; color: var(--text-3); }

.cvw-main { min-height: 0; overflow-y: auto; border: 1px solid var(--line-2); border-radius: 12px; padding: 1rem 1.1rem 1.2rem; }
.cvw-lesson-h { font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-3); } .cvw-lesson-h span { font-family: ui-monospace, monospace; color: var(--text-3); text-transform: none; letter-spacing: 0; }
.cvw-lesson-title { margin: 0.3rem 0 0.7rem; font-size: 1.35rem; }
.cvw-obj { border: 1px solid var(--line-2); border-radius: 10px; padding: 0.55rem 0.75rem; background: var(--surface); margin-bottom: 0.8rem; }
.cvw-obj-h { font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-3); margin-bottom: 0.25rem; }
.cvw-obj ul { margin: 0; padding-left: 1.1rem; } .cvw-obj li { font-size: 0.82rem; color: var(--text-2); line-height: 1.6; }
.cvw-transcript { font-size: 0.95rem; line-height: 1.7; color: var(--text); margin: 0 0 0.8rem; }
.cvw-concepts { display: flex; flex-wrap: wrap; gap: 0.35rem; margin-bottom: 0.8rem; }
.cvw-concept { font-size: 0.68rem; color: var(--text-2); border: 1px solid var(--line-2); border-radius: 999px; padding: 0.08rem 0.5rem; }
.cvw-src { font-size: 0.7rem; color: var(--text-3); border-top: 1px solid var(--line); padding-top: 0.7rem; }

.cvw-score { font-size: 0.95rem; color: var(--text-2); margin: 0.5rem 0 0.9rem; } .cvw-score b { font-size: 1.4rem; color: var(--text); font-variant-numeric: tabular-nums; }
.cvw-score-tag { margin-left: 0.5rem; font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700; color: var(--up); background: rgba(63,185,80,0.14); border-radius: 4px; padding: 0.08rem 0.4rem; }
.cvw-score.done b { color: #86efac; }
.cvw-q { border-top: 1px solid var(--line); padding: 0.75rem 0; }
.cvw-q-text { font-size: 0.88rem; font-weight: 600; margin-bottom: 0.5rem; }
.cvw-opts { display: flex; flex-direction: column; gap: 0.35rem; }
.cvw-opt { display: flex; align-items: center; gap: 0.5rem; text-align: left; border: 1px solid var(--line-2); background: var(--surface); color: var(--text-2); border-radius: 8px; padding: 0.45rem 0.6rem; font-size: 0.82rem; cursor: pointer; } .cvw-opt:hover:not(:disabled) { border-color: var(--accent); } .cvw-opt:disabled { cursor: default; }
.cvw-opt-mark { flex: 0 0 auto; color: var(--text-3); }
.cvw-opt.correct { border-color: rgba(63,185,80,0.5); background: rgba(63,185,80,0.08); color: #86efac; } .cvw-opt.correct .cvw-opt-mark { color: var(--up); }
.cvw-opt.wrong { border-color: rgba(248,81,73,0.5); background: rgba(248,81,73,0.08); color: #fca5a5; } .cvw-opt.wrong .cvw-opt-mark { color: var(--down); }
.cvw-opt.muted { opacity: 0.5; }
.cvw-explain { margin-top: 0.4rem; font-size: 0.76rem; line-height: 1.5; color: var(--text-3); } .cvw-explain.ok { color: #86efac; } .cvw-explain.unavail { color: var(--down); }
.cvw-receipt { margin-left: 0.4rem; font-family: ui-monospace, monospace; font-size: 0.64rem; color: var(--text-3); white-space: nowrap; }

.cvw-tutor { min-height: 0; overflow-y: auto; }
</style>
