<template>
  <section class="dx" aria-label="Academy explorer">
    <SurfaceHeader :title="isK12 ? 'Homeschool Explorer' : 'Degree Explorer'" :eyebrow="isK12 ? 'Academy · K-12 · standards-based' : 'Academy · University · degree-back-into'">
      <template #badge><span class="dx-pill">{{ isK12 ? 'NGSS · Common Core' : 'MIT catalogue' }}</span></template>
    </SurfaceHeader>

    <SplitPane storage-key="academy-explorer" label="programs" :initial="300">
      <template #list>
        <div class="dx-list" aria-label="Programs">
          <p class="dx-count">{{ list.length }} program{{ list.length === 1 ? '' : 's' }}</p>
          <button v-for="p in list" :key="p.id" class="dx-row" :class="{ on: p.id === selectedId }" @click="selectedId = p.id">
            <div class="dx-row-title">{{ p.title }}</div>
            <div class="dx-row-meta">{{ p.credential }} · {{ p.framework }}</div>
            <div class="dx-row-cov">
              <div class="dx-cov-bar"><span :style="{ width: coverageOf(p).pct + '%' }" :class="{ full: coverageOf(p).pct >= 90 }" /></div>
              <span>{{ coverageOf(p).pct }}%</span>
            </div>
          </button>
          <p v-if="list.length === 0" class="dx-empty">No programs at this level yet.</p>
        </div>
      </template>

      <template #detail>
        <article v-if="selected" class="dx-detail">
          <div class="dx-d-head">
            <span class="dx-level" :class="selected.level">{{ selected.level === 'k12' ? 'K-12' : selected.level }}</span>
            <h2>{{ selected.title }}</h2>
            <span class="dx-cred">{{ selected.credential }}</span>
          </div>
          <div class="dx-d-meta">{{ selected.institution }} · tutor embodies <b>{{ selected.teacher }}</b></div>
          <p class="dx-d-summary">{{ selected.summary }}</p>

          <!-- Coverage banner -->
          <div class="dx-cov-banner" :class="{ full: cov.pct >= 90 }">
            <div class="dx-cov-big">{{ cov.pct }}%<span>captured from the Commons</span></div>
            <div class="dx-cov-detail">
              <span><b>{{ cov.satisfied }}</b>/{{ cov.total }} requirements</span>
              <span v-if="cov.requiredUnits"><b>{{ cov.units }}</b>/{{ cov.requiredUnits }} units</span>
              <span><b>{{ capturedChunks(selected).toLocaleString() }}</b> chunks</span>
            </div>
          </div>

          <!-- Requirements → courses → skills (the registrar walk) -->
          <div class="dx-req-h">Requirements <span class="dx-hint">each traces to captured, openly-licensed content</span></div>
          <div v-for="r in selected.requirements" :key="r.id" class="dx-req" :class="{ gap: !r.satisfied }">
            <div class="dx-req-top">
              <span class="dx-req-flag" :class="{ gap: !r.satisfied }">{{ r.satisfied ? '✓' : '○' }}</span>
              <span class="dx-req-title">{{ r.title }}</span>
              <span v-if="r.code" class="dx-req-code">{{ r.code }}</span>
              <span v-if="r.units" class="dx-req-units">{{ r.units }}u</span>
            </div>
            <div v-for="c in r.courses" :key="c.id" class="dx-course">
              <component :is="c.captured ? 'RouterLink' : 'div'" :to="c.captured ? `/academy/course/${c.id}` : undefined" class="dx-course-main" :class="{ link: c.captured }">
                <span class="dx-course-title">{{ c.title }}</span>
                <span class="dx-course-src">{{ c.source }}</span>
                <span class="dx-lic" :class="{ open: c.license.startsWith('CC') }">{{ c.license }}</span>
                <span v-if="c.captured && c.chunks" class="dx-chunks">{{ c.chunks.toLocaleString() }} chunks</span>
                <span v-else-if="!c.captured" class="dx-uncaptured">not yet captured</span>
                <span v-if="c.captured" class="dx-open">open →</span>
              </component>
              <div class="dx-skills">
                <span v-for="sk in c.skills" :key="sk" class="dx-skill" :class="{ shared: sharedIds.has(sk) }" :title="sharedIds.has(sk) ? 'reused across programs' : ''">{{ skillName(sk) }}</span>
              </div>
            </div>
          </div>

          <p class="dx-foot">
            Designed on the registrar shape (<code>Program → Requirement → Course → Skill</code>). Coverage, units and chunk
            counts mirror <code>alexandrian-academy</code>’s real output; wiring the live capture + tutor is a loader swap.
          </p>
        </article>
        <div v-else class="dx-detail empty">Select a program</div>
      </template>
    </SplitPane>
  </section>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import SurfaceHeader from '../components/SurfaceHeader.vue';
import SplitPane from '../components/SplitPane.vue';
import { useCockpit } from '../stores/cockpit';
import { programs, coverageOf, capturedChunks, skillName, sharedSkills, type LadderLevel, type Program } from '../data/academyFixture';

const route = useRoute();
const cockpit = useCockpit();
const isK12 = computed(() => route.path.includes('homeschool'));
const levels = computed<LadderLevel[]>(() => (isK12.value ? ['k12'] : ['undergrad', 'grad']));
const list = computed<Program[]>(() => programs.filter((p) => levels.value.includes(p.level)));
const selectedId = ref<string>(list.value[0]?.id ?? '');
const selected = computed<Program | undefined>(() => list.value.find((p) => p.id === selectedId.value) ?? list.value[0]);
const cov = computed(() => (selected.value ? coverageOf(selected.value) : { satisfied: 0, total: 0, pct: 0 }));
const sharedIds = new Set(sharedSkills().map((s) => s.id));

watch(list, (l) => { if (!l.some((p) => p.id === selectedId.value) && l[0]) selectedId.value = l[0].id; });
watch(selected, (p) => {
  if (p) cockpit.setContext({ surface: isK12.value ? 'Academy · Homeschool' : 'Academy · Degrees', entityLabel: p.title, detail: `${coverageOf(p).pct}% captured`, route: route.path });
}, { immediate: true });
onMounted(() => { if (!selected.value && list.value[0]) selectedId.value = list.value[0].id; });
</script>

<style scoped>
.dx { height: 100%; min-height: 0; display: grid; grid-template-rows: auto 1fr; gap: 0.75rem; padding: 0.85rem 1rem 1rem; background: var(--bg); color: var(--text); }
.dx-pill { font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--accent); background: var(--accent-soft, rgba(120,160,255,0.12)); border-radius: 5px; padding: 0.1rem 0.4rem; }

.dx-list { min-height: 0; overflow-y: auto; border: 1px solid var(--line-2); border-radius: 12px; }
.dx-count { margin: 0; padding: 0.5rem 0.85rem; font-size: 0.66rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-3); border-bottom: 1px solid var(--line); }
.dx-row { width: 100%; display: flex; flex-direction: column; gap: 0.25rem; border: none; border-bottom: 1px solid var(--line); background: transparent; color: inherit; padding: 0.65rem 0.85rem; cursor: pointer; text-align: left; }
.dx-row:hover { background: rgba(255,255,255,0.03); } .dx-row.on { background: color-mix(in srgb, var(--accent) 8%, transparent); box-shadow: inset 3px 0 0 var(--accent); }
.dx-row-title { font-size: 0.9rem; font-weight: 600; } .dx-row-meta { font-size: 0.7rem; color: var(--text-3); }
.dx-row-cov { display: flex; align-items: center; gap: 0.5rem; font-size: 0.68rem; color: var(--text-2); font-variant-numeric: tabular-nums; }
.dx-cov-bar { flex: 1; height: 5px; border-radius: 4px; background: var(--line); overflow: hidden; } .dx-cov-bar span { display: block; height: 100%; background: var(--accent); } .dx-cov-bar span.full { background: var(--up); }
.dx-empty { padding: 1.2rem; color: var(--text-3); font-size: 0.85rem; }

.dx-detail { min-height: 0; overflow-y: auto; border: 1px solid var(--line-2); border-radius: 12px; padding: 1rem 1.1rem 1.2rem; }
.dx-detail.empty { display: grid; place-items: center; color: var(--text-3); font-size: 0.85rem; }
.dx-d-head { display: flex; align-items: baseline; gap: 0.5rem; flex-wrap: wrap; } .dx-d-head h2 { margin: 0; font-size: 1.3rem; }
.dx-level { font-size: 0.58rem; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700; border-radius: 4px; padding: 0.05rem 0.35rem; color: #58a6ff; background: rgba(88,166,255,0.14); }
.dx-level.k12 { color: #6ee7b7; background: rgba(63,185,80,0.14); }
.dx-cred { font-size: 0.74rem; color: var(--text-3); }
.dx-d-meta { font-size: 0.78rem; color: var(--text-2); margin-top: 0.25rem; } .dx-d-meta b { color: var(--text); }
.dx-d-summary { font-size: 0.88rem; line-height: 1.6; color: var(--text-2); margin: 0.7rem 0; }

.dx-cov-banner { display: flex; align-items: center; gap: 1.2rem; border: 1px solid var(--line-2); border-left: 3px solid var(--accent); border-radius: 10px; padding: 0.7rem 0.9rem; background: var(--surface); flex-wrap: wrap; }
.dx-cov-banner.full { border-left-color: var(--up); }
.dx-cov-big { font-size: 1.7rem; font-weight: 800; color: var(--text); font-variant-numeric: tabular-nums; display: flex; flex-direction: column; line-height: 1.05; }
.dx-cov-banner.full .dx-cov-big { color: #86efac; }
.dx-cov-big span { font-size: 0.6rem; font-weight: 400; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-3); }
.dx-cov-detail { display: flex; gap: 1rem; font-size: 0.78rem; color: var(--text-3); flex-wrap: wrap; } .dx-cov-detail b { color: var(--text); font-variant-numeric: tabular-nums; }

.dx-req-h { font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--text-3); margin: 1.1rem 0 0.5rem; }
.dx-hint { text-transform: none; letter-spacing: 0; color: var(--text-3); margin-left: 0.4rem; }
.dx-req { border-top: 1px solid var(--line); padding: 0.6rem 0; }
.dx-req-top { display: flex; align-items: center; gap: 0.5rem; }
.dx-req-flag { width: 1.2rem; height: 1.2rem; flex: 0 0 auto; display: grid; place-items: center; border-radius: 50%; font-size: 0.7rem; color: var(--up); background: rgba(63,185,80,0.14); } .dx-req-flag.gap { color: #e3b341; background: rgba(227,179,65,0.16); }
.dx-req-title { font-size: 0.88rem; font-weight: 600; flex: 1; } .dx-req.gap .dx-req-title { color: var(--text-2); }
.dx-req-code { font-size: 0.68rem; color: var(--text-3); font-family: ui-monospace, monospace; } .dx-req-units { font-size: 0.68rem; color: var(--text-3); }
.dx-course { margin: 0.35rem 0 0 1.7rem; }
.dx-course-main { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; text-decoration: none; color: inherit; padding: 0.25rem 0; }
.dx-course-main.link { cursor: pointer; } .dx-course-main.link:hover .dx-course-title { color: var(--accent); }
.dx-course-title { font-size: 0.82rem; color: var(--text); } .dx-course-src { font-size: 0.68rem; color: var(--text-3); }
.dx-lic { font-size: 0.6rem; border: 1px solid var(--line-2); border-radius: 4px; padding: 0.02rem 0.3rem; color: var(--text-3); } .dx-lic.open { color: var(--up); border-color: rgba(63,185,80,0.4); }
.dx-chunks { font-size: 0.66rem; color: var(--text-3); font-variant-numeric: tabular-nums; }
.dx-uncaptured { font-size: 0.66rem; color: #e3b341; }
.dx-open { font-size: 0.68rem; color: var(--accent); margin-left: auto; }
.dx-skills { display: flex; flex-wrap: wrap; gap: 0.3rem; margin: 0.25rem 0 0 0; }
.dx-skill { font-size: 0.66rem; color: var(--text-3); border: 1px solid var(--line); border-radius: 999px; padding: 0.05rem 0.45rem; }
.dx-skill.shared { color: var(--accent); border-color: color-mix(in srgb, var(--accent) 40%, transparent); }
.dx-foot { font-size: 0.72rem; color: var(--text-3); line-height: 1.5; margin-top: 1rem; border-top: 1px solid var(--line); padding-top: 0.7rem; } .dx-foot code { font-family: ui-monospace, monospace; color: var(--text-2); }
</style>
