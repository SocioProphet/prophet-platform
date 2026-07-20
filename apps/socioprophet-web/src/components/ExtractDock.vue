<template>
  <!-- Ubiquitous IE: the live extraction stack (entities / claims / topics + promote-to-graph)
       as a global slide-in dock, available on EVERY surface (⌘E / Ctrl+E) — mirror of the Graph
       and Noetica docks. Seeds from the current surface's context text; editable so you can extract
       any selection or pasted text anywhere. -->
  <Transition name="xdock">
    <aside v-if="open" class="xdock" role="complementary" aria-label="Extraction">
      <header class="xdock-head">
        <span class="xdock-glyph" aria-hidden="true">⌖</span>
        <span class="xdock-title">Extract</span>
        <span v-if="ctx.surface" class="xdock-ctx">{{ ctx.surface }}</span>
        <button class="xdock-x" type="button" aria-label="Close extraction" @click="$emit('close')">✕</button>
      </header>

      <label class="xdock-in">
        <span class="xdock-in-h">Text</span>
        <textarea
          v-model="text"
          rows="3"
          spellcheck="false"
          placeholder="Extract from this surface, a selection, or paste any text…"
        ></textarea>
      </label>

      <div class="xdock-body">
        <ExtractionPanel v-if="text.trim()" :text="text" :source="ctx.surface || 'Extract dock'" />
        <p v-else class="xdock-empty">Type or paste text — or open a surface with a selected item — to pull live entities, claims, and topics, and promote them into the graph.</p>
      </div>
    </aside>
  </Transition>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import ExtractionPanel from './ExtractionPanel.vue';
import { useCockpit } from '../stores/cockpit';

const props = defineProps<{ open: boolean }>();
defineEmits<{ (e: 'close'): void }>();
const cockpit = useCockpit();
const ctx = computed(() => cockpit.context);

// Seed the textarea from the surface's context text (or its entity label) whenever the dock opens
// or the context changes — but keep it editable so the user can extract anything on any page.
const text = ref('');
function seed() {
  const c = cockpit.context;
  const from = c.text || [c.entityLabel, c.detail].filter(Boolean).join(' — ');
  if (from && from.trim()) text.value = from;
}
watch(() => props.open, (o) => { if (o) seed(); });
watch(() => cockpit.context, () => { if (props.open) seed(); }, { deep: true });
</script>

<style scoped>
.xdock {
  position: fixed; top: 0; right: 0; bottom: 0; width: min(400px, 92vw); z-index: 60;
  display: flex; flex-direction: column; gap: 0.6rem;
  background: var(--surface); border-left: 1px solid var(--line-2);
  box-shadow: -18px 0 44px rgba(0, 0, 0, 0.45); padding: 0.85rem 0.95rem;
}
.xdock-head { display: flex; align-items: center; gap: 0.5rem; }
.xdock-glyph { color: var(--accent); }
.xdock-title { font-size: 0.8rem; font-weight: 700; letter-spacing: 0.02em; }
.xdock-ctx { margin-left: auto; font-size: 0.68rem; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.06em; }
.xdock-x { border: none; background: transparent; color: var(--text-3); cursor: pointer; font-size: 0.8rem; }
.xdock-x:hover { color: var(--text); }
.xdock-in { display: flex; flex-direction: column; gap: 0.25rem; }
.xdock-in-h { font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--text-3); }
.xdock-in textarea { resize: vertical; background: var(--bg); border: 1px solid var(--line-2); border-radius: 8px; color: var(--text); font: inherit; font-size: 0.82rem; line-height: 1.5; padding: 0.45rem 0.6rem; outline: none; }
.xdock-in textarea:focus { border-color: color-mix(in srgb, var(--accent) 45%, transparent); }
.xdock-body { min-height: 0; overflow-y: auto; }
.xdock-empty { font-size: 0.8rem; color: var(--text-3); line-height: 1.5; padding: 0.5rem 0.1rem; }

.xdock-enter-active, .xdock-leave-active { transition: transform 0.18s ease, opacity 0.18s ease; }
.xdock-enter-from, .xdock-leave-to { transform: translateX(16px); opacity: 0; }
</style>
