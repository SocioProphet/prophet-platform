// Claim registry — the shared store of reified claims across surfaces, with the
// dispute/revision loop. Claims persist locally; a future HellGraph writer emits
// each as a provenance-bearing hyperedge.
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { ReifiedClaim, ClaimStatus } from '../features/claims/types';

const STORE_KEY = 'sp-claims-v1';

function load(): ReifiedClaim[] {
  try { const raw = localStorage.getItem(STORE_KEY); const p = raw ? JSON.parse(raw) : []; return Array.isArray(p) ? p : []; } catch { return []; }
}

export const useClaims = defineStore('claims', () => {
  const claims = ref<ReifiedClaim[]>(load());
  function persist() { try { localStorage.setItem(STORE_KEY, JSON.stringify(claims.value)); } catch { /* */ } }

  // Assert new claims (dedup by id); keep the higher-confidence one on collision.
  function assert(incoming: ReifiedClaim[]) {
    const byId = new Map(claims.value.map((c) => [c.id, c]));
    for (const c of incoming) {
      const existing = byId.get(c.id);
      if (!existing) byId.set(c.id, c);
      else if (c.provenance.confidence > existing.provenance.confidence) byId.set(c.id, { ...c, status: existing.status, attestations: existing.attestations, disputes: existing.disputes });
    }
    claims.value = [...byId.values()];
    persist();
  }
  function attest(id: string) {
    claims.value = claims.value.map((c) => c.id === id ? { ...c, attestations: c.attestations + 1, status: (c.status === 'disputed' ? c.status : 'attested') as ClaimStatus } : c);
    persist();
  }
  function dispute(id: string, reason: string) {
    claims.value = claims.value.map((c) => c.id === id ? { ...c, status: 'disputed', disputes: [...c.disputes, { reason, by: 'you', ts: Date.now() }] } : c);
    persist();
  }
  function revise(id: string, newObject: string) {
    claims.value = claims.value.map((c) => c.id === id ? { ...c, object: newObject, status: 'revised', provenance: { ...c.provenance, timeObserved: new Date().toISOString() } } : c);
    persist();
  }
  function reset() { claims.value = []; persist(); }

  const forSource = (source: string) => computed(() => claims.value.filter((c) => c.provenance.source === source));
  const counts = computed(() => ({
    total: claims.value.length,
    attested: claims.value.filter((c) => c.status === 'attested').length,
    disputed: claims.value.filter((c) => c.status === 'disputed').length,
  }));

  return { claims, assert, attest, dispute, revise, reset, forSource, counts };
});
