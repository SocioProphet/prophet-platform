// Wall 4 — de-identification. Produces a de-identified view of the twin so a clinician can be granted a
// BLINDED slice: they opine on the data, not the person. Approach = HIPAA Safe-Harbor-style identifier
// removal + consistent date-SHIFTING (a per-view offset that breaks absolute dates while PRESERVING
// intervals, which are clinically meaningful). Direct identifiers (name/label, provider names, free-text
// notes) are stripped; the subject becomes a stable pseudonym; clinical codes/values/units/tiers are
// preserved (that is exactly what the reviewer needs). Non-diagnostic; synthetic data only.

// deterministic pseudonym so the same subject maps to the same token within a scope (unlinkable to identity)
function djb2(s: string): string { let h = 5381; for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) & 0xffffffff; return (h >>> 0).toString(16).padStart(8, '0'); }

const shiftDate = (iso: string, days: number): string => {
  if (!iso || iso.length < 7) return iso;
  const d = new Date(iso.length === 7 ? `${iso}-01` : iso);
  if (isNaN(d.getTime())) return iso;
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
};

export interface DeidReceipt {
  method: 'safe-harbor+date-shift';
  pseudonym: string;
  identifiersRemoved: string[]; // categories handled
  dateShiftDays: number;        // preserves intervals; absolute dates broken
  scope: DisclosureScope;       // the patient's agreed disclosure
  at: string;
}

// Disclosure scope — set by the PATIENT'S agreement. 'standard' shares the clinical essentials a doctor
// needs (age-band + sex + facts) and nothing identifying. 'minimal' shares only the facts. Anything
// beyond 'standard' is a doctor request the patient must approve (see consult.requestMore).
export type DisclosureScope = 'minimal' | 'standard';

// The de-identified view a blinded reviewer sees. Note: NO name/label/provider, subject is a pseudonym.
export interface DeidView {
  subject: { pseudonym: string; ageBand?: string; sex?: string };
  systems: {
    id: string; label: string; organs: string[];
    observations: { code: string; codeSystem: string; display: string; value: number; unit: string; refLow?: number; refHigh?: number; effective: string; trend?: number[]; epistemic: string; organ?: string }[];
    conditions: { code: string; codeSystem: string; display: string; onset: string; clinicalStatus: string; epistemic: string; organ?: string }[];
    encounters: { type: string; date: string }[]; // provider + free-text note REMOVED
    imaging: { modality: string; bodySite: string; date: string; description: string; epistemic: string }[];
  }[];
  disclaimer: string;
  receipt: DeidReceipt;
}

const NONDX = 'De-identified record for blinded review. Not a diagnosis; a clinician forms an opinion. Synthetic data.';

// Build a de-identified view from the twin bundle. `salt` scopes the pseudonym + date-shift to a consult
// so different consults are unlinkable. `scope` = the patient's agreed disclosure ('standard' keeps the
// coarsened age-band + sex a doctor needs). The bundle is the shape returned by the engine's bundle().
export function deidentify(bundle: any, salt = 'default', scope: DisclosureScope = 'standard'): DeidView {
  const subjectId = bundle?.subject?.id ?? 'subject';
  const pseudonym = `anon:${djb2(`${subjectId}|${salt}`)}`;
  // per-view deterministic date shift in [-183, +182] days — breaks absolute dates, preserves intervals
  const dateShiftDays = (parseInt(djb2(`shift|${subjectId}|${salt}`), 16) % 366) - 183;
  const removed = new Set<string>();

  const systems = (bundle?.systems ?? []).map((s: any) => ({
    id: s.id, label: s.label, organs: s.organs,
    observations: (s.observations ?? []).map((o: any) => ({
      code: o.code, codeSystem: o.codeSystem, display: o.display, value: o.value, unit: o.unit,
      refLow: o.refLow, refHigh: o.refHigh, effective: shiftDate(o.effective, dateShiftDays), trend: o.trend,
      epistemic: o.epistemic, organ: o.organ,
    })),
    conditions: (s.conditions ?? []).map((c: any) => ({
      code: c.code, codeSystem: c.codeSystem, display: c.display, onset: shiftDate(c.onset, dateShiftDays),
      clinicalStatus: c.clinicalStatus, epistemic: c.epistemic, organ: c.organ,
    })),
    encounters: (s.encounters ?? []).map((e: any) => {
      if (e.provider) removed.add('provider-names');
      if (e.note) removed.add('free-text-notes');
      return { type: e.type, date: shiftDate(e.date, dateShiftDays) }; // provider + note dropped
    }),
    imaging: (s.imaging ?? []).map((im: any) => ({
      modality: im.modality, bodySite: im.bodySite, date: shiftDate(im.date, dateShiftDays),
      description: im.description, epistemic: im.epistemic,
    })),
  }));

  if (bundle?.subject?.label) removed.add('names');
  if (bundle?.subject?.note) removed.add('narrative');
  removed.add('dates'); // shifted

  // 'standard' scope keeps the coarsened demographics a doctor needs; 'minimal' shares only facts.
  const subject: DeidView['subject'] = { pseudonym };
  if (scope === 'standard') {
    if (bundle?.subject?.ageBand) subject.ageBand = bundle.subject.ageBand;
    if (bundle?.subject?.sex) subject.sex = bundle.subject.sex;
  }
  return {
    subject,
    systems,
    disclaimer: NONDX,
    receipt: {
      method: 'safe-harbor+date-shift', pseudonym, identifiersRemoved: [...removed].sort(),
      dateShiftDays, scope, at: new Date().toISOString(),
    } as DeidReceipt,
  };
}

// Invariant helper: does a de-identified view leak any known direct identifier field? Used by the
// enforced non-diagnostic/de-id test. Returns the offending paths (empty = clean).
export function identifierLeaks(view: any): string[] {
  const leaks: string[] = [];
  const scan = (obj: any, path: string) => {
    if (obj == null || typeof obj !== 'object') return;
    for (const [k, v] of Object.entries(obj)) {
      const p = path ? `${path}.${k}` : k;
      // direct identifiers forbidden ANYWHERE in a de-identified view
      if (/^(name|note|provider|mrn|ssn|dob|email|phone|address|subjectLabel)$/i.test(k) && v) leaks.push(p);
      // `label`/`id` are PHI only on the subject (a system's anatomical label like "Cardiovascular" is not)
      if (/^(label|id)$/i.test(k) && v && /(^|\.)subject(\.|$)/i.test(p)) leaks.push(p);
      if (typeof v === 'object') scan(v, p);
    }
  };
  scan(view, '');
  return leaks;
}
