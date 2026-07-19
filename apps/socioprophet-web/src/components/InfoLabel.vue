<template>
  <!-- Labeling primitive: a label with a "what is this?" tooltip. Use it to make
       jargon (H3 cell, bounded ingest layer, gross yield…) self-explaining. -->
  <span class="il">
    <slot>{{ label }}</slot>
    <button class="il-i" type="button" :aria-label="label ? `What is ${label}?` : 'What is this?'">
      <span aria-hidden="true">ⓘ</span>
      <span class="il-pop" role="tooltip"><b v-if="label">{{ label }}</b>{{ info }}</span>
    </button>
  </span>
</template>

<script setup lang="ts">
defineProps<{ label?: string; info: string }>();
</script>

<style scoped>
.il { display: inline-flex; align-items: center; gap: 0.25rem; }
.il-i { position: relative; border: none; background: transparent; color: var(--text-3, #78716c); cursor: help; padding: 0; font-size: 0.72rem; line-height: 1; display: inline-flex; }
.il-i:hover { color: var(--text-2, #a8a29e); }
.il-pop {
  position: absolute; z-index: 60; bottom: calc(100% + 6px); left: 50%; transform: translateX(-50%) translateY(4px);
  width: max-content; max-width: 18rem; padding: 0.5rem 0.65rem; border-radius: 9px;
  background: #14161b; border: 1px solid rgba(255, 255, 255, 0.14); box-shadow: 0 10px 28px rgba(0, 0, 0, 0.5);
  color: rgba(255, 255, 255, 0.82); font-size: 0.72rem; font-weight: 400; line-height: 1.5; text-transform: none; letter-spacing: 0; text-align: left;
  opacity: 0; visibility: hidden; transition: opacity 0.12s ease, transform 0.12s ease; pointer-events: none;
}
.il-pop b { display: block; color: #fff; margin-bottom: 0.15rem; }
.il-i:hover .il-pop, .il-i:focus-visible .il-pop { opacity: 1; visibility: visible; transform: translateX(-50%) translateY(0); }
</style>
