<template>
  <section class="hm" aria-label="HolographMe reputation">
    <SurfaceHeader title="HolographMe" eyebrow="Portable, verified reputation — carried across every surface">
      <template #badge><span class="hm-stat">{{ people.length }} identities</span></template>
      <template #actions>
        <div class="hm-modes">
          <button v-for="t in TIER_ORDER" :key="t" class="hm-mode" :class="{ on: tierFilter === t }" type="button" @click="tierFilter = tierFilter === t ? 'all' : t">
            {{ TIER_META[t].label }}
          </button>
          <button class="hm-mode" :class="{ on: tierFilter === 'all' }" type="button" @click="tierFilter = 'all'">All</button>
        </div>
      </template>
    </SurfaceHeader>

    <p class="hm-lede">
      One reputation, resolved by handle / DID / name and carried across news, marketplace, and people.
      Modeled BFO-style: the <b>score</b> is a <em>disposition</em> (stable standing), <b>traits</b> are dispositions,
      and <b>occurrents</b> are the grounding episodes — the verified acts that earned it. This is the same lattice
      behind every <ReputationBadge subject="ada.newhope.social" /> chip in the product.
    </p>

    <div class="hm-grid">
      <article v-for="r in people" :key="r.id" class="hm-card" :style="{ '--tier': TIER_META[r.tier].color }">
        <header class="hm-card-h">
          <div class="hm-ring" :style="{ '--pct': r.score }">
            <span class="hm-score">{{ r.score }}</span>
          </div>
          <div class="hm-id">
            <div class="hm-name">{{ r.displayName }}</div>
            <div class="hm-tier">{{ TIER_META[r.tier].label }}</div>
            <div v-if="r.did" class="hm-did" :title="r.did">{{ r.did }}</div>
          </div>
        </header>

        <div class="hm-hats">
          <span v-for="h in r.hats" :key="h.kind" class="hm-hat" :class="h.kind">{{ hatIcon(h.kind) }} {{ h.label }}</span>
        </div>

        <div class="hm-ledger">
          <span class="hm-att">✓ {{ r.attestations }} attested</span>
          <span class="hm-dis">✕ {{ r.disputes }} disputed</span>
          <span class="hm-trust">{{ trust(r) }}% corroboration</span>
        </div>

        <div v-if="r.traits.length" class="hm-traits">
          <span v-for="t in r.traits" :key="t" class="hm-trait">{{ t }}</span>
        </div>

        <div class="hm-occ">
          <div class="hm-occ-h">Occurrents — grounding episodes</div>
          <div v-for="(o, i) in r.occurrents" :key="i" class="hm-occ-i">· {{ o }}</div>
        </div>

        <div class="hm-aliases">
          <span class="hm-alias-h">Answers to</span>
          <code v-for="a in r.aliases" :key="a" class="hm-alias">{{ a }}</code>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import SurfaceHeader from '../components/SurfaceHeader.vue';
import ReputationBadge from '../components/ReputationBadge.vue';
import { REPUTATIONS, TIER_META, type HatKind, type Tier, type Reputation } from '../features/reputation/reputation';

const TIER_ORDER: Tier[] = ['trusted', 'established', 'emerging', 'unrated'];
const tierFilter = ref<'all' | Tier>('all');

const people = computed(() =>
  [...REPUTATIONS]
    .filter((r) => tierFilter.value === 'all' || r.tier === tierFilter.value)
    .sort((a, b) => b.score - a.score),
);

const hatIcon = (k: HatKind) => ({ verified: '✓', expert: '★', moderator: '⚖', local: '⚲', source: '◈' }[k] ?? '');
// Corroboration = attestations against total signal — the share of standing that is independently vouched.
const trust = (r: Reputation) => Math.round((r.attestations / (r.attestations + r.disputes)) * 100);
</script>

<style scoped>
.hm { display: flex; flex-direction: column; gap: 1rem; }
.hm-stat { font-size: 0.72rem; color: var(--text-2); }
.hm-modes { display: flex; gap: 0.35rem; flex-wrap: wrap; }
.hm-mode { font-size: 0.72rem; padding: 0.2rem 0.6rem; border-radius: 999px; border: 1px solid var(--line-2); background: transparent; color: var(--text-2); cursor: pointer; }
.hm-mode.on { border-color: var(--accent, #58a6ff); color: var(--text); background: color-mix(in srgb, var(--accent, #58a6ff) 14%, transparent); }
.hm-lede { margin: 0; max-width: 62ch; font-size: 0.82rem; line-height: 1.6; color: var(--text-2); }
.hm-lede b { color: var(--text); font-weight: 600; } .hm-lede em { font-style: italic; color: var(--text); }

.hm-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(19rem, 1fr)); gap: 0.85rem; }
.hm-card { display: flex; flex-direction: column; gap: 0.6rem; padding: 0.95rem 1rem; border-radius: 14px; border: 1px solid var(--line-2); border-top: 2px solid var(--tier); background: var(--surface-1, rgba(255, 255, 255, 0.02)); }
.hm-card-h { display: flex; align-items: center; gap: 0.75rem; }
.hm-ring { --pct: 50; position: relative; width: 3rem; height: 3rem; border-radius: 50%; display: grid; place-items: center; flex: none;
  background: conic-gradient(var(--tier) calc(var(--pct) * 1%), rgba(255, 255, 255, 0.08) 0); }
.hm-ring::after { content: ''; position: absolute; inset: 4px; border-radius: 50%; background: var(--bg, #0d1117); }
.hm-score { position: relative; z-index: 1; font-size: 0.95rem; font-weight: 800; color: var(--tier); font-variant-numeric: tabular-nums; }
.hm-id { min-width: 0; }
.hm-name { font-size: 0.95rem; font-weight: 700; color: var(--text); }
.hm-tier { font-size: 0.66rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--tier); font-weight: 600; }
.hm-did { font-family: ui-monospace, monospace; font-size: 0.6rem; color: var(--text-3); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.hm-hats { display: flex; flex-wrap: wrap; gap: 0.3rem; }
.hm-hat { font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.03em; color: var(--text-2); border: 1px solid var(--line-2); border-radius: 999px; padding: 0.05rem 0.45rem; }
.hm-hat.verified { color: #4bbf73; border-color: rgba(75, 191, 115, 0.4); }
.hm-hat.source { color: #58a6ff; border-color: rgba(88, 166, 255, 0.4); }

.hm-ledger { display: flex; flex-wrap: wrap; gap: 0.6rem; font-size: 0.72rem; }
.hm-att { color: #4bbf73; } .hm-dis { color: #f0656a; } .hm-trust { color: var(--text-2); margin-left: auto; }

.hm-traits { display: flex; flex-wrap: wrap; gap: 0.3rem; }
.hm-trait { font-size: 0.66rem; color: #93b4ff; background: rgba(120, 160, 255, 0.12); border-radius: 999px; padding: 0.05rem 0.45rem; }

.hm-occ { display: grid; gap: 0.15rem; border-top: 1px solid var(--line-2); padding-top: 0.5rem; }
.hm-occ-h { font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-3); }
.hm-occ-i { font-size: 0.74rem; color: var(--text-2); line-height: 1.45; }

.hm-aliases { display: flex; flex-wrap: wrap; align-items: center; gap: 0.3rem; border-top: 1px solid var(--line-2); padding-top: 0.5rem; }
.hm-alias-h { font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-3); margin-right: 0.15rem; }
.hm-alias { font-family: ui-monospace, monospace; font-size: 0.62rem; color: var(--text-2); background: rgba(255, 255, 255, 0.04); border-radius: 5px; padding: 0.05rem 0.35rem; }
</style>
