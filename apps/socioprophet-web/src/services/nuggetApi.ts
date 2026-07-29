/**
 * KnowledgeNugget feed API (W11.5).
 *
 * ── THE LIVE DOOR IS REAL, AND IT IS THIS ONE ──────────────────────────────────────────────
 * `apps/nugget-extractor` (#1042) writes each nugget into hellgraph-service as a graph node:
 *
 *     POST /api/graph/node  {id: <nuggetId>, labels: ["KnowledgeNugget", "warrant:<type>"],
 *                            properties: contract.flatten(nugget, ingest_time)}
 *
 * and `contract.flatten` (contract.py :321) puts the FULL validated nugget on the node as
 * canonical JSON under the `nugget` property — deliberately, so "the graph carries the
 * spec-conformant OBJECT, not just a lossy projection".
 *
 * hellgraph-service serves label-scoped node reads at `GET /api/graph/query?label=…`
 * (server.ts :328), returning `{count, nodes}` with full properties. Composing the two gives a
 * genuine live feed with no new endpoint required — which is exactly what the emitter's design
 * note anticipated: "`warrant:<type>` is a LABEL, so 'give me everything that is not
 * model-generated' is a label query rather than a JSON scan".
 *
 * ── WHAT IS NOT WIRED, STATED PLAINLY ──────────────────────────────────────────────────────
 *   • No push. `/api/graph/query` is pull-only; there is no SSE/WS nugget stream, so "JustIN
 *     delivery" is currently a poll. The surface says so rather than implying a live push.
 *   • No grant scoping. The Memory Distribution Grant plane is not reachable from this app —
 *     there is no grant service base, no grant claim on the node, and nothing in
 *     hellgraph-service filters by grant. Subscription below is therefore a CLIENT-SIDE view
 *     filter and is labelled as one. It is not access control and must not be read as any.
 *
 * ── FALLBACK POSTURE (the #1052 lesson) ────────────────────────────────────────────────────
 * A failed live read must never quietly become fixture proof. So:
 *   • reachable + nuggets  → mode 'live'
 *   • reachable + zero     → mode 'live', an EMPTY feed, and an explicit empty state. Fixtures
 *                            are NOT substituted; an empty graph is a fact, not a gap to fill.
 *   • unreachable / error  → mode 'fixture', fixtures shown, and `error` carries the reason so
 *                            the surface can print it. Never 'live'.
 */
import { resolveBase } from '../config/cockpitRuntime';
import { FIXTURE_MALFORMED, FIXTURE_NUGGETS } from '../data/nuggetFixture';
import { parseNugget, type FeedItem } from '../features/nuggets/types';

const HELLGRAPH = resolveBase('hellgraph', 'VITE_HELLGRAPH_BASE', '/svc/hellgraph');

/** The node label the emitter writes. `apps/nugget-extractor/emitter.py` NUGGET_LABEL. */
export const NUGGET_LABEL = 'KnowledgeNugget';

export type NuggetLoadMode = 'live' | 'fixture';

export interface NuggetFeedResult {
  items: FeedItem[];
  mode: NuggetLoadMode;
  /** Why the live read did not produce the feed. Null when it did. */
  error: string | null;
  /** True when the graph answered and simply held no nuggets. Only meaningful when mode==='live'. */
  emptyLive: boolean;
}

interface GraphNode {
  id?: unknown;
  labels?: unknown;
  properties?: unknown;
}

/**
 * Pull nuggets from the graph.
 *
 * `warrantType` maps onto the emitter's `warrant:<type>` label so the filter runs server-side
 * where possible; with no filter it reads the `KnowledgeNugget` label.
 */
export async function fetchNuggets(warrantType?: string): Promise<NuggetFeedResult> {
  const label = warrantType ? `warrant:${warrantType}` : NUGGET_LABEL;
  const url = `${HELLGRAPH.replace(/\/$/, '')}/api/graph/query?label=${encodeURIComponent(label)}`;
  try {
    const res = await fetch(url, { headers: { accept: 'application/json' } });
    if (!res.ok) return fixture(`hellgraph ${res.status} on /api/graph/query?label=${label}`);
    const body = (await res.json()) as { count?: unknown; nodes?: unknown };
    if (!Array.isArray(body.nodes)) {
      return fixture('hellgraph returned an unrecognized /api/graph/query shape');
    }

    const items: FeedItem[] = [];
    for (const raw of body.nodes as GraphNode[]) {
      const nodeId = typeof raw?.id === 'string' ? raw.id : '';
      const props = (raw?.properties ?? {}) as Record<string, unknown>;
      const blob = props['nugget'];
      if (typeof blob !== 'string') {
        // The node exists but carries no canonical nugget JSON. That is unreadable, which is
        // NOT the same as invalid — we never checked the nugget, we just cannot see it.
        items.push({ ok: false, nodeId, reason: 'node has no canonical `nugget` property' });
        continue;
      }
      let parsed: unknown;
      try {
        parsed = JSON.parse(blob);
      } catch (e) {
        items.push({
          ok: false,
          nodeId,
          reason: `canonical nugget JSON did not parse: ${e instanceof Error ? e.message : String(e)}`,
        });
        continue;
      }
      items.push(parseNugget(parsed, nodeId));
    }

    // Reachable and empty is a LIVE fact. Do not paper over it with fixtures.
    return { items, mode: 'live', error: null, emptyLive: items.length === 0 };
  } catch (e) {
    return fixture(`hellgraph unreachable: ${e instanceof Error ? e.message : String(e)}`);
  }
}

/** The labelled fallback. Always stamped 'fixture', always carrying why. */
function fixture(error: string): NuggetFeedResult {
  const items: FeedItem[] = FIXTURE_NUGGETS.map((n) => parseNugget(n, n.id));
  // Carried on purpose: the fail-closed path should be visible in the fixture feed too.
  items.push(parseNugget(FIXTURE_MALFORMED, FIXTURE_MALFORMED.id));
  return { items, mode: 'fixture', error, emptyLive: false };
}

/** The fixture feed on its own, for tests and for the surface's explicit "show fixture" path. */
export function fixtureFeed(): NuggetFeedResult {
  return fixture('fixture requested explicitly');
}
