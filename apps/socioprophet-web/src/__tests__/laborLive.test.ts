import { describe, it, expect, vi, afterEach } from 'vitest';
import { remotiveToRequests, type LiveRole } from '../data/laborMarketFixture';
import { fetchLaborLive } from '../data/adapters/laborLive';

const ROLES: LiveRole[] = [
  { id: 2091045, title: 'Tier III Service Desk Engineer', company_name: 'Unio Digital', category: 'Information Technology', tags: ['azure', 'cisco', 'security', 'video', 'x', 'y', 'z'], job_type: 'full_time', publication_date: '2026-07-07T09:04:10', candidate_required_location: 'USA', salary: '', url: 'https://remotive.com/remote-jobs/it/tier-iii-209' },
  { id: 2091046, title: 'Staff Data Engineer', company_name: 'Northwind', category: 'Software Development', tags: ['python'], job_type: 'contract', publication_date: '2026-07-06T00:00:00', candidate_required_location: '', salary: '$150,000 - $190,000', url: 'https://remotive.com/remote-jobs/sw/staff-de-210' },
];

afterEach(() => vi.restoreAllMocks());

describe('remotive → LaborRequest mapping', () => {
  it('maps a real posting to a role request with real provenance', () => {
    const rs = remotiveToRequests(ROLES);
    expect(rs[0].id).toBe('live-2091045');
    expect(rs[0].requestType).toBe('role');
    expect(rs[0].requester).toBe('Unio Digital');
    expect(rs[0].objective).toBe('Tier III Service Desk Engineer');
    expect(rs[0].status).toBe('open');
    expect(rs[0].live?.source).toBe('Remotive');
    expect(rs[0].live?.url).toBe('https://remotive.com/remote-jobs/it/tier-iii-209');
  });

  it('is honest about pay: undisclosed when empty, verbatim note when posted', () => {
    const rs = remotiveToRequests(ROLES);
    expect(rs[0].compensation.transparency).toBe('undisclosed');
    expect(rs[1].compensation.transparency).toBe('disclosed');
    expect(rs[1].compensation.note).toBe('$150,000 - $190,000');
  });

  it('caps evaluation criteria (skill tags) and defaults location to Remote', () => {
    const rs = remotiveToRequests(ROLES);
    expect(rs[0].evaluationCriteria).toHaveLength(6);
    expect(rs[1].outcome).toContain('Remote');
    expect(rs[1].schedule).toContain('contract');
  });
});

describe('fetchLaborLive', () => {
  it('returns mapped requests on a healthy response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ jobs: ROLES }) }));
    const rs = await fetchLaborLive();
    expect(rs).toHaveLength(2);
    expect(rs![0].requester).toBe('Unio Digital');
  });

  it('fails closed to null on error or empty feed', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ jobs: [] }) }));
    expect(await fetchLaborLive()).toBeNull();
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network')));
    expect(await fetchLaborLive()).toBeNull();
  });
});
