<template>
  <!-- Reusable list|detail split: drag the divider to resize, collapse the list
       pane to reclaim width. Width + collapsed state persist per storageKey. -->
  <div class="sp2" :class="{ 'is-collapsed': collapsed, 'is-dragging': dragging }" :style="gridStyle">
    <div v-show="!collapsed" class="sp2-pane sp2-list"><slot name="list" /></div>

    <div
      v-show="!collapsed"
      class="sp2-divider"
      role="separator"
      aria-orientation="vertical"
      :aria-label="`Resize ${label} panel`"
      :aria-valuenow="Math.round(width)"
      :aria-valuemin="min"
      :aria-valuemax="max"
      tabindex="0"
      @pointerdown="onDown"
      @keydown="onKeyResize"
      @dblclick="resetWidth"
    >
      <span class="sp2-grip" aria-hidden="true"></span>
      <button class="sp2-collapse" type="button" :title="`Hide ${label} (⌘\\)`" :aria-label="`Hide ${label} panel`" @pointerdown.stop @click="setCollapsed(true)">‹</button>
    </div>

    <button v-show="collapsed" class="sp2-reopen" type="button" :title="`Show ${label}`" :aria-label="`Show ${label} panel`" @click="setCollapsed(false)">
      <span class="sp2-reopen-i" aria-hidden="true">›</span><span class="sp2-reopen-l">{{ label }}</span>
    </button>

    <div class="sp2-pane sp2-detail"><slot name="detail" /></div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue';

const props = withDefaults(defineProps<{
  storageKey: string;
  label?: string;
  min?: number;
  max?: number;
  initial?: number;
}>(), { label: 'list', min: 260, max: 680, initial: 380 });

const KEY = `sp2:${props.storageKey}`;
const clamp = (n: number) => Math.max(props.min, Math.min(props.max, n));

function load(): { w: number; c: boolean } {
  try {
    const w = Number(localStorage.getItem(`${KEY}:w`));
    return { w: w ? clamp(w) : props.initial, c: localStorage.getItem(`${KEY}:c`) === '1' };
  } catch { return { w: props.initial, c: false }; }
}
const saved = load();
const width = ref(saved.w);
const collapsed = ref(saved.c);
const dragging = ref(false);
let startX = 0;
let startW = 0;

const gridStyle = computed(() => ({
  gridTemplateColumns: collapsed.value ? '0 0 minmax(0, 1fr)' : `${width.value}px 14px minmax(0, 1fr)`,
}));

function persist() {
  try {
    localStorage.setItem(`${KEY}:w`, String(Math.round(width.value)));
    localStorage.setItem(`${KEY}:c`, collapsed.value ? '1' : '0');
  } catch { /* storage unavailable */ }
}
function setCollapsed(v: boolean) { collapsed.value = v; persist(); }
function resetWidth() { width.value = props.initial; persist(); }

function onMove(e: PointerEvent) { width.value = clamp(startW + (e.clientX - startX)); }
function onUp() {
  dragging.value = false;
  window.removeEventListener('pointermove', onMove);
  window.removeEventListener('pointerup', onUp);
  document.body.style.userSelect = '';
  persist();
}
function onDown(e: PointerEvent) {
  if (e.button !== 0) return;
  dragging.value = true;
  startX = e.clientX;
  startW = width.value;
  document.body.style.userSelect = 'none';
  window.addEventListener('pointermove', onMove);
  window.addEventListener('pointerup', onUp);
  e.preventDefault();
}
function onKeyResize(e: KeyboardEvent) {
  if (e.key === 'ArrowLeft') { width.value = clamp(width.value - 16); persist(); e.preventDefault(); }
  else if (e.key === 'ArrowRight') { width.value = clamp(width.value + 16); persist(); e.preventDefault(); }
  else if (e.key === 'Enter' || e.key === ' ') { setCollapsed(!collapsed.value); e.preventDefault(); }
}
onUnmounted(() => {
  window.removeEventListener('pointermove', onMove);
  window.removeEventListener('pointerup', onUp);
});
</script>

<style scoped>
.sp2 { position: relative; height: 100%; min-height: 0; min-width: 0; display: grid; align-items: stretch; }
/* Panes are grids so the surface's own .*-list / .*-detail child stretches to fill and keeps its own overflow. */
.sp2-pane { min-width: 0; min-height: 0; display: grid; grid-template-rows: 1fr; }

.sp2-divider { position: relative; display: grid; place-items: center; cursor: col-resize; touch-action: none; }
.sp2-divider:focus-visible { outline: 2px solid var(--accent, #58a6ff); outline-offset: -2px; border-radius: 4px; }
.sp2-grip { width: 3px; height: 34px; border-radius: 3px; background: var(--line-2); transition: background 0.12s ease, height 0.12s ease; }
.sp2-divider:hover .sp2-grip, .is-dragging .sp2-grip { background: var(--accent, #58a6ff); height: 52px; }

.sp2-collapse { position: absolute; top: 6px; left: 50%; transform: translateX(-50%); width: 16px; height: 18px; display: grid; place-items: center; padding: 0; border: 1px solid var(--line-2); border-radius: 5px; background: var(--bg); color: var(--text-2); font-size: 0.7rem; line-height: 1; cursor: pointer; opacity: 0; transition: opacity 0.12s ease, color 0.12s ease; }
.sp2-divider:hover .sp2-collapse, .sp2-collapse:focus-visible { opacity: 1; }
.sp2-collapse:hover { color: var(--text); border-color: var(--accent, #58a6ff); }

.sp2-reopen { position: absolute; top: 8px; left: 0; z-index: 5; display: inline-flex; align-items: center; gap: 0.2rem; padding: 0.25rem 0.45rem 0.25rem 0.35rem; border: 1px solid var(--line-2); border-left: none; border-radius: 0 8px 8px 0; background: var(--bg); color: var(--text-2); font-size: 0.66rem; cursor: pointer; }
.sp2-reopen:hover { color: var(--text); border-color: var(--accent, #58a6ff); }
.sp2-reopen-i { font-size: 0.85rem; line-height: 1; }
.sp2-reopen-l { text-transform: uppercase; letter-spacing: 0.05em; }

@media (prefers-reduced-motion: reduce) { .sp2-grip, .sp2-collapse { transition: none; } }
/* On narrow viewports the surfaces already hide the detail; keep list full-width and drop the divider. */
@media (max-width: 1080px) { .sp2 { grid-template-columns: 1fr !important; } .sp2-divider, .sp2-detail, .sp2-reopen { display: none; } .sp2.is-collapsed .sp2-list { display: grid; } }
</style>
