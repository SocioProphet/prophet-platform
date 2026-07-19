<template>
  <!-- Consistent empty/zero state: icon + what's missing + how to fix it. -->
  <div class="es">
    <div class="es-icon" aria-hidden="true">{{ icon || '◇' }}</div>
    <div class="es-title">{{ title }}</div>
    <p v-if="hint" class="es-hint">{{ hint }}</p>
    <div v-if="$slots.action" class="es-action"><slot name="action" /></div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ title: string; hint?: string; icon?: string }>();
</script>

<style scoped>
.es { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 0.5rem; padding: 2rem 1.25rem; text-align: center; color: var(--text-2, #a8a29e); }
.es-icon { font-size: 1.8rem; opacity: 0.5; }
.es-title { font-size: var(--fs-md, 0.95rem); font-weight: 600; color: var(--text, #ece9e3); }
.es-hint { margin: 0; max-width: 26rem; font-size: var(--fs-base, 0.86rem); line-height: 1.55; color: var(--text-3, #78716c); }
.es-action { margin-top: 0.35rem; }
</style>
