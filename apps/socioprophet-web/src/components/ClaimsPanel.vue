<template>
  <!-- Reified claims for the current item: Subject·Predicate·Object with the full
       provenance tuple, attest / dispute / revise, and a Sherlock verify. Each is a
       hyperedge candidate in HellGraph. -->
  <div class="cp" v-if="rows.length">
    <div class="cp-head">
      <span class="cp-title">Reified claims</span>
      <ProvenanceBadge :p="claimProv" compact />
      <span class="cp-count">{{ rows.length }}</span>
    </div>
    <div class="cp-list">
      <div v-for="c in rows" :key="c.id" class="cp-claim" :class="c.status">
        <div class="cp-spo">
          <span class="cp-subj">{{ c.subject }}</span>
          <span class="cp-pred">{{ c.predicate }}</span>
          <span class="cp-obj">{{ c.object }}</span>
          <span class="cp-status" :style="{ color: statusColor(c.status), borderColor: statusColor(c.status) }">{{ c.status }}</span>
        </div>
        <div class="cp-prov" :title="`${c.provenance.extractionMethod} · ${c.provenance.modelVersion}`">
          <span>{{ c.provenance.source }}</span>
          <span class="cp-sep">·</span>
          <span>{{ Math.round(c.provenance.confidence * 100) }}% conf</span>
          <span v-if="c.attestations" class="cp-att">✓ {{ c.attestations }}</span>
          <span v-if="c.disputes.length" class="cp-dis">✕ {{ c.disputes.length }}</span>
        </div>
        <div class="cp-actions">
          <button class="cp-btn attest" type="button" title="Attest (corroborate)" @click="claims.attest(c.id)">✓ attest</button>
          <button class="cp-btn dispute" type="button" title="Dispute" @click="disputeId = disputeId === c.id ? '' : c.id">✕ dispute</button>
          <button class="cp-btn" type="button" title="Verify with Sherlock" @click="verify(c)">⌕ verify</button>
        </div>
        <div v-if="disputeId === c.id" class="cp-reasons">
          <button v-for="r in DISPUTE_REASONS" :key="r" type="button" @click="doDispute(c.id, r)">{{ r }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, watch, ref } from 'vue';
import { reify } from '../features/claims/reify';
import { STATUS_META, type ReifiedClaim, type ClaimStatus } from '../features/claims/types';
import { useClaims } from '../stores/claims';
import { useCockpit } from '../stores/cockpit';
import { useOntology } from '../stores/ontology';
import { prov } from '../features/provenance/types';
import ProvenanceBadge from './ProvenanceBadge.vue';

const props = defineProps<{ text: string; source: string }>();
const claims = useClaims();
const cockpit = useCockpit();
const ontology = useOntology();
const disputeId = ref('');
const DISPUTE_REASONS = ['contradicted by source', 'outdated', 'misattributed', 'unverifiable'];

// Reify the current item + assert into the shared registry; induce relations into the ontology.
watch(() => [props.text, props.source], () => {
  if (!props.text) return;
  const reified = reify(props.text, props.source);
  claims.assert(reified);
  ontology.observe([], reified.map((c) => c.predicate), []);
}, { immediate: true });

const rows = computed(() => claims.claims.filter((c) => c.provenance.source === props.source));
const claimProv = prov('reasoned', { verifier: 'reifier', formula: 'S·P·O + {source, method, model, time, confidence}', receipt: 'sha256:claims', note: 'Each claim is an n-ary hyperedge candidate with a full provenance tuple — attestable, disputable, revisable.' });
const statusColor = (s: ClaimStatus) => STATUS_META[s].color;
function doDispute(id: string, reason: string) { claims.dispute(id, reason); disputeId.value = ''; }
function verify(c: ReifiedClaim) {
  cockpit.askAbout(`Sherlock evidence check on the claim: "${c.subject} ${c.predicate} ${c.object}" (source ${c.provenance.source}, ${Math.round(c.provenance.confidence * 100)}% confidence). Corroborated, contradicted, or unverified — and by what?`);
}
</script>

<style scoped>
.cp { display: flex; flex-direction: column; gap: 0.5rem; }
.cp-head { display: flex; align-items: center; gap: 0.5rem; }
.cp-title { font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.1em; color: rgba(255, 255, 255, 0.5); font-weight: 700; }
.cp-count { margin-left: auto; font-size: 0.66rem; color: rgba(255, 255, 255, 0.4); }
.cp-list { display: flex; flex-direction: column; gap: 0.4rem; }
.cp-claim { border: 1px solid var(--line-2); border-radius: 9px; padding: 0.5rem 0.6rem; background: var(--surface-2); }
.cp-claim.disputed { border-color: rgba(240, 101, 106, 0.4); } .cp-claim.attested { border-color: rgba(75, 191, 115, 0.35); }
.cp-spo { display: flex; align-items: center; gap: 0.4rem; flex-wrap: wrap; font-size: 0.8rem; }
.cp-subj { color: #fff; font-weight: 600; } .cp-obj { color: var(--text); }
.cp-pred { color: #93b4ff; font-style: italic; font-size: 0.74rem; }
.cp-status { margin-left: auto; font-size: 0.56rem; text-transform: uppercase; letter-spacing: 0.04em; font-weight: 700; border: 1px solid; border-radius: 4px; padding: 0.03rem 0.3rem; }
.cp-prov { display: flex; align-items: center; gap: 0.4rem; margin-top: 0.3rem; font-size: 0.66rem; color: var(--text-3); }
.cp-sep { opacity: 0.5; } .cp-att { color: var(--up); } .cp-dis { color: var(--down); }
.cp-actions { display: flex; gap: 0.35rem; margin-top: 0.4rem; }
.cp-btn { border: 1px solid var(--line-2); background: transparent; color: var(--text-2); border-radius: 6px; padding: 0.15rem 0.45rem; font-size: 0.68rem; cursor: pointer; }
.cp-btn.attest:hover { color: var(--up); border-color: rgba(75, 191, 115, 0.4); } .cp-btn.dispute:hover { color: var(--down); border-color: rgba(240, 101, 106, 0.4); } .cp-btn:hover { color: var(--text); }
.cp-reasons { display: flex; flex-wrap: wrap; gap: 0.3rem; margin-top: 0.4rem; }
.cp-reasons button { border: 1px solid var(--line-2); background: var(--surface); color: var(--text-2); border-radius: 6px; padding: 0.12rem 0.4rem; font-size: 0.66rem; cursor: pointer; } .cp-reasons button:hover { border-color: var(--down); color: var(--down); }
</style>
