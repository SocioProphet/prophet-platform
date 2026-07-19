// Reified claims — the SOTA of the extraction/provenance/hypergraph moat. Every
// extracted fact becomes a first-class CLAIM: an n-ary Subject·Predicate·Object
// binding that carries its full provenance tuple (source, extraction method, model
// version, time observed, confidence) and can be attested, disputed, or revised.
// This is a hyperedge in HellGraph — the thing binary-link ontologies can't model.
export type ClaimStatus = 'asserted' | 'attested' | 'disputed' | 'revised';

export interface ClaimProvenance {
  source: string;
  extractionMethod: string; // e.g. 'Holmes pattern v0'
  modelVersion: string;
  timeObserved: string;     // ISO
  confidence: number;       // 0..1
}

export interface ClaimDispute { reason: string; by: string; ts: number }

export interface ReifiedClaim {
  id: string;
  subject: string;
  predicate: string;
  object: string;
  // n-ary: every entity the claim binds (subject, object, + contextual members) —
  // the hyperedge members. A "situation" is a claim binding many members.
  members: string[];
  provenance: ClaimProvenance;
  status: ClaimStatus;
  attestations: number;
  disputes: ClaimDispute[];
  topics: string[];
}

export const STATUS_META: Record<ClaimStatus, { label: string; color: string }> = {
  asserted: { label: 'asserted', color: '#93b4ff' },
  attested: { label: 'attested', color: '#4bbf73' },
  disputed: { label: 'disputed', color: '#f0656a' },
  revised: { label: 'revised', color: '#e3b341' },
};
