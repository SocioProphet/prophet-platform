<template>
  <!-- A panel that can collapse to its header — the reusable version of the
       ad-hoc collapse logic (map panels, inspectors, sidebars). -->
  <section class="cpx" :class="{ collapsed: !open }">
    <header class="cpx-h" @click="open = !open">
      <span class="cpx-title"><slot name="title">{{ title }}</slot></span>
      <span v-if="$slots.meta" class="cpx-meta"><slot name="meta" /></span>
      <span class="cpx-caret" aria-hidden="true">{{ open ? '▾' : '▸' }}</span>
    </header>
    <div v-show="open" class="cpx-body"><slot /></div>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue';
const props = defineProps<{ title?: string; defaultOpen?: boolean }>();
const open = ref(props.defaultOpen !== false);
</script>

<style scoped>
.cpx { border: 1px solid var(--line-2, rgba(255, 255, 255, 0.13)); border-radius: 12px; overflow: hidden; background: var(--surface, #15171c); }
.cpx-h { display: flex; align-items: center; gap: 0.5rem; padding: 0.6rem 0.85rem; cursor: pointer; user-select: none; }
.cpx-h:hover { background: rgba(255, 255, 255, 0.03); }
.cpx-title { flex: 1; font-size: 0.66rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-3, #78716c); font-weight: 700; }
.cpx-meta { font-size: 0.7rem; color: var(--text-3, #78716c); }
.cpx-caret { color: var(--text-3, #78716c); font-size: 0.7rem; }
.cpx-body { padding: 0 0.85rem 0.85rem; }
</style>
