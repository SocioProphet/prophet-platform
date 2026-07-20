// Canonical knowledge-graph client — hellgraph-service, the shared HTTP HellGraph engine
// (prophet-platform/apps/hellgraph-service). This is the ONE backend the cockpit's Knowledge
// Graph and the Prophet Studio Graph Explorer both read, so the graph is unified across surfaces.
//
// Base is the same-origin `/svc/hellgraph` proxy (see vite.config.ts) → :8090 in dev.
// Endpoints mirror the agent-machine surface contract, so SurfaceResult/GraphHealth are reused.
import type { SurfaceResult, GraphHealth } from './agentMachineApi';
import { resolveBase } from '../config/cockpitRuntime';

const BASE = resolveBase('hellgraph', 'VITE_HELLGRAPH_BASE', '/svc/hellgraph');

export const graphSurface = async (view = 'all', limit = 34, root = ''): Promise<SurfaceResult> => {
  const q = new URLSearchParams({ view, limit: String(limit) });
  if (root) q.set('root', root);
  const res = await fetch(`${BASE}/api/graph/surface?${q.toString()}`);
  if (!res.ok) throw new Error(`graph surface ${res.status}`);
  return res.json();
};

export async function graphHealth(): Promise<GraphHealth> {
  const res = await fetch(`${BASE}/api/graph/stats`);
  if (!res.ok) throw new Error(`graph stats ${res.status}`);
  const d = (await res.json()) as { nodes: number; edges: number };
  return { ok: true, nodes: d.nodes, edges: d.edges };
}

// GraphRAG grounding: seed on a query, return the N-hop facts as provenance-cited citations
// (each carrying its assertion time). This is how a surface anchors itself to the LIVE graph —
// the facts the News→IE→graph loop writes surface here with fresh assertedAt timestamps.
export interface GroundFact {
  n: number; fact: string; subject: string; predicate: string; object: string;
  assertedAt?: string; isIri?: boolean;
}
export interface Grounding {
  question: string; seeds: string[]; groundedNodes: string[]; citations: GroundFact[]; semanticEnabled?: boolean;
}
export async function groundGraph(q: string, hops = 1): Promise<Grounding> {
  const params = new URLSearchParams({ q, hops: String(hops) });
  const res = await fetch(`${BASE}/api/graph/ground?${params.toString()}`);
  if (!res.ok) throw new Error(`graph ground ${res.status}`);
  return res.json();
}
