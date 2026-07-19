// Live governance adapter — binds the Organization Control Plane to the REAL sovereign
// Agent Machine (Noetica) running on :8080. Read-only: it consumes the agent-machine's
// already-live /api/governance, /api/autonomy and /api/containment endpoints and maps
// them onto the Control Plane's shapes. Fails closed (null) so the surface falls back to
// the fixture demo when the agent-machine isn't running. This is what makes the plane
// real rather than a paper tiger: the audit trail below is the machine's actual
// policy-admitted reasoning runs, the ladder is enforced, the membrane is its live purpose.
import { govPosture, autonomyState, containment, govRecent, govDecisions, type GovPosture, type AutonomyState, type Containment, type GovRun, type GovDecisionRecord, type EngagementPolicy } from '../../services/agentMachineApi';
import type { AuditEntry, QueueItem, QueueKind } from '../controlPlaneFixture';
import type { OmegaState } from '../../ontology/ontogenesis';
import type { Alert } from '../../features/controlPlane/governance';

export interface LiveGovernance {
  posture: GovPosture;
  autonomy: AutonomyState;
  containment: Containment;
  runs: GovRun[];
  audit: AuditEntry[];   // decided (policy-admitted) runs + human decisions, mapped to audit rows
  queue: QueueItem[];    // HELD runs (policy_admitted === false) awaiting human review
  alerts: Alert[];       // posture/containment-derived alerts
}

// A policy-admitted, memory-written run is the machine's strongest evidence rung; an
// admitted-but-not-persisted run is actionable; a held run sits lower. Derived, labelled.
function omegaOfRun(r: GovRun): OmegaState {
  if (!r.policy_admitted) return 'LINKED';
  return r.memory_written ? 'TRUSTED' : 'ACTIONABLE';
}

const subjectOfRun = (r: GovRun) => `${r.task ?? 'run'} · ${r.output_tokens ?? 0} tok · ${r.tokens_egressed ?? 0} egressed`;

// Decided (policy-admitted) runs → audit rows. Held runs go to the queue instead.
// Guard run_id: one malformed record must degrade to skipping that row, not throw and drop
// the entire live view to fixture (.slice on a missing id would).
export function runsToAudit(runs: GovRun[]): AuditEntry[] {
  return runs.filter((r) => r.policy_admitted && typeof r.run_id === 'string' && r.run_id).map((r) => ({
    id: `run-${r.run_id}`,
    at: r.timestamp,
    actor: `${r.provider}/${r.model_routed}`,
    decision: 'admitted',
    subject: subjectOfRun(r),
    omega: omegaOfRun(r),
    receipt: `run:${r.run_id.slice(0, 8)}`,
  }));
}

// HELD runs (the policy did NOT auto-admit) → the human review queue. When the machine's
// policy admits everything, this is correctly empty (an honest 'queue clear').
export function runsToQueue(runs: GovRun[]): QueueItem[] {
  return runs.filter((r) => !r.policy_admitted && typeof r.run_id === 'string' && r.run_id).map((r) => ({
    id: r.run_id,
    kind: (r.task === 'canon' ? 'canon-edit' : 'action') as QueueKind,
    summary: `${r.task ?? 'run'} · ${r.model_routed} held by policy (${r.output_tokens ?? 0} tok, ${r.tokens_egressed ?? 0} egressed)`,
    subject: `agent-machine · ${r.provider}`,
    policy: 'review',
    omega: omegaOfRun(r),
    confidence: r.error ? 0.4 : 0.7,
    seatId: r.session_id ?? 'session',
    at: r.timestamp,
    receivedAt: r.timestamp,
  }));
}

// Human decisions recorded on the machine → audit rows (so operator Admit/Reject persists).
export function decisionsToAudit(decisions: GovDecisionRecord[]): AuditEntry[] {
  return decisions.filter((d) => typeof d.decision_id === 'string' && typeof d.run_id === 'string' && d.run_id).map((d) => ({
    id: `dec-${d.decision_id}`,
    at: d.timestamp,
    actor: d.actor,
    decision: d.decision,
    subject: `run ${d.run_id.slice(0, 8)}`,
    omega: 'LINKED' as OmegaState,
    receipt: d.receipt,
    reason: d.reason,
  }));
}

// Posture + containment → governance alerts (the real machine's risk surface).
export function governanceAlerts(posture: GovPosture, cont: Containment): Alert[] {
  const out: Alert[] = [];
  if (posture.killSwitchArmed || cont.killed) {
    out.push({ id: 'am-kill', severity: 'critical', kind: 'suspended-grant',
      title: 'Kill-switch ARMED — agent halted', detail: cont.reason || posture.killSwitchReason || 'The containment kill-switch is armed; the agent cannot act until disarmed.' });
  }
  if (cont.purpose === 'full') {
    out.push({ id: 'am-purpose', severity: 'warn', kind: 'low-admit-autonomy',
      title: `Purpose bound to “full” — all ${cont.purpose_allows.length} capabilities allowed`,
      detail: 'The agent runs with the broadest capability grant (net, exec, fs-write…). Narrow the purpose to least-privilege for routine work.' });
  }
  if (!posture.scopedConfigured) {
    out.push({ id: 'am-scoped', severity: 'info', kind: 'low-admit-autonomy',
      title: 'SCOPE-D egress policy not configured', detail: 'No EngagementPolicy governs egress routing — cloud calls are ungoverned until a scoped policy is bound.' });
  }
  const rank = { critical: 0, warn: 1, info: 2 } as const;
  return out.sort((a, b) => rank[a.severity] - rank[b.severity]);
}

// A sovereign-default SCOPE-D EngagementPolicy the console can bind when egress is ungoverned:
// NO cloud targets authorized (every non-local route stays on-device — maximal sovereignty), and
// every escalation action class gated to a human approver. Grounded in the lib/scope-d.ts schema.
export function buildLeastPrivilegePolicy(): EngagementPolicy {
  return {
    policyId: 'cockpit-least-privilege',
    name: 'Cockpit least-privilege egress',
    targetBoundary: { authorizedTargets: [], outOfScopeTargets: ['third-party-services', 'public-internet'] },
    authorizedTargets: [],
    authorizedModes: ['local'],
    approvalRules: [
      { actionClass: 'network_call', requiredGate: 'human' },
      { actionClass: 'credential_access', requiredGate: 'human' },
      { actionClass: 'destructive_action', requiredGate: 'human' },
      { actionClass: 'deployment', requiredGate: 'human' },
      { actionClass: 'identity_write', requiredGate: 'human' },
    ],
    blockedActions: [],
  };
}

export async function fetchLiveGovernance(): Promise<LiveGovernance | null> {
  try {
    const [posture, autonomy, cont, recent] = await Promise.all([govPosture(), autonomyState(), containment(), govRecent()]);
    if (!posture || !autonomy) return null;
    const runs = recent?.runs ?? [];
    // Human decisions are best-effort — the endpoint may not exist on an older machine.
    let decisions: GovDecisionRecord[] = [];
    try { decisions = (await govDecisions())?.decisions ?? []; } catch { /* endpoint absent → runs-only audit */ }
    const audit = [...decisionsToAudit(decisions), ...runsToAudit(runs)];
    return { posture, autonomy, containment: cont, runs, audit, queue: runsToQueue(runs), alerts: governanceAlerts(posture, cont) };
  } catch {
    return null; // agent-machine not running / unreachable → fall back to fixture
  }
}
