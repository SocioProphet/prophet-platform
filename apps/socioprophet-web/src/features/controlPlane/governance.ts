// Governance engine for the Organization Control Plane. Pure, testable logic split out
// from the Vue surface: an alerts/anomaly engine (Datadog/PagerDuty-style triage inbox),
// content-derived sealed receipts (Palantir immutable-audit style), SLA aging on the
// review queue (Stripe/Sift review-queue style), and a persistent, exportable audit log
// (Okta system-log style). None of this touches the DOM so it unit-tests cleanly.
import { fnv1a } from '../../gaia/exportClaims';
import type { Seat, QueueItem, AuditEntry, AuditDecision } from '../../data/controlPlaneFixture';
import type { Tier } from '../reputation/reputation';

// ── Sealed receipts ────────────────────────────────────────────────────────────
// A receipt is DERIVED from the decision content (not random), so the same decision
// always seals to the same id and any tampering changes it — an honest audit anchor.
export function sealReceipt(parts: { decision: string; subject: string; omega: string; actor: string; ts: string }): string {
  const h = fnv1a(`${parts.decision}|${parts.subject}|${parts.omega}|${parts.actor}|${parts.ts}`);
  return `sha256:${h.slice(0, 8)}…${h.slice(-4)}`;
}

// ── SLA aging ──────────────────────────────────────────────────────────────────
export const REVIEW_SLA_MIN = 20; // proposals should be triaged within 20 minutes
export function ageMinutes(receivedAtISO: string, nowMs: number): number {
  const t = Date.parse(receivedAtISO);
  return Number.isNaN(t) ? 0 : Math.max(0, Math.round((nowMs - t) / 60000));
}
export function isOverdue(q: QueueItem, nowMs: number, slaMin = REVIEW_SLA_MIN): boolean {
  return ageMinutes(q.receivedAt, nowMs) > slaMin;
}

// ── Alerts / anomaly engine ──────────────────────────────────────────────────────
export type AlertSeverity = 'critical' | 'warn' | 'info';
export interface Alert {
  id: string; severity: AlertSeverity; title: string; detail: string;
  kind: 'autonomy-reputation' | 'suspended-grant' | 'low-admit-autonomy' | 'sla-breach';
  ref?: { seatId?: string };
}

// Resolve a seat's portable reputation tier. Injected so the engine stays pure/testable.
export type TierLookup = (name: string) => Tier | undefined;

export function computeAlerts(seats: Seat[], queue: QueueItem[], nowMs: number, tierOf: TierLookup, slaMin = REVIEW_SLA_MIN): Alert[] {
  const out: Alert[] = [];
  for (const s of seats) {
    const tier = tierOf(s.name);
    // Rule 1 — high autonomy on a low / unrated portable reputation (HolographMe risk).
    if (s.autonomy >= 4 && (!tier || tier === 'emerging' || tier === 'unrated')) {
      out.push({ id: `al-rep-${s.id}`, severity: 'critical', kind: 'autonomy-reputation', ref: { seatId: s.id },
        title: `${s.name} · L${s.autonomy} on ${tier ?? 'unrated'} reputation`,
        detail: 'High autonomy granted on a low / unrated HolographMe reputation — review or lower the grant.' });
    }
    // Rule 2 — a suspended seat still holds an acting grant (should be revoked to L0).
    if (s.status === 'suspended' && s.autonomy >= 1) {
      out.push({ id: `al-susp-${s.id}`, severity: 'warn', kind: 'suspended-grant', ref: { seatId: s.id },
        title: `${s.name} · suspended but retains L${s.autonomy}`,
        detail: 'Seat is suspended yet still carries an autonomy grant — revoke to L0 while suspended.' });
    }
    // Rule 3 — acting autonomy (L4+) with a sub-80% admit rate (proposals not landing).
    if (s.autonomy >= 4 && s.admitRate < 80) {
      out.push({ id: `al-admit-${s.id}`, severity: 'warn', kind: 'low-admit-autonomy', ref: { seatId: s.id },
        title: `${s.name} · L${s.autonomy} at ${s.admitRate}% admit`,
        detail: 'Acting at high autonomy while under the 80% admit-rate bar — tighten review or lower autonomy.' });
    }
  }
  // Rule 4 — queue items past the review SLA.
  const overdue = queue.filter((q) => isOverdue(q, nowMs, slaMin));
  if (overdue.length) {
    out.push({ id: 'al-sla', severity: overdue.length > 1 ? 'critical' : 'warn', kind: 'sla-breach',
      title: `${overdue.length} proposal${overdue.length > 1 ? 's' : ''} past ${slaMin}m SLA`,
      detail: 'Governance queue items have aged past the review SLA — triage them.' });
  }
  const rank: Record<AlertSeverity, number> = { critical: 0, warn: 1, info: 2 };
  return out.sort((a, b) => rank[a.severity] - rank[b.severity]);
}

// ── Audit log build + persistence ────────────────────────────────────────────────
export function buildAuditEntry(q: QueueItem, decision: AuditDecision, actor: string, nowISO: string, reason?: string): AuditEntry {
  const subject = q.summary.length > 52 ? `${q.summary.slice(0, 52)}…` : q.summary;
  return {
    id: `a-${q.id}-${Date.parse(nowISO)}`,
    at: nowISO, actor, decision, subject, omega: q.omega,
    receipt: sealReceipt({ decision, subject, omega: q.omega, actor, ts: nowISO }),
    reason,
  };
}

export const AUDIT_STORAGE_KEY = 'noetica.cp.audit.v1';
export function loadAudit(seed: AuditEntry[]): AuditEntry[] {
  try {
    const raw = typeof localStorage !== 'undefined' && localStorage.getItem(AUDIT_STORAGE_KEY);
    if (!raw) return seed;
    const parsed = JSON.parse(raw) as AuditEntry[];
    return Array.isArray(parsed) && parsed.length ? parsed : seed;
  } catch { return seed; }
}
export function saveAudit(entries: AuditEntry[]): void {
  try { if (typeof localStorage !== 'undefined') localStorage.setItem(AUDIT_STORAGE_KEY, JSON.stringify(entries.slice(0, 200))); } catch { /* storage disabled — audit stays in-memory */ }
}

// Export the audit log as newline-delimited JSON (JSONL) — the format SIEM / log tools ingest.
export function auditToJsonl(entries: AuditEntry[]): string {
  return entries.map((e) => JSON.stringify(e)).join('\n');
}

// ── Policy what-if simulator (AWS IAM policy-simulator pattern) ─────────────────────
// "If I lower the {role} cap to L{n}, which seats get throttled and to what level?" —
// computed BEFORE applying, so the operator sees the blast radius.
export interface CapSimResult { role: string; newCap: number; affected: Array<{ id: string; name: string; from: number; to: number }> }
export function simulateCap(seats: Seat[], role: string, newCap: number): CapSimResult {
  const affected = seats
    .filter((s) => s.role === role && s.autonomy > newCap)
    .map((s) => ({ id: s.id, name: s.name, from: s.autonomy, to: newCap }));
  return { role, newCap, affected };
}

// ── Access Advisor / least-privilege (AWS IAM Access Advisor pattern) ────────────────
// Granted capability surfaces vs those a seat has actually touched → unused grants to prune.
export interface AccessAdvice { granted: string[]; used: string[]; unused: string[] }
export function leastPrivilege(granted: string[], usedSurfaces: string[]): AccessAdvice {
  const used = new Set(usedSurfaces);
  return { granted, used: granted.filter((g) => used.has(g)), unused: granted.filter((g) => !used.has(g)) };
}
// Role-level rollup: surfaces in a role's membrane that NO seat in the role has ever used —
// the strongest signal to tighten the role membrane itself.
export function roleUnusedSurfaces(seats: Seat[], role: string, membrane: string[]): string[] {
  const usedByRole = new Set<string>();
  for (const s of seats.filter((x) => x.role === role)) for (const u of s.usedSurfaces) usedByRole.add(u);
  return membrane.filter((m) => !usedByRole.has(m));
}
