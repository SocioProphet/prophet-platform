<script setup lang="ts">
// W11.6 — the depth control. Writes the STORED preference (stores/settings.ts → localStorage),
// so setting it once changes every proof surface, on this visit and the next.
//
// It is a segmented control rather than a hidden "advanced" switch on purpose: TA-E's premise
// is that depth is a property of the CONSUMER, so it has to be as visible and as durable as a
// theme setting. What it does NOT do is change any claim — see features/depth/expertise.ts.
import { computed } from 'vue';
import { useSettings } from '../../stores/settings';
import { EXPERTISE_LEVELS, depthPolicy, type Expertise } from '../../features/depth/expertise';

withDefaults(defineProps<{ compact?: boolean }>(), { compact: false });

const settings = useSettings();
const level = computed<Expertise>(() => settings.expertise as Expertise);
const policy = computed(() => depthPolicy(level.value));
</script>

<template>
  <div class="dc" role="group" aria-label="Detail depth">
    <span class="dc-l">depth</span>
    <div class="dc-seg">
      <button
        v-for="l in EXPERTISE_LEVELS"
        :key="l"
        class="dc-opt"
        type="button"
        :class="{ on: level === l }"
        :aria-pressed="level === l"
        @click="settings.setExpertise(l)"
      >
        {{ depthPolicy(l).label }}
      </button>
    </div>
    <span v-if="!compact" class="dc-blurb">{{ policy.blurb }}</span>
    <!-- The guarantee, stated where the control is, because a depth control is exactly the
         affordance a reader would suspect of hiding bad news. -->
    <span v-if="!compact" class="dc-vow">
      Depth changes what is shown, never what is claimed — warrant type, seal state and
      model-generated markers show at every depth.
    </span>
  </div>
</template>

<style scoped>
.dc {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.dc-l {
  color: var(--faint);
  font-size: 0.6rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.dc-seg {
  display: inline-flex;
  border: 1px solid var(--border-2);
  border-radius: var(--r-1);
  overflow: hidden;
}
.dc-opt {
  background: transparent;
  color: var(--muted);
  border: 0;
  border-right: 1px solid var(--border-2);
  padding: 2px 10px;
  font-size: 0.68rem;
  cursor: pointer;
  font-family: inherit;
}
.dc-opt:last-child {
  border-right: 0;
}
.dc-opt:hover {
  color: var(--ink);
  background: var(--surface);
}
.dc-opt.on {
  color: var(--accent-ink);
  background: var(--accent-wash);
}
.dc-opt:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: -2px;
}
.dc-blurb {
  color: var(--faint);
  font-size: 0.64rem;
}
.dc-vow {
  flex-basis: 100%;
  color: var(--faint);
  font-size: 0.6rem;
  line-height: 1.45;
  border-left: 2px solid var(--hairline-strong);
  padding-left: 0.45rem;
}
</style>
