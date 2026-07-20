// Academy retrieval — the tutor's grounding backend, abstracted over BOTH offerings:
//   • cloud  → search-orchestrator (POST /v0/search/query), the deployed academy ingest over the
//              captured Commons chunks.
//   • local  → on-device Noetica (agent-machine :8080), which is building the same academy path —
//              so the cockpit tutor can ground against the user's LOCAL corpus too.
//   • fixture→ the in-app course transcripts (the guaranteed offline fallback).
//
// This is the "integrate both ways" seam: one tutor, either engine, same cited-passage contract.
// 'auto' tries cloud then local then falls back to fixture — always best-effort, never breaks.
import { resolveBase } from '../config/cockpitRuntime';

export type AcademySource = 'auto' | 'cloud' | 'local' | 'fixture';
export type PassageOrigin = 'cloud' | 'local' | 'fixture';

export interface TutorPassage {
  text: string;
  title: string;
  chunkRef: string;
  score: number;
  origin: PassageOrigin;
  uri?: string;
}
export interface RetrieveResult { passages: TutorPassage[]; origin: PassageOrigin }

const CLOUD = resolveBase('search', 'VITE_SEARCH_BASE', '/svc/search');
// On-device Noetica — the SAME base the cockpit already uses for the sovereign agent-machine.
const LOCAL = resolveBase('agentMachine', 'VITE_AGENT_MACHINE', 'http://127.0.0.1:8080');

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function isAcademy(r: any): boolean {
  return /academy|learning|course|lecture|ocw/i.test(String(r?.source ?? r?.entity_type ?? ''));
}

// Cloud: search-orchestrator fans academy records into /v0/search/query.
async function cloudRetrieve(query: string, limit: number): Promise<TutorPassage[]> {
  const body = { query_id: `tutor-${Date.now()}`, actor_id: 'cockpit-tutor', text: query, mode: 'academy', limit };
  const res = await fetch(`${CLOUD}/v0/search/query`, {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`search ${res.status}`);
  const d = (await res.json()) as { results?: unknown[] };
  return (d.results ?? [])
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .filter((r: any) => isAcademy(r))
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .map((r: any) => ({
      text: String(r.snippet ?? r.title ?? ''),
      title: String(r.title ?? 'Lecture'),
      chunkRef: String(r.path_or_uri ?? r.result_id ?? r.object_id ?? ''),
      score: Number(r.score?.final ?? 0),
      origin: 'cloud' as const,
      uri: typeof r.path_or_uri === 'string' && /^https?:/.test(r.path_or_uri) ? r.path_or_uri : undefined,
    }))
    .filter((p: TutorPassage) => p.text.length > 0);
}

// Local: on-device Noetica. Contract mirrors the cloud shape; when Noetica exposes its academy
// retrieval this lights up with the user's local corpus. Best-effort — fails closed.
async function localRetrieve(query: string, limit: number): Promise<TutorPassage[]> {
  const res = await fetch(`${LOCAL}/api/academy/retrieve`, {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ text: query, limit }),
  });
  if (!res.ok) throw new Error(`noetica ${res.status}`);
  const d = (await res.json()) as { passages?: unknown[] };
  return (d.passages ?? [])
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .map((p: any) => ({
      text: String(p.text ?? p.snippet ?? ''),
      title: String(p.title ?? 'Lecture'),
      chunkRef: String(p.chunkRef ?? p.ref ?? ''),
      score: Number(p.score ?? 0),
      origin: 'local' as const,
    }))
    .filter((p: TutorPassage) => p.text.length > 0);
}

export async function retrievePassages(query: string, source: AcademySource = 'auto', limit = 4): Promise<RetrieveResult> {
  const order: PassageOrigin[] = source === 'cloud' ? ['cloud']
    : source === 'local' ? ['local']
    : source === 'fixture' ? []
    : ['cloud', 'local'];
  for (const o of order) {
    try {
      const passages = o === 'cloud' ? await cloudRetrieve(query, limit) : await localRetrieve(query, limit);
      if (passages.length) return { passages: passages.sort((a, b) => b.score - a.score), origin: o };
    } catch { /* try the next provider, then fixture */ }
  }
  return { passages: [], origin: 'fixture' };
}

export const ORIGIN_META: Record<PassageOrigin, { glyph: string; label: string }> = {
  cloud: { glyph: '☁', label: 'cloud · academy ingest' },
  local: { glyph: '⌂', label: 'local · on-device Noetica' },
  fixture: { glyph: '○', label: 'commons · captured transcript' },
};
