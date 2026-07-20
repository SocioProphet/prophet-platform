// Vendored from synapseiq/packages/enrichment (the 3 pure functions synapse-bridge needs — the rest
// of that package pulls in @socioprophet/synapseiq-contracts + adapters we don't need here). Re-vendor
// from ~/dev/synapseiq on change. No deps, no I/O.

/** Canonical display name: collapse whitespace, trim non-alphanumerics, lowercase. */
export function normalizeName(name: string): string {
  return name.trim().replace(/\s+/g, ' ').replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, '').toLowerCase();
}

/** Canonical relation token: UPPER_SNAKE (SUPPORTS, WORKS_AT) — the graph edge-label convention. */
export function normalizeToken(token: string): string {
  return token.trim().replace(/[\s-]+/g, '_').replace(/[^\w]/g, '').toUpperCase();
}

/**
 * Align a source entity_type to the KKO upper ontology (the estate standard). Peircean categories:
 * Generals (Thirdness) = types/classes/concepts; Possibilities (Firstness) = qualities; else the entity
 * is a Particular (Secondness) — the default for named things (org/person/place/product).
 */
export function kkoClassOf(entityType: string): 'Particulars' | 'Generals' | 'Possibilities' {
  const t = entityType.toLowerCase();
  if (/type|class|concept|category|kind|taxonom|ontolog/.test(t)) return 'Generals';
  if (/quality|possibility|attribute|property|feeling|potential/.test(t)) return 'Possibilities';
  return 'Particulars';
}
