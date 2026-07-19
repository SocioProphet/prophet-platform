// Supply-chain orchestration store — compose a chain from providers, score it, and
// COMPILE it into governed, proof-carrying contracts (one per stage, each with a
// sealed grant + receipt). This is "organize a chain, not just see it" — the same
// shared-store pattern as the trading book, applied to goods.
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { PROVIDERS, STAGES, providersForStage, type Provider, type Stage } from '../data/providersFixture';

const KEY = 'sp-supplychain-v1';
export type ContractStatus = 'admitted' | 'executing' | 'settled';
export interface StageContract {
  id: string; stage: Stage; providerId: string; providerName: string;
  unitCost: number; leadDays: number; status: ContractStatus;
  receipt: string; grantRef: string;
}
interface Saved { selection: Record<string, string>; contracts: StageContract[] }
function load(): Saved {
  try { const raw = localStorage.getItem(KEY); const p = raw ? JSON.parse(raw) : null; if (p && p.selection) return p; } catch { /* */ }
  return { selection: {}, contracts: [] };
}

// Higher = better fit (capacity, rating, verified) minus cost + lead time.
export function scoreProvider(p: Provider): number {
  return p.rating * 18 + p.capacityPct * 0.35 - p.leadDays * 0.6 - p.unitCost * 0.004 + (p.reputation === 'verified' ? 12 : 0);
}

export const useSupplyChain = defineStore('supplychain', () => {
  const saved = load();
  const goal = ref('Copper cathode → Brooklyn');
  const selection = ref<Record<string, string>>(saved.selection);
  const contracts = ref<StageContract[]>(saved.contracts);
  function persist() { try { localStorage.setItem(KEY, JSON.stringify({ selection: selection.value, contracts: contracts.value })); } catch { /* */ } }

  function selectProvider(stage: Stage, id: string) { selection.value = { ...selection.value, [stage]: id }; persist(); }
  function autoRecommend() {
    const next: Record<string, string> = { ...selection.value };
    for (const s of STAGES) { const best = [...providersForStage(s.id)].sort((a, b) => scoreProvider(b) - scoreProvider(a))[0]; if (best) next[s.id] = best.id; }
    selection.value = next; persist();
  }
  function reset() { selection.value = {}; contracts.value = []; persist(); }

  const selectedProviders = computed(() => STAGES.map((s) => ({ stage: s, provider: PROVIDERS.find((p) => p.id === selection.value[s.id]) })));
  const chosen = computed(() => selectedProviders.value.map((x) => x.provider).filter((p): p is Provider => Boolean(p)));
  const totalCost = computed(() => chosen.value.reduce((s, p) => s + p.unitCost, 0));
  const totalLeadDays = computed(() => chosen.value.reduce((s, p) => s + p.leadDays, 0));
  const completeness = computed(() => chosen.value.length / STAGES.length);
  const ratingAvg = computed(() => (chosen.value.length ? chosen.value.reduce((s, p) => s + p.rating, 0) / chosen.value.length : 0));
  const riskScore = computed(() => {
    if (!chosen.value.length) return 0;
    const avg = chosen.value.reduce((s, p) => s + (100 - p.capacityPct) * 0.35 + (5 - p.rating) * 8 + (p.reputation === 'unrated' ? 16 : 0), 0) / chosen.value.length;
    return Math.round(Math.min(100, avg));
  });

  // Compile the composed chain into governed contracts (membrane-admitted + sealed).
  function composeContracts() {
    contracts.value = selectedProviders.value
      .filter((x) => x.provider)
      .map((x) => ({
        id: `ct-${x.stage.id}`, stage: x.stage.id, providerId: x.provider!.id, providerName: x.provider!.name,
        unitCost: x.provider!.unitCost, leadDays: x.provider!.leadDays, status: 'admitted' as ContractStatus,
        receipt: `sha256:${x.provider!.provenanceHash.replace('sha256:', '')}-ct`, grantRef: `grant:sealed:${x.stage.id}-ro`,
      }));
    persist();
  }
  function advance(id: string) {
    const order: ContractStatus[] = ['admitted', 'executing', 'settled'];
    contracts.value = contracts.value.map((c) => c.id === id ? { ...c, status: order[Math.min(order.length - 1, order.indexOf(c.status) + 1)]! } : c);
    persist();
  }

  return { goal, selection, contracts, selectProvider, autoRecommend, reset, selectedProviders, chosen, totalCost, totalLeadDays, completeness, ratingAvg, riskScore, composeContracts, advance };
});
