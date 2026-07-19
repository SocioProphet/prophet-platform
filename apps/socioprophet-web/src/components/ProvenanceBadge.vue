<template>
  <!-- The moat, made visible: a compact verdict badge with a "why this?" popover
       that walks method → verifier → sources → as-of → receipt. Reveal on hover
       or keyboard focus. -->
  <span class="pv" :class="tier.verdict">
    <button class="pv-badge" type="button" :aria-label="`Provenance: ${tier.label}`">
      <span class="pv-glyph" aria-hidden="true">{{ tier.glyph }}</span>
      <span v-if="!compact" class="pv-label">{{ tier.label }}</span>
    </button>
    <span class="pv-pop" role="tooltip">
      <span class="pv-pop-head"><span class="pv-glyph" aria-hidden="true">{{ tier.glyph }}</span>{{ tier.label }}</span>
      <span class="pv-pop-blurb">{{ tier.blurb }}</span>
      <span class="pv-row"><b>Method</b><span>{{ p.method }}</span></span>
      <span v-if="p.formula" class="pv-row"><b>Formula</b><code>{{ p.formula }}</code></span>
      <span v-if="p.verifier" class="pv-row"><b>Verifier</b><span>{{ p.verifier }}</span></span>
      <span v-if="p.sources && p.sources.length" class="pv-row"><b>Sources</b><span>{{ p.sources.join(', ') }}</span></span>
      <span v-if="p.asOf" class="pv-row"><b>As of</b><span>{{ p.asOf }}</span></span>
      <span v-if="p.receipt" class="pv-row"><b>Receipt</b><code class="pv-hash">{{ p.receipt }}</code></span>
      <span v-if="p.note" class="pv-note">{{ p.note }}</span>
    </span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { tierOf, type Provenance } from '../features/provenance/types';
const props = defineProps<{ p: Provenance; compact?: boolean }>();
const tier = computed(() => tierOf(props.p));
</script>

<style scoped>
.pv { position: relative; display: inline-flex; vertical-align: middle; }
.pv-badge {
  display: inline-flex; align-items: center; gap: 0.25rem; cursor: help;
  border: 1px solid currentColor; border-radius: 999px; background: transparent;
  padding: 0.05rem 0.4rem; font-size: 0.62rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.03em;
  line-height: 1.4;
}
.pv-glyph { font-size: 0.7rem; }
/* Verdict colors — sourced from the shared semantic tokens (one source of truth). */
.pv.verified .pv-badge { color: var(--live); background: rgba(75, 191, 115, 0.1); }
.pv.reasoned .pv-badge { color: var(--info); background: rgba(88, 166, 255, 0.1); }
.pv.grounded .pv-badge { color: var(--teal); background: rgba(45, 212, 191, 0.1); }
.pv.unassayed .pv-badge { color: var(--amber); background: rgba(227, 179, 65, 0.1); }
.pv.unverified .pv-badge { color: var(--neutral); background: rgba(139, 148, 158, 0.1); }

/* Popover — revealed on hover/focus */
.pv-pop {
  position: absolute; z-index: 50; bottom: calc(100% + 6px); left: 0;
  display: grid; gap: 0.3rem; width: max-content; max-width: 22rem;
  padding: 0.6rem 0.7rem; border-radius: 10px;
  background: #14161b; border: 1px solid rgba(255, 255, 255, 0.14); box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
  opacity: 0; visibility: hidden; transform: translateY(4px); transition: opacity 0.12s ease, transform 0.12s ease;
  color: rgba(255, 255, 255, 0.85); font-size: 0.72rem; text-transform: none; letter-spacing: 0; font-weight: 400; text-align: left;
}
.pv-badge:hover + .pv-pop, .pv-badge:focus-visible + .pv-pop, .pv:hover .pv-pop { opacity: 1; visibility: visible; transform: translateY(0); }
.pv-pop-head { display: flex; align-items: center; gap: 0.3rem; font-weight: 700; text-transform: capitalize; }
.pv.verified .pv-pop-head { color: #7ee2a8; } .pv.reasoned .pv-pop-head { color: #93c5fd; } .pv.grounded .pv-pop-head { color: #5eead4; } .pv.unassayed .pv-pop-head { color: #f0c987; } .pv.unverified .pv-pop-head { color: #b8c0cc; }
.pv-pop-blurb { color: rgba(255, 255, 255, 0.6); font-size: 0.7rem; margin-bottom: 0.15rem; }
.pv-row { display: grid; grid-template-columns: 4.5rem 1fr; gap: 0.5rem; align-items: baseline; }
.pv-row b { color: rgba(255, 255, 255, 0.45); font-weight: 600; font-size: 0.66rem; }
.pv-row code, .pv-hash { font-family: ui-monospace, 'SF Mono', monospace; font-size: 0.66rem; color: rgba(255, 255, 255, 0.75); overflow-wrap: anywhere; }
.pv-note { color: rgba(255, 255, 255, 0.55); font-size: 0.68rem; border-top: 1px solid rgba(255, 255, 255, 0.08); padding-top: 0.3rem; }
</style>
