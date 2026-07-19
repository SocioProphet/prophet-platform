<template>
  <!-- A row of cross-surface jumps for the same entity (the graph moat, navigable). -->
  <div v-if="links.length" class="xl">
    <RouterLink v-for="l in links" :key="l.surface + l.label" class="xl-link" :to="l.to" :title="`Trace to ${l.surface}`">
      <span class="xl-icon" aria-hidden="true">{{ l.icon }}</span>
      <span class="xl-label">{{ l.label }}</span>
      <span class="xl-arrow" aria-hidden="true">→</span>
    </RouterLink>
  </div>
</template>

<script setup lang="ts">
import type { CrossLink } from '../features/crosslink/entityLinks';
defineProps<{ links: CrossLink[] }>();
</script>

<style scoped>
.xl { display: flex; flex-wrap: wrap; gap: 0.4rem; }
.xl-link {
  display: inline-flex; align-items: center; gap: 0.35rem;
  border: 1px solid var(--line-2); border-radius: 8px; background: var(--surface-2);
  color: var(--text-2); text-decoration: none; padding: 0.32rem 0.6rem; font-size: 0.76rem;
  transition: border-color 0.15s ease, color 0.15s ease;
}
.xl-link:hover { border-color: var(--accent); color: var(--accent); }
.xl-icon { font-size: 0.82rem; opacity: 0.9; }
.xl-arrow { opacity: 0.5; font-size: 0.72rem; }
</style>
