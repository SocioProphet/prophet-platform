<script setup lang="ts">
// The promotion membrane, made literal. Each promotion state is a chamber; between chambers sits a
// permeable gate. Evidence permeates left→right toward canon — an animated pulse conveys that flow —
// but the final CANONICAL chamber is sealed (only a human crosses that boundary; the invariant). One
// component for every twin (Earth/GAIA, Human/HDT, Knowledge), so the discipline reads as one system.
// Live occupancy (how many items sit at each state) rides on the chambers when provided.
// Motion is opt-in via prefers-reduced-motion — static by default for anyone who asks for less motion.
import { computed } from 'vue';
import { EPISTEMIC_COLORS } from '../../services/studioApi';

const props = defineProps<{
  states: { state: string; epistemic?: string | null; canonical?: boolean }[];
  occupancy?: Record<string, number>;
  compact?: boolean;
}>();

function epi(mode?: string | null): string { return EPISTEMIC_COLORS[mode || 'observed'] || 'var(--epi-unknown)'; }
function count(state: string): number { return props.occupancy?.[state] ?? 0; }
const total = computed(() => Object.values(props.occupancy ?? {}).reduce((n, v) => n + v, 0));
</script>

<template>
  <div class="mem" :class="{ compact }" role="img" aria-label="promotion membrane">
    <div class="track" aria-hidden="true"><span class="pulse" /></div>
    <template v-for="(m, i) in states" :key="m.state">
      <div class="cell" :class="{ canon: m.canonical }">
        <span class="c-state">{{ m.state }}</span>
        <span class="c-epi" :style="{ color: epi(m.epistemic) }">{{ m.epistemic }}</span>
        <span v-if="count(m.state)" class="c-occ tnum" :title="count(m.state) + ' at ' + m.state">{{ count(m.state) }}</span>
        <span v-if="m.canonical" class="c-seal" title="sealed — only a human canonizes">⛬</span>
      </div>
      <span v-if="i < states.length - 1" class="gate" :class="{ 'to-canon': states[i + 1].canonical }" aria-hidden="true">
        <i class="g-line" /><i class="g-arrow">▸</i>
      </span>
    </template>
    <span v-if="total" class="mem-total tnum">{{ total }} live</span>
  </div>
</template>

<style scoped>
.mem { position: relative; display: flex; align-items: stretch; gap: 0; flex-wrap: wrap; padding: 4px 0; }
/* the flow track sits behind the chambers; the pulse travels it toward canon */
.track { position: absolute; left: 0; right: 46px; top: 50%; height: 2px; background: transparent; overflow: hidden; pointer-events: none; }
.pulse { display: none; }
@media (prefers-reduced-motion: no-preference) {
  .pulse { display: block; position: absolute; top: -1px; left: 0; width: 26px; height: 4px; border-radius: 2px;
    background: linear-gradient(90deg, transparent, var(--accent), transparent); opacity: .5;
    animation: permeate 4.2s ease-in-out infinite; }
}
@keyframes permeate { 0% { transform: translateX(-30px); opacity: 0; } 12% { opacity: .55; } 88% { opacity: .55; } 100% { transform: translateX(100%); opacity: 0; } }

.cell { position: relative; z-index: 1; display: flex; flex-direction: column; gap: 1px; border: 1px solid var(--hairline);
  border-radius: var(--r-2); padding: 5px 10px; background: var(--surface); min-width: 76px; }
.cell.canon { border-color: color-mix(in srgb, var(--epi-attested) 45%, var(--hairline)); background: var(--epi-attested-wash, var(--ok-wash)); }
.c-state { font-weight: 600; font-size: 12px; color: var(--ink); }
.c-epi { font-size: 10px; }
.c-occ { position: absolute; top: -7px; right: -7px; background: var(--accent); color: #04122e; font-size: 10px; font-weight: 700;
  min-width: 15px; height: 15px; border-radius: 999px; display: grid; place-items: center; padding: 0 3px; }
.c-seal { position: absolute; bottom: 3px; right: 5px; font-size: 9px; color: var(--epi-attested); }

.gate { position: relative; z-index: 1; display: flex; align-items: center; justify-content: center; width: 26px; flex: 0 0 auto; }
.gate .g-line { position: absolute; left: 0; right: 0; top: 50%; height: 1px; background: var(--hairline-strong); }
.gate .g-arrow { position: relative; font-size: 10px; color: var(--faint); background: var(--bar, var(--sunken)); padding: 0 1px; }
/* the boundary into the canonical chamber reads as a firmer, gated membrane */
.gate.to-canon .g-line { background: repeating-linear-gradient(90deg, var(--epi-attested) 0 3px, transparent 3px 6px); opacity: .7; height: 2px; }
.gate.to-canon .g-arrow { color: var(--epi-attested); }

.mem-total { margin-left: 10px; align-self: center; font-size: 10.5px; color: var(--muted); }

.mem.compact .cell { min-width: 0; padding: 3px 7px; }
.mem.compact .c-state { font-size: 11px; }
.mem.compact .c-epi { font-size: 9px; }
.mem.compact .gate { width: 18px; }
</style>
