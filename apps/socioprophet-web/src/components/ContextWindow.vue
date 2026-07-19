<script setup lang="ts">
import { computed } from 'vue';
import { buildBudgetView, fmtTokens, type NoeticaContext } from '../features/noetica/contextBudget';

// Pass the agent-machine's per-turn context payload; renders a "what's in the context
// window" breakdown (stacked bar + line items). Shows an honest empty state when absent.
const props = defineProps<{ context: NoeticaContext | null }>();
const view = computed(() => (props.context ? buildBudgetView(props.context) : null));
</script>

<template>
  <section class="cw" aria-label="Noetica context window">
    <header class="cw-head">
      <span class="cw-title">Context window</span>
      <span v-if="view" class="cw-total">{{ fmtTokens(view.used) }} / {{ fmtTokens(view.budget) }} <b>({{ view.usedPct }}%)</b></span>
    </header>

    <template v-if="view">
      <div class="cw-bar" :title="`${view.usedPct}% of the ${fmtTokens(view.budget)}-token budget used`">
        <span v-for="s in view.slices" :key="s.key" class="cw-seg" :style="{ width: (s.tokens / view.budget * 100) + '%', background: s.color }" />
      </div>
      <ul class="cw-rows">
        <li v-for="s in view.slices" :key="s.key" class="cw-row" :class="{ free: s.key === 'free' }">
          <span class="cw-dot" :style="{ background: s.color }" />
          <span class="cw-label">{{ s.label }}</span>
          <span class="cw-tok">{{ fmtTokens(s.tokens) }}</span>
          <span class="cw-pct">{{ s.pct }}%</span>
        </li>
      </ul>
      <p class="cw-foot">model <b>{{ view.model }}</b> · window {{ fmtTokens(view.window) }} · budget {{ fmtTokens(view.budget) }} (70%)</p>
    </template>

    <p v-else class="cw-empty">No context reading yet — ask Noetica something, or connect the agent machine. The breakdown appears once a turn runs.</p>
  </section>
</template>

<style scoped>
.cw { border: 1px solid var(--line-2); border-radius: 12px; background: var(--surface); padding: 0.85rem 1rem; color: var(--text); }
.cw-head { display: flex; align-items: baseline; justify-content: space-between; gap: 0.6rem; margin-bottom: 0.6rem; }
.cw-title { font-size: 0.9rem; font-weight: 640; }
.cw-total { font-size: 0.76rem; color: var(--text-3); font-variant-numeric: tabular-nums; } .cw-total b { color: var(--text); }
.cw-bar { display: flex; height: 8px; border-radius: 5px; overflow: hidden; background: #2a2e35; margin-bottom: 0.7rem; }
.cw-seg { height: 100%; }
.cw-rows { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.28rem; }
.cw-row { display: grid; grid-template-columns: 12px 1fr auto auto; align-items: center; gap: 0.55rem; font-size: 0.8rem; }
.cw-row.free { color: var(--text-3); }
.cw-dot { width: 10px; height: 10px; border-radius: 3px; }
.cw-label { color: var(--text-2); } .cw-row.free .cw-label { color: var(--text-3); }
.cw-tok { color: var(--text); font-variant-numeric: tabular-nums; text-align: right; min-width: 3.2rem; }
.cw-pct { color: var(--text-3); font-variant-numeric: tabular-nums; text-align: right; min-width: 3rem; }
.cw-foot { margin: 0.7rem 0 0; font-size: 0.66rem; color: var(--text-3); } .cw-foot b { color: var(--text-2); }
.cw-empty { margin: 0; font-size: 0.8rem; color: var(--text-3); line-height: 1.5; }
</style>
