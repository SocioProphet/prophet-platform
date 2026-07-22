// Grant scoping — the consent membrane between the twin and an authorized clinician. The doctor
// chart must render EXACTLY what the patient's grant covers: a structured scope (which body
// systems, which record kinds, how far back), not a free-text label. applyScope() filters the
// full bundle down to the granted slice and reports WITHHELD COUNTS — never content — so the
// doctor can see that more history exists (and request it) without seeing it. Every successful
// read is a receipt; every failure is an explicit block with a reason. This is the doctrine
// ("every access is a receipt or a block") applied to the clinician surface, where the subject
// stays IDENTIFIED (the doctor is authorized) — unlike deident.ts, which strips identity for
// blinded reviewers. Two different membranes for two different trust relationships.
import type { Grant } from './data.js';

export type RecordKind =
  | 'observations' | 'conditions' | 'encounters' | 'imaging'
  | 'medications' | 'allergies' | 'immunizations' | 'readings';

export interface GrantScope {
  systems: string[] | 'all';   // body-system ids the grant covers
  kinds: RecordKind[] | 'all'; // record kinds the grant covers
  lookbackDays: number | null; // how far back; null = full history
}

// Named presets a patient picks when granting access. 'cardiometabolic' matches the wedge:
// heart + metabolic (hepatic carries lipid/glucose panels) + renal.
export const SCOPE_PRESETS: Record<string, GrantScope> = {
  'full-history':    { systems: 'all', kinds: 'all', lookbackDays: null },
  'cardiometabolic': { systems: ['cardiovascular', 'hepatic', 'urinary'], kinds: 'all', lookbackDays: null },
  'meds-allergies':  { systems: 'all', kinds: ['medications', 'allergies'], lookbackDays: null },
  'recent-90d':      { systems: 'all', kinds: 'all', lookbackDays: 90 },
};

export function resolveScope(preset?: string, spec?: Partial<GrantScope>): GrantScope {
  const base = SCOPE_PRESETS[preset ?? ''] ?? SCOPE_PRESETS['full-history'];
  return { ...base, ...(spec ?? {}) };
}

// A grant either opens (ok) or blocks with a stated reason — never a silent partial.
export function resolveGrant(grants: Grant[], id: string):
  | { ok: true; grant: Grant }
  | { ok: false; reason: string } {
  const g = grants.find((x) => x.id === id);
  if (!g) return { ok: false, reason: 'grant not found' };
  if (g.revoked) return { ok: false, reason: 'grant revoked — read denied' };
  if (new Date(g.expires_at) <= new Date()) return { ok: false, reason: 'grant expired — read denied' };
  return { ok: true, grant: g };
}

export const KINDS: RecordKind[] = ['observations', 'conditions', 'encounters', 'imaging', 'medications', 'allergies', 'immunizations', 'readings'];
const inKinds = (scope: GrantScope, k: RecordKind) => scope.kinds === 'all' || scope.kinds.includes(k);
const inSystems = (scope: GrantScope, sys?: string) => scope.systems === 'all' || (sys != null && scope.systems.includes(sys));

// Each record kind dates differently; conditions use onset, meds use started, the rest are as named.
const recordDate = (k: RecordKind, r: any): string | undefined =>
  k === 'conditions' ? r.onset : k === 'medications' ? r.started : (r.effective ?? r.date);

// Clinical-safety floor: a time-boxed grant must never hide what could kill the patient in the
// room. Allergies (if the kind is granted) and ACTIVE conditions ignore lookbackDays.
const safetyFloor = (k: RecordKind, r: any) =>
  k === 'allergies' || (k === 'conditions' && r.clinicalStatus === 'active');

function inWindow(scope: GrantScope, k: RecordKind, r: any): boolean {
  if (scope.lookbackDays == null || safetyFloor(k, r)) return true;
  const d = recordDate(k, r);
  if (!d) return true; // undated records pass — withholding on a missing date hides silently
  return new Date(d).getTime() >= Date.now() - scope.lookbackDays * 86_400_000;
}

// keep = kind granted AND (record's system in scope, where the record has one) AND inside the window
const keeps = (scope: GrantScope, k: RecordKind, sys: string | undefined, r: any) =>
  inKinds(scope, k) && (sys == null || inSystems(scope, sys)) && inWindow(scope, k, r);

export type WithheldCounts = Partial<Record<RecordKind, number>> & { total: number };

// Filter the full bundle() output down to the granted slice. Subject stays identified; grants
// (the patient's control panel), ingest internals, and captured media are NOT in the clinician
// view. Withheld = per-kind count deltas (full − kept) — counts leave, content never does.
export function applyScope(full: any, scope: GrantScope): { view: any; withheld: WithheldCounts } {
  const systems = (full.systems ?? [])
    .filter((s: any) => inSystems(scope, s.id))
    .map((s: any) => ({
      ...s,
      observations: (s.observations ?? []).filter((r: any) => keeps(scope, 'observations', s.id, r)),
      conditions: (s.conditions ?? []).filter((r: any) => keeps(scope, 'conditions', s.id, r)),
      encounters: (s.encounters ?? []).filter((r: any) => keeps(scope, 'encounters', s.id, r)),
      imaging: (s.imaging ?? []).filter((r: any) => keeps(scope, 'imaging', s.id, r)),
      medications: (s.medications ?? []).filter((r: any) => keeps(scope, 'medications', s.id, r)),
    }));

  const medications = (full.medications ?? []).filter((r: any) => keeps(scope, 'medications', r.system, r));
  const allergies = (full.allergies ?? []).filter((r: any) => keeps(scope, 'allergies', undefined, r));
  const immunizations = (full.immunizations ?? []).filter((r: any) => keeps(scope, 'immunizations', undefined, r));
  const readings = (full.readings ?? []).filter((r: any) => keeps(scope, 'readings', r.system, r));
  const timeline = systems.flatMap((s: any) => s.encounters).sort((a: any, b: any) => (a.date < b.date ? 1 : -1));

  const sum = (k: string) => (full.systems ?? []).reduce((n: number, s: any) => n + ((s[k] ?? []).length), 0);
  const kept = {
    observations: systems.reduce((n: number, s: any) => n + s.observations.length, 0),
    conditions: systems.reduce((n: number, s: any) => n + s.conditions.length, 0),
    encounters: timeline.length,
    imaging: systems.reduce((n: number, s: any) => n + s.imaging.length, 0),
    medications: medications.length, allergies: allergies.length,
    immunizations: immunizations.length, readings: readings.length,
  };
  const fullCounts: Record<RecordKind, number> = {
    observations: sum('observations'), conditions: sum('conditions'), encounters: sum('encounters'),
    imaging: sum('imaging'), medications: (full.medications ?? []).length,
    allergies: (full.allergies ?? []).length, immunizations: (full.immunizations ?? []).length,
    readings: (full.readings ?? []).length,
  };
  const withheld: WithheldCounts = { total: 0 };
  for (const k of KINDS) {
    const w = fullCounts[k] - (kept as any)[k];
    if (w > 0) { withheld[k] = w; withheld.total += w; }
  }

  const view = {
    subject: full.subject, // identified — the clinician is authorized, unlike a blinded reviewer
    systems, medications, allergies, immunizations, readings,
    careTeam: full.careTeam, timeline,
    counts: kept,
    ontology: full.ontology,
    disclaimer: full.disclaimer,
  };
  return { view, withheld };
}

export const scopeSummary = (s: GrantScope): string =>
  [
    s.systems === 'all' ? 'all systems' : s.systems.join(' + '),
    s.kinds === 'all' ? 'all record kinds' : s.kinds.join(', '),
    s.lookbackDays == null ? 'full history' : `last ${s.lookbackDays} days`,
  ].join(' · ');
