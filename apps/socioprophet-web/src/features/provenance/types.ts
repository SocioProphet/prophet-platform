// Provenance / assay model — the moat, made visible. Every figure in the cockpit
// can declare HOW it was produced; the badge projects that to a verdict tier so a
// user (or auditor) can tell a *computed & replayable* number from a generated one.
// Mirrors the estate's "Assay" thinking (method / binding / verifier / receipt),
// projected to a render-time verdict.

export type ProvMethod =
  | 'computed'    // deterministic compute — replayable from inputs (the moat)
  | 'reasoned'    // model reasoning with an evidence trace
  | 'retrieved'   // grounded in a retrieved source
  | 'fixture'     // deterministic fixture — not yet assayed against a live source
  | 'generated';  // model-generated, unverified

export type Verdict = 'verified' | 'reasoned' | 'grounded' | 'unassayed' | 'unverified';

export interface Provenance {
  method: ProvMethod;
  verifier?: string;   // what checked / would replay it (e.g. 'VDT engine', 'sympy')
  sources?: string[];  // source refs (feeds, canon ids, datasets)
  asOf?: string;       // as-of timestamp/label
  receipt?: string;    // content hash / receipt ref
  formula?: string;    // the computation, when method === 'computed'
  note?: string;
}

export interface VerdictTier {
  verdict: Verdict;
  label: string;
  glyph: string;
  blurb: string;
}

export const TIERS: Record<ProvMethod, VerdictTier> = {
  computed: { verdict: 'verified', label: 'verified', glyph: '◆', blurb: 'Computed & replayable from its inputs' },
  reasoned: { verdict: 'reasoned', label: 'reasoned', glyph: '◆', blurb: 'Model reasoning with an evidence trace' },
  retrieved: { verdict: 'grounded', label: 'grounded', glyph: '◇', blurb: 'Grounded in a retrieved source' },
  fixture: { verdict: 'unassayed', label: 'unassayed', glyph: '○', blurb: 'Deterministic fixture — not yet assayed against a live source' },
  generated: { verdict: 'unverified', label: 'generated', glyph: '·', blurb: 'Model-generated, not verified' },
};

export const tierOf = (p: Provenance): VerdictTier => TIERS[p.method];

// Small helper so surfaces can declare provenance inline.
export function prov(method: ProvMethod, opts: Omit<Provenance, 'method'> = {}): Provenance {
  return { method, ...opts };
}
