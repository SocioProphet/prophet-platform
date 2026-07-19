<template>
  <!-- The one header every surface should use: eyebrow + title (+ badge slot),
       an optional search slot, and an actions slot (Ask Noetica, provenance…).
       Unifies the title / search / provenance / assistant pattern across surfaces. -->
  <header class="sh">
    <div class="sh-id">
      <p v-if="eyebrow" class="sh-eyebrow">{{ eyebrow }}</p>
      <div class="sh-titlerow">
        <h1 class="sh-title">{{ title }}</h1>
        <slot name="badge" />
      </div>
    </div>
    <div v-if="$slots.search" class="sh-search"><slot name="search" /></div>
    <div v-if="$slots.actions" class="sh-actions"><slot name="actions" /></div>
  </header>
</template>

<script setup lang="ts">
defineProps<{ title: string; eyebrow?: string }>();
</script>

<style scoped>
.sh { display: flex; align-items: center; justify-content: space-between; gap: 1rem; flex-wrap: wrap; }
.sh-id { display: flex; flex-direction: column; }
.sh-eyebrow { margin: 0 0 0.1rem; font-size: var(--fs-eyebrow, 0.62rem); text-transform: uppercase; letter-spacing: var(--ls-eyebrow, 0.1em); color: var(--text-3, #78716c); }
.sh-titlerow { display: flex; align-items: baseline; gap: 0.55rem; flex-wrap: wrap; }
.sh-title { margin: 0; font-size: var(--fs-xl, 1.25rem); letter-spacing: -0.01em; color: var(--text, #ece9e3); font-weight: 640; }
.sh-search { flex: 1 1 16rem; display: flex; justify-content: center; min-width: 0; }
.sh-actions { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
</style>
