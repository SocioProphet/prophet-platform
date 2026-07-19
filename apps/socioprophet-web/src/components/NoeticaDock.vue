<template>
  <!-- Global Noetica assistant dock: the chat surface as a slide-in panel so it
       is available on EVERY page without navigating away. Reuses NoeticaChat
       (which binds the shared useNoeticaChat singleton, so the session is the
       same one the footer Ask-Noetica bar and the /noetica page use). -->
  <Transition name="ndock">
    <aside v-if="open" class="ndock" role="complementary" aria-label="Noetica assistant">
      <button class="ndock-close" type="button" aria-label="Close Noetica" title="Close (Esc)" @click="$emit('close')">✕</button>
      <!-- Context banner: what the assistant is aware of on the current surface -->
      <div v-if="ctx.surface" class="ndock-ctx" :title="`Noetica is aware of: ${ctx.surface}`">
        <span class="ndock-ctx-eye">On</span>
        <span class="ndock-ctx-surface">{{ ctx.surface }}</span>
        <span v-if="ctx.entityLabel" class="ndock-ctx-sep">·</span>
        <span v-if="ctx.entityLabel" class="ndock-ctx-entity">{{ ctx.entityLabel }}</span>
        <button v-if="ctx.entityLabel" class="ndock-ctx-ask" type="button" @click="askContext">Ask about this</button>
      </div>
      <NoeticaChat />
    </aside>
  </Transition>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import NoeticaChat from '../pages/NoeticaChat.vue';
import { useCockpit } from '../stores/cockpit';
defineProps<{ open: boolean }>();
defineEmits<{ (e: 'close'): void }>();
const cockpit = useCockpit();
const ctx = computed(() => cockpit.context);
function askContext() {
  const c = cockpit.context;
  const bits = [c.entityLabel, c.detail].filter(Boolean).join(' — ');
  cockpit.askAbout(`I'm looking at ${bits || c.surface} on the ${c.surface} surface. Give me a concise read: what matters, risks, and what to do next.`);
}
</script>

<style scoped>
.ndock {
  position: fixed; top: 0; right: 0; bottom: 0; z-index: 1250;
  width: min(30rem, 94vw);
  display: flex; flex-direction: column;
  background: #1e1e1e;
  border-left: 1px solid rgba(255, 255, 255, 0.12);
  box-shadow: -14px 0 48px rgba(0, 0, 0, 0.55);
}
/* Context banner */
.ndock-ctx {
  display: flex; align-items: center; gap: 0.4rem; flex-wrap: wrap;
  padding: 0.4rem 0.75rem; font-size: 0.72rem;
  background: rgba(47, 107, 255, 0.1); border-bottom: 1px solid rgba(47, 107, 255, 0.25); color: #a8a29e;
}
.ndock-ctx-eye { font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.06em; color: #93b4ff; }
.ndock-ctx-surface { color: #ece9e3; font-weight: 600; }
.ndock-ctx-sep { color: #78716c; }
.ndock-ctx-entity { color: #ece9e3; }
.ndock-ctx-ask { margin-left: auto; border: 1px solid rgba(47, 107, 255, 0.5); background: transparent; color: #93b4ff; border-radius: 999px; padding: 0.1rem 0.55rem; font-size: 0.68rem; cursor: pointer; }
.ndock-ctx-ask:hover { background: rgba(47, 107, 255, 0.16); color: #fff; }
/* Let the embedded chat fill the dock, and reserve header room for the ✕ */
.ndock :deep(.nx) { flex: 1; min-height: 0; }
.ndock :deep(.nx-head) { padding-right: 2.9rem; }
.ndock-close {
  position: absolute; top: 8px; right: 10px; z-index: 2;
  width: 26px; height: 26px; border-radius: 7px;
  border: 1px solid rgba(255, 255, 255, 0.14); background: rgba(255, 255, 255, 0.05);
  color: #a8a29e; font-size: 0.78rem; cursor: pointer;
}
.ndock-close:hover { color: #ece9e3; border-color: var(--text-3); }
.ndock-enter-active, .ndock-leave-active { transition: transform 0.24s ease; }
.ndock-enter-from, .ndock-leave-to { transform: translateX(100%); }
</style>
