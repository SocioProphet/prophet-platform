// Agora — the work + knowledge plane (sovereign Jira/Confluence). Reads the deployed agora service
// (apps/agora, :8080) via nginx /svc/agora. Every board card + wiki page is a proof-carrying
// HellGraph fact in the project collection, so it's citable/preservable via Studio's commons — no
// export. Reads are open; writes require the agora-write-token (Bearer).
import { resolveBase } from '../config/cockpitRuntime';

const BASE = resolveBase('agora', 'VITE_AGORA_BASE', '/svc/agora');

export const WORK_STATUSES = ['backlog', 'todo', 'in_progress', 'in_review', 'done', 'cancelled'] as const;
export const WORK_TYPES = ['task', 'epic', 'story', 'bug', 'spike', 'milestone'] as const;
export type WorkStatus = typeof WORK_STATUSES[number];
export type WorkType = typeof WORK_TYPES[number];

export interface WorkItem {
  work_id: string; title: string; type: string; status: string;
  priority?: string | null; assignee?: string | null; team?: string | null;
  sprint?: string | null; epic?: string | null; tags: string[]; updated_at?: string; epistemic_mode: string;
}
export interface AgoraPage { page_id: string; title: string; parent?: string | null; updated_at?: string }
export interface AgoraTeam { team_id: string; name: string; members: string[] }
export interface AgoraBundle {
  project: string; collection: string;
  board: { columns: Record<string, WorkItem[]>; count: number };
  pages: AgoraPage[]; teams: AgoraTeam[];
  stats: { work_items: number; pages: number; teams: number };
  commons: { citable: boolean; preservable: boolean; curatable: boolean; note: string };
  degraded?: string | null;
}

export async function loadAgora(project = 'default'): Promise<AgoraBundle> {
  const res = await fetch(`${BASE}/api/agora?project=${encodeURIComponent(project)}`, { headers: { accept: 'application/json' } });
  if (!res.ok) throw new Error(`agora unreachable (${res.status})`);
  return (await res.json()) as AgoraBundle;
}

export interface NewWork { project?: string; title: string; type?: string; status?: string; priority?: string; assignee?: string; team?: string; tags?: string[]; actor?: string }
export async function createWork(input: NewWork, token: string): Promise<{ work_id: string; title: string; status: string; proof_carrying: boolean }> {
  const res = await fetch(`${BASE}/api/agora/work`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', authorization: `Bearer ${token}` },
    body: JSON.stringify({ project: 'default', ...input }),
  });
  if (res.status === 401 || res.status === 403) throw new Error('write token required / rejected');
  if (!res.ok) throw new Error(`create failed (${res.status})`);
  return await res.json();
}
