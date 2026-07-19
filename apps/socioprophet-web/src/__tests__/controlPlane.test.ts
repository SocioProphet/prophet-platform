import { describe, it, expect } from 'vitest';
import { SEATS, QUEUE, ROLE_POLICY, AUDIT, AUTONOMY_LEVELS } from '../data/controlPlaneFixture';
import { notationOf } from '../ontology/ontogenesis';
import { reputationFor } from '../features/reputation/reputation';

describe('organization control plane', () => {
  it('defines the full L0–L5 autonomy ladder', () => {
    expect(AUTONOMY_LEVELS.map((l) => l.level)).toEqual([0, 1, 2, 3, 4, 5]);
  });

  it('GOVERNANCE INVARIANT: no fielded seat exceeds its role autonomy cap', () => {
    const capOf = (role: string) => ROLE_POLICY.find((p) => p.role === role)?.autonomyCap ?? 5;
    for (const s of SEATS) expect(s.autonomy).toBeLessThanOrEqual(capOf(s.role));
  });

  it('every seat has a role with a defined policy (autonomy cap + membrane)', () => {
    for (const s of SEATS) {
      const p = ROLE_POLICY.find((x) => x.role === s.role);
      expect(p, `role policy for ${s.role}`).toBeDefined();
      expect(p!.membrane.length).toBeGreaterThan(0);
    }
  });

  it('queue items reference a real seat and carry a governed policy + Ω grade', () => {
    for (const q of QUEUE) {
      expect(SEATS.some((s) => s.id === q.seatId)).toBe(true);
      expect(['proposed', 'provisional', 'review']).toContain(q.policy);
      expect(notationOf(q.omega)).toBeGreaterThanOrEqual(0); // valid Ω rung
    }
  });

  it('audit decisions are from the governed decision set', () => {
    for (const a of AUDIT) expect(['admitted', 'rejected', 'held-for-review', 'executed']).toContain(a.decision);
  });

  it('fielded seats carry a HolographMe reputation (except the unrated intern)', () => {
    const rated = SEATS.filter((s) => s.role !== 'Intern');
    for (const s of rated) expect(reputationFor(s.name), `reputation for ${s.name}`).toBeDefined();
  });

  it('surfaces the autonomy>reputation risk: a high-autonomy seat on a low reputation is flagged', () => {
    const risky = SEATS.filter((s) => { const r = reputationFor(s.name); return s.autonomy >= 4 && (!r || r.tier === 'emerging' || r.tier === 'unrated'); });
    expect(risky.length).toBeGreaterThan(0); // 'the skeptic' at L5 (emerging) is the demo case
    expect(risky.some((s) => s.name === 'the skeptic')).toBe(true);
  });
});
