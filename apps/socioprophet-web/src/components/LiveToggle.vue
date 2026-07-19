<template>
  <!-- One crisp control for every fixture→live adapter: idle → loading → live → error. -->
  <button class="lt" :class="{ on: state === 'live', err: state === 'error' }" :disabled="state === 'loading'" type="button" :title="title" @click="$emit('click')">
    {{ state === 'loading' ? '⟳ live…' : state === 'live' ? `● ${liveText}` : state === 'error' ? '⚠ offline' : `↻ ${label}` }}
  </button>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ state: 'idle' | 'loading' | 'live' | 'error'; label?: string; liveText?: string; title?: string }>(), {
  label: 'Go live',
  liveText: 'Live',
  title: 'Pull real data from a public source (no key). Falls back to fixture if unreachable.',
});
defineEmits<{ (e: 'click'): void }>();
</script>

<style scoped>
.lt {
  border: 1px solid var(--line-2); background: transparent; color: var(--text-2);
  border-radius: 8px; padding: 0.3rem 0.6rem; font-size: var(--fs-sm, 0.78rem); cursor: pointer;
  white-space: nowrap; transition: border-color 0.12s ease, color 0.12s ease, background 0.12s ease;
}
.lt:hover:not(:disabled) { border-color: var(--live); color: var(--live); }
.lt.on { border-color: var(--live); color: var(--live); background: var(--live-soft); }
.lt.err { border-color: rgba(240, 101, 106, 0.5); color: var(--down); }
.lt:disabled { opacity: 0.6; cursor: default; }
.lt:focus-visible { outline: 2px solid var(--info); outline-offset: 2px; }
@media (prefers-reduced-motion: reduce) { .lt { transition: none; } }
</style>
