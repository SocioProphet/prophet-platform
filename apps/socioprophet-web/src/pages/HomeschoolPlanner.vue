<template>
  <section class="hp" aria-label="Homeschool planner">
    <SurfaceHeader title="Homeschool Planner" eyebrow="Academy · K-12 · standards-based">
      <template #badge><span class="hp-pill">NGSS · Common Core</span></template>
      <template #actions>
        <button v-if="plan.size" class="hp-reset" @click="resetPlan">Clear plan</button>
      </template>
    </SurfaceHeader>

    <!-- Grade band + subject selectors -->
    <div class="hp-selectors">
      <div class="hp-bands">
        <button v-for="g in gradePrograms" :key="g.band" class="hp-band" :class="{ on: g.band === band }" @click="band = g.band">{{ g.label }}</button>
      </div>
      <div class="hp-subjects">
        <button v-for="s in program.subjects" :key="s.subject" class="hp-subject" :class="{ on: s.subject === subject }" @click="subject = s.subject">
          {{ s.subject }}<span class="hp-subj-cov">{{ coverageOfSubject(s).pct }}%</span>
        </button>
      </div>
    </div>

    <div class="hp-body">
      <!-- Standards for the chosen band + subject -->
      <div class="hp-standards" aria-label="Standards">
        <div class="hp-std-h">{{ strand?.framework }} · {{ subject }} <span>{{ strand?.standards.length }} standards</span></div>
        <div v-for="st in strand?.standards ?? []" :key="st.code" class="hp-std" :class="{ planned: plan.has(st.code), covered: covered.has(st.code) }">
          <div class="hp-std-top">
            <code class="hp-code">{{ st.code }}</code>
            <span class="hp-std-title">{{ st.title }}</span>
            <span class="hp-std-actions">
              <button class="hp-chip" :class="{ on: plan.has(st.code) }" @click="togglePlan(st.code)">{{ plan.has(st.code) ? '✓ in plan' : '+ plan' }}</button>
              <button class="hp-chip cov" :class="{ on: covered.has(st.code) }" :disabled="!plan.has(st.code)" :title="plan.has(st.code) ? 'Mark this standard covered' : 'Add to plan first'" @click="toggleCovered(st.code)">{{ covered.has(st.code) ? '● covered' : '○ covered' }}</button>
            </span>
          </div>
          <p class="hp-std-desc">{{ st.description }}</p>
          <div class="hp-std-foot">
            <span v-for="(r, i) in st.resources" :key="i" class="hp-res" :class="{ uncaptured: !r.captured }">
              {{ r.title }} <em>{{ r.source }}</em><span v-if="!r.captured" class="hp-res-x"> · not yet captured</span>
            </span>
            <span class="hp-skills"><span v-for="sk in st.skills" :key="sk" class="hp-skill">{{ skillName(sk) }}</span></span>
          </div>
        </div>
      </div>

      <!-- My Plan -->
      <aside class="hp-plan" aria-label="My plan">
        <div class="hp-plan-h">My plan</div>
        <template v-if="plan.size">
          <div class="hp-progress">
            <div class="hp-prog-num"><b>{{ covered.size }}</b> / {{ plan.size }}<span>covered</span></div>
            <div class="hp-prog-bar"><span :style="{ width: planPct + '%' }" :class="{ full: planPct >= 100 }" /></div>
            <div class="hp-prog-pct">{{ planPct }}%</div>
          </div>
          <div v-for="grp in planBySubject" :key="grp.subject" class="hp-plan-grp">
            <div class="hp-plan-grp-h">{{ grp.subject }}</div>
            <button v-for="c in grp.codes" :key="c.code" class="hp-plan-item" :class="{ done: covered.has(c.code) }" @click="toggleCovered(c.code)">
              <span class="hp-plan-mark">{{ covered.has(c.code) ? '●' : '○' }}</span>
              <code>{{ c.code }}</code> {{ c.title }}
            </button>
          </div>
          <p class="hp-plan-note">A parent-owned plan against the public standards — coverage tracked locally. As the Commons captures each standard's OER, the tutor grounds on it.</p>
        </template>
        <p v-else class="hp-plan-empty">Add standards to build a term plan. Track what you've covered, see the gaps, and let the grounded tutor teach each one.</p>
      </aside>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue';
import SurfaceHeader from '../components/SurfaceHeader.vue';
import { useCockpit } from '../stores/cockpit';
import { gradePrograms, coverageOfSubject, type SubjectStrand } from '../data/homeschoolFixture';
import { skillName } from '../data/academyFixture';

const cockpit = useCockpit();
const STORE = 'sp-homeschool-v1';

const band = ref<string>('6-8');
const program = computed(() => gradePrograms.find((g) => g.band === band.value) ?? gradePrograms[0]!);
const subject = ref<string>(program.value.subjects[0]?.subject ?? '');
const strand = computed<SubjectStrand | undefined>(() => program.value.subjects.find((s) => s.subject === subject.value) ?? program.value.subjects[0]);

const plan = ref<Set<string>>(new Set());
const covered = ref<Set<string>>(new Set());
function persist() {
  try { localStorage.setItem(STORE, JSON.stringify({ plan: [...plan.value], covered: [...covered.value] })); } catch { /* */ }
}
function togglePlan(code: string) {
  const p = new Set(plan.value);
  if (p.has(code)) { p.delete(code); const c = new Set(covered.value); c.delete(code); covered.value = c; } else p.add(code);
  plan.value = p; persist();
}
function toggleCovered(code: string) {
  if (!plan.value.has(code)) return;
  const c = new Set(covered.value); c.has(code) ? c.delete(code) : c.add(code); covered.value = c; persist();
}
function resetPlan() { plan.value = new Set(); covered.value = new Set(); persist(); }

const planPct = computed(() => (plan.value.size ? Math.round((covered.value.size / plan.value.size) * 100) : 0));
// Codes in the plan, resolved to titles + grouped by subject (across all bands).
const planBySubject = computed(() => {
  const byCode = new Map<string, { code: string; title: string; subject: string }>();
  for (const g of gradePrograms) for (const s of g.subjects) for (const st of s.standards) byCode.set(st.code, { code: st.code, title: st.title, subject: s.subject });
  const groups = new Map<string, { code: string; title: string }[]>();
  for (const code of plan.value) {
    const info = byCode.get(code); if (!info) continue;
    if (!groups.has(info.subject)) groups.set(info.subject, []);
    groups.get(info.subject)!.push({ code: info.code, title: info.title });
  }
  return [...groups.entries()].map(([subject, codes]) => ({ subject, codes }));
});

watch(band, () => { if (!program.value.subjects.some((s) => s.subject === subject.value)) subject.value = program.value.subjects[0]?.subject ?? ''; });
watch([band, subject], () => cockpit.setContext({ surface: 'Academy · Homeschool', entityLabel: `${program.value.label} · ${subject.value}`, detail: `${plan.value.size} in plan`, route: '/academy/homeschool' }), { immediate: true });
onMounted(() => {
  try {
    const raw = localStorage.getItem(STORE);
    if (raw) { const d = JSON.parse(raw) as { plan?: string[]; covered?: string[] }; plan.value = new Set(d.plan ?? []); covered.value = new Set(d.covered ?? []); }
  } catch { /* */ }
});
</script>

<style scoped>
.hp { height: 100%; min-height: 0; display: grid; grid-template-rows: auto auto 1fr; gap: 0.75rem; padding: 0.85rem 1rem 1rem; background: var(--bg); color: var(--text); }
.hp-pill { font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.06em; color: #6ee7b7; background: rgba(63,185,80,0.14); border-radius: 5px; padding: 0.1rem 0.4rem; }
.hp-reset { border: 1px solid var(--line-2); background: transparent; color: var(--text-3); border-radius: 8px; padding: 0.3rem 0.7rem; font-size: 0.76rem; cursor: pointer; } .hp-reset:hover { color: var(--text); }

.hp-selectors { display: flex; flex-direction: column; gap: 0.5rem; }
.hp-bands { display: flex; gap: 0.4rem; }
.hp-band { border: 1px solid var(--line-2); background: transparent; color: var(--text-2); border-radius: 8px; padding: 0.35rem 0.75rem; font-size: 0.8rem; cursor: pointer; } .hp-band.on { border-color: var(--accent); color: var(--accent); background: var(--accent-soft, rgba(120,160,255,0.12)); }
.hp-subjects { display: flex; gap: 0.35rem; flex-wrap: wrap; }
.hp-subject { display: inline-flex; align-items: center; gap: 0.4rem; border: 1px solid var(--line-2); background: transparent; color: var(--text-3); border-radius: 999px; padding: 0.25rem 0.7rem; font-size: 0.78rem; cursor: pointer; } .hp-subject.on { border-color: var(--accent); color: var(--text); }
.hp-subj-cov { font-size: 0.64rem; color: var(--text-3); font-variant-numeric: tabular-nums; }

.hp-body { min-height: 0; display: grid; grid-template-columns: 1fr minmax(280px, 340px); gap: 1.1rem; }
@media (max-width: 980px) { .hp-body { grid-template-columns: 1fr; } .hp-plan { display: none; } }

.hp-standards { min-height: 0; overflow-y: auto; }
.hp-std-h { font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-3); margin-bottom: 0.5rem; } .hp-std-h span { color: var(--text-3); text-transform: none; letter-spacing: 0; }
.hp-std { border-top: 1px solid var(--line); padding: 0.7rem 0; }
.hp-std.planned { box-shadow: inset 3px 0 0 var(--accent); padding-left: 0.6rem; }
.hp-std.covered { box-shadow: inset 3px 0 0 var(--up); }
.hp-std-top { display: flex; align-items: baseline; gap: 0.5rem; flex-wrap: wrap; }
.hp-code { font-family: var(--font-mono); font-size: 0.68rem; color: var(--text-3); }
.hp-std-title { font-size: 0.92rem; font-weight: 650; flex: 1; }
.hp-std-actions { display: flex; gap: 0.35rem; }
.hp-chip { border: 1px solid var(--line-2); background: transparent; color: var(--text-3); border-radius: 6px; padding: 0.15rem 0.5rem; font-size: 0.7rem; cursor: pointer; } .hp-chip:hover { border-color: var(--accent); color: var(--accent); }
.hp-chip.on { border-color: var(--accent); color: var(--accent); background: var(--accent-soft, rgba(120,160,255,0.12)); }
.hp-chip.cov.on { border-color: rgba(63,185,80,0.5); color: #6ee7b7; background: rgba(63,185,80,0.1); }
.hp-chip:disabled { opacity: 0.4; cursor: default; }
.hp-std-desc { font-size: 0.82rem; line-height: 1.55; color: var(--text-2); margin: 0.35rem 0; }
.hp-std-foot { display: flex; align-items: center; gap: 0.5rem 0.9rem; flex-wrap: wrap; font-size: 0.72rem; color: var(--text-3); }
.hp-res em { font-style: normal; color: var(--up); } .hp-res.uncaptured em { color: #e3b341; } .hp-res-x { color: #e3b341; }
.hp-skills { display: flex; gap: 0.3rem; flex-wrap: wrap; margin-left: auto; }
.hp-skill { font-size: 0.64rem; color: var(--text-3); border: 1px solid var(--line); border-radius: 999px; padding: 0.03rem 0.45rem; }

.hp-plan { min-height: 0; overflow-y: auto; border-left: 1px solid var(--line-2); padding-left: 1.1rem; }
.hp-plan-h { font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-3); margin-bottom: 0.6rem; }
.hp-progress { display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.9rem; }
.hp-prog-num { font-size: 0.8rem; color: var(--text-2); } .hp-prog-num b { font-size: 1.5rem; color: var(--text); font-variant-numeric: tabular-nums; } .hp-prog-num span { display: block; font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-3); }
.hp-prog-bar { flex: 1; height: 7px; border-radius: 4px; background: var(--line); overflow: hidden; } .hp-prog-bar span { display: block; height: 100%; background: var(--accent); } .hp-prog-bar span.full { background: var(--up); }
.hp-prog-pct { font-size: 0.82rem; font-weight: 700; color: var(--text); font-variant-numeric: tabular-nums; }
.hp-plan-grp { margin-bottom: 0.7rem; }
.hp-plan-grp-h { font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-3); margin-bottom: 0.25rem; }
.hp-plan-item { display: flex; align-items: baseline; gap: 0.4rem; width: 100%; text-align: left; border: none; background: transparent; color: var(--text-2); padding: 0.28rem 0; font-size: 0.78rem; cursor: pointer; border-bottom: 1px solid var(--line); }
.hp-plan-item:hover { color: var(--text); } .hp-plan-item.done { color: var(--text-3); } .hp-plan-item.done code { text-decoration: line-through; }
.hp-plan-mark { color: var(--text-3); } .hp-plan-item.done .hp-plan-mark { color: var(--up); }
.hp-plan-item code { font-family: var(--font-mono); font-size: 0.68rem; color: var(--text-3); }
.hp-plan-note { font-size: 0.72rem; color: var(--text-3); line-height: 1.5; margin-top: 0.6rem; }
.hp-plan-empty { font-size: 0.82rem; color: var(--text-3); line-height: 1.6; }
</style>
