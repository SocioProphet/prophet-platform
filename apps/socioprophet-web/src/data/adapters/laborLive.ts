import { fetchT } from './http';
import { remotiveToRequests, type LaborRequest, type LiveRole } from '../laborMarketFixture';

// Real open roles from the Remotive public jobs API (remotive.com/api/remote-jobs) —
// no key, sends `access-control-allow-origin: *`. Each posting is a real labor request
// (a 'role'), mapped onto the LaborRequest contract. Fails closed (null) so the board
// falls back to the fixture. Category is optional; pass to narrow the feed.

interface RemotiveResponse { jobs?: LiveRole[] }

export async function fetchLaborLive(limit = 40, category?: string): Promise<LaborRequest[] | null> {
  try {
    const params = new URLSearchParams({ limit: String(limit) });
    if (category) params.set('category', category);
    const res = await fetchT(`https://remotive.com/api/remote-jobs?${params.toString()}`, { headers: { accept: 'application/json' } });
    if (!res.ok) return null;
    const j = (await res.json()) as RemotiveResponse;
    const jobs = (j.jobs ?? []).filter((r) => r && r.id != null && r.title && r.company_name && r.url);
    if (!jobs.length) return null;
    return remotiveToRequests(jobs.slice(0, limit));
  } catch {
    return null;
  }
}
