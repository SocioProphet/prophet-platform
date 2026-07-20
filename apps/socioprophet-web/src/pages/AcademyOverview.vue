<template>
  <section class="ac" aria-label="Academy">
    <SurfaceHeader title="Academy" eyebrow="Alexandrian Academy · Knowledge Commons">
      <template #badge><span class="ac-pill">open · CC</span></template>
    </SurfaceHeader>

    <!-- The moat, stated: what no competitor has all four of. -->
    <div class="ac-moat">
      <div class="ac-moat-lead">A learning platform with four things no one else has together —</div>
      <div class="ac-pillars">
        <div v-for="p in PILLARS" :key="p.t" class="ac-pillar">
          <span class="ac-pillar-g">{{ p.g }}</span>
          <div><b>{{ p.t }}</b><span>{{ p.d }}</span></div>
        </div>
      </div>
    </div>

    <!-- The ladder — K-12 → undergrad → grad → professional (built in your audience order). -->
    <div class="ac-ladder">
      <div v-for="(l, i) in LADDER" :key="l.level" class="ac-rung" :class="{ live: rungCount(l.level) > 0 }">
        <span class="ac-rung-n">{{ i + 1 }}</span>
        <div class="ac-rung-b">
          <b>{{ l.label }}</b>
          <span>{{ l.blurb }}</span>
        </div>
        <span class="ac-rung-c">{{ rungCount(l.level) ? `${rungCount(l.level)} program${rungCount(l.level) === 1 ? '' : 's'}` : 'soon' }}</span>
      </div>
    </div>

    <!-- Featured programs, with real coverage from the registrar shape. -->
    <div class="ac-section-h">Programs <span class="ac-hint">degree-back-into · coverage from the Commons</span></div>
    <div class="ac-programs">
      <RouterLink v-for="p in programs" :key="p.id" class="ac-prog" :to="p.level === 'k12' ? '/academy/homeschool' : '/academy/degrees'">
        <div class="ac-prog-top">
          <span class="ac-level" :class="p.level">{{ p.level === 'k12' ? 'K-12' : p.level }}</span>
          <span class="ac-prog-fw">{{ p.framework }}</span>
        </div>
        <div class="ac-prog-title">{{ p.title }} <span class="ac-cred">{{ p.credential }}</span></div>
        <div class="ac-prog-teacher">tutor embodies {{ p.teacher }}</div>
        <div class="ac-cov">
          <div class="ac-cov-bar"><span :style="{ width: coverageOf(p).pct + '%' }" :class="{ full: coverageOf(p).pct >= 90 }" /></div>
          <span class="ac-cov-n">{{ coverageOf(p).pct }}% captured</span>
        </div>
        <div class="ac-prog-meta">
          {{ coverageOf(p).satisfied }}/{{ coverageOf(p).total }} requirements
          <template v-if="coverageOf(p).requiredUnits">· {{ coverageOf(p).units }}/{{ coverageOf(p).requiredUnits }} units</template>
          · {{ capturedChunks(p).toLocaleString() }} chunks
        </div>
      </RouterLink>
    </div>

    <!-- The graph-native bit: skills reused across programs (one node, many degrees). -->
    <div v-if="shared.length" class="ac-shared">
      <div class="ac-section-h">Shared skills <span class="ac-hint">one node serves many programs — the curriculum is a graph, not a catalog</span></div>
      <div class="ac-skills">
        <span v-for="s in shared" :key="s.id" class="ac-skill">
          {{ s.name }}<span class="ac-skill-n">×{{ s.programs.length }}</span>
        </span>
      </div>
    </div>

    <div class="ac-cta">
      <RouterLink class="ac-cta-btn" to="/academy/homeschool">Open the Homeschool explorer →</RouterLink>
      <RouterLink class="ac-cta-btn" to="/academy/degrees">Open the Degree explorer →</RouterLink>
      <span class="ac-cta-note">Designed on the registrar shape — wiring to the live capture + tutor services is a loader swap.</span>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted } from 'vue';
import SurfaceHeader from '../components/SurfaceHeader.vue';
import { useCockpit } from '../stores/cockpit';
import { programs, LADDER, coverageOf, capturedChunks, sharedSkills, type LadderLevel } from '../data/academyFixture';

const cockpit = useCockpit();
const shared = sharedSkills();

const PILLARS = [
  { g: '◆', t: 'Grounded tutor', d: 'answers cited to the exact lecture — the anti-Chegg' },
  { g: '◈', t: 'Graph-native degree', d: 'skills reuse across programs, not a flat catalog' },
  { g: '✓', t: 'Verified assessment', d: 'the board engine measures mastery, not guesses' },
  { g: '○', t: 'Open & sovereign', d: 'CC-clean corpus, owned — an open Coursera' },
];

function rungCount(level: LadderLevel): number {
  return programs.filter((p) => p.level === level).length;
}

onMounted(() => cockpit.setContext({
  surface: 'Academy',
  entityLabel: `${programs.length} programs`,
  detail: 'Alexandrian Academy · open courseware',
  route: '/academy',
}));
</script>

<style scoped>
.ac { height: 100%; min-height: 0; overflow-y: auto; display: flex; flex-direction: column; gap: 1rem; padding: 0.85rem 1.1rem 1.5rem; background: var(--bg); color: var(--text); }
.ac-pill { font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--up); background: rgba(63,185,80,0.14); border-radius: 5px; padding: 0.1rem 0.4rem; }

/* De-boxed (Tufte): the moat reads from a hairline rule + whitespace, not a bordered card. */
.ac-moat { border: 0; border-top: 2px solid var(--text); border-radius: 0; background: transparent; padding: 0.7rem 0 0.2rem; }
.ac-moat-lead { font-size: 0.9rem; color: var(--text-2); margin-bottom: 0.7rem; }
.ac-pillars { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 0.6rem; }
.ac-pillar { display: flex; gap: 0.55rem; align-items: flex-start; }
.ac-pillar-g { font-size: 1rem; color: var(--accent); line-height: 1.3; flex: 0 0 auto; }
.ac-pillar b { display: block; font-size: 0.86rem; color: var(--text); } .ac-pillar span { font-size: 0.74rem; color: var(--text-3); line-height: 1.45; }

.ac-ladder { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 0.5rem; }
.ac-rung { display: flex; align-items: center; gap: 0.6rem; border: 1px solid var(--line-2); border-radius: 10px; padding: 0.55rem 0.7rem; background: var(--surface); opacity: 0.55; }
.ac-rung.live { opacity: 1; border-left: 3px solid var(--accent); }
.ac-rung-n { width: 1.4rem; height: 1.4rem; flex: 0 0 auto; display: grid; place-items: center; border-radius: 50%; border: 1px solid var(--line-2); font-size: 0.72rem; color: var(--text-3); font-variant-numeric: tabular-nums; }
.ac-rung.live .ac-rung-n { border-color: var(--accent); color: var(--accent); }
.ac-rung-b { flex: 1; min-width: 0; } .ac-rung-b b { display: block; font-size: 0.82rem; } .ac-rung-b span { font-size: 0.68rem; color: var(--text-3); }
.ac-rung-c { font-size: 0.66rem; color: var(--text-3); white-space: nowrap; }

.ac-section-h { font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--text-3); margin-top: 0.3rem; }
.ac-hint { text-transform: none; letter-spacing: 0; color: var(--text-3); margin-left: 0.5rem; }

.ac-programs { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 0.7rem; }
.ac-prog { display: flex; flex-direction: column; gap: 0.35rem; border: 1px solid var(--line-2); border-radius: 12px; background: var(--surface); padding: 0.85rem; text-decoration: none; color: inherit; transition: border-color 0.15s, transform 0.1s; }
.ac-prog:hover { border-color: var(--accent); transform: translateY(-1px); }
.ac-prog-top { display: flex; align-items: center; gap: 0.5rem; }
.ac-level { font-size: 0.58rem; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700; border-radius: 4px; padding: 0.05rem 0.35rem; color: var(--accent); background: var(--accent-soft, rgba(120,160,255,0.12)); }
.ac-level.undergrad { color: #58a6ff; background: rgba(88,166,255,0.14); } .ac-level.k12 { color: #6ee7b7; background: rgba(63,185,80,0.14); }
.ac-prog-fw { font-size: 0.7rem; color: var(--text-3); }
.ac-prog-title { font-size: 1.02rem; font-weight: 650; } .ac-cred { font-size: 0.72rem; color: var(--text-3); font-weight: 400; }
.ac-prog-teacher { font-size: 0.74rem; color: var(--text-2); }
.ac-cov { display: flex; align-items: center; gap: 0.5rem; margin-top: 0.2rem; }
.ac-cov-bar { flex: 1; height: 6px; border-radius: 4px; background: var(--line); overflow: hidden; }
.ac-cov-bar span { display: block; height: 100%; background: var(--accent); } .ac-cov-bar span.full { background: var(--up); }
.ac-cov-n { font-size: 0.72rem; color: var(--text-2); font-variant-numeric: tabular-nums; }
.ac-prog-meta { font-size: 0.7rem; color: var(--text-3); }

.ac-shared { display: flex; flex-direction: column; gap: 0.4rem; }
.ac-skills { display: flex; flex-wrap: wrap; gap: 0.4rem; }
.ac-skill { display: inline-flex; align-items: center; gap: 0.35rem; font-size: 0.74rem; color: var(--text-2); border: 1px solid var(--line-2); border-radius: 999px; padding: 0.15rem 0.55rem; }
.ac-skill-n { font-size: 0.62rem; color: var(--accent); font-variant-numeric: tabular-nums; }

.ac-cta { display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap; margin-top: 0.3rem; }
.ac-cta-btn { text-decoration: none; border: 1px solid var(--line-2); border-radius: 8px; padding: 0.4rem 0.8rem; font-size: 0.8rem; color: var(--text); background: var(--surface); }
.ac-cta-btn:hover { border-color: var(--accent); color: var(--accent); }
.ac-cta-note { font-size: 0.7rem; color: var(--text-3); }
</style>
