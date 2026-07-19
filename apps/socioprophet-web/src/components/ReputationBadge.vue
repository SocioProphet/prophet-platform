<template>
  <!-- HolographMe reputation chip — tier + score + Hats, with a hover breakdown
       (attestations/disputes, traits = dispositions, occurrents = grounding episodes). -->
  <span v-if="rep" class="rb">
    <button class="rb-chip" type="button" :style="{ '--tier': tierColor }" :aria-label="`Reputation ${rep.score}`">
      <span class="rb-score">{{ rep.score }}</span>
      <span v-for="h in rep.hats" :key="h.kind" class="rb-hat" :class="h.kind">{{ hatIcon(h.kind) }}{{ h.label }}</span>
    </button>
    <span class="rb-pop" role="tooltip">
      <span class="rb-pop-h"><b :style="{ color: tierColor }">{{ tierMeta.label }}</b> · {{ rep.displayName }}</span>
      <span v-if="rep.did" class="rb-did">{{ rep.did }}</span>
      <span class="rb-row"><span>Standing</span><b>{{ rep.score }}/100 <small>(disposition)</small></b></span>
      <span class="rb-row"><span>Attestations</span><b class="up">✓ {{ rep.attestations }}</b></span>
      <span class="rb-row"><span>Disputes</span><b class="down">✕ {{ rep.disputes }}</b></span>
      <span v-if="rep.traits.length" class="rb-traits"><span v-for="t in rep.traits" :key="t" class="rb-trait">{{ t }}</span></span>
      <span v-if="rep.occurrents.length" class="rb-occ">
        <span class="rb-occ-h">Recent (occurrents)</span>
        <span v-for="(o, i) in rep.occurrents.slice(0, 3)" :key="i" class="rb-occ-i">· {{ o }}</span>
      </span>
      <span class="rb-note">Portable, verified reputation — carried across news, marketplace, and people.</span>
    </span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { reputationFor, TIER_META, type HatKind } from '../features/reputation/reputation';

const props = defineProps<{ subject: string }>();
const rep = computed(() => reputationFor(props.subject));
const tierMeta = computed(() => (rep.value ? TIER_META[rep.value.tier] : TIER_META.unrated));
const tierColor = computed(() => tierMeta.value.color);
const hatIcon = (k: HatKind) => ({ verified: '✓ ', expert: '★ ', moderator: '⚖ ', local: '⚲ ', source: '◈ ' }[k] ?? '');
</script>

<style scoped>
.rb { position: relative; display: inline-flex; vertical-align: middle; }
.rb-chip { display: inline-flex; align-items: center; gap: 0.25rem; cursor: help; border: 1px solid var(--tier); border-radius: 999px; background: color-mix(in srgb, var(--tier) 12%, transparent); padding: 0.05rem 0.4rem; font-size: 0.62rem; line-height: 1.4; }
.rb-score { color: var(--tier); font-weight: 800; font-variant-numeric: tabular-nums; }
.rb-hat { color: var(--text-2); font-size: 0.58rem; text-transform: uppercase; letter-spacing: 0.03em; }
.rb-hat.verified { color: #4bbf73; }
.rb-pop { position: absolute; z-index: 60; bottom: calc(100% + 6px); left: 0; display: grid; gap: 0.25rem; width: max-content; max-width: 20rem; padding: 0.55rem 0.65rem; border-radius: 10px; background: #14161b; border: 1px solid rgba(255, 255, 255, 0.14); box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5); color: rgba(255, 255, 255, 0.82); font-size: 0.72rem; text-align: left; opacity: 0; visibility: hidden; transform: translateY(4px); transition: opacity 0.12s ease, transform 0.12s ease; pointer-events: none; }
.rb-chip:hover + .rb-pop, .rb:hover .rb-pop { opacity: 1; visibility: visible; transform: translateY(0); }
.rb-pop-h { font-weight: 600; color: #fff; }
.rb-did { font-family: ui-monospace, monospace; font-size: 0.62rem; color: var(--text-3); overflow-wrap: anywhere; }
.rb-row { display: flex; align-items: baseline; justify-content: space-between; gap: 0.5rem; } .rb-row span { color: rgba(255, 255, 255, 0.5); } .rb-row b.up { color: #4bbf73; } .rb-row b.down { color: #f0656a; } .rb-row small { color: var(--text-3); }
.rb-traits { display: flex; flex-wrap: wrap; gap: 0.25rem; } .rb-trait { font-size: 0.64rem; color: #93b4ff; background: rgba(120, 160, 255, 0.12); border-radius: 999px; padding: 0.03rem 0.4rem; }
.rb-occ { display: grid; gap: 0.1rem; border-top: 1px solid rgba(255, 255, 255, 0.08); padding-top: 0.3rem; } .rb-occ-h { font-size: 0.58rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-3); } .rb-occ-i { font-size: 0.66rem; color: rgba(255, 255, 255, 0.6); }
.rb-note { color: rgba(255, 255, 255, 0.5); font-size: 0.64rem; border-top: 1px solid rgba(255, 255, 255, 0.08); padding-top: 0.3rem; }
</style>
