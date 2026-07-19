<template>
  <!-- A GAIA governed world-claim, made visible: anchor + evidence + uncertainty +
       policy status. This is the thing peers don't have — data as a governed claim,
       not a coloured cell. -->
  <div class="wc" :class="claim.policy_status.status">
    <div class="wc-h">
      <span class="wc-status">{{ statusLabel }}</span>
      <span class="wc-type">WorldClaim · {{ claim.claim_type.replace(/_/g, ' ') }}</span>
    </div>
    <!-- Ontogenesis Ω ladder: where this datum sits on the governed path to truth. -->
    <div class="wc-omega" :title="`Ontogenesis Ω ladder — ${conf.stepsToActionable} rung(s) to ACTIONABLE`">
      <span class="wc-omega-k">Ω</span>
      <span class="wc-omega-track">
        <i v-for="r in OMEGA_LADDER" :key="r.id" class="wc-omega-rung" :class="{ on: r.notation <= conf.notation, here: r.notation === conf.notation }" />
      </span>
      <span class="wc-omega-v">{{ conf.omega }} · {{ conf.notation }}/6</span>
    </div>
    <div class="wc-unc">
      <span class="wc-unc-label">confidence</span>
      <span class="wc-unc-bar"><i :style="{ width: Math.round(claim.uncertainty.confidence_score * 100) + '%' }" /></span>
      <span class="wc-unc-v">{{ Math.round(claim.uncertainty.confidence_score * 100) }}% · {{ claim.uncertainty.uncertainty_class }}</span>
    </div>
    <dl class="wc-rows">
      <div><dt>Anchor</dt><dd>{{ claim.geo_anchor.anchor_type }} · {{ (claim.geo_anchor.h3_cells && claim.geo_anchor.h3_cells[0]) || claim.geo_anchor.anchor_id }}</dd></div>
      <div><dt>Evidence</dt><dd><span v-for="e in claim.source_evidence" :key="e.evidence_id" class="wc-ev" :class="{ synth: e.source_type === 'synthetic_fixture' }">{{ e.source_type }}</span></dd></div>
      <div><dt>Source</dt><dd>{{ claim.attribution.primary_source_name }}</dd></div>
      <div v-if="claim.temporal_validity.staleness_class"><dt>As of</dt><dd>{{ claim.temporal_validity.valid_from.slice(0, 10) }} · {{ claim.temporal_validity.staleness_class }}</dd></div>
    </dl>
    <p v-if="advisory" class="wc-advisory">{{ advisory }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { WorldClaim } from '../gaia/worldClaim';
import { omegaConformance, OMEGA_LADDER } from '../ontology/ontogenesis';
const props = defineProps<{ claim: WorldClaim }>();
const conf = computed(() => omegaConformance(props.claim));
const LABELS: Record<string, string> = { admitted: '◆ Admitted world state', provisional: '◐ Provisional', proposed: '○ Proposed (illustrative)', review: '⚠ Flagged for review', rejected: '✕ Rejected' };
const statusLabel = computed(() => LABELS[props.claim.policy_status.status] ?? props.claim.policy_status.status);
const advisory = computed(() => props.claim.map_display?.advisory_label || (props.claim.policy_status.constraints?.length ? props.claim.policy_status.constraints.join(' · ') : ''));
</script>

<style scoped>
.wc { border: 1px solid var(--line-2); border-radius: 10px; background: var(--surface-2, #1b1e25); padding: 0.65rem 0.75rem; display: flex; flex-direction: column; gap: 0.5rem; }
.wc.admitted { border-left: 3px solid var(--live); }
.wc.proposed, .wc.provisional, .wc.review { border-left: 3px solid var(--amber); }
.wc.rejected { border-left: 3px solid var(--down); }
.wc-h { display: flex; align-items: baseline; justify-content: space-between; gap: 0.5rem; }
.wc-status { font-size: 0.72rem; font-weight: 700; letter-spacing: -0.01em; }
.wc.admitted .wc-status { color: var(--live); }
.wc.proposed .wc-status, .wc.provisional .wc-status, .wc.review .wc-status { color: var(--amber); }
.wc.rejected .wc-status { color: var(--down); }
.wc-type { font-family: var(--mono, ui-monospace); font-size: 0.54rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--text-3); }
.wc-omega { display: flex; align-items: center; gap: 0.4rem; font-size: 0.6rem; color: var(--text-3); }
.wc-omega-k { font-weight: 700; color: var(--text-2); }
.wc-omega-track { flex: 1; display: flex; gap: 2px; }
.wc-omega-rung { flex: 1; height: 5px; border-radius: 2px; background: rgba(255,255,255,0.1); }
.wc-omega-rung.on { background: var(--amber); }
.wc.admitted .wc-omega-rung.on { background: var(--live); }
.wc-omega-rung.here { box-shadow: 0 0 0 1px var(--text); }
.wc-omega-v { white-space: nowrap; font-variant-numeric: tabular-nums; letter-spacing: 0.04em; text-transform: uppercase; }
.wc-unc { display: flex; align-items: center; gap: 0.4rem; font-size: 0.6rem; color: var(--text-3); }
.wc-unc-label { text-transform: uppercase; letter-spacing: 0.06em; white-space: nowrap; }
.wc-unc-bar { flex: 1; height: 5px; border-radius: 3px; background: rgba(255,255,255,0.1); overflow: hidden; }
.wc-unc-bar i { display: block; height: 100%; background: var(--live); }
.wc.proposed .wc-unc-bar i, .wc.provisional .wc-unc-bar i, .wc.review .wc-unc-bar i { background: var(--amber); }
.wc-unc-v { white-space: nowrap; font-variant-numeric: tabular-nums; }
.wc-rows { margin: 0; display: grid; gap: 0.25rem; }
.wc-rows > div { display: grid; grid-template-columns: 4.2rem 1fr; gap: 0.5rem; align-items: baseline; }
.wc-rows dt { font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-3); }
.wc-rows dd { margin: 0; font-size: 0.74rem; color: var(--text-2); overflow-wrap: anywhere; }
.wc-ev { display: inline-block; font-family: var(--mono, ui-monospace); font-size: 0.58rem; color: var(--live); border: 1px solid rgba(75,191,115,0.4); border-radius: 4px; padding: 0.02rem 0.3rem; margin: 0 0.2rem 0.2rem 0; }
.wc-ev.synth { color: var(--amber); border-color: rgba(227,179,65,0.4); }
.wc-advisory { margin: 0; font-size: 0.62rem; color: var(--amber); line-height: 1.4; }
</style>
