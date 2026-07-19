// Operator & infra surfaces — the compute / data / identity surfaces that live in
// the Noetica React app + standalone repos, surfaced on the cockpit's hamburger so
// they're reachable from one place. Each renders via OperatorSurface.vue.
export type SurfaceStatus = 'wired' | 'in-noetica' | 'standalone';

export interface OperatorSurfaceDef {
  id: string;
  title: string;
  eyebrow: string;
  blurb: string;
  capabilities: { label: string; detail: string }[];
  servedBy: string;
  status: SurfaceStatus;
  repo?: string;
}

export const OPERATOR_SURFACES: OperatorSurfaceDef[] = [
  {
    id: 'data-catalog', title: 'Data Catalog', eyebrow: 'Data & DataOps', status: 'in-noetica',
    blurb: 'Discover the datasets, corpora and canon feeding the brain — with schema, lineage, and access policy on every asset.',
    servedBy: 'Noetica agent-machine · data plane (:8080)',
    capabilities: [
      { label: 'Dataset & corpus registry', detail: 'Every source the brain reads, versioned and searchable.' },
      { label: 'Schema + lineage', detail: 'Walk an asset back to the pipeline stage and receipt that produced it.' },
      { label: 'Canon browser', detail: 'Frontier-authored canon vs. mined terms, side by side.' },
      { label: 'Access policy', detail: 'Who/what can read each asset, enforced by the capability membrane.' },
    ],
  },
  {
    id: 'pipelines', title: 'Pipelines', eyebrow: 'Data & DataOps', status: 'in-noetica',
    blurb: 'Batch + streaming data pipelines — ingestion, transform DAGs and backfills, each stage emitting a receipt.',
    servedBy: 'Apache Beam (batch) · Ray (distributed) via agent-machine',
    capabilities: [
      { label: 'Beam batch jobs', detail: 'Bounded ingestion + transforms with deterministic stopping.' },
      { label: 'Ray distributed', detail: 'Parallel compute across the lattice for heavy stages.' },
      { label: 'Backfill / replay', detail: 'Re-run a window from a cursor; results reconcile against receipts.' },
      { label: 'Per-stage receipts', detail: 'Input/output hashes + policy decisions — the provenance spine.' },
    ],
  },
  {
    id: 'labs', title: 'Model Labs', eyebrow: 'AI & Model Ops', status: 'in-noetica',
    blurb: 'Run experiments and boards, compare arms, and measure the verified-compute uplift that is the moat.',
    servedBy: 'Noetica agent-machine · eval harness',
    capabilities: [
      { label: 'Experiment runs', detail: 'Seeded, reproducible; every run is an artifact.' },
      { label: 'Board / A-B', detail: 'Compare mechanisms on identical inputs (n≥30).' },
      { label: 'Eval harness', detail: 'Clean-eval, no contamination; held-out sets.' },
      { label: 'Verified-compute uplift', detail: 'The measured delta from computing vs. generating an answer.' },
    ],
  },
  {
    id: 'studio', title: 'Studio', eyebrow: 'AI & Model Ops', status: 'in-noetica',
    blurb: 'Author agents, prompts, tools and skills, and wire them to the capability membrane before they run anywhere.',
    servedBy: 'Noetica agent-machine · agent builder',
    capabilities: [
      { label: 'Agent builder', detail: 'Compose surface + tools + retrieval + skills into an agent.' },
      { label: 'Prompt + skill library', detail: 'Reusable, versioned, testable.' },
      { label: 'Membrane wiring', detail: 'Bind each capability to a governed admission decision.' },
      { label: 'Sealed receipts', detail: 'Every agent action emits an attested machine receipt.' },
    ],
  },
  {
    id: 'rag-inspect', title: 'RAG Inspect', eyebrow: 'AI & Model Ops', status: 'in-noetica',
    blurb: 'Open the box: the chunks, scores, grounding and reasoning trace behind any answer.',
    servedBy: 'Noetica agent-machine · retrieval trace',
    capabilities: [
      { label: 'Retrieval trace', detail: 'Which passages were pulled, with similarity scores.' },
      { label: 'Grounding gate', detail: 'Was the answer grounded, partial, or ungrounded?' },
      { label: 'Faithfulness', detail: 'Does the narration match what the harness actually did?' },
      { label: 'Episode recall', detail: 'When the answer reuses a prior session, it says so.' },
    ],
  },
  {
    id: 'holograph-me', title: 'HolographMe', eyebrow: 'Identity & Reputation', status: 'standalone', repo: 'SocioProphet/HolographMe',
    blurb: 'Your portable, verified identity and reputation — a private correspondence lattice plus a reputation you carry across every surface.',
    servedBy: 'HolographMe (standalone) · not yet embedded',
    capabilities: [
      { label: 'Private identity lattice', detail: 'Correspondence-based identity that never leaves your device.' },
      { label: 'Portable reputation', detail: 'Sacred-capital reputation you carry to news, marketplace, people.' },
      { label: 'Verified Hats', detail: 'Role/expertise attestations, cryptographically bound.' },
      { label: 'One-way disclosure', detail: 'Reveal reputation without revealing identity.' },
    ],
  },
  {
    id: 'lattice-forge', title: 'Lattice Forge', eyebrow: 'Compute placement', status: 'standalone', repo: 'SocioProphet/lattice-forge',
    blurb: 'Where compute runs: runtime placement, notebook routing, and a compute marketplace across your lattice.',
    servedBy: 'lattice-forge (standalone) · referenced by the map runtime adapter',
    capabilities: [
      { label: 'Runtime placement', detail: 'Decide where a job runs — local, scale-up, cloud.' },
      { label: 'Notebook routing', detail: 'Route interactive compute to the right executor.' },
      { label: 'Compute marketplace', detail: 'Bid/settle compute like any other governed resource.' },
      { label: 'Execution-placement surface', detail: 'The lattice-runtime contract the map already names.' },
    ],
  },
];

export const operatorSurfaceById = (id: string): OperatorSurfaceDef | undefined => OPERATOR_SURFACES.find((s) => s.id === id);
