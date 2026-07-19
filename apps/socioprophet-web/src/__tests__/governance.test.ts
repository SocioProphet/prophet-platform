import { describe, it, expect } from 'vitest';
import { SEATS, QUEUE, AUDIT, type Seat, type QueueItem } from '../data/controlPlaneFixture';
import { reputationFor } from '../features/reputation/reputation';
import { computeAlerts, isOverdue, ageMinutes, sealReceipt, buildAuditEntry, auditToJsonl, REVIEW_SLA_MIN, simulateCap, leastPrivilege, roleUnusedSurfaces } from '../features/controlPlane/governance';
import { ROLE_POLICY } from '../data/controlPlaneFixture';

const tierOf = (name: string) => reputationFor(name)?.tier;
const NOW = Date.now();

describe('sealed receipts', () => {
  it('are content-derived and deterministic (tamper-evident)', () => {
    const p = { decision: 'admitted', subject: 'ACS income · Tract 44', omega: 'TRUSTED', actor: 'you', ts: '2026-07-09T12:00:00Z' };
    expect(sealReceipt(p)).toBe(sealReceipt({ ...p }));
    expect(sealReceipt(p)).not.toBe(sealReceipt({ ...p, decision: 'rejected' }));
    expect(sealReceipt(p)).toMatch(/^sha256:[0-9a-f]{8}…[0-9a-f]{4}$/);
  });
});

describe('SLA aging', () => {
  it('flags queue items past the review SLA', () => {
    const fresh: QueueItem = { ...QUEUE[0], receivedAt: new Date(NOW - 5 * 60000).toISOString() };
    const stale: QueueItem = { ...QUEUE[0], receivedAt: new Date(NOW - (REVIEW_SLA_MIN + 10) * 60000).toISOString() };
    expect(isOverdue(fresh, NOW)).toBe(false);
    expect(isOverdue(stale, NOW)).toBe(true);
    expect(ageMinutes(stale.receivedAt, NOW)).toBe(REVIEW_SLA_MIN + 10);
  });
});

describe('alerts / anomaly engine', () => {
  it('raises the autonomy>reputation risk for a high-autonomy seat on emerging reputation', () => {
    const alerts = computeAlerts(SEATS, QUEUE, NOW, tierOf);
    const rep = alerts.find((a) => a.kind === 'autonomy-reputation');
    expect(rep).toBeDefined();
    // 'the skeptic' is L5 on an emerging reputation — the canonical demo case.
    expect(alerts.some((a) => a.kind === 'autonomy-reputation' && a.title.includes('the skeptic'))).toBe(true);
  });

  it('flags a suspended seat that still holds an acting grant', () => {
    const suspended: Seat[] = [{ ...SEATS[0], id: 'sx', name: 'Test', status: 'suspended', autonomy: 3 }];
    const alerts = computeAlerts(suspended, [], NOW, () => 'trusted');
    expect(alerts.some((a) => a.kind === 'suspended-grant')).toBe(true);
  });

  it('flags high autonomy with a sub-80% admit rate', () => {
    const seat: Seat[] = [{ ...SEATS[0], id: 'sy', name: 'Test', status: 'active', autonomy: 4, admitRate: 72 }];
    const alerts = computeAlerts(seat, [], NOW, () => 'trusted');
    expect(alerts.some((a) => a.kind === 'low-admit-autonomy')).toBe(true);
  });

  it('raises a single SLA-breach alert when queue items age out, sorted critical-first', () => {
    const stale = QUEUE.map((q) => ({ ...q, receivedAt: new Date(NOW - 60 * 60000).toISOString() }));
    const alerts = computeAlerts([], stale, NOW, () => 'trusted');
    const sla = alerts.filter((a) => a.kind === 'sla-breach');
    expect(sla).toHaveLength(1);
    expect(alerts[0].severity).toBe('critical');
  });

  it('is quiet when everything is healthy', () => {
    const healthy: Seat[] = [{ ...SEATS[0], id: 'sz', name: 'Ok', status: 'active', autonomy: 2, admitRate: 95 }];
    expect(computeAlerts(healthy, [], NOW, () => 'trusted')).toHaveLength(0);
  });
});

describe('audit log build + export', () => {
  it('builds an entry with a sealed receipt and optional reason', () => {
    const e = buildAuditEntry(QUEUE[3], 'rejected', 'you', new Date(NOW).toISOString(), 'low-confidence');
    expect(e.decision).toBe('rejected');
    expect(e.reason).toBe('low-confidence');
    expect(e.receipt).toMatch(/^sha256:/);
  });

  it('exports the trail as valid JSONL (one JSON object per line)', () => {
    const jsonl = auditToJsonl(AUDIT);
    const lines = jsonl.split('\n');
    expect(lines).toHaveLength(AUDIT.length);
    expect(() => lines.forEach((l) => JSON.parse(l))).not.toThrow();
  });
});

describe('policy what-if simulator', () => {
  it('reports which seats a lowered cap would throttle, and to what level', () => {
    // Trader cap is L4; Grace sits at L4. Lower to L2 → Grace throttled L4→L2.
    const r = simulateCap(SEATS, 'Trader', 2);
    expect(r.affected).toHaveLength(1);
    expect(r.affected[0].name).toBe('Grace');
    expect(r.affected[0].from).toBe(4);
    expect(r.affected[0].to).toBe(2);
  });
  it('reports no blast radius when seats are already under the proposed cap', () => {
    expect(simulateCap(SEATS, 'Compliance', 3).affected).toHaveLength(0); // B. Berners at L2 ≤ 3
  });
});

describe('access advisor / least-privilege', () => {
  it('splits granted surfaces into used vs unused for a seat', () => {
    const analyst = ROLE_POLICY.find((p) => p.role === 'Analyst')!;
    const ada = SEATS.find((s) => s.name === 'Ada L.')!;
    const a = leastPrivilege(analyst.membrane, ada.usedSurfaces);
    expect(a.unused).toContain('news');       // granted, never used
    expect(a.used).toContain('map');           // granted + used
    expect(a.used).not.toContain('news');
  });
  it('flags role-membrane surfaces no seat in the role has ever used', () => {
    const intern = ROLE_POLICY.find((p) => p.role === 'Intern')!;
    // The only Intern (suspended) used nothing → the whole membrane is role-unused.
    expect(roleUnusedSurfaces(SEATS, 'Intern', intern.membrane)).toEqual(intern.membrane);
  });
});
