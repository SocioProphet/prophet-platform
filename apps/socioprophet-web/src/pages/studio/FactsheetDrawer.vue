<script setup lang="ts">
// A reusable right-side slide-over drawer — the estate's detail surface. Backdrop + panel, ESC to
// close, focus moves into the panel on open, reduced-motion aware. Content is a slot, so any surface
// can present a designed factsheet in it (Catalog uses it for datasets). Teleported to <body> so it
// escapes the Studio scroll container and overlays the whole cockpit.
import { watch, ref, nextTick, onBeforeUnmount } from 'vue';

const props = defineProps<{ open: boolean; title?: string; eyebrow?: string }>();
const emit = defineEmits<{ (e: 'close'): void }>();

const panel = ref<HTMLElement | null>(null);
function onKey(e: KeyboardEvent) { if (e.key === 'Escape') emit('close'); }

watch(() => props.open, (o) => {
  if (o) {
    document.addEventListener('keydown', onKey);
    nextTick(() => panel.value?.focus());
  } else {
    document.removeEventListener('keydown', onKey);
  }
});
onBeforeUnmount(() => document.removeEventListener('keydown', onKey));
</script>

<template>
  <Teleport to="body">
    <Transition name="fd">
      <div v-if="open" class="fd studio-scope" @click.self="emit('close')">
        <div class="fd-panel" ref="panel" tabindex="-1" role="dialog" aria-modal="true" :aria-label="title || 'details'">
          <header class="fd-h">
            <div class="fd-h-t">
              <span v-if="eyebrow" class="fd-eyebrow">{{ eyebrow }}</span>
              <h2>{{ title }}</h2>
            </div>
            <div class="fd-h-actions"><slot name="actions" /></div>
            <button class="fd-x" @click="emit('close')" aria-label="Close">✕</button>
          </header>
          <div class="fd-body"><slot /></div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.fd { position: fixed; inset: 0; z-index: 200; display: flex; justify-content: flex-end;
  background: color-mix(in srgb, #000 55%, transparent); }
.fd-panel { width: min(460px, 92vw); height: 100%; background: var(--ground); border-left: 1px solid var(--hairline-strong);
  box-shadow: var(--e-3); display: flex; flex-direction: column; outline: none; }
.fd-h { display: flex; align-items: flex-start; gap: var(--sp-3); padding: var(--sp-4) var(--sp-4) var(--sp-3); border-bottom: 1px solid var(--hairline); background: var(--bar); }
.fd-h-t { min-width: 0; flex: 1; }
.fd-eyebrow { display: block; font-size: 10px; text-transform: uppercase; letter-spacing: .08em; color: var(--faint); margin-bottom: 2px; }
.fd-h h2 { margin: 0; font-size: 1.05rem; color: var(--bar-ink); font-weight: 600; word-break: break-word; }
.fd-h-actions { display: flex; gap: 6px; align-items: center; }
.fd-x { flex: 0 0 auto; width: 28px; height: 28px; border: 1px solid var(--hairline-strong); background: var(--surface); color: var(--ink-2); border-radius: var(--r-2); cursor: pointer; }
.fd-x:hover { color: var(--ink); }
.fd-body { flex: 1; overflow-y: auto; padding: var(--sp-4); color: var(--ink); }

/* transitions — reduced-motion collapses to a fade */
.fd-enter-active, .fd-leave-active { transition: opacity .18s ease; }
.fd-enter-active .fd-panel, .fd-leave-active .fd-panel { transition: transform .22s cubic-bezier(.22,.61,.36,1); }
.fd-enter-from, .fd-leave-to { opacity: 0; }
.fd-enter-from .fd-panel, .fd-leave-to .fd-panel { transform: translateX(100%); }
@media (prefers-reduced-motion: reduce) {
  .fd-enter-active .fd-panel, .fd-leave-active .fd-panel { transition: none; }
  .fd-enter-from .fd-panel, .fd-leave-to .fd-panel { transform: none; }
}
</style>
