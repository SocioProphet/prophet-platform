<script setup lang="ts">
// The spinal correspondence chart with three honestly-separated lenses. Toggle Modern (verified),
// Chiropractic (traditional), and TCM (hypothesis) — same spinal level, different overlays, each
// labelled by its epistemic tier. The differentiator: no incumbent holds all three, correctly tiered,
// on one chart. Non-diagnostic — it correlates and attributes; it never says a level causes a disease.
import { ref, computed } from 'vue';
import { SPINE, LENS_TIER, LENS_LABEL, TIER_EPI, type Lens } from '../data/spinalCorrespondence';
import { EPISTEMIC_COLORS } from '../services/studioApi';

const props = defineProps<{ recordOrgans?: string[] }>();
const emit = defineEmits<{ (e: 'organ', organ: string): void }>();

const active = ref<Record<Lens, boolean>>({ modern: true, chiropractic: true, tcm: false });
function toggle(l: Lens) { active.value = { ...active.value, [l]: !active.value[l] }; }
const lenses = computed<Lens[]>(() => (['modern', 'chiropractic', 'tcm'] as Lens[]).filter((l) => active.value[l]));
function tierColor(l: Lens): string { return EPISTEMIC_COLORS[TIER_EPI[LENS_TIER[l]]] || 'var(--epi-unknown)'; }
const REGION_COLOR: Record<string, string> = { cervical: '#5b95f9', thoracic: '#2dd4bf', lumbar: '#e0975a', sacral: '#a082f8' };
function hasRecords(organ?: string): boolean { return !!organ && !!props.recordOrgans?.includes(organ); }
function corrFor(seg: (typeof SPINE)[number], l: Lens) { return seg.corr.filter((c) => c.lens === l); }
</script>

<template>
  <div class="spine">
    <div class="sp-bar">
      <span class="sp-title">Spinal correspondence</span>
      <div class="sp-lenses">
        <button v-for="l in (['modern','chiropractic','tcm'] as Lens[])" :key="l" class="lens" :class="{ on: active[l] }"
                :style="active[l] ? { borderColor: tierColor(l), color: tierColor(l) } : {}" @click="toggle(l)">
          <i class="ldot" :style="{ background: tierColor(l) }" />{{ LENS_LABEL[l] }}
          <small>{{ LENS_TIER[l] }}</small>
        </button>
      </div>
    </div>
    <p class="sp-note">⚕ Correlation + attribution, not diagnosis. Modern = evidence-based innervation; chiropractic + TCM are attributed traditional/ hypothesis overlays — the segment level tracks real anatomy, specific disease-causation claims are not asserted.</p>

    <div class="sp-grid" role="table" aria-label="Spinal correspondence chart">
      <div class="sp-head" role="row" :style="{ gridTemplateColumns: `72px repeat(${lenses.length}, 1fr)` }">
        <span role="columnheader">Segment</span>
        <span v-for="l in lenses" :key="l" role="columnheader" :style="{ color: tierColor(l) }">{{ LENS_LABEL[l] }}</span>
      </div>
      <div v-for="seg in SPINE" :key="seg.id" class="sp-row" role="row" :style="{ gridTemplateColumns: `72px repeat(${lenses.length}, 1fr)` }">
        <span class="seg" :style="{ '--rc': REGION_COLOR[seg.region] }" :title="seg.region">{{ seg.id }}</span>
        <span v-for="l in lenses" :key="l" class="cell" role="cell">
          <template v-for="(c, i) in corrFor(seg, l)" :key="i">
            <button v-if="hasRecords(c.organ)" class="corr link" :style="{ '--tc': tierColor(l) }" @click="emit('organ', c.organ!)" :title="'has records — open'">
              {{ c.target }} <i class="rec">●</i>
            </button>
            <span v-else class="corr" :style="{ '--tc': tierColor(l) }">{{ c.target }}</span>
          </template>
          <span v-if="!corrFor(seg, l).length" class="dash">·</span>
        </span>
      </div>
    </div>

    <div class="sp-legend">
      <span><i class="ldot" :style="{ background: EPISTEMIC_COLORS.verified }" />verified — evidence-based</span>
      <span><i class="ldot" :style="{ background: EPISTEMIC_COLORS.attested }" />traditional — attributed</span>
      <span><i class="ldot" :style="{ background: EPISTEMIC_COLORS.hypothesis }" />hypothesis — bridge</span>
      <span class="lg-rec"><i class="rec">●</i> links to your records</span>
    </div>
  </div>
</template>

<style scoped>
.spine { font: 14px/1.5 var(--ui); color: var(--ink); }
.sp-bar { display: flex; align-items: center; gap: var(--sp-3); flex-wrap: wrap; margin-bottom: var(--sp-2); }
.sp-title { font-size: 1.05rem; font-weight: 600; }
.sp-lenses { display: flex; gap: 6px; flex-wrap: wrap; margin-left: auto; }
.lens { display: inline-flex; align-items: center; gap: 6px; border: 1px solid var(--hairline-strong); background: var(--surface); color: var(--muted); border-radius: var(--pill); padding: 4px 11px; font-size: 12px; cursor: pointer; }
.lens small { text-transform: uppercase; letter-spacing: .04em; font-size: 9px; opacity: .8; }
.lens .ldot { width: 8px; height: 8px; border-radius: 50%; opacity: .4; } .lens.on .ldot { opacity: 1; }
.sp-note { font-size: 11.5px; color: var(--muted); background: var(--warn-wash); border-radius: var(--r-2); padding: 6px 10px; margin: 0 0 var(--sp-3); }

.sp-grid { border: 1px solid var(--hairline); border-radius: var(--r-3); overflow: hidden; }
.sp-head, .sp-row { display: grid; align-items: stretch; gap: 0; }
.sp-head { background: var(--sunken); border-bottom: 1px solid var(--hairline); }
.sp-head span { padding: 7px 10px; font-size: 10.5px; text-transform: uppercase; letter-spacing: .05em; color: var(--faint); }
.sp-row { border-bottom: 1px solid var(--hairline); } .sp-row:last-child { border-bottom: 0; } .sp-row:hover { background: var(--surface-2); }
.seg { display: flex; align-items: center; justify-content: center; font-weight: 600; font-size: 12px; color: var(--ink); border-right: 1px solid var(--hairline); box-shadow: inset 3px 0 0 var(--rc); }
.cell { padding: 6px 10px; border-right: 1px solid var(--hairline); display: flex; flex-direction: column; gap: 4px; min-width: 0; } .cell:last-child { border-right: 0; }
.corr { font-size: 12px; color: var(--ink-2); border-left: 2px solid var(--tc); padding-left: 7px; text-align: left; }
.corr.link { background: none; border-top: 0; border-right: 0; border-bottom: 0; cursor: pointer; color: var(--ink); }
.corr.link:hover { color: var(--accent); }
.corr .rec { color: var(--accent); font-size: 8px; font-style: normal; vertical-align: middle; }
.dash { color: var(--faint); padding-left: 7px; }
.sp-legend { display: flex; gap: var(--sp-4); flex-wrap: wrap; margin-top: var(--sp-3); font-size: 11px; color: var(--muted); }
.sp-legend span { display: inline-flex; align-items: center; gap: 5px; } .sp-legend .ldot { width: 8px; height: 8px; border-radius: 50%; }
.lg-rec .rec { color: var(--accent); font-style: normal; font-size: 9px; }
</style>
