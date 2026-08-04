// audit.ts — HIPAA-shaped audit controls (45 CFR §164.312(b)). An APPEND-ONLY trail of every access to
// the twin's records: who acted, what they did, on what, the outcome, and the receipt it produced.
// Successes AND blocks are recorded — a denied access is itself a security event worth keeping. The log
// is append-only by construction: there is NO exported way to mutate or delete a past entry, and the
// cap drops the OLDEST while counting what was dropped (never a silent loss of the count). Queryable for
// compliance review. In production this persists to tamper-evident storage; here it is an in-memory
// append-only ring. This is the audit CONTROL — a real HIPAA safeguard, distinct from full certification.
import { mintId } from './ids.js';

export type AuditOutcome = 'ok' | 'blocked';
export interface AuditEvent {
  id: string;
  at: string;
  actor: string;        // the acting identity (patient id, grant holder digest, 'operator', 'anonymous')
  action: string;       // e.g. 'doctor-view', 'patient-auth', 'vision', 'evidence-read'
  resource: string;     // what was accessed (e.g. 'twin', a grant id, 'population')
  outcome: AuditOutcome;
  reason?: string;      // why, for a block
  receipt?: string;     // the receipt id this access produced, tying the trail to the record layer
}

const LOG: AuditEvent[] = [];
const CAP = Math.max(100, Number(process.env.HEALTH_TWIN_AUDIT_MAX ?? 50_000));
let dropped = 0; // count of oldest entries evicted at the cap — reported, never silently lost

// Append an access to the trail. The ONLY mutator, and it only ever appends (+ bounded eviction).
export function audit(e: Omit<AuditEvent, 'id' | 'at'>): AuditEvent {
  const entry: AuditEvent = { id: mintId('audit'), at: new Date().toISOString(), ...e };
  LOG.push(entry);
  if (LOG.length > CAP) { LOG.shift(); dropped++; }
  return entry;
}

export interface AuditQuery { actor?: string; action?: string; outcome?: AuditOutcome; limit?: number }
// Read the trail for compliance review. Returns a COPY (callers cannot reach in and mutate the log).
export function auditQuery(q: AuditQuery = {}): { events: AuditEvent[]; total: number; droppedAtCap: number; cap: number } {
  let events = LOG;
  if (q.actor) events = events.filter((e) => e.actor === q.actor);
  if (q.action) events = events.filter((e) => e.action === q.action);
  if (q.outcome) events = events.filter((e) => e.outcome === q.outcome);
  const limit = Math.max(1, Math.min(1000, q.limit ?? 200));
  return {
    events: events.slice(-limit).reverse().map((e) => ({ ...e })), // newest first, defensive copy
    total: events.length, droppedAtCap: dropped, cap: CAP,
  };
}

export const auditSize = () => LOG.length;
