import { describe, it, expect, vi, afterEach } from 'vitest';
import { runsToAudit, runsToQueue, decisionsToAudit, governanceAlerts, buildLeastPrivilegePolicy, fetchLiveGovernance } from '../data/adapters/controlPlaneLive';
import type { GovRun, GovPosture, Containment, AutonomyState } from '../services/agentMachineApi';

const RUNS: GovRun[] = [
  { run_id: 'e7e402ea-2dfe-47f8', model_routed: 'qwen2.5:7b', provider: 'ollama', policy_admitted: true, memory_written: true, timestamp: '2026-07-06T23:27:38.082Z', latency_ms: 278972, input_tokens: 1464, output_tokens: 33, cost_usd: 0, tokens_egressed: 0, task: 'general', session_id: 's1' },
  { run_id: 'ab12cd34-0000-1111', model_routed: 'llama3.2:3b', provider: 'ollama', policy_admitted: false, memory_written: false, timestamp: '2026-07-06T22:00:00.000Z', latency_ms: 1200, input_tokens: 40, output_tokens: 5, cost_usd: 0, tokens_egressed: 128, task: 'chat', session_id: 's1' },
];

const POSTURE: GovPosture = {
  killSwitchArmed: false, killSwitchReason: null, scopedConfigured: false, policyId: null, policyName: null,
  authorityHierarchy: [{ level: 'root', label: 'Kill-switch', description: '', active: false }, { level: 'developer', label: 'Capability gate', description: '', active: true }],
  escalationActionClasses: ['destructive_action'],
};
const CONT_FULL: Containment = { killed: false, reason: null, since: null, purpose: 'full', purpose_allows: ['net', 'fs-read', 'fs-write', 'exec', 'tool', 'model', 'memory-write'], purposes: [] };

afterEach(() => vi.restoreAllMocks());

describe('runs → audit trail', () => {
  it('maps only policy-admitted runs into the audit, with a real run receipt', () => {
    const a = runsToAudit(RUNS);
    expect(a).toHaveLength(1); // the held run is NOT in the audit — it goes to the queue
    expect(a[0].decision).toBe('admitted');
    expect(a[0].receipt).toBe('run:e7e402ea');
    expect(a[0].actor).toBe('ollama/qwen2.5:7b');
    expect(a[0].omega).toBe('TRUSTED');          // admitted + memory-written = strongest rung
  });
});

describe('held runs → review queue', () => {
  it('routes only NON-admitted runs into the queue (honest empty when policy admits all)', () => {
    const q = runsToQueue(RUNS);
    expect(q).toHaveLength(1);
    expect(q[0].id).toBe('ab12cd34-0000-1111'); // run_id becomes the queue id for decision writeback
    expect(q[0].policy).toBe('review');
    expect(q[0].summary).toContain('128 egressed');
    expect(runsToQueue(RUNS.filter((r) => r.policy_admitted))).toHaveLength(0);
  });
});

describe('malformed records degrade gracefully (no whole-view crash)', () => {
  it('skips a run/decision missing run_id instead of throwing', () => {
    const bad = [{ ...RUNS[0], run_id: undefined as unknown as string }, RUNS[1]];
    expect(() => runsToAudit(bad)).not.toThrow();
    expect(() => runsToQueue(bad)).not.toThrow();
    expect(runsToAudit(bad)).toHaveLength(0);  // RUNS[0] (admitted) had its id stripped → skipped
    expect(runsToQueue(bad)).toHaveLength(1);  // RUNS[1] (held) still maps
    expect(() => decisionsToAudit([{ decision_id: 'd', run_id: undefined as unknown as string, decision: 'admitted', actor: 'x', timestamp: 't', receipt: 'r' }])).not.toThrow();
  });
});

describe('human decisions → audit trail', () => {
  it('maps recorded operator decisions with their sealed receipt', () => {
    const a = decisionsToAudit([{ decision_id: 'd1', run_id: 'ab12cd34ffff', decision: 'rejected', reason: 'unsourced', actor: 'operator', timestamp: '2026-07-09T12:00:00Z', receipt: 'sha256:decision:ab' }]);
    expect(a[0].decision).toBe('rejected');
    expect(a[0].actor).toBe('operator');
    expect(a[0].receipt).toBe('sha256:decision:ab');
    expect(a[0].reason).toBe('unsourced');
  });
});

describe('posture/containment → governance alerts', () => {
  it('raises a critical alert when the kill-switch is armed', () => {
    const alerts = governanceAlerts({ ...POSTURE, killSwitchArmed: true, killSwitchReason: 'manual halt' }, { ...CONT_FULL, killed: true, reason: 'manual halt' });
    expect(alerts[0].severity).toBe('critical');
    expect(alerts[0].title).toContain('Kill-switch');
  });
  it('warns on a broad "full" purpose grant and notes unscoped egress', () => {
    const alerts = governanceAlerts(POSTURE, CONT_FULL);
    expect(alerts.some((a) => a.title.includes('full'))).toBe(true);
    expect(alerts.some((a) => a.title.includes('SCOPE-D'))).toBe(true);
    expect(alerts.some((a) => a.severity === 'critical')).toBe(false); // nothing armed
  });
});

describe('least-privilege egress policy', () => {
  it('authorizes NO cloud targets (everything stays local — sovereign default)', () => {
    const p = buildLeastPrivilegePolicy();
    expect(p.policyId).toBeTruthy();
    expect(p.name).toBeTruthy();          // policyId + name are the machine's required fields
    expect(p.authorizedTargets).toEqual([]);
    expect(p.targetBoundary?.outOfScopeTargets).toContain('public-internet');
  });
  it('gates every escalation action class to a human approver', () => {
    const gated = new Set(buildLeastPrivilegePolicy().approvalRules?.map((r) => r.actionClass));
    for (const cls of ['network_call', 'credential_access', 'destructive_action', 'deployment', 'identity_write']) expect(gated.has(cls)).toBe(true);
    expect(buildLeastPrivilegePolicy().approvalRules?.every((r) => r.requiredGate === 'human')).toBe(true);
  });
});

describe('fetchLiveGovernance', () => {
  const AUT: AutonomyState = { session: { role: 'operator', authorizedLevel: 'L1', evidence: ['manual-bind'] }, enforced: true, ladder: [] };
  it('assembles live governance from the agent-machine endpoints', async () => {
    const routes: Record<string, unknown> = {
      '/api/governance/posture': POSTURE, '/api/autonomy': AUT, '/api/containment': CONT_FULL, '/api/governance/recent': { runs: RUNS },
    };
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      const path = new URL(url, 'http://x').pathname;
      return Promise.resolve({ ok: true, json: () => Promise.resolve(routes[path]) });
    }));
    const g = await fetchLiveGovernance();
    expect(g).not.toBeNull();
    expect(g!.audit).toHaveLength(1);  // 1 admitted run (held run routes to the queue)
    expect(g!.queue).toHaveLength(1);  // 1 held run
    expect(g!.autonomy.session.authorizedLevel).toBe('L1');
    expect(g!.alerts.length).toBeGreaterThan(0);
  });
  it('fails closed to null when the agent-machine is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('ECONNREFUSED')));
    expect(await fetchLiveGovernance()).toBeNull();
  });
});
